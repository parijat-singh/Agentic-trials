from __future__ import annotations

import glob
import os
import re

_BUY_SIGNALS = {"strong buy", "buy", "cautious buy"}

_VERDICT_PATTERNS = [
    # Format used by report_writer: **Recommendation:** Value  (colon inside bold)
    r'\*\*Recommendation:\*\*\s*(.+?)(?:\s*\\?\s*\n|$)',
    r'\*\*Verdict:\*\*\s*(.+?)(?:\s*\\?\s*\n|$)',
    r'\*\*Investment Verdict:\*\*\s*(.+?)(?:\s*\\?\s*\n|$)',
    # Alternative: **Recommendation** : Value  (colon outside bold)
    r'\*\*Recommendation\*\*[:\s]+(.+?)(?:\n|$)',
    r'\*\*Verdict\*\*[:\s]+(.+?)(?:\n|$)',
    r'\*\*Investment Verdict\*\*[:\s]+(.+?)(?:\n|$)',
]

_KNOWN_VERDICTS = [
    "strong buy", "cautious buy", "buy",
    "hold", "watchlist", "avoid", "sell", "high risk",
]


def find_latest_report(symbol: str, reports_dir: str) -> str | None:
    """Return path of the newest .md deep-analysis report for symbol, or None."""
    sym = symbol.upper()
    pattern = os.path.join(reports_dir, f"{sym}_deep_analysis_*.md")
    matches = sorted(glob.glob(pattern), reverse=True)
    return matches[0] if matches else None


def extract_verdict(md_path: str) -> str:
    """Parse the verdict from section 1 of a deep-analysis .md report."""
    try:
        with open(md_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return "unknown"

    # Isolate section 1 (between ## 1. and ## 2.)
    m = re.search(r"## 1\..*?(?=## 2\.|\Z)", text, re.DOTALL)
    section = m.group(0) if m else text

    for pattern in _VERDICT_PATTERNS:
        fm = re.search(pattern, section, re.IGNORECASE)
        if fm:
            return fm.group(1).strip().lower()

    # Fallback: scan section text for known verdict keywords (longest match first)
    section_lower = section.lower()
    for verdict in _KNOWN_VERDICTS:
        if verdict in section_lower:
            return verdict

    return "unknown"


def is_buy_signal(verdict: str) -> bool:
    """Return True if the verdict qualifies as an acceptable buy signal."""
    v = verdict.strip().lower()
    return any(sig in v for sig in _BUY_SIGNALS)
