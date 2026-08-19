from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from app.database.models import ChatSettingsDoc
from app.services import redis as redis_service

# Heuristic weights used by the scoring system.
WEIGHT_REPEATED = 2
WEIGHT_MANY_LINKS = 3
WEIGHT_MASS_MENTIONS = 3
WEIGHT_FLOOD_BURST = 4
WEIGHT_SCAM_PATTERN = 5
WEIGHT_LONG_MESSAGE = 1
WEIGHT_SUSPICIOUS_INVITE = 2

MAX_MENTIONS = 4
MAX_LINKS = 2
LONG_MESSAGE_CHARS = 3000

REPEAT_TTL = 60  # seconds between repeated messages that count

SCAM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(win|won|claim)\b.{0,40}\b(prize|gift|cash|reward|wallet)\b", re.I),
    re.compile(r"\b(free|gift)\b.{0,20}\b(iphone|playstation|airdrop|crypto|bitcoin)\b", re.I),
    re.compile(r"\binvest\b.{0,30}\b(double|guaranteed|profit|return)\b", re.I),
    re.compile(r"\b(click|visit|pm|dm)\b.{0,30}\b(verify|claim|withdraw)\b", re.I),
    re.compile(r"\bairdrop\b.{0,40}\b(register|claim|send)\b", re.I),
    re.compile(r"\b((bank|paypal|cashapp|venmo)\b.{0,30}\b(verify|login|pin|password))", re.I),
    re.compile(r"\b(miner|mining)\b.{0,20}\b(rent|earn|buy)\b", re.I),
    re.compile(r"\b(sure|100%)?\b.{0,20}\bfree\b.{0,30}\b(robux|gems|v-bucks|credits)\b", re.I),
]

URL_RE = re.compile(
    r"(?:https?://|www\.|t\.me/|telegram\.me/|discord\.gg/)[^\s<>\"']+",
    re.I,
)
MENTION_RE = re.compile(r"(?:@\w+|tg://user\?id=\d+)")


@dataclass
class ScanResult:
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    repeated: bool = False


def extract_links(text: str) -> list[str]:
    return URL_RE.findall(text)


def extract_mentions(text: str) -> list[str]:
    return MENTION_RE.findall(text)


def is_scam_text(text: str) -> bool:
    return any(pattern.search(text) for pattern in SCAM_PATTERNS)


def domain_of(url: str) -> str:
    """Best-effort domain extraction from a URL string."""
    lowered = url.lower().lstrip("htps:/w.")
    if lowered.startswith("t.me/") or lowered.startswith("telegram.me/"):
        return lowered.split("/")[0] + "/" + (lowered.split("/")[1] if "/" in lowered else "")
    for prefix in ("http://", "https://", "www."):
        if lowered.startswith(prefix):
            lowered = lowered[len(prefix):]
    host = lowered.split("/")[0].split("?")[0].split("#")[0]
    parts = host.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return host


async def _check_repeated(
    chat_id: int, user_id: int, text: str
) -> bool:
    if not text:
        return False
    digest = hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16]
    key = f"repeat:{chat_id}:{user_id}:{digest}"
    count = await redis_service.incr_window(key, REPEAT_TTL)
    return count >= 2


async def scan_message(
    chat_id: int,
    user_id: int,
    text: str,
    settings: ChatSettingsDoc,
) -> ScanResult:
    """Compute a spam score for a single message using multiple heuristics."""
    result = ScanResult()
    if not text:
        return result

    result.links = extract_links(text)

    if len(result.links) >= MAX_LINKS:
        result.score += WEIGHT_MANY_LINKS
        result.reasons.append(f"Too many links ({len(result.links)})")

    mentions = extract_mentions(text)
    if len(mentions) >= MAX_MENTIONS:
        result.score += WEIGHT_MASS_MENTIONS
        result.reasons.append(f"Mass mentions ({len(mentions)})")

    if is_scam_text(text):
        result.score += WEIGHT_SCAM_PATTERN
        result.reasons.append("Known scam pattern")

    if len(text) > LONG_MESSAGE_CHARS:
        result.score += WEIGHT_LONG_MESSAGE
        result.reasons.append("Extremely long message")

    # A burst of identical messages inflates the score strongly.
    result.repeated = await _check_repeated(chat_id, user_id, text)
    if result.repeated:
        result.score += WEIGHT_REPEATED
        result.reasons.append("Repeated message")

    return result