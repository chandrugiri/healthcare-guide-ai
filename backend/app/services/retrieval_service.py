from __future__ import annotations

import logging
import re
import time
import uuid
from collections import defaultdict
from typing import Protocol

from app.core.config import settings
from app.models.retrieval import RetrievedChunk
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import ChromaVectorStore, VectorQueryResult

logger = logging.getLogger(__name__)


class RetrievalServiceError(Exception):
    """Base error for retrieval failures."""


class RetrievalValidationError(RetrievalServiceError, ValueError):
    pass


class VectorSearchStore(Protocol):
    def query_by_embedding(
        self, query_embedding: list[float], candidate_count: int
    ) -> list[VectorQueryResult]:
        ...


class SemanticRetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorSearchStore,
        top_k: int | None = None,
        candidate_count: int | None = None,
        min_similarity: float | None = None,
        max_chunks_per_source: int | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.top_k = top_k if top_k is not None else settings.retrieval_top_k
        self.candidate_count = (
            candidate_count
            if candidate_count is not None
            else settings.retrieval_candidate_count
        )
        self.min_similarity = (
            min_similarity
            if min_similarity is not None
            else settings.retrieval_min_similarity
        )
        self.max_chunks_per_source = (
            max_chunks_per_source
            if max_chunks_per_source is not None
            else settings.retrieval_max_chunks_per_source
        )

    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        query = question.strip()
        if not query:
            raise RetrievalValidationError("Question must not be empty")

        query_embedding = self.embedding_service.embed_query(query)
        candidates = self.vector_store.query_by_embedding(
            query_embedding=query_embedding,
            candidate_count=self.candidate_count,
        )
        results = self._rank_and_filter(candidates, top_k or self.top_k)
        duration_ms = (time.perf_counter() - started) * 1000

        logger.info(
            "retrieval request_id=%s query_length=%s candidates_retrieved=%s "
            "candidates_filtered=%s final_result_count=%s duration_ms=%.2f",
            request_id,
            len(query),
            len(candidates),
            len(candidates) - len(results),
            len(results),
            duration_ms,
        )
        return results

    def _rank_and_filter(
        self, candidates: list[VectorQueryResult], limit: int
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        highest_similarity = max(
            _similarity_from_cosine_distance(candidate.distance)
            for candidate in candidates
        )
        if highest_similarity < self.min_similarity:
            return []

        seen_ids: set[str] = set()
        seen_text_keys: set[str] = set()
        source_counts: defaultdict[str, int] = defaultdict(int)
        results: list[RetrievedChunk] = []

        for candidate in candidates:
            if candidate.chunk_id in seen_ids:
                continue
            similarity = _similarity_from_cosine_distance(candidate.distance)
            if similarity < self.min_similarity:
                continue
            if _is_low_value_content(candidate.document):
                continue
            text_key = _near_duplicate_key(candidate.document)
            if text_key in seen_text_keys:
                continue

            chunk = _to_retrieved_chunk(candidate, similarity)
            if source_counts[chunk.source_file] >= self.max_chunks_per_source:
                continue

            seen_ids.add(candidate.chunk_id)
            seen_text_keys.add(text_key)
            source_counts[chunk.source_file] += 1
            results.append(chunk)
            if len(results) >= limit:
                break
        return results


RetrievalService = SemanticRetrievalService


def _similarity_from_cosine_distance(distance: float) -> float:
    return min(1.0, max(0.0, 1.0 - distance))


def _near_duplicate_key(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(words[:80])


def _is_low_value_content(text: str) -> bool:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        return True

    low_value_patterns = [
        r"\b(publication|published|publisher|copyright|all rights reserved|licen[cs]e)\b",
        r"\b(isbn|issn|doi|version|document version|revision|updated|last updated)\b",
        r"\b(contact|email|telephone|phone|fax|website|www|http)\b",
        r"\b(order|purchase|sales|subscribe|subscription|refund|returns?)\b",
        r"\b(terms and conditions|privacy policy|permission|reproduced)\b",
    ]
    healthcare_patterns = [
        r"\b(health|healthy|symptom|treatment|doctor|clinician|patient|medical)\b",
        r"\b(blood pressure|sleep|dehydration|activity|exercise|heart|diet|food)\b",
        r"\b(water|medicine|care|risk|disease|condition|pain|emergency)\b",
    ]

    low_value_hits = sum(
        1 for pattern in low_value_patterns if re.search(pattern, text, re.IGNORECASE)
    )
    has_healthcare_signal = any(
        re.search(pattern, text, re.IGNORECASE) for pattern in healthcare_patterns
    )
    if low_value_hits >= 2 and not has_healthcare_signal:
        return True
    if low_value_hits >= 3 and len(words) < 120:
        return True
    return False


def _to_retrieved_chunk(
    candidate: VectorQueryResult, similarity_score: float
) -> RetrievedChunk:
    metadata = candidate.metadata
    return RetrievedChunk(
        chunk_id=candidate.chunk_id,
        text=candidate.document,
        source_file=str(metadata.get("source_file", "")),
        page_number=int(metadata.get("page_number", 1)),
        chunk_index=int(metadata.get("chunk_index", 0)),
        content_type=str(metadata.get("content_type", "text")),  # type: ignore[arg-type]
        table_index=(
            int(metadata["table_index"]) if metadata.get("table_index") is not None else None
        ),
        distance=candidate.distance,
        similarity_score=similarity_score,
    )
