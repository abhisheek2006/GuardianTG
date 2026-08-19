from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import ChatSettingsDoc
from app.services.antispam import domain_of, extract_links

# Telegram's own essential service domains are always allowed so the bot
# never breaks @username mentions, t.me links the group relies on, etc.
ALWAYS_ALLOWED = {
    "t.me",
    "telegram.me",
    "telesco.pe",
    "telegram.dog",
    "telegram.org",
    "telegra.ph",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "x.com",
    "twitter.com",
}

ALLOW_ALL = object()


@dataclass
class LinkDecision:
    blocked: bool
    reason: str = ""
    links: list[str] = None  # type: ignore[assignment]


def _match_rule(domain: str, rules: list[str]) -> bool:
    """Match a domain against a rule list (allowing dotted-suffix matches)."""
    domain = domain.lower().strip()
    for rule in rules:
        rule = rule.lower().strip().lstrip(".").lstrip("www.")
        if not rule:
            continue
        if rule == domain or domain.endswith("." + rule):
            return True
    return False


def is_link_allowed(domain: str, settings: ChatSettingsDoc) -> bool:
    if domain in ALWAYS_ALLOWED:
        return True
    if _match_rule(domain, settings.allow_domains):
        return True
    if _match_rule(domain, settings.block_domains):
        return False
    # Default policy: everything not explicitly allowed or blocked is blocked.
    return False


def decide(text: str, settings: ChatSettingsDoc) -> LinkDecision:
    """Anti-link decision for a message. `block_all=True` is the default policy."""
    links = extract_links(text)
    if not links:
        return LinkDecision(blocked=False, links=[])

    blocked_domains: set[str] = set()
    for url in links:
        domain = domain_of(url)
        if not is_link_allowed(domain, settings):
            blocked_domains.add(domain)

    if blocked_domains:
        return LinkDecision(
            blocked=True,
            reason=f"Blocked domains: {', '.join(sorted(blocked_domains))}",
            links=links,
        )
    return LinkDecision(blocked=False, links=links)


def parse_domain(value: str) -> str:
    """Normalize user input like 'youtube.com', 'www.youtube.com/' -> 'youtube.com'."""
    value = value.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.split("/")[0].split("?")[0].strip()


LINK_BUTTON_STYLES = ["🔗", "🌐", "🟦", "🟩", "🟧"]


def build_link_keyboard(links: list[str], max_buttons: int = 4) -> InlineKeyboardMarkup:
    """Turn the links of an admin message into a designed inline keyboard.

    Telegram inline buttons have a fixed grey look (colours are not
    supported by the API), so we use emoji accents + domain labels to make
    each button readable and consistent.
    """
    buttons: list[list[InlineKeyboardButton]] = []
    for i, url in enumerate(links[:max_buttons]):
        style = LINK_BUTTON_STYLES[i % len(LINK_BUTTON_STYLES)]
        domain = domain_of(url)
        label = domain or url
        buttons.append([InlineKeyboardButton(f"{style} Open {label}", url=url)])
    return InlineKeyboardMarkup(buttons)