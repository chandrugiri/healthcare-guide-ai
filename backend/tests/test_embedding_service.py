from __future__ import annotations

import pytest

from app.services.embedding_service import (
    DocumentEmbeddingInput,
    EmbeddingAuthenticationError,
    EmbeddingResponseError,
    EmbeddingTransientError,
    GeminiEmbeddingService,
)


class FakeEmbedding:
    def __init__(self, values: list[float]) -> None:
        self.values = values


class FakeResponse:
    def __init__(self, embeddings: list[FakeEmbedding]) -> None:
        self.embeddings = embeddings


class FakeError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"fake error {code}")
        self.code = code


class FakeModels:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def embed_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.models = FakeModels(responses)


def _service(
    client: FakeClient, sleep_calls: list[float] | None = None
) -> GeminiEmbeddingService:
    sleeps = sleep_calls if sleep_calls is not None else []
    return GeminiEmbeddingService(
        api_key="test-key",
        model="gemini-embedding-2",
        dimension=3,
        max_retries=3,
        client=client,  # type: ignore[arg-type]
        sleep_seconds=0,
        sleep_func=sleeps.append,
    )


def _content_text(content: object) -> str:
    return content.parts[0].text  # type: ignore[attr-defined]


def test_document_and_query_formatting() -> None:
    client = FakeClient(
        [
            FakeResponse([FakeEmbedding([1.0, 2.0, 3.0])]),
            FakeResponse([FakeEmbedding([4.0, 5.0, 6.0])]),
        ]
    )
    service = _service(client)

    assert service.embed_document("Body text", "guide.pdf") == [1.0, 2.0, 3.0]
    assert service.embed_query("What helps sleep?") == [4.0, 5.0, 6.0]

    document_contents = client.models.calls[0]["contents"]
    query_contents = client.models.calls[1]["contents"]
    assert _content_text(document_contents[0]) == "title: guide.pdf | text: Body text"
    assert (
        _content_text(query_contents[0])
        == "task: question answering | query: What helps sleep?"
    )


def test_batched_documents_use_separate_content_objects() -> None:
    client = FakeClient(
        [FakeResponse([FakeEmbedding([1.0, 0.0, 0.0]), FakeEmbedding([0.0, 1.0, 0.0])])]
    )
    service = _service(client)

    vectors = service.embed_documents(
        [
            DocumentEmbeddingInput(text="First chunk", title="a.pdf"),
            DocumentEmbeddingInput(text="Second chunk", title="b.pdf"),
        ]
    )

    contents = client.models.calls[0]["contents"]
    assert len(contents) == 2
    assert contents[0] is not contents[1]
    assert _content_text(contents[0]) == "title: a.pdf | text: First chunk"
    assert _content_text(contents[1]) == "title: b.pdf | text: Second chunk"
    assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def test_embedding_count_validation() -> None:
    client = FakeClient([FakeResponse([FakeEmbedding([1.0, 2.0, 3.0])])])
    service = _service(client)

    with pytest.raises(EmbeddingResponseError):
        service.embed_documents(
            [
                DocumentEmbeddingInput(text="First", title="a.pdf"),
                DocumentEmbeddingInput(text="Second", title="b.pdf"),
            ]
        )


def test_embedding_dimension_validation() -> None:
    client = FakeClient([FakeResponse([FakeEmbedding([1.0, 2.0])])])
    service = _service(client)

    with pytest.raises(EmbeddingResponseError):
        service.embed_document("Body", "guide.pdf")


def test_retry_behaviour_for_transient_errors() -> None:
    client = FakeClient(
        [
            FakeError(429),
            FakeError(503),
            FakeResponse([FakeEmbedding([1.0, 2.0, 3.0])]),
        ]
    )
    sleep_calls: list[float] = []
    service = _service(client, sleep_calls)

    assert service.embed_query("question") == [1.0, 2.0, 3.0]
    assert len(client.models.calls) == 3
    assert sleep_calls == [10.0, 0]


def test_repeated_transient_errors_raise_domain_error() -> None:
    client = FakeClient([FakeError(429), FakeError(429), FakeError(429)])
    service = _service(client)

    with pytest.raises(EmbeddingTransientError):
        service.embed_query("question")


def test_authentication_failure_is_not_retried() -> None:
    client = FakeClient([FakeError(401)])
    service = _service(client)

    with pytest.raises(EmbeddingAuthenticationError):
        service.embed_query("question")
    assert len(client.models.calls) == 1


def test_429_retry_delay_from_provider_is_respected() -> None:
    retry_error = FakeError(429)
    retry_error.response_json = {
        "error": {
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.RetryInfo",
                    "retryDelay": "13.5s",
                }
            ]
        }
    }
    client = FakeClient([retry_error, FakeResponse([FakeEmbedding([1.0, 2.0, 3.0])])])
    sleep_calls: list[float] = []
    service = _service(client, sleep_calls)

    assert service.embed_query("question") == [1.0, 2.0, 3.0]
    assert sleep_calls == [13.5]
