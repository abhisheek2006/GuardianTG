from __future__ import annotations

import html as html_lib
import re

# Telegram HTML supports <b> <i> <code> <spoiler> <blockquote> <a href>.
# Marker syntax (designed for /broadcast and welcome messages):
#   _mono_      -> <code>mono</code>
#   {bold}      -> <b>bold</b>
#   "spoiler"   -> <spoiler>spoiler</spoiler>
#   :quote:     -> <blockquote>quote</blockquote>
#   [label](url)-> <a href="url">label</a>
#   https://... -> auto-linked

_BLOCKQUOTE_RE = re.compile(r":(?!:)([^:\n]{1,200}?):")
_SPOILER_RE = re.compile(r'"([^"\n]{1,120}?)"')
_BOLD_RE = re.compile(r"\{([^{}\n]{1,120}?)\}")
_MONO_RE = re.compile(r"(?<!\w)_([^_\n]{1,200}?)_(?!\w)")
_LINK_RE = re.compile(
    r"\[([^\[\]\n]{1,200}?)\]\(((?:https?|tg://)[^\s<>()]+)\)"
)
_BARE_URL_RE = re.compile(r"(?<![\w>])(https?://[^\s<>\"']+)")
_INVALID_TAG_RE = re.compile(r"<(\s*(?:[a-z]+\s*)?/?)\s*>")


def format_rich_text(text: str) -> str:
    """Convert GuardianTG markers to Telegram HTML.

    The output is safe HTML: everything is escaped first, then only the
    recognised markers become real tags/links.
    """
    out = html_lib.escape(text, quote=False)

    out = _BLOCKQUOTE_RE.sub(r"<blockquote>\1</blockquote>", out)
    out = _SPOILER_RE.sub(r"<spoiler>\1</spoiler>", out)
    out = _BOLD_RE.sub(r"<b>\1</b>", out)
    out = _MONO_RE.sub(r"<code>\1</code>", out)
    out = _LINK_RE.sub(r'<a href="\2">\1</a>', out)

    def _linkify(match: re.Match) -> str:
        url = match.group(1)
        return f'<a href="{url}">{url}</a>'

    out = _BARE_URL_RE.sub(_linkify, out)
    return out


def has_formatting(text: str) -> bool:
    """True when the text uses any of the recognised markers."""
    return any(
        re.search(pattern, text)
        for pattern in (
            _BLOCKQUOTE_RE,
            _SPOILER_RE,
            _BOLD_RE,
            _MONO_RE,
            _LINK_RE,
            _BARE_URL_RE,
        )
    )


def strip_formatting(text: str) -> str:
    """Plain-text fallback: remove markers without sending invalid HTML."""
    out = text
    out = _BLOCKQUOTE_RE.sub(r"\1", out)
    out = _SPOILER_RE.sub(r"\1", out)
    out = _BOLD_RE.sub(r"\1", out)
    out = _MONO_RE.sub(r"\1", out)
    out = _LINK_RE.sub(r"\1", out)
    return out