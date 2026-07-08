from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.chat import ChatRequest, ChatResponse
from app.services.embedding_service import EmbeddingTransientError, GeminiEmbeddingService
from app.services.generation_service import (
    GeminiGenerationService,
    GenerationTransientError,
)
from app.services.rag_service import RAGService
from app.services.retrieval_service import SemanticRetrievalService
from app.services.vector_store import ChromaVectorStore


router = APIRouter(tags=["chat"])


def build_rag_service() -> RAGService:
    embedding_service = GeminiEmbeddingService()
    vector_store = ChromaVectorStore()
    retrieval_service = SemanticRetrievalService(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )
    generation_service = GeminiGenerationService()
    return RAGService(
        retrieval_service=retrieval_service,
        generation_service=generation_service,
    )


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    return build_rag_service()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> ChatResponse:
    try:
        return rag_service.answer(
            question=request.question,
            history=request.history,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except (EmbeddingTransientError, GenerationTransientError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The healthcare information service is temporarily unavailable. "
                "Please try again shortly."
            ),
        ) from exc
