from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./talentlens.db"
    jwt_secret: str = "change-me-in-development"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "talentlens_documents"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    upload_dir: str = "uploads"
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
