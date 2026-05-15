"""
Stock Analyst
=============
Calls an LLM (OpenAI GPT-4o primary, Claude Opus 4.7 fallback) with a
comprehensive fund-manager-grade prompt to produce an investment research
report in Markdown.
"""

from __future__ import annotations

import os

# Ensure .env is loaded even when this module is imported before api_server runs
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)
except ImportError:
    pass
from typing import Callable

from deep_analysis.filing_extractor import extract_text_from_filing, extract_key_sections
from deep_analysis.market_data_fetcher import fetch_market_data

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a Master Fund Manager and institutional equity analyst with deep \
expertise in fundamental investing, SEC filings, valuation, forensic \
accounting, competitive strategy, capital allocation, and risk analysis.

Your task is to analyze the stock symbol provided and produce an objective, \
investment-grade assessment of whether the stock is worth buying, holding, \
watching, or avoiding.

You must behave like a disciplined long-term fund manager, not a promoter, \
trader, or hype-driven commentator. Your analysis must be grounded in facts, \
filings, numbers, and logical reasoning.\
"""

_ANALYSIS_TEMPLATE = """\
Stock symbol to analyze: {symbol}

--- MARKET DATA ---
{market_data}

--- ANNUAL FILING EXCERPTS (10-K / 20-F) ---
{annual_text}

--- QUARTERLY FILING EXCERPTS (10-Q / 6-K) ---
{quarterly_text}

---

Using all data above, produce a comprehensive investment research report \
covering ALL of the following sections. Be specific, cite numbers, and do NOT \
use hype language.

## 1. Executive Investment Verdict
Give a clear conclusion: Strong Buy / Buy / Cautious Buy / Hold / Watchlist / Avoid / Sell / High Risk.
Include: current price, market cap, enterprise value, one-sentence thesis, one-sentence main risk, \
suggested investor action.

## 2. Company Overview
Business model, revenue streams, customer segments, geographic exposure, \
quality assessment (High / Average / Weak).

## 3. Revenue Analysis
3-5 year growth, latest quarter, organic vs acquisition-driven, segment trends, \
recurring revenue, customer concentration, pricing power. Flag red flags.

## 4. Profitability and Margin Analysis
Gross/operating/EBITDA/net margins, trends, cost structure, GAAP vs non-GAAP. \
Flag red flags.

## 5. Cash Flow Quality
Operating CF, FCF, FCF margin, cash conversion, capex intensity, SBC impact. \
Compare net income vs OCF vs FCF. Flag red flags.

## 6. Balance Sheet and Liquidity
Cash, debt, net debt/cash, debt maturity, interest coverage, goodwill, \
lease obligations. Assess: Fortress / Healthy / Manageable / Stressed / Dangerous.

## 7. Dilution and Shareholder Returns
Share count trend, SBC, buybacks, dividends, insider ownership and activity. \
Flag dilution red flags.

## 8. Management and Capital Allocation
Credibility, guidance history, acquisition track record, compensation alignment, \
governance red flags.

## 9. Competitive Position and Industry Analysis
Industry size/growth, competitors, market share, moat assessment (Durable / \
Weakening / None / Commoditized). Flag competitive red flags.

## 10. SEC Filing Risk Review
New or worsening risks, litigation, regulatory investigations, accounting policy \
changes, material weaknesses, contingencies. Summarize in plain English.

## 11. Accounting Quality and Forensic Review
Revenue recognition, deferred revenue, receivables, capitalized costs, \
depreciation assumptions, GAAP vs non-GAAP adjustments, restatements. \
Flag aggressive accounting.

## 12. Valuation Analysis
P/E, Forward P/E, PEG, EV/Sales, EV/EBITDA, P/FCF, DCF if applicable. \
Compare to historical and peer multiples. Explain the most appropriate metric.

## 13. Bull Case, Base Case, and Bear Case
Three scenarios with revenue/margin/multiple assumptions, catalysts, implied \
upside or downside, and rough probability weights.

## 14. Red Flags Table
| Red Flag | Evidence | Severity (Low/Medium/High) | Why It Matters | Thesis-Breaking? |
(Be direct. Do not bury red flags in optimistic commentary.)

## 15. Strengths and Weaknesses
Two separate tables: key investment positives and key weaknesses/uncertainties.

## 16. Key Catalysts
Stock-moving events over the next 3–24 months.

## 17. Final Investment Scorecard
Score 1–10 each: Business Quality, Revenue Growth, Margin Profile, Cash Flow \
Quality, Balance Sheet, Management Quality, Competitive Moat, Valuation \
Attractiveness, Risk/Reward, Red Flag Severity. Calculate overall score.

## 18. Final Decision
Clear recommendation (Buy / Cautious Buy / Hold / Watchlist / Avoid / Sell).
Include: one-paragraph thesis, ideal entry price / valuation range, upgrade \
conditions, downgrade conditions, position sizing (Small/Medium/Large/Avoid), \
time horizon.

Before finalizing the report, challenge your own conclusion. Ask: \
"What would make this recommendation wrong?" Then revise the recommendation \
if the downside risks outweigh the upside.

Rules:
- Be objective and evidence-based.
- Cite numbers and filings.
- No hype language.
- Do not ignore red flags.
- Separate facts from assumptions.
- Highlight uncertainty clearly.
- If data is missing, say so clearly.
- Output format: clear headings, tables, concise explanations.
"""

# Max chars of filing text per filing — keep total prompt under ~25K tokens.
# 20K chars ≈ 5K tokens; two filings + prompt overhead fits comfortably in a
# 30K TPM budget (OpenAI free tier) and well within Claude's context window.
_MAX_FILING_CHARS = 20_000


def _build_messages(symbol: str, annual_path: str | None, quarterly_path: str | None) -> list[dict]:
    market_data = fetch_market_data(symbol)

    def _load(path: str | None) -> str:
        if not path or not os.path.exists(path):
            return "[Filing not available]"
        raw = extract_text_from_filing(path)
        return extract_key_sections(raw, max_chars=_MAX_FILING_CHARS) or "[No structured sections found]"

    annual_text    = _load(annual_path)
    quarterly_text = _load(quarterly_path)

    user_content = _ANALYSIS_TEMPLATE.format(
        symbol=symbol,
        market_data=market_data,
        annual_text=annual_text,
        quarterly_text=quarterly_text,
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]


def analyze_stock(
    symbol: str,
    annual_path: str | None = None,
    quarterly_path: str | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> str:
    """
    Run the full AI analysis for *symbol* and return the report as Markdown.

    Tries OpenAI (OPENAI_API_KEY) first; falls back to Claude (ANTHROPIC_API_KEY).
    Raises ValueError if neither key is set.
    """
    def _log(msg: str):
        print(msg, flush=True)
        if log_callback:
            log_callback(msg + "\n")

    messages = _build_messages(symbol, annual_path, quarterly_path)

    primary_model  = os.environ.get("DEEP_ANALYSIS_PRIMARY_MODEL", "gpt-4o")
    openai_key     = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key  = os.environ.get("ANTHROPIC_API_KEY", "")

    # httpx client with SSL verification disabled (Windows intermediate-CA issue)
    import httpx
    _http_client = httpx.Client(verify=False)

    # ── Try OpenAI ───────────────────────────────────────────────────────────
    if openai_key:
        try:
            from openai import OpenAI
            _log(f"  [AI] Calling OpenAI ({primary_model}) for {symbol}...")
            client   = OpenAI(api_key=openai_key, http_client=_http_client)
            response = client.chat.completions.create(
                model=primary_model,
                messages=messages,
                max_tokens=8000,
                temperature=0.2,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            _log(f"  [AI] OpenAI call failed: {exc}. Trying Claude fallback...")

    # ── Try Claude fallback ──────────────────────────────────────────────────
    if anthropic_key:
        try:
            import anthropic
            _log(f"  [AI] Calling Claude (claude-opus-4-7) for {symbol}...")
            system_msg  = messages[0]["content"]
            user_msg    = messages[1]["content"]
            client      = anthropic.Anthropic(
                api_key=anthropic_key,
                http_client=_http_client,
            )
            response    = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=8000,
                system=system_msg,
                messages=[{"role": "user", "content": user_msg}],
            )
            return response.content[0].text
        except Exception as exc:
            _log(f"  [AI] Claude call failed: {exc}")
            raise

    raise ValueError(
        "No LLM API key found. Set OPENAI_API_KEY (primary) or "
        "ANTHROPIC_API_KEY (fallback) in your environment."
    )
