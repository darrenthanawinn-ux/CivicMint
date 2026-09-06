"""
Retrieval layer: wraps Chroma queries with timeout handling, caching, and a
similarity threshold, and normalizes results into a plain dataclass the rest
of the app depends on (so nothing outside this file needs to know Chroma's
result-dict shape).

Failure handling: a vector-store timeout or exception here must NEVER bubble
up as a raw 500 to the client. We catch, log server-side only, and return an
empty result list -- callers (the agent orchestrator) are required to treat
"no chunks retrieved" as a valid, expected state and fall back accordingly.
"""
from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass
from typing import List

from app.cache import rag_cache
from app.config import get_settings
from app.rag.vector_store import get_collection

logger = logging.getLogger("civicmint.rag.retriever")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag-retrieve")


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    source_document: str
    section: str
    score: float  # cosine similarity, 0..1 (higher = more relevant)


def _cosine_distance_to_similarity(distance: float) -> float:
    # Chroma returns cosine *distance* (0 = identical). Clamp defensively --
    # floating point noise can occasionally push this a hair outside [0, 2].
    distance = max(0.0, min(2.0, distance))
    return max(0.0, 1.0 - (distance / 2.0))


def _run_query(query_text: str, top_k: int) -> List[RetrievedChunk]:
    collection = get_collection()
    results = collection.query(query_texts=[query_text], n_results=top_k)

    ids = (results.get("ids") or [[]])[0]
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    chunks: List[RetrievedChunk] = []
    for chunk_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
        meta = meta or {}
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=doc,
                source_document=str(meta.get("source_document", "unknown")),
                section=str(meta.get("section", "unknown")),
                score=_cosine_distance_to_similarity(dist),
            )
        )
    return chunks


def retrieve(query_text: str, top_k: int | None = None) -> List[RetrievedChunk]:
    """
    Synchronous, timeout-guarded, cached retrieval. Returns [] on any failure
    rather than raising -- callers must treat that as "degrade gracefully",
    not "something to surface to the user as a hard error".
    """
    settings = get_settings()
    top_k = top_k or settings.RAG_TOP_K

    cache_key = rag_cache.make_key("retrieve", query_text, str(top_k))
    cached = rag_cache.get(cache_key)
    if cached is not None:
        return cached

    future = _executor.submit(_run_query, query_text, top_k)
    try:
        result = future.result(timeout=settings.RAG_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        logger.error("RAG retrieval timed out after %.1fs for query.", settings.RAG_TIMEOUT_SECONDS)
        future.cancel()
        return []
    except Exception:  # noqa: BLE001 -- deliberate: never let a vector-store error escape
        logger.exception("RAG retrieval failed.")
        return []

    rag_cache.set(cache_key, result)
    return result
