from pathlib import Path

import pytest

from app.models.document import TextChunk
from app.services.vector_store import ChromaVectorStore, VectorStoreValidationError


def _chunk(
    chunk_id: str = "chunk-1",
    content_type: str = "text",
    table_index: int | None = None,
) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        source_file="guide.pdf",
        page_number=2,
        chunk_index=4,
        text="Useful healthcare guidance long enough to store.",
        character_count=48,
        content_type=content_type,  # type: ignore[arg-type]
        table_index=table_index,
    )


def _store(path: Path) -> ChromaVectorStore:
    return ChromaVectorStore(
        chroma_path=path,
        collection_name="test_healthcare_guide_documents",
        embedding_dimension=3,
    )


def test_chroma_upsert_and_metadata_preservation(tmp_path: Path) -> None:
    store = _store(tmp_path / "chroma")
    chunk = _chunk(content_type="table", table_index=1)

    store.upsert_chunks([chunk], [[0.1, 0.2, 0.3]])

    assert store.count() == 1
    stored = store.collection.get(ids=[chunk.chunk_id], include=["metadatas", "documents"])
    assert stored["documents"] == [chunk.text]
    metadata = stored["metadatas"][0]
    assert metadata["source_file"] == "guide.pdf"
    assert metadata["page_number"] == 2
    assert metadata["chunk_index"] == 4
    assert metadata["content_type"] == "table"
    assert metadata["table_index"] == 1
    assert metadata["character_count"] == 48


def test_deterministic_rerun_without_duplicates(tmp_path: Path) -> None:
    store = _store(tmp_path / "chroma")
    chunk = _chunk()

    store.upsert_chunks([chunk], [[0.1, 0.2, 0.3]])
    store.upsert_chunks([chunk], [[0.3, 0.2, 0.1]])

    assert store.count() == 1


def test_existing_chunk_ids_and_chunk_exists(tmp_path: Path) -> None:
    store = _store(tmp_path / "chroma")
    chunk = _chunk()
    store.upsert_chunks([chunk], [[0.1, 0.2, 0.3]])

    assert store.chunk_exists("chunk-1") is True
    assert store.chunk_exists("missing") is False
    assert store.existing_chunk_ids(["chunk-1", "missing"]) == {"chunk-1"}


def test_mismatched_chunk_embedding_count(tmp_path: Path) -> None:
    store = _store(tmp_path / "chroma")

    with pytest.raises(VectorStoreValidationError):
        store.upsert_chunks([_chunk()], [])


def test_embedding_dimension_validation(tmp_path: Path) -> None:
    store = _store(tmp_path / "chroma")

    with pytest.raises(VectorStoreValidationError):
        store.upsert_chunks([_chunk()], [[0.1, 0.2]])


def test_collection_clearing(tmp_path: Path) -> None:
    store = _store(tmp_path / "chroma")
    store.upsert_chunks([_chunk()], [[0.1, 0.2, 0.3]])

    store.clear_collection()

    assert store.count() == 0
    metadata = store.get_collection_metadata()
    assert metadata.get("hnsw:space") == "cosine"
