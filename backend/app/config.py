"""
Centralized application configuration.

All tunables are pulled from environment variables (via .env in local dev)
so nothing sensitive or environment-specific is hardcoded into source.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "data" / "chroma_store"
FORMS_DIR = BASE_DIR / "data" / "forms"
FILLED_FORMS_DIR = BASE_DIR / "data" / "filled_forms"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "CivicMint API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # --- CORS ---
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # --- LLM Providers (either is optional; app degrades gracefully without both) ---
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    LLM_MODEL: str = "claude-sonnet-4-6"
    LLM_PROVIDER: str = "anthropic"  # "anthropic" | "openai" | "none"
    LLM_TIMEOUT_SECONDS: float = 20.0
    LLM_MAX_RETRIES: int = 2

    # --- Embeddings ---
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # --- Vector store ---
    CHROMA_COLLECTION_NAME: str = "municipal_code"
    RAG_TOP_K: int = 6
    RAG_TIMEOUT_SECONDS: float = 8.0

    # --- Rate limiting (sliding window) ---
    RATE_LIMIT_MAX_REQUESTS: int = 10
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # --- Caching ---
    CACHE_TTL_SECONDS: int = 900  # 15 minutes
    CACHE_MAX_ENTRIES: int = 512

    # --- Input validation ---
    MAX_DESCRIPTION_LENGTH: int = 1200
    MAX_ADDRESS_LENGTH: int = 250
    MAX_BUSINESS_NAME_LENGTH: int = 150

    # --- PDF form filling ---
    PDF_MAX_FIELD_CHARS: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()
