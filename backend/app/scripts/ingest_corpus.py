from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Callable

from app.core.config import settings
from app.core.logging import configure_logging
from app.models.document import TextChunk
from app.services.embedding_service import (
    DocumentEmbeddingInput,
    EmbeddingService,
    EmbeddingServiceError,
    GeminiEmbeddingService,
)
from app.services.pdf_parser import PDFParser, PDFParserError
from app.services.text_chunker import TextChunker
from app.services.vector_store import ChromaVectorStore


def ingest_corpus(
    embedding_service: EmbeddingService,
    vector_store: ChromaVectorStore,
    knowledge_base_path: Path,
    batch_size: int,
    rebuild: bool = False,
    request_delay_seconds: float | None = None,
    sleep_func: Callable[[float], None] = time.sleep,
) -> int:
    if rebuild:
        print("Clearing Chroma collection before ingestion")
        vector_store.clear_collection()

    parser = PDFParser()
    chunker = TextChunker()
    pdf_files = sorted(knowledge_base_path.rglob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {knowledge_base_path}")
        return vector_store.count()

    for pdf_path in pdf_files:
        print(f"Processing document: {pdf_path.name}")
        try:
            result = parser.parse_with_metadata(pdf_path)
            chunks = chunker.chunk_pages(result.pages)
        except PDFParserError as exc:
            print(f"  failed to parse document: {exc}")
            continue

        existing_ids = vector_store.existing_chunk_ids([chunk.chunk_id for chunk in chunks])
        new_chunks = [chunk for chunk in chunks if chunk.chunk_id not in existing_ids]
        print(f"  chunks produced: {len(chunks)}")
        print(f"  already stored/skipped: {len(chunks) - len(new_chunks)}")
        print(f"  new chunks requiring embeddings: {len(new_chunks)}")
        batches_completed = 0
        stored_for_document = 0
        batches = _batches(new_chunks, batch_size)

        try:
            for batch_index, batch in enumerate(batches):
                embeddings = embedding_service.embed_documents(
                    [
                        DocumentEmbeddingInput(text=chunk.text, title=chunk.source_file)
                        for chunk in batch
                    ]
                )
                vector_store.upsert_chunks(batch, embeddings)
                batches_completed += 1
                stored_for_document += len(batch)
                print(f"  batches completed: {batches_completed}")
                print(f"  records stored: {stored_for_document}")
                if batch_index < len(batches) - 1:
                    delay = (
                        request_delay_seconds
                        if request_delay_seconds is not None
                        else settings.embedding_request_delay_seconds
                    )
                    print(f"  waiting {delay:.1f} seconds before next embedding batch")
                    sleep_func(delay)
        except EmbeddingServiceError:
            print("Embedding API failed repeatedly; stopping ingestion safely")
            raise

    final_count = vector_store.count()
    print(f"Final collection count: {final_count}")
    return final_count


def main() -> None:
    configure_logging()
    args = _parse_args()
    embedding_service = GeminiEmbeddingService()
    vector_store = ChromaVectorStore()
    ingest_corpus(
        embedding_service=embedding_service,
        vector_store=vector_store,
        knowledge_base_path=Path(settings.knowledge_base_path),
        batch_size=settings.embedding_batch_size,
        rebuild=args.rebuild,
        request_delay_seconds=settings.embedding_request_delay_seconds,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Healthcare Guide PDFs")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear and recreate the Chroma collection before ingestion",
    )
    return parser.parse_args()


def _batches(items: list[TextChunk], batch_size: int) -> list[list[TextChunk]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


if __name__ == "__main__":
    main()
