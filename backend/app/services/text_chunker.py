from __future__ import annotations

import hashlib
import re

from app.models.document import ParsedPage, ParsedTable, TextChunk


DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


class TextChunker:
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        min_prose_chunk_chars: int = 100,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must not be negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if min_prose_chunk_chars < 0:
            raise ValueError("min_prose_chunk_chars must not be negative")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_prose_chunk_chars = min_prose_chunk_chars

    def chunk_pages(self, pages: list[ParsedPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for page in pages:
            chunks.extend(self.chunk_page(page, start_index=len(chunks)))
        return chunks

    def chunk_page(self, page: ParsedPage, start_index: int = 0) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for text in self._split_prose(page.text):
            chunks.append(
                self._build_chunk(
                    source_file=page.source_file,
                    page_number=page.page_number,
                    chunk_index=start_index + len(chunks),
                    text=text,
                    content_type="text",
                    table_index=None,
                )
            )

        for table in page.tables:
            for text in self._split_table(table):
                chunks.append(
                    self._build_chunk(
                        source_file=page.source_file,
                        page_number=page.page_number,
                        chunk_index=start_index + len(chunks),
                        text=text,
                        content_type="table",
                        table_index=table.table_index,
                    )
                )
        return chunks

    def _split_prose(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", text)
            if paragraph.strip() and not _is_discardable_paragraph(paragraph)
        ]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if not paragraph:
                continue
            if len(paragraph) > self.chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(self._split_oversized_text(paragraph))
                continue

            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                chunks.append(current)
                current = self._with_overlap(current, paragraph)

        if current:
            chunks.append(current)
        return self._filter_low_information_prose(chunks)

    def _filter_low_information_prose(self, chunks: list[str]) -> list[str]:
        useful = [chunk.strip() for chunk in chunks if chunk.strip()]
        merged: list[str] = []
        index = 0
        while index < len(useful):
            chunk = useful[index]
            if (
                len(chunk) < self.min_prose_chunk_chars
                and index + 1 < len(useful)
                and not _is_low_information_prose(chunk)
            ):
                candidate = f"{chunk}\n\n{useful[index + 1]}".strip()
                if len(candidate) <= self.chunk_size:
                    useful[index + 1] = candidate
                    index += 1
                    continue
            if (
                len(chunk) < self.min_prose_chunk_chars
                and merged
                and not _is_low_information_prose(chunk)
            ):
                candidate = f"{merged[-1]}\n\n{chunk}".strip()
                if len(candidate) <= self.chunk_size:
                    merged[-1] = candidate
                    index += 1
                    continue
            if len(chunk) >= self.min_prose_chunk_chars and not _is_low_information_prose(
                chunk
            ):
                merged.append(chunk)
            index += 1
        return merged

    def _split_oversized_text(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if not sentence:
                continue
            if len(sentence) > self.chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(self._split_by_words(sentence))
                continue
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                chunks.append(current)
                current = self._with_overlap(current, sentence)
        if current:
            chunks.append(current)
        return chunks

    def _split_by_words(self, text: str) -> list[str]:
        words = text.split()
        chunks: list[str] = []
        current_words: list[str] = []
        current_length = 0
        for word in words:
            added = len(word) + (1 if current_words else 0)
            if current_words and current_length + added > self.chunk_size:
                current_text = " ".join(current_words)
                chunks.append(current_text)
                overlap_words = self._overlap_words(current_text)
                current_words = overlap_words + [word]
                current_length = len(" ".join(current_words))
            else:
                current_words.append(word)
                current_length += added
        if current_words:
            chunks.append(" ".join(current_words))
        return chunks

    def _with_overlap(self, previous: str, next_text: str) -> str:
        if self.chunk_overlap == 0:
            return next_text
        overlap = self._trailing_overlap(previous)
        return f"{overlap}\n\n{next_text}".strip() if overlap else next_text

    def _trailing_overlap(self, text: str) -> str:
        if len(text) <= self.chunk_overlap:
            return text
        start = max(text.rfind(" ", 0, len(text) - self.chunk_overlap), 0)
        return text[start:].strip()

    def _overlap_words(self, text: str) -> list[str]:
        return self._trailing_overlap(text).split()

    def _split_table(self, table: ParsedTable) -> list[str]:
        markdown = table.markdown.strip()
        if not markdown:
            return []
        if len(markdown) <= self.chunk_size:
            return [markdown]

        lines = [line for line in markdown.splitlines() if line.strip()]
        if len(lines) <= 2:
            return self._split_by_words(markdown)

        header = lines[:2]
        body_rows = lines[2:]
        chunks: list[str] = []
        current_rows: list[str] = []

        for row in body_rows:
            candidate_lines = header + current_rows + [row]
            candidate = "\n".join(candidate_lines)
            if current_rows and len(candidate) > self.chunk_size:
                chunks.append("\n".join(header + current_rows))
                current_rows = [row]
            elif len(candidate) > self.chunk_size:
                chunks.append(candidate)
                current_rows = []
            else:
                current_rows.append(row)

        if current_rows:
            chunks.append("\n".join(header + current_rows))
        return [chunk for chunk in chunks if chunk.strip()]

    def _build_chunk(
        self,
        source_file: str,
        page_number: int,
        chunk_index: int,
        text: str,
        content_type: str,
        table_index: int | None,
    ) -> TextChunk:
        chunk_id = _chunk_id(source_file, page_number, chunk_index, content_type, text)
        return TextChunk(
            chunk_id=chunk_id,
            source_file=source_file,
            page_number=page_number,
            chunk_index=chunk_index,
            text=text,
            character_count=len(text),
            content_type=content_type,  # type: ignore[arg-type]
            table_index=table_index,
        )


def chunk_pages(
    pages: list[ParsedPage],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    return TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap).chunk_pages(
        pages
    )


def _chunk_id(
    source_file: str,
    page_number: int,
    chunk_index: int,
    content_type: str,
    text: str,
) -> str:
    value = f"{source_file}|{page_number}|{chunk_index}|{content_type}|{text}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_low_information_prose(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = compact.lower()
    if not compact:
        return True
    if re.fullmatch(r"\d+", compact):
        return True
    if re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", compact, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"\d+\s*/\s*\d+", compact):
        return True
    if re.fullmatch(r"(https?://|www\.)\S+", compact, flags=re.IGNORECASE):
        return True
    if len(compact) < 160 and re.search(
        r"\b(publication|copyright|all rights reserved|confidential|isbn)\b", lowered
    ):
        return True
    words = re.findall(r"[A-Za-z]+", compact)
    if len(words) <= 8 and not re.search(r"[.!?:;]", compact):
        return True
    return False


def _is_discardable_paragraph(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    lowered = compact.lower()
    return bool(
        re.fullmatch(r"\d+", compact)
        or re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", compact, flags=re.IGNORECASE)
        or re.fullmatch(r"\d+\s*/\s*\d+", compact)
        or re.fullmatch(r"(https?://|www\.)\S+", compact, flags=re.IGNORECASE)
        or (
            len(compact) < 160
            and re.search(
                r"\b(publication|copyright|all rights reserved|confidential|isbn)\b",
                lowered,
            )
        )
    )
