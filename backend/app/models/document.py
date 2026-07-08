from typing import Literal

from pydantic import BaseModel, Field


class ParsedTable(BaseModel):
    source_file: str
    page_number: int = Field(ge=1)
    table_index: int
    markdown: str


class ParsedPage(BaseModel):
    source_file: str
    page_number: int = Field(ge=1)
    text: str
    tables: list[ParsedTable]


class TextChunk(BaseModel):
    chunk_id: str
    source_file: str
    page_number: int = Field(ge=1)
    chunk_index: int
    text: str
    character_count: int
    content_type: Literal["text", "table"]
    table_index: int | None
