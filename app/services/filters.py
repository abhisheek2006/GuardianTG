from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.database.models import CustomFilterDoc

# Lightweight built-in profanity/suspicious-word list. Custom group filters
# are the primary mechanism and are stored per chat.
BUILTIN_PATTERNS: list[str] = [
    "scam",
    "scammer",
    "fraud",
    "phishing",
    "pyramid scheme",
    "bitcoin giveaway",
    "nude free",
    "sure win",
]


@dataclass
class FilterMatch:
    filter: CustomFilterDoc
    pattern: str


def _normalise(text: str) -> str:
    return text.lower().strip()


def check_text(text: str, filters: list[CustomFilterDoc]) -> Optional[FilterMatch]:
    """Return the first matching filter (case-insensitive substring match)."""
    normalised = _normalise(text)
    for f in filters:
        pattern = _normalise(f.pattern)
        if not pattern:
            continue
        if pattern in normalised:
            return FilterMatch(filter=f, pattern=f.pattern)
    return None


def check_builtin(text: str) -> Optional[str]:
    normalised = _normalise(text)
    for pattern in BUILTIN_PATTERNS:
        if pattern in normalised:
            return pattern
    return None


def validate_pattern(pattern: str) -> bool:
    """Validate a custom filter pattern (bounded length, printable)."""
    pattern = pattern.strip()
    if not pattern or len(pattern) > 200:
        return False
    if re.search(r"[\x00-\x1f]", pattern):
        return False
    return True