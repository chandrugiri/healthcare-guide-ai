import pytest

from app.models.document import ParsedPage, ParsedTable
from app.services.text_chunker import TextChunker, chunk_pages


def _page(text: str, tables: list[ParsedTable] | None = None) -> ParsedPage:
    return ParsedPage(
        source_file="guide.pdf",
        page_number=3,
        text=text,
        tables=tables or [],
    )


def test_chunk_metadata_and_content_type_preservation() -> None:
    chunks = TextChunker(
        chunk_size=80, chunk_overlap=10, min_prose_chunk_chars=0
    ).chunk_pages(
        [_page("Paragraph one.\n\nParagraph two.")]
    )

    assert len(chunks) == 1
    assert chunks[0].source_file == "guide.pdf"
    assert chunks[0].page_number == 3
    assert chunks[0].content_type == "text"
    assert chunks[0].table_index is None
    assert chunks[0].character_count == len(chunks[0].text)


def test_deterministic_chunk_ids() -> None:
    page = _page("A deterministic paragraph.")

    first = TextChunker(min_prose_chunk_chars=0).chunk_pages([page])
    second = TextChunker(min_prose_chunk_chars=0).chunk_pages([page])

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_chunk_overlap_validation() -> None:
    with pytest.raises(ValueError):
        TextChunker(chunk_size=100, chunk_overlap=100)


def test_oversized_paragraph_fallback_avoids_empty_chunks() -> None:
    text = " ".join(f"word{i}" for i in range(80))

    chunks = TextChunker(
        chunk_size=60, chunk_overlap=10, min_prose_chunk_chars=0
    ).chunk_pages([_page(text)])

    assert len(chunks) > 1
    assert all(chunk.text for chunk in chunks)
    assert all(len(chunk.text) <= 80 for chunk in chunks)


def test_empty_text_handling() -> None:
    assert TextChunker().chunk_pages([_page("   ")]) == []


def test_table_index_preserved_and_small_table_stays_one_chunk() -> None:
    table = ParsedTable(
        source_file="guide.pdf",
        page_number=3,
        table_index=2,
        markdown="| Name | Value |\n| --- | --- |\n| Pulse | 72 |",
    )

    chunks = TextChunker(chunk_size=200, chunk_overlap=20).chunk_pages(
        [_page("", [table])]
    )

    assert len(chunks) == 1
    assert chunks[0].content_type == "table"
    assert chunks[0].table_index == 2


def test_large_tables_split_by_rows_and_repeat_headers() -> None:
    rows = "\n".join(f"| Row {index} | Value {index} |" for index in range(10))
    table = ParsedTable(
        source_file="guide.pdf",
        page_number=3,
        table_index=1,
        markdown=f"| Name | Value |\n| --- | --- |\n{rows}",
    )

    chunks = TextChunker(chunk_size=95, chunk_overlap=20).chunk_pages(
        [_page("", [table])]
    )

    assert len(chunks) > 1
    assert all(chunk.text.startswith("| Name | Value |\n| --- | --- |") for chunk in chunks)
    assert all(chunk.content_type == "table" for chunk in chunks)


def test_prose_and_table_chunks_remain_separate() -> None:
    table = ParsedTable(
        source_file="guide.pdf",
        page_number=3,
        table_index=0,
        markdown="| A | B |\n| --- | --- |\n| C | D |",
    )

    chunks = TextChunker(
        chunk_size=80, chunk_overlap=10, min_prose_chunk_chars=0
    ).chunk_pages(
        [_page("Body paragraph.", [table])]
    )

    assert [chunk.content_type for chunk in chunks] == ["text", "table"]


def test_merges_short_heading_with_following_body_text() -> None:
    body = (
        "This section explains when to contact a healthcare professional and "
        "what information to prepare before the appointment."
    )

    chunks = TextChunker(chunk_size=300, chunk_overlap=20).chunk_pages(
        [_page(f"When to Get Help\n\n{body}")]
    )

    assert len(chunks) == 1
    assert chunks[0].text.startswith("When to Get Help\n\nThis section explains")


def test_filters_low_information_prose_chunks() -> None:
    text = (
        "Healthcare Guide AI\n\n"
        "https://example.org\n\n"
        "12\n\n"
        "Copyright 2026 Example Publisher\n\n"
        "Patients should seek urgent care for chest pain, severe shortness of "
        "breath, stroke symptoms, or other rapidly worsening symptoms."
    )

    chunks = TextChunker(chunk_size=300, chunk_overlap=20).chunk_pages([_page(text)])

    assert len(chunks) == 1
    assert "https://example.org" not in chunks[0].text
    assert "Copyright" not in chunks[0].text
    assert "Patients should seek urgent care" in chunks[0].text


def test_default_filters_very_short_title_only_chunk() -> None:
    chunks = TextChunker().chunk_pages([_page("Healthcare Guide AI")])

    assert chunks == []
