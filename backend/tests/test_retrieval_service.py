from pathlib import Path

import pytest

from app.models.document import TextChunk
from app.services.retrieval_service import (
    RetrievalValidationError,
    SemanticRetrievalService,
)
from app.services.vector_store import ChromaVectorStore, VectorQueryResult


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_document(self, text: str, title: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return [1.0, 0.0, 0.0]

    def embed_documents(self, items: list[object]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in items]


class FakeVectorStore:
    def __init__(self, results: list[VectorQueryResult]) -> None:
        self.results = results
        self.calls: list[tuple[list[float], int]] = []

    def query_by_embedding(
        self, query_embedding: list[float], candidate_count: int
    ) -> list[VectorQueryResult]:
        self.calls.append((query_embedding, candidate_count))
        return self.results


def _result(
    chunk_id: str,
    distance: float,
    source_file: str = "guide.pdf",
    text: str | None = None,
    content_type: str = "text",
    table_index: int | None = None,
) -> VectorQueryResult:
    metadata = {
        "source_file": source_file,
        "page_number": 2,
        "chunk_index": 4,
        "content_type": content_type,
        "character_count": 120,
    }
    if table_index is not None:
        metadata["table_index"] = table_index
    return VectorQueryResult(
        chunk_id=chunk_id,
        document=text or f"Evidence passage for {chunk_id} with useful health guidance.",
        metadata=metadata,
        distance=distance,
    )


def _service(
    results: list[VectorQueryResult],
    min_similarity: float = 0.62,
    top_k: int = 5,
    max_chunks_per_source: int = 3,
) -> tuple[SemanticRetrievalService, FakeEmbeddingService, FakeVectorStore]:
    embedding = FakeEmbeddingService()
    store = FakeVectorStore(results)
    service = SemanticRetrievalService(
        embedding_service=embedding,
        vector_store=store,
        top_k=top_k,
        candidate_count=12,
        min_similarity=min_similarity,
        max_chunks_per_source=max_chunks_per_source,
    )
    return service, embedding, store


def test_empty_question_validation() -> None:
    service, _, _ = _service([])

    with pytest.raises(RetrievalValidationError):
        service.retrieve("   ")


def test_query_embedding_is_generated_once_and_candidates_are_retrieved() -> None:
    service, embedding, store = _service([_result("a", 0.2)])

    results = service.retrieve("How can I sleep better?")

    assert len(results) == 1
    assert embedding.queries == ["How can I sleep better?"]
    assert store.calls == [([1.0, 0.0, 0.0], 12)]


def test_similarity_score_calculation() -> None:
    service, _, _ = _service([_result("a", 0.35)])

    results = service.retrieve("question")

    assert results[0].similarity_score == pytest.approx(0.65)


def test_similarity_threshold_filtering() -> None:
    service, _, _ = _service(
        [_result("low", 0.9), _result("high", 0.2)], min_similarity=0.5
    )

    results = service.retrieve("question")

    assert [result.chunk_id for result in results] == ["high"]


def test_duplicate_id_removal() -> None:
    service, _, _ = _service([_result("a", 0.1), _result("a", 0.05)])

    results = service.retrieve("question")

    assert [result.chunk_id for result in results] == ["a"]


def test_near_duplicate_text_removal() -> None:
    text = "Drink water regularly and seek medical care if dehydration symptoms worsen."
    service, _, _ = _service(
        [_result("a", 0.1, text=text), _result("b", 0.11, text=text)]
    )

    results = service.retrieve("question")

    assert [result.chunk_id for result in results] == ["a"]


def test_maximum_chunks_per_source() -> None:
    service, _, _ = _service(
        [
            _result("a", 0.1, source_file="same.pdf"),
            _result("b", 0.11, source_file="same.pdf"),
            _result("c", 0.12, source_file="same.pdf"),
            _result("d", 0.13, source_file="other.pdf"),
        ],
        max_chunks_per_source=2,
    )

    results = service.retrieve("question")

    assert [result.chunk_id for result in results] == ["a", "b", "d"]


def test_ranking_order_is_preserved_and_top_k_limit_applies() -> None:
    service, _, _ = _service(
        [_result("a", 0.1), _result("b", 0.2), _result("c", 0.3)],
        top_k=2,
    )

    results = service.retrieve("question")

    assert [result.chunk_id for result in results] == ["a", "b"]


def test_empty_result_when_nothing_passes_threshold() -> None:
    service, _, _ = _service([_result("a", 0.9)], min_similarity=0.5)

    assert service.retrieve("question") == []


def test_unsupported_query_returns_no_results_when_top_score_is_weak() -> None:
    service, _, _ = _service(
        [
            _result("refund-a", 0.43, text="Company refund policy and sales terms."),
            _result("refund-b", 0.46, text="Publication contact and ordering details."),
        ]
    )

    assert service.retrieve("What is the company refund policy?") == []


def test_relevant_healthcare_query_still_returns_results() -> None:
    service, _, _ = _service(
        [
            _result(
                "sleep",
                0.22,
                text=(
                    "Healthy sleep habits include keeping a consistent schedule and "
                    "limiting caffeine late in the day."
                ),
            )
        ]
    )

    results = service.retrieve("How can I improve my sleep?")

    assert [result.chunk_id for result in results] == ["sleep"]


def test_low_value_publication_boilerplate_is_filtered() -> None:
    service, _, _ = _service(
        [
            _result(
                "boilerplate",
                0.1,
                text=(
                    "Publication version 3. Copyright 2026. Contact sales for "
                    "permissions, licence terms, ordering information, and returns."
                ),
            ),
            _result(
                "health",
                0.2,
                text="Adults can support heart health with regular activity and a balanced diet.",
            ),
        ]
    )

    results = service.retrieve("What supports heart health?")

    assert [result.chunk_id for result in results] == ["health"]


def test_threshold_remains_configurable() -> None:
    service, _, _ = _service([_result("weak", 0.45)], min_similarity=0.5)

    results = service.retrieve("question")

    assert [result.chunk_id for result in results] == ["weak"]


def test_metadata_mapping_for_prose_and_table_chunks() -> None:
    service, _, _ = _service(
        [
            _result("text", 0.1, content_type="text"),
            _result("table", 0.2, content_type="table", table_index=3),
        ]
    )

    results = service.retrieve("question")

    assert results[0].content_type == "text"
    assert results[0].table_index is None
    assert results[1].content_type == "table"
    assert results[1].table_index == 3


def test_chroma_query_support_with_temporary_store(tmp_path: Path) -> None:
    store = ChromaVectorStore(
        chroma_path=tmp_path / "chroma",
        collection_name="retrieval_query_test",
        embedding_dimension=3,
    )
    chunk = TextChunk(
        chunk_id="chunk-1",
        source_file="guide.pdf",
        page_number=1,
        chunk_index=0,
        text="Healthy sleep evidence passage.",
        character_count=31,
        content_type="text",
        table_index=None,
    )
    store.upsert_chunks([chunk], [[1.0, 0.0, 0.0]])
    service = SemanticRetrievalService(
        embedding_service=FakeEmbeddingService(),
        vector_store=store,
        min_similarity=0.0,
    )

    results = service.retrieve("sleep")

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"
    assert results[0].source_file == "guide.pdf"
