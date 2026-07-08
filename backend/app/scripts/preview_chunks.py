from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.logging import configure_logging
from app.models.document import TextChunk
from app.services.pdf_parser import PDFParser, PDFParserError
from app.services.text_chunker import TextChunker


def main() -> None:
    configure_logging()
    knowledge_base_path = Path(settings.knowledge_base_path)
    pdf_files = sorted(knowledge_base_path.rglob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {knowledge_base_path}")
        return

    parser = PDFParser()
    chunker = TextChunker()

    for pdf_path in pdf_files:
        try:
            result = parser.parse_with_metadata(pdf_path)
            chunks = chunker.chunk_pages(result.pages)
        except PDFParserError as exc:
            print(f"\n{pdf_path.name}")
            print(f"  failed: {exc}")
            continue

        prose_chunks = [chunk for chunk in chunks if chunk.content_type == "text"]
        table_chunks = [chunk for chunk in chunks if chunk.content_type == "table"]

        print(f"\n{result.source_file}")

        if prose_chunks:
            print("  Prose chunks")
            for chunk in prose_chunks[:2]:
                _print_chunk(chunk)
        else:
            print("  No prose chunks found.")

        if table_chunks:
            print("  Table chunks")
            _print_chunk(table_chunks[0])
        else:
            print("  No table chunks found.")


def _print_chunk(chunk: TextChunk) -> None:
    print("  ---")
    print(f"  source filename: {chunk.source_file}")
    print(f"  page number: {chunk.page_number}")
    print(f"  content type: {chunk.content_type}")
    if chunk.table_index is not None:
        print(f"  table index: {chunk.table_index}")
    print(f"  chunk ID: {chunk.chunk_id}")
    print(f"  character count: {chunk.character_count}")
    print("  full chunk text:")
    print(chunk.text)


if __name__ == "__main__":
    main()
