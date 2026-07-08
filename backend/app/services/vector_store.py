from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb

from app.core.config import settings
from app.models.document import TextChunk


class VectorStoreError(Exception):
    """Base error for vector store operations."""


class VectorStoreValidationError(VectorStoreError):
    pass


@dataclass(frozen=True)
class VectorQueryResult:
    chunk_id: str
    document: str
    metadata: dict[str, Any]
    distance: float


class ChromaVectorStore:
    def __init__(
        self,
        chroma_path: str | Path | None = None,
        collection_name: str | None = None,
        embedding_dimension: int | None = None,
    ) -> None:
        self.chroma_path = Path(chroma_path or settings.chroma_path)
        self.collection_name = collection_name or settings.chroma_collection_name
        self.embedding_dimension = embedding_dimension or settings.embedding_dimension
        self.client = chromadb.PersistentClient(path=str(self.chroma_path))
        self.collection = self._get_or_create_collection()

    def upsert_chunks(
        self, chunks: list[TextChunk], embeddings: list[list[float]]
    ) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreValidationError(
                f"Chunk count {len(chunks)} does not match embedding count {len(embeddings)}"
            )
        if not chunks:
            return

        for embedding in embeddings:
            self._validate_embedding(embedding)

        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[self._metadata(chunk) for chunk in chunks],
        )

    def count(self) -> int:
        return int(self.collection.count())

    def existing_chunk_ids(self, chunk_ids: list[str]) -> set[str]:
        if not chunk_ids:
            return set()
        result = self.collection.get(ids=chunk_ids)
        return set(result.get("ids", []))

    def chunk_exists(self, chunk_id: str) -> bool:
        return chunk_id in self.existing_chunk_ids([chunk_id])

    def query_by_embedding(
        self, query_embedding: list[float], candidate_count: int
    ) -> list[VectorQueryResult]:
        self._validate_embedding(query_embedding)
        if candidate_count <= 0:
            raise VectorStoreValidationError("candidate_count must be greater than zero")

        response = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_count,
            include=["documents", "metadatas", "distances"],
        )
        return _parse_query_response(response)

    def clear_collection(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self._get_or_create_collection()

    def get_collection_metadata(self) -> dict[str, Any]:
        metadata = getattr(self.collection, "metadata", None)
        return dict(metadata or {})

    def _get_or_create_collection(self) -> Any:
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    def _validate_embedding(self, embedding: list[float]) -> None:
        if not embedding:
            raise VectorStoreValidationError("Embedding vector must not be empty")
        if len(embedding) != self.embedding_dimension:
            raise VectorStoreValidationError(
                f"Expected embedding dimension {self.embedding_dimension}, "
                f"received {len(embedding)}"
            )

    def _metadata(self, chunk: TextChunk) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "source_file": chunk.source_file,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "content_type": chunk.content_type,
            "character_count": chunk.character_count,
        }
        if chunk.table_index is not None:
            metadata["table_index"] = chunk.table_index
        return metadata


def _parse_query_response(response: dict[str, Any]) -> list[VectorQueryResult]:
    ids = _first_result_list(response.get("ids"))
    documents = _first_result_list(response.get("documents"))
    metadatas = _first_result_list(response.get("metadatas"))
    distances = _first_result_list(response.get("distances"))
    row_count = min(len(ids), len(documents), len(metadatas), len(distances))

    results: list[VectorQueryResult] = []
    for index in range(row_count):
        chunk_id = ids[index]
        document = documents[index]
        metadata = metadatas[index]
        distance = distances[index]
        if not isinstance(chunk_id, str) or not isinstance(document, str):
            continue
        if not isinstance(metadata, dict):
            continue
        if not isinstance(distance, (int, float)):
            continue
        results.append(
            VectorQueryResult(
                chunk_id=chunk_id,
                document=document,
                metadata=metadata,
                distance=float(distance),
            )
        )
    return results


def _first_result_list(value: object) -> list[Any]:
    if not isinstance(value, list) or not value:
        return []
    first = value[0]
    return first if isinstance(first, list) else []
