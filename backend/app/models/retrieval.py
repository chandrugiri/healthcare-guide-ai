from typing import Literal

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source_file: str
    page_number: int = Field(ge=1)
    chunk_index: int
    content_type: Literal["text", "table"]
    table_index: int | None
    distance: float
    similarity_score: float
