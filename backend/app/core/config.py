from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Healthcare Guide AI API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    frontend_origin: str = "http://localhost:3000"
    gemini_api_key: str = ""
    knowledge_base_path: str = "../knowledge-base"
    chroma_path: str = "./data/chroma"
    embedding_model: str = "gemini-embedding-2"
    embedding_dimension: int = 768
    chroma_collection_name: str = "healthcare_guide_documents"
    embedding_batch_size: int = 10
    embedding_max_retries: int = 5
    embedding_request_delay_seconds: float = 6.5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
