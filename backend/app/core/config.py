from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Healthcare Guide AI API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    frontend_origin: str = "http://localhost:3000"
    gemini_api_key: str = ""
    knowledge_base_path: str = "../knowledge-base"
    chroma_path: str = "./data/chroma"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
