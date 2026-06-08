"""Token-based text chunking using tiktoken (500 tokens, 50 overlap by default)."""
from __future__ import annotations

import logging

import tiktoken

from backend.config import settings

logger = logging.getLogger(__name__)


def _get_encoding(model: str):
    """Return the tiktoken encoding for ``model``, falling back to cl100k_base
    (the encoding used by text-embedding-3-* models)."""
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
    model: str | None = None,
) -> list[str]:
    """Split ``text`` into overlapping token windows.

    Returns a list of decoded chunk strings. An empty/whitespace input yields an
    empty list. ``overlap`` is clamped to be strictly less than ``chunk_size``.
    """
    text = (text or "").strip()
    if not text:
        return []

    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = settings.CHUNK_OVERLAP if overlap is None else overlap
    overlap = max(0, min(overlap, chunk_size - 1))
    step = chunk_size - overlap

    enc = _get_encoding(model or settings.EMBEDDING_MODEL)
    tokens = enc.encode(text)
    if len(tokens) <= chunk_size:
        return [text]

    chunks: list[str] = []
    for start in range(0, len(tokens), step):
        window = tokens[start : start + chunk_size]
        if not window:
            break
        chunks.append(enc.decode(window).strip())
        if start + chunk_size >= len(tokens):
            break
    return [c for c in chunks if c]
