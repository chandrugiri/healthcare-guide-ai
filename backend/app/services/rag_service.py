from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Protocol

from app.core.config import settings
from app.models.chat import ChatHistoryMessage, ChatResponse, ChatSource
from app.models.retrieval import RetrievedChunk
from app.services.generation_service import (
    GenerationService,
    GenerationTransientError,
    map_generation_error,
)

logger = logging.getLogger(__name__)

GREETING_RESPONSE = (
    "Hello! I'm Healthcare Guide AI. You can ask me general questions about health, "
    "wellbeing, prevention, common symptoms, or when to seek medical help. "
    "How can I help today?"
)

NO_EVIDENCE_RESPONSE = (
    "I don't have enough information in the available healthcare resources to answer "
    "that confidently. Please try rephrasing your question or ask about another "
    "general health topic."
)

MEDICATION_SAFETY_RESPONSE = (
    "I can provide general healthcare information, but I can’t prescribe or recommend "
    "a specific medicine, dosage, or treatment. Please speak with a qualified "
    "pharmacist, GP, or other healthcare professional who can assess your individual "
    "situation. If your symptoms are severe, rapidly worsening, or urgent, seek urgent "
    "medical care."
)

MEDICATION_SAFETY_NOTICE = (
    "This assistant does not prescribe medicines or provide personalised treatment "
    "decisions."
)

SAFETY_NOTICE = (
    "This is general healthcare information, not a diagnosis or treatment plan. "
    "Consult a qualified healthcare professional when appropriate."
)


class RetrievalProvider(Protocol):
    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
        ...


class RAGService:
    def __init__(
        self,
        retrieval_service: RetrievalProvider,
        generation_service: GenerationService,
        context_top_k: int | None = None,
        max_context_characters: int | None = None,
        max_question_length: int | None = None,
        max_history_messages: int | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.generation_service = generation_service
        self.context_top_k = (
            context_top_k if context_top_k is not None else settings.generation_context_top_k
        )
        self.max_context_characters = (
            max_context_characters
            if max_context_characters is not None
            else settings.generation_max_context_characters
        )
        self.max_question_length = (
            max_question_length
            if max_question_length is not None
            else settings.chat_max_question_length
        )
        self.max_history_messages = (
            max_history_messages
            if max_history_messages is not None
            else settings.chat_max_history_messages
        )

    def answer(
        self, question: str, history: list[ChatHistoryMessage] | None = None
    ) -> ChatResponse:
        request_id = str(uuid.uuid4())
        started = time.perf_counter()
        query = question.strip()
        self._validate_question(query)
        trimmed_history = self._trim_history(history or [])

        if _is_greeting(query):
            return self._response(request_id, GREETING_RESPONSE, [], True, None)
        if _is_medication_change_request(query):
            return self._response(
                request_id,
                MEDICATION_SAFETY_RESPONSE,
                [],
                False,
                MEDICATION_SAFETY_NOTICE,
            )

        retrieved = self.retrieval_service.retrieve(query)
        if not retrieved:
            return self._response(request_id, NO_EVIDENCE_RESPONSE, [], True, None)

        selected = self._select_context(retrieved[: self.context_top_k])
        prompt = self._build_prompt(query, trimmed_history, selected)
        try:
            raw_answer = self.generation_service.generate_answer(prompt)
        except Exception as exc:
            raise map_generation_error(exc) from exc

        answer = _remove_invalid_citations(raw_answer, len(selected))
        sources = [_to_chat_source(index, chunk) for index, chunk in enumerate(selected, 1)]
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "rag request_id=%s model=%s source_count=%s context_characters=%s "
            "duration_ms=%.2f result_status=%s",
            request_id,
            settings.generation_model,
            len(sources),
            len(prompt),
            duration_ms,
            "success",
        )
        return self._response(request_id, answer, sources, False, SAFETY_NOTICE)

    def _validate_question(self, question: str) -> None:
        if not question:
            raise ValueError("Question must not be empty")
        if len(question) > self.max_question_length:
            raise ValueError("Question is too long")

    def _trim_history(
        self, history: list[ChatHistoryMessage]
    ) -> list[ChatHistoryMessage]:
        for message in history:
            if not message.content.strip():
                raise ValueError("History message content must not be empty")
        return history[-self.max_history_messages :]

    def _select_context(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        selected = list(chunks)
        while selected and len(_build_context(selected)) > self.max_context_characters:
            selected.pop()
        return selected

    def _build_prompt(
        self,
        question: str,
        history: list[ChatHistoryMessage],
        chunks: list[RetrievedChunk],
    ) -> str:
        history_text = "\n".join(
            f"{message.role}: {message.content}" for message in history
        )
        return (
            "Conversation history:\n"
            f"{history_text if history_text else 'None'}\n\n"
            "Retrieved context:\n"
            f"{_build_context(chunks)}\n\n"
            f"Question: {question}\n"
            "Answer with citations from the supplied sources only."
        )

    def _response(
        self,
        request_id: str,
        answer: str,
        sources: list[ChatSource],
        insufficient_context: bool,
        safety_notice: str | None,
    ) -> ChatResponse:
        return ChatResponse(
            answer=answer,
            sources=sources,
            insufficient_context=insufficient_context,
            safety_notice=safety_notice,
            request_id=request_id,
        )


def _build_context(chunks: list[RetrievedChunk]) -> str:
    sections: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        sections.append(
            f"[Source {index}]\n"
            f"File: {chunk.source_file}\n"
            f"Page: {chunk.page_number}\n"
            f"Content:\n{chunk.text}"
        )
    return "\n\n".join(sections)


def _to_chat_source(source_id: int, chunk: RetrievedChunk) -> ChatSource:
    return ChatSource(
        source_id=source_id,
        source_file=chunk.source_file,
        page_number=chunk.page_number,
        content_type=chunk.content_type,
        table_index=chunk.table_index,
        similarity_score=chunk.similarity_score,
        excerpt=chunk.text[:300],
    )


def _remove_invalid_citations(answer: str, available_count: int) -> str:
    def replace(match: re.Match[str]) -> str:
        source_number = int(match.group(1))
        return match.group(0) if 1 <= source_number <= available_count else ""

    return re.sub(r"\[(\d+)\]", replace, answer)


def _is_greeting(question: str) -> bool:
    return question.strip().lower() in {"hi", "hello", "hey"}


def _is_medication_change_request(question: str) -> bool:
    lowered = " ".join(question.lower().split())
    request_patterns = (
        r"\bprescrib(?:e|ed|es|ing)\b",
        r"\b(?:need|want|get|renew|request)\s+(?:a\s+)?prescription\b",
        r"\b(?:what|which)\s+(?:tablet|medicine)\b.*\b(?:should|can)\s+i\s+"
        r"(?:take|use)\b",
        r"\brecommend(?:\s+(?:a|some))?\s+(?:medicine|medication)\b",
        r"\b(?:medicine|tablet|treatment)\s+for\b",
        r"\bwhich\s+antibiotic\b",
        r"\b(?:can|should)\s+i\s+take\b",
        r"\b(?:increase|reduce)\s+(?:my\s+)?(?:dose|dosage)\b",
        r"\bchange\s+(?:my\s+)?(?:dose|dosage|medicine|medication|treatment)\b",
        r"\bstop\s+taking\b",
    )
    if any(re.search(pattern, lowered) for pattern in request_patterns):
        return True

    medication_signal = re.search(
        r"\b(medicine|medication|dose|dosage|treatment|tablet|pill|antibiotic)\b",
        lowered,
    )
    change_signal = re.search(
        r"\b(stop|stopping|quit|change|reduce|increase|skip|adjust)\b", lowered
    )
    return bool(medication_signal and change_signal)
