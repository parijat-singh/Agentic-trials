"""
Filing Extractor
================
Converts raw SEC EDGAR HTML filings into clean, section-structured text
suitable for inclusion in an LLM prompt.
"""

import os
import re

from bs4 import BeautifulSoup

# Ordered list of (section_label, list_of_trigger_phrases).
# The first trigger phrase found (case-insensitive) marks the start of that section.
_SECTION_PATTERNS = [
    ("BUSINESS OVERVIEW", [
        r"item\s+1[.\s]+business",
        r"part\s+i[.\s]+item\s+1",
    ]),
    ("RISK FACTORS", [
        r"item\s+1a[.\s]+risk factors",
        r"risk factors",
    ]),
    ("MD&A", [
        r"item\s+7[.\s]+management",
        r"management.s discussion and analysis",
    ]),
    ("FINANCIAL STATEMENTS", [
        r"item\s+8[.\s]+financial statements",
        r"consolidated balance sheet",
        r"consolidated statements? of (operations|income)",
    ]),
]

_MAX_SECTION_CHARS = 8_000    # cap per section; total filing capped by caller


def extract_text_from_filing(filepath: str) -> str:
    """Parse an HTML (or plain-text) SEC filing and return clean plain text."""
    if not os.path.exists(filepath):
        return ""

    with open(filepath, "rb") as fh:
        raw = fh.read()

    # Try HTML parsing first; fall back to raw decode
    try:
        soup = BeautifulSoup(raw, "lxml")
        # Remove script/style noise
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
    except Exception:
        text = raw.decode("utf-8", errors="replace")

    # Collapse excessive whitespace while preserving paragraph breaks
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def extract_key_sections(text: str, max_chars: int = 300_000) -> str:
    """
    Locate the key investment-relevant sections within a filing's plain text
    and return them as a labelled block.  Falls back to the first `max_chars`
    characters of the raw text if no sections are found.
    """
    if not text:
        return ""

    lower = text.lower()
    found: list[tuple[int, str]] = []   # (start_pos, label)

    for label, patterns in _SECTION_PATTERNS:
        for pat in patterns:
            m = re.search(pat, lower)
            if m:
                found.append((m.start(), label))
                break  # only need one hit per section label

    # Sort by position so we can slice between consecutive sections
    found.sort(key=lambda x: x[0])

    if not found:
        # No recognisable sections — return truncated raw text
        return text[:max_chars]

    parts: list[str] = []
    for i, (start, label) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else start + _MAX_SECTION_CHARS
        snippet = text[start:end].strip()
        if len(snippet) > _MAX_SECTION_CHARS:
            snippet = snippet[:_MAX_SECTION_CHARS] + "\n[... truncated ...]"
        parts.append(f"== {label} ==\n{snippet}")

    combined = "\n\n".join(parts)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n[... truncated ...]"
    return combined
