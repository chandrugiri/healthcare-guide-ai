from fastapi import APIRouter, HTTPException, status

from app.models.chat import ChatRequest, ChatResponse
from app.services.embedding_service import GeminiEmbeddingService
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


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return build_rag_service().answer(
            question=request.question,
            history=request.history,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except GenerationTransientError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The answer generation service is temporarily unavailable.",
        ) from exc
