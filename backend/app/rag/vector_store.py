"""
Thin wrapper around a persistent Chroma collection.

Kept deliberately small: all retrieval-quality logic (thresholding,
re-ranking, timeout handling) lives in retriever.py, not here. This module's
only job is "give me a handle to the collection".
"""
from __future__ import annotations

import logging
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import CHROMA_DIR, get_settings
from app.rag.embeddings import get_embedding_function

logger = logging.getLogger("civicmint.rag.vector_store")


@lru_cache
def get_chroma_client() -> "chromadb.ClientAPI":
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


@lru_cache
def get_collection():
    settings = get_settings()
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def collection_is_empty() -> bool:
    try:
        return get_collection().count() == 0
    except Exception:  # noqa: BLE001
        logger.exception("Failed to check collection count; assuming empty.")
        return True
