from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from app.models.document import ParsedPage, ParsedTable

logger = logging.getLogger(__name__)


class PDFParserError(Exception):
    """Base exception for domain-specific PDF parsing failures."""


class PDFFileNotFoundError(PDFParserError):
    pass


class PDFEncryptedError(PDFParserError):
    pass


class PDFUnsupportedError(PDFParserError):
    pass


class PDFCorruptError(PDFParserError):
    pass


@dataclass(frozen=True)
class TextBlock:
    text: str
    bbox: tuple[float, float, float, float]
    region: str


@dataclass
class PDFParseResult:
    source_file: str
    total_pages: int
    pages: list[ParsedPage]
    skipped_empty_pages: int
    detected_tables: int
    removed_header_footer_patterns: list[str] = field(default_factory=list)


def parse_pdf(path: str | Path) -> list[ParsedPage]:
    return PDFParser().parse(path)


def parse_pdf_with_metadata(path: str | Path) -> PDFParseResult:
    return PDFParser().parse_with_metadata(path)


class HeaderFooterCleaner:
    """Conservative repeated header/footer detection using page regions."""

    def __init__(self, min_repeated_pages: int = 2) -> None:
        self.min_repeated_pages = min_repeated_pages
        self.removed_patterns: list[str] = []

    def clean(self, pages_blocks: list[list[TextBlock]]) -> list[list[TextBlock]]:
        repeated = self._find_repeated_patterns(pages_blocks)
        self.removed_patterns = sorted({pattern for pattern, _ in repeated})
        if self.removed_patterns:
            logger.info(
                "Removed repeated header/footer patterns: %s",
                ", ".join(self.removed_patterns),
            )

        cleaned_pages: list[list[TextBlock]] = []
        for blocks in pages_blocks:
            cleaned_pages.append(
                [
                    block
                    for block in blocks
                    if (self._normalise_repeated_text(block.text), block.region)
                    not in repeated
                ]
            )
        return cleaned_pages

    def _find_repeated_patterns(
        self, pages_blocks: list[list[TextBlock]]
    ) -> set[tuple[str, str]]:
        page_count = len(pages_blocks)
        if page_count < self.min_repeated_pages:
            return set()

        threshold = max(self.min_repeated_pages, int(page_count * 0.5))
        counter: Counter[tuple[str, str]] = Counter()
        for blocks in pages_blocks:
            seen_on_page = {
                (self._normalise_repeated_text(block.text), block.region)
                for block in blocks
                if block.region in {"top", "bottom"}
                and self._normalise_repeated_text(block.text)
            }
            counter.update(seen_on_page)

        return {
            pattern
            for pattern, count in counter.items()
            if count >= threshold and self._is_removable_pattern(pattern[0])
        }

    def _normalise_repeated_text(self, text: str) -> str:
        value = _normalise_inline_text(text).lower()
        value = re.sub(r"\bpage\s+\d+(\s+of\s+\d+)?\b", "page #", value)
        value = re.sub(r"^\d+\s*/\s*\d+$", "# / #", value)
        value = re.sub(r"^\d+$", "#", value)
        return value.strip(" -_|")

    def _is_removable_pattern(self, text: str) -> bool:
        if not text:
            return False
        if text in {"#", "page #", "# / #"}:
            return True
        if re.search(r"https?://|www\.|\.org|\.gov|\.com", text):
            return True
        if re.search(r"confidential|publication|copyright|all rights reserved", text):
            return True
        return len(text) >= 4


class PDFParser:
    def __init__(self, header_footer_cleaner: HeaderFooterCleaner | None = None) -> None:
        self.header_footer_cleaner = header_footer_cleaner or HeaderFooterCleaner()

    def parse(self, path: str | Path) -> list[ParsedPage]:
        return self.parse_with_metadata(path).pages

    def parse_with_metadata(self, path: str | Path) -> PDFParseResult:
        pdf_path = Path(path)
        source_file = pdf_path.name
        document = self._open_document(pdf_path)

        try:
            page_tables: list[list[ParsedTable]] = []
            table_bboxes_by_page: list[list[tuple[float, float, float, float]]] = []
            pages_blocks: list[list[TextBlock]] = []

            for page_index in range(document.page_count):
                page = document.load_page(page_index)
                page_number = page_index + 1
                tables, table_bboxes = self._extract_tables(page, source_file, page_number)
                page_tables.append(tables)
                table_bboxes_by_page.append(table_bboxes)
                pages_blocks.append(self._extract_text_blocks(page, table_bboxes))

            cleaned_blocks = self.header_footer_cleaner.clean(pages_blocks)
            parsed_pages: list[ParsedPage] = []
            skipped_empty_pages = 0

            for page_index, blocks in enumerate(cleaned_blocks):
                page_number = page_index + 1
                text = _normalise_page_text("\n\n".join(block.text for block in blocks))
                tables = page_tables[page_index]

                if not text and not tables:
                    skipped_empty_pages += 1
                    logger.warning(
                        "Page %s in %s has no useful extractable text or tables",
                        page_number,
                        source_file,
                    )
                    continue

                parsed_pages.append(
                    ParsedPage(
                        source_file=source_file,
                        page_number=page_number,
                        text=text,
                        tables=tables,
                    )
                )

            return PDFParseResult(
                source_file=source_file,
                total_pages=document.page_count,
                pages=parsed_pages,
                skipped_empty_pages=skipped_empty_pages,
                detected_tables=sum(len(tables) for tables in page_tables),
                removed_header_footer_patterns=list(
                    self.header_footer_cleaner.removed_patterns
                ),
            )
        finally:
            document.close()

    def _open_document(self, pdf_path: Path) -> fitz.Document:
        if not pdf_path.exists():
            raise PDFFileNotFoundError(f"PDF file does not exist: {pdf_path}")
        if pdf_path.suffix.lower() != ".pdf":
            raise PDFUnsupportedError(f"Unsupported file type: {pdf_path.suffix}")

        try:
            document = fitz.open(pdf_path)
        except fitz.FileDataError as exc:
            raise PDFCorruptError(f"PDF file is corrupt or unreadable: {pdf_path}") from exc
        except RuntimeError as exc:
            raise PDFCorruptError(f"Could not open PDF file: {pdf_path}") from exc

        if document.is_encrypted:
            document.close()
            raise PDFEncryptedError(f"PDF file is encrypted: {pdf_path}")
        return document

    def _extract_text_blocks(
        self,
        page: fitz.Page,
        table_bboxes: list[tuple[float, float, float, float]],
    ) -> list[TextBlock]:
        raw_blocks = page.get_text("blocks", sort=True)
        blocks: list[TextBlock] = []
        page_height = float(page.rect.height)

        for raw_block in raw_blocks:
            x0, y0, x1, y1, text, *_ = raw_block
            if _overlaps_any((x0, y0, x1, y1), table_bboxes):
                continue
            cleaned = _clean_block_text(str(text))
            if not cleaned:
                continue
            blocks.append(
                TextBlock(
                    text=cleaned,
                    bbox=(float(x0), float(y0), float(x1), float(y1)),
                    region=_page_region(float(y0), float(y1), page_height),
                )
            )
        return blocks

    def _extract_tables(
        self, page: fitz.Page, source_file: str, page_number: int
    ) -> tuple[list[ParsedTable], list[tuple[float, float, float, float]]]:
        try:
            found_tables = page.find_tables()
        except Exception as exc:  # pragma: no cover - exercised via monkeypatch
            logger.warning(
                "Table extraction failed for %s page %s: %s",
                source_file,
                page_number,
                exc,
            )
            return [], []

        parsed_tables: list[ParsedTable] = []
        table_bboxes: list[tuple[float, float, float, float]] = []
        for table_index, table in enumerate(getattr(found_tables, "tables", [])):
            try:
                rows = table.extract()
                if not is_genuine_table(rows):
                    logger.info(
                        "Rejected table candidate %s from %s page %s",
                        table_index,
                        source_file,
                        page_number,
                    )
                    continue
                markdown = rows_to_markdown(rows)
            except Exception as exc:
                logger.warning(
                    "Could not extract table %s from %s page %s: %s",
                    table_index,
                    source_file,
                    page_number,
                    exc,
                )
                continue

            if not markdown:
                continue

            parsed_tables.append(
                ParsedTable(
                    source_file=source_file,
                    page_number=page_number,
                    table_index=table_index,
                    markdown=markdown,
                )
            )
            bbox = getattr(table, "bbox", None)
            if bbox:
                table_bboxes.append(tuple(float(value) for value in bbox))

        return parsed_tables, table_bboxes


def rows_to_markdown(rows: list[list[Any]] | None) -> str:
    if not rows:
        return ""

    first_row_has_values = bool(rows[0]) and any(_normalise_cell(cell) for cell in rows[0])
    normalised_rows = [
        [_normalise_cell(cell) for cell in row]
        for row in rows
        if row and any(_normalise_cell(cell) for cell in row)
    ]
    if not normalised_rows:
        return ""

    width = max(len(row) for row in normalised_rows)
    padded_rows = [row + [""] * (width - len(row)) for row in normalised_rows]
    non_empty_columns = [
        index
        for index in range(width)
        if any(row[index].strip() for row in padded_rows)
    ]
    compact_rows = [[row[index] for index in non_empty_columns] for row in padded_rows]
    if not compact_rows or not compact_rows[0]:
        return ""

    header_index = _find_header_index(compact_rows) if first_row_has_values else None
    if header_index is None:
        headers = [f"Column {index + 1}" for index in range(len(compact_rows[0]))]
        body_rows = compact_rows
    else:
        headers = compact_rows[header_index]
        body_rows = compact_rows[header_index + 1 :]

    headers = [
        _escape_markdown_cell(header) if header else f"Column {index + 1}"
        for index, header in enumerate(headers)
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in body_rows:
        padded = row + [""] * (len(headers) - len(row))
        lines.append(
            "| "
            + " | ".join(_escape_markdown_cell(cell) for cell in padded[: len(headers)])
            + " |"
        )

    return "\n".join(lines)


def is_genuine_table(rows: list[list[Any]] | None) -> bool:
    """Reject common PyMuPDF false positives before suppressing prose blocks."""
    if not rows:
        return False

    normalised_rows = [
        [_normalise_cell(cell) for cell in row]
        for row in rows
        if row and any(_normalise_cell(cell) for cell in row)
    ]
    if len(normalised_rows) < 2:
        return False

    width = max(len(row) for row in normalised_rows)
    padded_rows = [row + [""] * (width - len(row)) for row in normalised_rows]
    meaningful_columns = [
        index
        for index in range(width)
        if sum(1 for row in padded_rows if row[index].strip()) >= 2
    ]
    if len(meaningful_columns) < 2:
        return False

    compact_rows = [[row[index] for index in meaningful_columns] for row in padded_rows]
    populated_cells = [cell for row in compact_rows for cell in row if cell.strip()]
    total_cells = len(compact_rows) * len(meaningful_columns)
    if len(populated_cells) / max(total_cells, 1) < 0.35:
        return False

    total_text = sum(len(cell) for cell in populated_cells)
    longest_cell = max((len(cell) for cell in populated_cells), default=0)
    if total_text and longest_cell / total_text > 0.65:
        return False

    header_index = _find_header_index(compact_rows)
    has_named_header = header_index is not None and any(
        re.search(r"[A-Za-z]", cell) for cell in compact_rows[header_index]
    )
    average_cell_length = total_text / max(len(populated_cells), 1)
    if header_index is not None:
        header_cells = [cell for cell in compact_rows[header_index] if cell.strip()]
        average_header_length = sum(len(cell) for cell in header_cells) / max(
            len(header_cells), 1
        )
        if average_header_length > 35:
            return False
    if not has_named_header and len(meaningful_columns) >= 3:
        return False
    if not has_named_header and average_cell_length > 80:
        return False
    if _resembles_leaflet(compact_rows):
        return False

    return True


def _find_header_index(rows: list[list[str]]) -> int | None:
    for index, row in enumerate(rows[:3]):
        filled = [cell for cell in row if cell.strip()]
        if len(filled) >= max(1, len(row) // 2):
            return index
    return None


def _clean_block_text(text: str) -> str:
    lines = [_normalise_line(line) for line in text.splitlines()]
    useful_lines = [
        line
        for line in lines
        if line
        and not re.fullmatch(r"[-_=*.\s]{1,8}", line)
        and not _is_standalone_page_number(line)
        and not _is_bare_url(line)
    ]
    return "\n".join(_join_wrapped_lines(useful_lines))


def _normalise_page_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalise_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalise_line(text: str) -> str:
    value = _normalise_inline_text(text)
    return re.sub(r"^[•◦▪▫‣⁃]\s*", "- ", value)


def _normalise_cell(cell: Any) -> str:
    if cell is None:
        return ""
    return _normalise_inline_text(str(cell).replace("\n", " "))


def _escape_markdown_cell(cell: str) -> str:
    return cell.replace("|", "\\|")


def _join_wrapped_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []

    joined: list[str] = []
    for line in lines:
        if not joined:
            joined.append(line)
            continue

        previous = joined[-1]
        if _should_repair_hyphenation(previous, line):
            joined[-1] = previous[:-1] + line
        elif _should_join_visual_wrap(previous, line):
            joined[-1] = f"{previous} {line}"
        else:
            joined.append(line)
    return joined


def _should_repair_hyphenation(previous: str, current: str) -> bool:
    return bool(re.search(r"[A-Za-z]-$", previous) and re.match(r"^[a-z]", current))


def _should_join_visual_wrap(previous: str, current: str) -> bool:
    if _is_list_item(previous) or _is_list_item(current):
        return False
    if _looks_like_heading(previous) or _looks_like_heading(current):
        return False
    if re.search(r"[.!?:;)]$", previous):
        return False
    return bool(re.match(r"^[a-z,(]", current) or len(previous) > 55)


def _is_list_item(text: str) -> bool:
    return bool(re.match(r"^(-|\*|\d+[.)]|[A-Za-z][.)])\s+", text))


def _looks_like_heading(text: str) -> bool:
    if len(text) > 90 or len(text.split()) > 12:
        return False
    if re.search(r"[.!?]$", text):
        return False
    words = re.findall(r"[A-Za-z]+", text)
    if not words:
        return False
    title_case_words = sum(1 for word in words if word[:1].isupper())
    return title_case_words / len(words) >= 0.6


def _is_standalone_page_number(text: str) -> bool:
    return bool(
        re.fullmatch(r"\d+", text)
        or re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", text, flags=re.IGNORECASE)
        or re.fullmatch(r"\d+\s*/\s*\d+", text)
    )


def _is_bare_url(text: str) -> bool:
    return bool(re.fullmatch(r"(https?://|www\.)\S+", text, flags=re.IGNORECASE))


def _resembles_leaflet(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    populated = [cell for row in rows for cell in row if cell.strip()]
    if not populated:
        return False
    long_cells = [cell for cell in populated if len(cell.split()) >= 8]
    short_cells = [cell for cell in populated if len(cell.split()) <= 3]
    return len(long_cells) >= 3 and len(short_cells) <= 1


def _page_region(y0: float, y1: float, page_height: float) -> str:
    if y1 <= page_height * 0.15:
        return "top"
    if y0 >= page_height * 0.85:
        return "bottom"
    return "body"


def _overlaps_any(
    bbox: tuple[float, float, float, float],
    candidates: list[tuple[float, float, float, float]],
) -> bool:
    return any(_overlap_ratio(bbox, candidate) > 0.25 for candidate in candidates)


def _overlap_ratio(
    bbox: tuple[float, float, float, float],
    candidate: tuple[float, float, float, float],
) -> float:
    x0 = max(bbox[0], candidate[0])
    y0 = max(bbox[1], candidate[1])
    x1 = min(bbox[2], candidate[2])
    y1 = min(bbox[3], candidate[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    bbox_area = max((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 1.0)
    return intersection / bbox_area
