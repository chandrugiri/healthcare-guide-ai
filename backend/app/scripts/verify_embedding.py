from __future__ import annotations

from app.core.config import settings
from app.core.logging import configure_logging
from app.services.embedding_service import GeminiEmbeddingService


def main() -> None:
    configure_logging()
    service = GeminiEmbeddingService()
    vector = service.embed_document(
        text="Healthy sleep habits include maintaining a consistent sleep schedule.",
        title="verification",
    )
    print(f"model name: {settings.embedding_model}")
    print(f"embedding dimension: {len(vector)}")
    print("success: embedding connection verified")


if __name__ == "__main__":
    main()
