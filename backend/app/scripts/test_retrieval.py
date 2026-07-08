from __future__ import annotations

from app.core.config import settings
from app.core.logging import configure_logging
from app.services.embedding_service import GeminiEmbeddingService
from app.services.retrieval_service import SemanticRetrievalService
from app.services.vector_store import ChromaVectorStore


QUERIES = [
    "How can I improve my sleep?",
    "What are the signs of dehydration?",
    "How can I lower high blood pressure?",
    "How much physical activity should adults do?",
    "What foods support a healthy heart?",
    "What is the company refund policy?",
]


def main() -> None:
    configure_logging()
    retrieval = SemanticRetrievalService(
        embedding_service=GeminiEmbeddingService(),
        vector_store=ChromaVectorStore(),
    )

    for query in QUERIES:
        print(f"\nquery: {query}")
        results = retrieval.retrieve(query, top_k=settings.retrieval_top_k)
        if not results:
            print("No sufficiently relevant evidence found.")
            continue
        for rank, chunk in enumerate(results, start=1):
            preview = chunk.text[:300].replace("\n", " ")
            print(f"rank: {rank}")
            print(f"source filename: {chunk.source_file}")
            print(f"page number: {chunk.page_number}")
            print(f"content type: {chunk.content_type}")
            print(f"similarity score: {chunk.similarity_score:.3f}")
            print(f"passage: {preview}")


if __name__ == "__main__":
    main()
