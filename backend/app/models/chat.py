from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("History message content must not be empty")
        return value


class ChatRequest(BaseModel):
    question: str
    history: list[ChatHistoryMessage] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question must not be empty")
        return value


class ChatSource(BaseModel):
    source_id: int
    source_file: str
    page_number: int
    content_type: Literal["text", "table"]
    table_index: int | None
    similarity_score: float
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    insufficient_context: bool
    safety_notice: str | None
    request_id: str
