"""Mask secrets before they are written to the audit log."""

import re
from typing import Any

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"(?i)\b(?:api[_-]?key|secret|token)\b\s*[:=]\s*\S+")),
    ("api_key", re.compile(r"sk-[A-Za-z0-9_\-]{8,}")),
    ("payment_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("aadhaar", re.compile(r"\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b")),
    ("pan", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("email", re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b")),
    ("phone", re.compile(r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{3}\)?[\s\-.]?)\d{3}[\s\-.]\d{4}\b")),
]


def mask_text(value: str) -> str:
    """Replace secret-shaped substrings with typed redaction tokens."""
    masked = value
    for label, pattern in _PATTERNS:
        masked = pattern.sub(f"[REDACTED:{label}]", masked)
    return masked


def mask_value(value: Any) -> Any:
    """Recursively mask strings inside JSON-like structures."""
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {str(key): mask_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_value(item) for item in value]
    return value
