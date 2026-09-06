"""
Ingestion script: chunk the sample municipal code corpus and load it into
the Chroma collection with strict metadata (source document + section
number) attached to every chunk.

Run standalone:
    python -m app.rag.ingest

This is what makes citation integrity possible downstream -- every chunk
carries the *exact* section it came from, so the agent orchestrator can
verify (not just trust) any citation the LLM produces.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, TypedDict

from app.config import DATA_DIR
from app.rag.vector_store import get_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civicmint.rag.ingest")

CORPUS_DIR = DATA_DIR / "sample_municipal_code"

_ENTRY_RE = re.compile(
    r"\[SOURCE:\s*(?P<source>[^|]+)\|\s*SECTION:\s*(?P<section>[^\]]+)\]\s*(?P<body>.*?)(?=\n\[SOURCE:|\Z)",
    re.S,
)


class Chunk(TypedDict):
    id: str
    text: str
    source_document: str
    section: str


def parse_file(path: Path) -> List[Chunk]:
    raw = path.read_text(encoding="utf-8")
    chunks: List[Chunk] = []
    for i, match in enumerate(_ENTRY_RE.finditer(raw)):
        source = match.group("source").strip()
        section = match.group("section").strip()
        body = match.group("body").strip()
        if not body:
            continue
        chunk_id = f"{path.stem}::{section}".replace(" ", "_")
        chunks.append(
            Chunk(id=chunk_id, text=body, source_document=source, section=section)
        )
    return chunks


def load_all_chunks() -> List[Chunk]:
    if not CORPUS_DIR.exists():
        logger.warning("Corpus directory %s does not exist.", CORPUS_DIR)
        return []
    all_chunks: List[Chunk] = []
    for path in sorted(CORPUS_DIR.glob("*.txt")):
        all_chunks.extend(parse_file(path))
    return all_chunks


def ingest(reset: bool = False) -> int:
    collection = get_collection()
    if reset:
        existing = collection.get()
        if existing and existing.get("ids"):
            collection.delete(ids=existing["ids"])

    chunks = load_all_chunks()
    if not chunks:
        logger.warning("No chunks found to ingest.")
        return 0

    collection.upsert(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[
            {"source_document": c["source_document"], "section": c["section"]}
            for c in chunks
        ],
    )
    logger.info("Ingested %d chunks into collection '%s'.", len(chunks), collection.name)
    return len(chunks)


if __name__ == "__main__":
    count = ingest(reset=True)
    print(f"Ingested {count} municipal code chunks.")
