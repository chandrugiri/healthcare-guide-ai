from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from google import genai
from google.genai import errors, types

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingServiceError(Exception):
    """Base error for embedding provider failures."""


class EmbeddingConfigurationError(EmbeddingServiceError):
    pass


class EmbeddingAuthenticationError(EmbeddingServiceError):
    pass


class EmbeddingRequestError(EmbeddingServiceError):
    pass


class EmbeddingTransientError(EmbeddingServiceError):
    pass


class EmbeddingResponseError(EmbeddingServiceError):
    pass


@dataclass(frozen=True)
class DocumentEmbeddingInput:
    text: str
    title: str


class EmbeddingService(Protocol):
    def embed_document(self, text: str, title: str) -> list[float]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...

    def embed_documents(self, items: list[DocumentEmbeddingInput]) -> list[list[float]]:
        ...


class GeminiEmbeddingService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        max_retries: int | None = None,
        client: genai.Client | None = None,
        sleep_seconds: float = 1.0,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key
        if not self.api_key and client is None:
            raise EmbeddingConfigurationError("GEMINI_API_KEY is not configured")
        self.model = model or settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension
        self.max_retries = (
            max_retries if max_retries is not None else settings.embedding_max_retries
        )
        self.client = client or genai.Client(api_key=self.api_key)
        self.sleep_seconds = sleep_seconds
        self._sleep = sleep_func or time.sleep

    def embed_document(self, text: str, title: str) -> list[float]:
        return self.embed_documents([DocumentEmbeddingInput(text=text, title=title)])[0]

    def embed_query(self, query: str) -> list[float]:
        formatted = f"task: question answering | query: {query}"
        embeddings = self._embed_contents([self._content(formatted)])
        return embeddings[0]

    def embed_documents(self, items: list[DocumentEmbeddingInput]) -> list[list[float]]:
        if not items:
            return []
        contents = [
            self._content(f"title: {item.title} | text: {item.text}") for item in items
        ]
        return self._embed_contents(contents)

    def _embed_contents(self, contents: list[types.Content]) -> list[list[float]]:
        response = self._call_with_retry(contents)
        embeddings = getattr(response, "embeddings", None)
        if embeddings is None:
            raise EmbeddingResponseError("Embedding response did not include embeddings")
        if len(embeddings) != len(contents):
            raise EmbeddingResponseError(
                f"Expected {len(contents)} embeddings, received {len(embeddings)}"
            )

        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = list(getattr(embedding, "values", []) or [])
            self._validate_vector(values)
            vectors.append(values)
        return vectors

    def _call_with_retry(self, contents: list[types.Content]) -> object:
        attempt = 0
        while True:
            try:
                return self.client.models.embed_content(
                    model=self.model,
                    contents=contents,
                    config=types.EmbedContentConfig(
                        outputDimensionality=self.dimension
                    ),
                )
            except Exception as exc:
                if not self._is_retryable_error(exc):
                    raise self._to_domain_error(exc) from exc
                attempt += 1
                if attempt >= self.max_retries:
                    logger.warning(
                        "Embedding request failed after %s attempts", attempt
                    )
                    raise EmbeddingTransientError(
                        "Embedding request failed after retries"
                    ) from exc
                wait_seconds = self._retry_wait_seconds(exc, attempt)
                logger.warning(
                    "Embedding request failed; retrying attempt %s after %.1f seconds",
                    attempt + 1,
                    wait_seconds,
                )
                self._sleep(wait_seconds)

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self.dimension:
            raise EmbeddingResponseError(
                f"Expected embedding dimension {self.dimension}, received {len(vector)}"
            )

    def _content(self, text: str) -> types.Content:
        return types.Content(parts=[types.Part(text=text)])

    def _is_retryable_error(self, exc: Exception) -> bool:
        status_code = getattr(exc, "code", None)
        if isinstance(exc, errors.ServerError):
            return True
        if status_code in {408, 409, 429, 500, 502, 503, 504}:
            return True
        return False

    def _to_domain_error(self, exc: Exception) -> EmbeddingServiceError:
        status_code = getattr(exc, "code", None)
        if status_code in {400, 422}:
            return EmbeddingRequestError("Embedding request was malformed")
        if status_code in {401, 403}:
            return EmbeddingAuthenticationError("Embedding authentication failed")
        return EmbeddingServiceError("Embedding request failed")

    def _retry_wait_seconds(self, exc: Exception, attempt: int) -> float:
        provider_delay = _extract_retry_delay_seconds(exc)
        if provider_delay is not None:
            return provider_delay
        base_delay = self.sleep_seconds * (2 ** (attempt - 1))
        if getattr(exc, "code", None) == 429:
            return max(10.0, base_delay)
        return base_delay


def _extract_retry_delay_seconds(exc: Exception) -> float | None:
    response_delay = _find_retry_delay(getattr(exc, "response_json", None))
    if response_delay is not None:
        return response_delay
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            return _parse_duration_seconds(str(retry_after))
    return None


def _find_retry_delay(value: object) -> float | None:
    if isinstance(value, dict):
        for key in ("retryDelay", "retry_delay"):
            if key in value:
                parsed = _parse_duration_seconds(str(value[key]))
                if parsed is not None:
                    return parsed
        if "seconds" in value and set(value).issubset({"seconds", "nanos"}):
            seconds = float(value.get("seconds") or 0)
            nanos = float(value.get("nanos") or 0)
            return seconds + nanos / 1_000_000_000
        for item in value.values():
            parsed = _find_retry_delay(item)
            if parsed is not None:
                return parsed
    if isinstance(value, list):
        for item in value:
            parsed = _find_retry_delay(item)
            if parsed is not None:
                return parsed
    return None


def _parse_duration_seconds(value: str) -> float | None:
    stripped = value.strip()
    if re.fullmatch(r"\d+(\.\d+)?s", stripped):
        return float(stripped[:-1])
    if re.fullmatch(r"\d+(\.\d+)?", stripped):
        return float(stripped)
    return None
