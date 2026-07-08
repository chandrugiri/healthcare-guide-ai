from collections.abc import Iterator
import inspect

import pytest
from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.main import app
from app.models.chat import ChatResponse
from app.services.embedding_service import EmbeddingTransientError
from app.services.generation_service import GenerationTransientError


client = TestClient(app)


class FakeRAGService:
    def answer(self, question: str, history: list[object] | None = None) -> ChatResponse:
        return ChatResponse(
            answer="Use consistent sleep routines [1].",
            sources=[],
            insufficient_context=False,
            safety_notice=None,
            request_id="req-1",
        )


class FailingRAGService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def answer(self, question: str, history: list[object] | None = None) -> ChatResponse:
        raise self.error


@pytest.fixture(autouse=True)
def clear_rag_dependency() -> Iterator[None]:
    app.dependency_overrides.clear()
    chat_route.get_rag_service.cache_clear()
    yield
    app.dependency_overrides.clear()
    chat_route.get_rag_service.cache_clear()


def test_sync_chat_endpoint_returns_chat_response() -> None:
    app.dependency_overrides[chat_route.get_rag_service] = FakeRAGService

    response = client.post("/api/chat", json={"question": "How can I sleep?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Use consistent sleep routines [1]."
    assert response.json()["request_id"] == "req-1"
    assert not inspect.iscoroutinefunction(chat_route.chat)


def test_chat_endpoint_validation_error() -> None:
    response = client.post("/api/chat", json={"question": ""})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "error",
    [EmbeddingTransientError("temporary"), GenerationTransientError("temporary")],
)
def test_chat_endpoint_safe_503_response(error: Exception) -> None:
    app.dependency_overrides[chat_route.get_rag_service] = lambda: FailingRAGService(
        error
    )

    response = client.post("/api/chat", json={"question": "How can I sleep?"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "The healthcare information service is temporarily unavailable. "
            "Please try again shortly."
        )
    }


def test_rag_dependency_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    builds: list[FakeRAGService] = []

    def build() -> FakeRAGService:
        service = FakeRAGService()
        builds.append(service)
        return service

    monkeypatch.setattr(chat_route, "build_rag_service", build)

    assert client.post("/api/chat", json={"question": "First"}).status_code == 200
    assert client.post("/api/chat", json={"question": "Second"}).status_code == 200
    assert len(builds) == 1


def test_rag_dependency_remains_overrideable() -> None:
    service = FakeRAGService()
    app.dependency_overrides[chat_route.get_rag_service] = lambda: service

    response = client.post("/api/chat", json={"question": "How can I sleep?"})

    assert response.status_code == 200
    assert response.json()["request_id"] == "req-1"
