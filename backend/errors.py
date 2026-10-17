"""Client-safe descriptions of exceptions.

Provider exceptions carry text that must not reach the UI or the API response:
an OpenAI 401, for example, quotes the (partly masked) API key, and others echo
request URLs or account details. Callers log the raw exception and hand clients
only ``describe_error(exc)`` — a short reason chosen from a fixed set.
"""
from __future__ import annotations


def describe_error(exc: BaseException) -> str:
    """Classify ``exc`` by HTTP status or exception type, never by its message."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    name = type(exc).__name__

    if status in (401, 403) or any(
        s in name for s in ("Authentication", "PermissionDenied", "APIKey", "Forbidden")
    ):
        return "the provider rejected the credentials"
    if status == 429 or any(s in name for s in ("RateLimit", "UsageLimit", "LimitError")):
        return "the provider's usage limit was reached"
    if isinstance(exc, TimeoutError) or "Timeout" in name:
        return "the provider timed out"
    if isinstance(exc, ConnectionError) or "Connection" in name:
        return "the provider could not be reached"
    return "an unexpected error occurred"
