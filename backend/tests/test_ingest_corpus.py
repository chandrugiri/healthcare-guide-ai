from pathlib import Path

import fitz

from app.services.embedding_service import DocumentEmbeddingInput
from app.services.vector_store import ChromaVectorStore
from app.scripts.ingest_corpus import ingest_corpus


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[list[DocumentEmbeddingInput]] = []

    def embed_document(self, text: str, title: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_query(self, query: str) -> list[float]:
        return [0.1, 0.2, 0.3]

    def embed_documents(self, items: list[DocumentEmbeddingInput]) -> list[list[float]]:
        self.calls.append(items)
        return [[0.1, 0.2, 0.3] for _ in items]


def _write_pdf(path: Path, page_count: int = 1) -> Path:
    document = fitz.open()
    for index in range(page_count):
        page = document.new_page()
        page.insert_text(
            (72, 200),
            (
                f"Page {index + 1} guidance. Patients should keep a consistent sleep "
                "schedule, limit caffeine late in the day, and seek medical advice "
                "when symptoms are persistent or rapidly worsening."
            ),
            fontsize=11,
        )
    document.save(path)
    document.close()
    return path


def test_ingestion_with_mocked_embedding_provider(tmp_path: Path) -> None:
    knowledge_base = tmp_path / "knowledge-base"
    knowledge_base.mkdir()
    _write_pdf(knowledge_base / "guide.pdf")
    vector_store = ChromaVectorStore(
        chroma_path=tmp_path / "chroma",
        collection_name="ingest_test",
        embedding_dimension=3,
    )
    embedding_service = FakeEmbeddingService()

    count = ingest_corpus(
        embedding_service=embedding_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=2,
        rebuild=False,
    )

    assert count == 1
    assert vector_store.count() == 1
    assert len(embedding_service.calls) == 1


def test_ingestion_rebuild_clears_existing_collection(tmp_path: Path) -> None:
    knowledge_base = tmp_path / "knowledge-base"
    knowledge_base.mkdir()
    _write_pdf(knowledge_base / "guide.pdf")
    vector_store = ChromaVectorStore(
        chroma_path=tmp_path / "chroma",
        collection_name="ingest_rebuild_test",
        embedding_dimension=3,
    )
    embedding_service = FakeEmbeddingService()

    ingest_corpus(
        embedding_service=embedding_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=2,
        rebuild=False,
    )
    count = ingest_corpus(
        embedding_service=embedding_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=2,
        rebuild=True,
    )

    assert count == 1
    assert vector_store.count() == 1


def test_existing_chunks_are_skipped_without_embedding_call(tmp_path: Path) -> None:
    knowledge_base = tmp_path / "knowledge-base"
    knowledge_base.mkdir()
    _write_pdf(knowledge_base / "guide.pdf", page_count=3)
    vector_store = ChromaVectorStore(
        chroma_path=tmp_path / "chroma",
        collection_name="skip_existing_test",
        embedding_dimension=3,
    )
    first_service = FakeEmbeddingService()
    ingest_corpus(
        embedding_service=first_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=2,
        rebuild=False,
        request_delay_seconds=0,
    )
    second_service = FakeEmbeddingService()

    count = ingest_corpus(
        embedding_service=second_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=2,
        rebuild=False,
        request_delay_seconds=0,
    )

    assert count == 3
    assert second_service.calls == []


def test_only_missing_chunks_are_embedded(tmp_path: Path) -> None:
    knowledge_base = tmp_path / "knowledge-base"
    knowledge_base.mkdir()
    _write_pdf(knowledge_base / "guide.pdf", page_count=3)
    vector_store = ChromaVectorStore(
        chroma_path=tmp_path / "chroma",
        collection_name="missing_only_test",
        embedding_dimension=3,
    )
    first_service = FakeEmbeddingService()
    ingest_corpus(
        embedding_service=first_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=2,
        rebuild=False,
        request_delay_seconds=0,
    )
    stored = vector_store.collection.get()
    vector_store.collection.delete(ids=stored["ids"][:1])
    second_service = FakeEmbeddingService()

    ingest_corpus(
        embedding_service=second_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=2,
        rebuild=False,
        request_delay_seconds=0,
    )

    assert sum(len(call) for call in second_service.calls) == 1
    assert vector_store.count() == 3


def test_request_delay_between_batches_but_not_after_final(tmp_path: Path) -> None:
    knowledge_base = tmp_path / "knowledge-base"
    knowledge_base.mkdir()
    _write_pdf(knowledge_base / "guide.pdf", page_count=3)
    vector_store = ChromaVectorStore(
        chroma_path=tmp_path / "chroma",
        collection_name="delay_test",
        embedding_dimension=3,
    )
    embedding_service = FakeEmbeddingService()
    sleep_calls: list[float] = []

    ingest_corpus(
        embedding_service=embedding_service,
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=1,
        rebuild=False,
        request_delay_seconds=6.5,
        sleep_func=sleep_calls.append,
    )

    total_batches = len(embedding_service.calls)
    assert sleep_calls == [6.5] * max(total_batches - 1, 0)


def test_rerunning_ingestion_completes_without_duplicates(tmp_path: Path) -> None:
    knowledge_base = tmp_path / "knowledge-base"
    knowledge_base.mkdir()
    _write_pdf(knowledge_base / "guide.pdf")
    vector_store = ChromaVectorStore(
        chroma_path=tmp_path / "chroma",
        collection_name="rerun_no_duplicates_test",
        embedding_dimension=3,
    )

    first_count = ingest_corpus(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=1,
        rebuild=False,
        request_delay_seconds=0,
    )
    second_count = ingest_corpus(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
        knowledge_base_path=knowledge_base,
        batch_size=1,
        rebuild=False,
        request_delay_seconds=0,
    )

    assert first_count == second_count == 1
