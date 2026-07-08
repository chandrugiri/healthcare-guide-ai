from pathlib import Path

import fitz
import pytest

from app.services.pdf_parser import (
    HeaderFooterCleaner,
    PDFCorruptError,
    PDFFileNotFoundError,
    PDFParser,
    TextBlock,
    is_genuine_table,
    rows_to_markdown,
)


def _write_pdf(path: Path, pages: list[list[tuple[float, float, str]]]) -> Path:
    document = fitz.open()
    for entries in pages:
        page = document.new_page()
        for x, y, text in entries:
            page.insert_text((x, y), text, fontsize=11)
    document.save(path)
    document.close()
    return path


def _write_table_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page()
    rows = [["Name", "Value"], ["Blood pressure", "120/80"], ["Pulse", "72"]]
    x0, y0 = 72, 100
    cell_width, cell_height = 140, 28

    for row_index in range(len(rows) + 1):
        y = y0 + row_index * cell_height
        page.draw_line((x0, y), (x0 + 2 * cell_width, y))
    for col_index in range(3):
        x = x0 + col_index * cell_width
        page.draw_line((x, y0), (x, y0 + len(rows) * cell_height))
    for row_index, row in enumerate(rows):
        for col_index, cell in enumerate(row):
            page.insert_text(
                (x0 + col_index * cell_width + 6, y0 + row_index * cell_height + 18),
                cell,
                fontsize=10,
            )

    document.save(path)
    document.close()
    return path


def test_multi_page_text_extraction_and_page_numbers(tmp_path: Path) -> None:
    pdf_path = _write_pdf(
        tmp_path / "multi.pdf",
        [
            [(72, 120, "First page body content.")],
            [(72, 120, "Second page body content.")],
        ],
    )

    pages = PDFParser().parse(pdf_path)

    assert [page.page_number for page in pages] == [1, 2]
    assert pages[0].source_file == "multi.pdf"
    assert "First page body content." in pages[0].text
    assert "Second page body content." in pages[1].text


def test_empty_page_handling(tmp_path: Path) -> None:
    document = fitz.open()
    document.new_page()
    pdf_path = tmp_path / "empty.pdf"
    document.save(pdf_path)
    document.close()

    result = PDFParser().parse_with_metadata(pdf_path)

    assert result.pages == []
    assert result.skipped_empty_pages == 1


def test_missing_file_error(tmp_path: Path) -> None:
    with pytest.raises(PDFFileNotFoundError):
        PDFParser().parse(tmp_path / "missing.pdf")


def test_corrupt_file_error(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_text("not a real pdf", encoding="utf-8")

    with pytest.raises(PDFCorruptError):
        PDFParser().parse(pdf_path)


def test_repeated_header_footer_and_page_number_removal(tmp_path: Path) -> None:
    pdf_path = _write_pdf(
        tmp_path / "headers.pdf",
        [
            [
                (72, 30, "Healthcare Guide AI"),
                (72, 120, "Meaningful body content one."),
                (72, 780, "Page 1 of 2"),
            ],
            [
                (72, 30, "Healthcare Guide AI"),
                (72, 120, "Meaningful body content two."),
                (72, 780, "Page 2 of 2"),
            ],
        ],
    )

    result = PDFParser().parse_with_metadata(pdf_path)
    combined_text = "\n".join(page.text for page in result.pages)

    assert "Healthcare Guide AI" not in combined_text
    assert "Page 1 of 2" not in combined_text
    assert "Meaningful body content one." in combined_text
    assert "Meaningful body content two." in combined_text
    assert "healthcare guide ai" in result.removed_header_footer_patterns


def test_preserves_non_repeated_top_heading(tmp_path: Path) -> None:
    pdf_path = _write_pdf(
        tmp_path / "heading.pdf",
        [
            [(72, 30, "Chapter 1: Getting Care"), (72, 120, "Body one.")],
            [(72, 30, "Chapter 2: Paying Bills"), (72, 120, "Body two.")],
        ],
    )

    pages = PDFParser().parse(pdf_path)

    assert "Chapter 1: Getting Care" in pages[0].text
    assert "Chapter 2: Paying Bills" in pages[1].text


def test_header_footer_cleaner_is_separate_and_testable() -> None:
    cleaner = HeaderFooterCleaner()
    cleaned = cleaner.clean(
        [
            [
                TextBlock("Repeated Footer", (0, 760, 100, 780), "bottom"),
                TextBlock("Body A", (0, 200, 100, 220), "body"),
            ],
            [
                TextBlock("Repeated Footer", (0, 760, 100, 780), "bottom"),
                TextBlock("Body B", (0, 200, 100, 220), "body"),
            ],
        ]
    )

    assert [[block.text for block in page] for page in cleaned] == [["Body A"], ["Body B"]]
    assert cleaner.removed_patterns == ["repeated footer"]


def test_simple_table_detection_and_markdown_conversion(tmp_path: Path) -> None:
    pdf_path = _write_table_pdf(tmp_path / "table.pdf")

    pages = PDFParser().parse(pdf_path)

    assert len(pages) == 1
    assert len(pages[0].tables) == 1
    markdown = pages[0].tables[0].markdown
    assert "| Name | Value |" in markdown
    assert "| Blood pressure | 120/80 |" in markdown


def test_markdown_conversion_without_usable_headers() -> None:
    markdown = rows_to_markdown([["", ""], ["A", "B"], ["C", "D"]])

    assert "| Column 1 | Column 2 |" in markdown
    assert "| A | B |" in markdown


def test_markdown_escapes_pipes_and_removes_empty_columns() -> None:
    markdown = rows_to_markdown([["Name", "Value", ""], ["A|B", "C", ""]])

    assert "A\\|B" in markdown
    assert "Column 3" not in markdown


def test_table_extraction_failure_does_not_stop_page_processing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = _write_pdf(
        tmp_path / "text.pdf",
        [[(72, 120, "Body survives table extraction failure.")]],
    )

    def fail_find_tables(self: fitz.Page) -> None:
        raise RuntimeError("table failure")

    monkeypatch.setattr(fitz.Page, "find_tables", fail_find_tables)

    pages = PDFParser().parse(pdf_path)

    assert len(pages) == 1
    assert "Body survives table extraction failure." in pages[0].text
    assert pages[0].tables == []


def test_repairs_line_break_hyphenation_and_visual_wraps(tmp_path: Path) -> None:
    pdf_path = _write_pdf(
        tmp_path / "wrapped.pdf",
        [
            [
                (
                    72,
                    120,
                    "The medical re-\ncord includes details that are visually\nwrapped across lines.",
                )
            ]
        ],
    )

    pages = PDFParser().parse(pdf_path)

    assert "medical record includes details that are visually wrapped" in pages[0].text


def test_removes_standalone_page_numbers_and_bare_urls(tmp_path: Path) -> None:
    pdf_path = _write_pdf(
        tmp_path / "noise.pdf",
        [[(72, 120, "Page 4\nhttps://example.org\nUseful clinical body text remains.")]],
    )

    pages = PDFParser().parse(pdf_path)

    assert "Page 4" not in pages[0].text
    assert "https://example.org" not in pages[0].text
    assert "Useful clinical body text remains." in pages[0].text


def test_rejects_false_positive_leaflet_table_rows() -> None:
    rows = [
        [
            "Eat well by choosing vegetables and fibre every day",
            "Move more with short walks and regular strength activity",
        ],
        [
            "Sleep routines and social support can help long term health",
            "Speak with a clinician if symptoms change or worsen",
        ],
    ]

    assert is_genuine_table(rows) is False


def test_retains_valid_structured_table_rows() -> None:
    rows = [
        ["Blood pressure", "Range"],
        ["Normal", "Less than 120/80"],
        ["High", "140/90 or higher"],
    ]

    assert is_genuine_table(rows) is True


def test_rejected_table_content_remains_available_as_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = _write_pdf(
        tmp_path / "leaflet.pdf",
        [
            [
                (
                    72,
                    120,
                    "Eat well by choosing vegetables and fibre every day\n"
                    "Move more with short walks and strength activity",
                )
            ]
        ],
    )

    class FakeTable:
        bbox = (60, 100, 500, 170)

        def extract(self) -> list[list[str]]:
            return [
                [
                    "Eat well by choosing vegetables and fibre every day",
                    "Move more with short walks and strength activity",
                ],
                ["Sleep well and seek support", "Talk to a clinician if symptoms change"],
            ]

    class FakeTables:
        tables = [FakeTable()]

    def fake_find_tables(self: fitz.Page) -> FakeTables:
        return FakeTables()

    monkeypatch.setattr(fitz.Page, "find_tables", fake_find_tables)

    pages = PDFParser().parse(pdf_path)

    assert pages[0].tables == []
    assert "Eat well by choosing vegetables" in pages[0].text
    assert "Move more with short walks" in pages[0].text
