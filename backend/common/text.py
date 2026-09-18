"""HTML -> plain text, tuned for the three ATS payload shapes we ingest."""
from __future__ import annotations

import html
import re

_SCRIPT_STYLE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_BLOCK_END = re.compile(r"</(p|div|li|tr|h[1-6]|section|article)>", re.I)
_BREAK = re.compile(r"<br\s*/?>", re.I)
_LIST_ITEM = re.compile(r"<li\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS_RUN = re.compile(r"[ \t\r\f\v]+")
_NL_RUN = re.compile(r"\n{3,}")


def html_to_text(raw: str | None) -> str:
    """Flatten an HTML job description into readable plain text.

    Greenhouse double-escapes its `content` field (``&lt;p&gt;``), so we unescape
    first, strip tags while preserving block boundaries, then unescape again to
    catch entities that were nested inside the escaped markup.
    """
    if not raw:
        return ""

    text = html.unescape(raw)
    text = _SCRIPT_STYLE.sub(" ", text)
    text = _BREAK.sub("\n", text)
    text = _LIST_ITEM.sub("\n- ", text)
    text = _BLOCK_END.sub("\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)

    text = _WS_RUN.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _NL_RUN.sub("\n\n", text)
    return text.strip()


def truncate_for_model(text: str, max_chars: int = 12000) -> str:
    """Clip a description to a token budget without cutting mid-sentence.

    Eligibility signals (experience floor, grad year, work authorisation) cluster
    near the top and in the requirements block, so a head-clip is safe.
    """
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars]
    boundary = max(clipped.rfind("\n"), clipped.rfind(". "))
    if boundary > max_chars * 0.6:
        clipped = clipped[: boundary + 1]
    return clipped.rstrip() + "\n\n[description truncated]"
