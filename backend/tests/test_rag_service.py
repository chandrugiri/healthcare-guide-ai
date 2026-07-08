import logging

import pytest

from app.models.chat import ChatHistoryMessage
from app.models.retrieval import RetrievedChunk
from app.services.generation_service import GenerationTransientError
from app.services.rag_service import (
    GREETING_RESPONSE,
    MEDICATION_SAFETY_RESPONSE,
    MEDICATION_SAFETY_NOTICE,
    NO_EVIDENCE_RESPONSE,
    RAGService,
    _remove_invalid_citations,
)


class FakeRetrievalService:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.calls: list[str] = []

    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
        self.calls.append(question)
        return self.chunks


class FakeGenerationService:
    def __init__(self, answer: str = "Generated answer [1]") -> None:
        self.answer = answer
        self.prompts: list[str] = []

    def generate_answer(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answer


def _chunk(index: int, text: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chunk-{index}",
        text=text or f"Healthcare evidence passage {index}.",
        source_file=f"source-{index}.pdf",
        page_number=index,
        chunk_index=index,
        content_type="text",
        table_index=None,
        distance=0.2,
        similarity_score=0.8,
    )


def _service(
    chunks: list[RetrievedChunk],
    answer: str = "Generated answer [1]",
    **kwargs: object,
) -> tuple[RAGService, FakeRetrievalService, FakeGenerationService]:
    retrieval = FakeRetrievalService(chunks)
    generation = FakeGenerationService(answer)
    service = RAGService(
        retrieval_service=retrieval,
        generation_service=generation,
        **kwargs,
    )
    return service, retrieval, generation


def test_greeting_bypasses_retrieval_and_gemini() -> None:
    service, retrieval, generation = _service([])

    response = service.answer("hello")

    assert response.answer == GREETING_RESPONSE
    assert response.insufficient_context is True
    assert retrieval.calls == []
    assert generation.prompts == []


def test_empty_question_validation() -> None:
    service, _, _ = _service([])

    with pytest.raises(ValueError):
        service.answer("   ")


def test_question_length_validation() -> None:
    service, _, _ = _service([], max_question_length=5)

    with pytest.raises(ValueError):
        service.answer("too long")


def test_history_trimming() -> None:
    service, _, generation = _service([_chunk(1)], max_history_messages=2)
    history = [
        ChatHistoryMessage(role="user", content="one"),
        ChatHistoryMessage(role="assistant", content="two"),
        ChatHistoryMessage(role="user", content="three"),
    ]

    service.answer("How can I sleep?", history)

    prompt = generation.prompts[0]
    assert "one" not in prompt
    assert "two" in prompt
    assert "three" in prompt


def test_normal_retrieval_called_once_and_top_3_passed_to_generation() -> None:
    service, retrieval, generation = _service(
        [_chunk(1), _chunk(2), _chunk(3), _chunk(4)],
        context_top_k=3,
    )

    response = service.answer("How can I sleep?")

    assert retrieval.calls == ["How can I sleep?"]
    prompt = generation.prompts[0]
    assert "[Source 1]" in prompt
    assert "[Source 3]" in prompt
    assert "[Source 4]" not in prompt
    assert len(response.sources) == 3


def test_context_character_limit_removes_lowest_ranked_source() -> None:
    service, _, generation = _service(
        [_chunk(1, "A" * 60), _chunk(2, "B" * 60), _chunk(3, "C" * 60)],
        max_context_characters=180,
    )

    response = service.answer("How can I sleep?")

    assert len(response.sources) == 1
    assert "source-1.pdf" in generation.prompts[0]
    assert "source-2.pdf" not in generation.prompts[0]


def test_no_evidence_response_bypasses_gemini() -> None:
    service, retrieval, generation = _service([])

    response = service.answer("What helps sleep?")

    assert response.answer == NO_EVIDENCE_RESPONSE
    assert response.sources == []
    assert response.insufficient_context is True
    assert retrieval.calls == ["What helps sleep?"]
    assert generation.prompts == []


@pytest.mark.parametrize(
    "question",
    [
        "Should I stop my blood pressure medication?",
        "What tablet can I use for fever?",
        "Can you prescribe medicine for cold and flu?",
        "Which antibiotic should I take?",
        "Should I increase my dosage?",
    ],
)
def test_personalised_medication_request_bypasses_retrieval_and_gemini(
    question: str,
) -> None:
    service, retrieval, generation = _service([])

    response = service.answer(question)

    assert response.answer == MEDICATION_SAFETY_RESPONSE
    assert response.sources == []
    assert response.insufficient_context is False
    assert response.safety_notice == MEDICATION_SAFETY_NOTICE
    assert retrieval.calls == []
    assert generation.prompts == []


def test_neutral_medication_question_is_not_blocked() -> None:
    service, retrieval, generation = _service([_chunk(1)])

    response = service.answer("What is paracetamol?")

    assert retrieval.calls == ["What is paracetamol?"]
    assert generation.prompts
    assert response.answer == "Generated answer [1]"


@pytest.mark.parametrize(
    "question",
    [
        "What are antibiotics?",
        "Can I take a walk after dinner?",
        "Should I take some rest?",
        "Can I take a shower with a fever?",
    ],
)
def test_non_medication_take_questions_are_not_blocked(question: str) -> None:
    service, retrieval, generation = _service([_chunk(1)])

    service.answer(question)

    assert retrieval.calls == [question]
    assert generation.prompts


def test_backend_created_sources_preserve_filename_and_page() -> None:
    service, _, _ = _service([_chunk(1)])

    response = service.answer("How can I sleep?")

    assert response.sources[0].source_file == "source-1.pdf"
    assert response.sources[0].page_number == 1


def test_invalid_generated_citation_numbers_are_removed() -> None:
    service, _, _ = _service([_chunk(1)], answer="Use sleep routines [1] [4].")

    response = service.answer("How can I sleep?")

    assert response.answer == "Use sleep routines [1]."


@pytest.mark.parametrize(
    ("answer", "available_count", "expected"),
    [
        ("Valid [1].", 2, "Valid [1]."),
        ("Invalid [99].", 2, "Invalid."),
        ("Grouped [1, 2].", 2, "Grouped [1, 2]."),
        ("Mixed [1, 99].", 2, "Mixed [1]."),
        ("Invalid group [98, 99].", 2, "Invalid group."),
        ("Adjacent [1][2].", 2, "Adjacent [1][2]."),
        ("Duplicate [2, 1, 2].", 2, "Duplicate [2, 1]."),
        ("Keep [clinical note].", 2, "Keep [clinical note]."),
    ],
)
def test_grouped_citation_validation(
    answer: str, available_count: int, expected: str
) -> None:
    assert _remove_invalid_citations(answer, available_count) == expected


def test_sensitive_values_and_full_questions_are_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    service, _, _ = _service([_chunk(1)])
    question = "How can I improve sleep with a very specific private detail?"

    with caplog.at_level(logging.INFO):
        service.answer(question)

    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "request_id=" in logs
    assert "model=" in logs
    assert question not in logs
    assert "Healthcare evidence passage" not in logs


def test_generation_transient_error_propagates_for_api_mapping() -> None:
    class FailingGeneration:
        def generate_answer(self, prompt: str) -> str:
            raise GenerationTransientError("temporary")

    service = RAGService(
        retrieval_service=FakeRetrievalService([_chunk(1)]),
        generation_service=FailingGeneration(),
    )

    with pytest.raises(GenerationTransientError):
        service.answer("How can I sleep?")
