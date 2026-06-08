"""Chat model factory. The Analyst and Writer nodes share this so the model is
configured in exactly one place (CHAT_MODEL in .env)."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from backend.config import settings


def get_chat_model(temperature: float = 0.2, **kwargs) -> ChatOpenAI:
    """Return a configured ChatOpenAI instance.

    Model id comes from ``CHAT_MODEL`` (default ``gpt-4o``). Swap to a different
    OpenAI model — or point at any OpenAI-compatible endpoint — via env without
    touching node code.
    """
    return ChatOpenAI(
        model=settings.CHAT_MODEL,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
        **kwargs,
    )
