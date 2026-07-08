from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.main import app
from app.models.chat import ChatResponse
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
    def answer(self, question: str, history: list[object] | None = None) -> ChatResponse:
        raise GenerationTransientError("temporary")


def test_chat_endpoint_success(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(chat_route, "build_rag_service", lambda: FakeRAGService())

    response = client.post("/api/chat", json={"question": "How can I sleep?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Use consistent sleep routines [1]."
    assert response.json()["request_id"] == "req-1"


def test_chat_endpoint_validation_error() -> None:
    response = client.post("/api/chat", json={"question": ""})

    assert response.status_code == 422


def test_chat_endpoint_safe_503_response(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(chat_route, "build_rag_service", lambda: FailingRAGService())

    response = client.post("/api/chat", json={"question": "How can I sleep?"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The answer generation service is temporarily unavailable."
    }
