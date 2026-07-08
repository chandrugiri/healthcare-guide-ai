from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.logging import configure_logging
from app.services.pdf_parser import PDFParser, PDFParserError
from app.services.text_chunker import TextChunker


def main() -> None:
    configure_logging()
    knowledge_base_path = Path(settings.knowledge_base_path)
    pdf_files = sorted(knowledge_base_path.rglob("*.pdf"))

    parser = PDFParser()
    chunker = TextChunker()

    total_documents = 0
    total_pages = 0
    total_tables = 0
    total_prose_chunks = 0
    total_table_chunks = 0

    if not pdf_files:
        print(f"No PDF files found in {knowledge_base_path}")

    for pdf_path in pdf_files:
        try:
            result = parser.parse_with_metadata(pdf_path)
            chunks = chunker.chunk_pages(result.pages)
        except PDFParserError as exc:
            print(f"{pdf_path.name}: failed - {exc}")
            continue

        prose_chunks = [chunk for chunk in chunks if chunk.content_type == "text"]
        table_chunks = [chunk for chunk in chunks if chunk.content_type == "table"]

        total_documents += 1
        total_pages += result.total_pages
        total_tables += result.detected_tables
        total_prose_chunks += len(prose_chunks)
        total_table_chunks += len(table_chunks)

        print(f"\n{result.source_file}")
        print(f"  total PDF pages: {result.total_pages}")
        print(f"  extracted pages: {len(result.pages)}")
        print(f"  skipped empty pages: {result.skipped_empty_pages}")
        print(f"  detected tables: {result.detected_tables}")
        print(f"  generated prose chunks: {len(prose_chunks)}")
        print(f"  generated table chunks: {len(table_chunks)}")
        print(f"  total generated chunks: {len(chunks)}")
        print(
            "  repeated header/footer patterns removed: "
            + (
                ", ".join(result.removed_header_footer_patterns)
                if result.removed_header_footer_patterns
                else "none"
            )
        )

    print("\nCorpus totals")
    print(f"  total documents: {total_documents}")
    print(f"  total pages: {total_pages}")
    print(f"  total detected tables: {total_tables}")
    print(f"  total prose chunks: {total_prose_chunks}")
    print(f"  total table chunks: {total_table_chunks}")
    print(f"  total chunks: {total_prose_chunks + total_table_chunks}")


if __name__ == "__main__":
    main()
