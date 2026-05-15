"""
Market Data Fetcher
===================
Pulls current price, valuation multiples, and financial summary for a stock
symbol via yfinance.  Returns a formatted string for inclusion in the LLM prompt.
"""

from __future__ import annotations

import yfinance as yf


_FIELDS = [
    ("Sector",                "sector"),
    ("Industry",              "industry"),
    ("Current Price",         "currentPrice"),
    ("Previous Close",        "previousClose"),
    ("52-Week High",          "fiftyTwoWeekHigh"),
    ("52-Week Low",           "fiftyTwoWeekLow"),
    ("Market Cap",            "marketCap"),
    ("Enterprise Value",      "enterpriseValue"),
    ("Beta",                  "beta"),
    ("Shares Outstanding",    "sharesOutstanding"),
    ("Float Shares",          "floatShares"),
    # --- Valuation ---
    ("Trailing P/E",          "trailingPE"),
    ("Forward P/E",           "forwardPE"),
    ("PEG Ratio",             "pegRatio"),
    ("Price/Book",            "priceToBook"),
    ("EV/Revenue",            "enterpriseToRevenue"),
    ("EV/EBITDA",             "enterpriseToEbitda"),
    # --- Profitability ---
    ("Revenue (TTM)",         "totalRevenue"),
    ("Gross Profit (TTM)",    "grossProfits"),
    ("EBITDA",                "ebitda"),
    ("Net Income (TTM)",      "netIncomeToCommon"),
    ("Earnings Per Share",    "trailingEps"),
    ("Revenue Growth (YoY)",  "revenueGrowth"),
    ("Earnings Growth (YoY)", "earningsGrowth"),
    ("Gross Margins",         "grossMargins"),
    ("Operating Margins",     "operatingMargins"),
    ("Profit Margins",        "profitMargins"),
    # --- Balance Sheet / Cash Flow ---
    ("Total Cash",            "totalCash"),
    ("Total Debt",            "totalDebt"),
    ("Free Cash Flow",        "freeCashflow"),
    ("Operating Cash Flow",   "operatingCashflow"),
    # --- Returns ---
    ("Return on Assets",      "returnOnAssets"),
    ("Return on Equity",      "returnOnEquity"),
    # --- Dividends ---
    ("Dividend Yield",        "dividendYield"),
    ("Payout Ratio",          "payoutRatio"),
    # --- Analyst ---
    ("Analyst Target Price",  "targetMeanPrice"),
    ("Recommendation",        "recommendationKey"),
]


def _fmt(value) -> str:
    """Human-readable formatting for numbers, percentages, and strings."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        if abs(value) < 0.1 and value != 0:
            return f"{value:.4f}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        if abs(value) >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        if abs(value) >= 1_000_000:
            return f"${value / 1_000_000:.1f}M"
        return f"{value:,}"
    return str(value)


def fetch_market_data(symbol: str) -> str:
    """
    Return a formatted multi-line string of key market and financial metrics
    for *symbol*, ready for insertion into an LLM analysis prompt.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
    except Exception as exc:
        return f"[Market data unavailable for {symbol}: {exc}]"

    lines: list[str] = [f"=== MARKET DATA: {symbol} ==="]
    for label, key in _FIELDS:
        val = info.get(key)
        # Format percentages for ratio fields that yfinance returns as fractions
        if key in ("revenueGrowth", "earningsGrowth", "grossMargins",
                   "operatingMargins", "profitMargins", "dividendYield",
                   "payoutRatio", "returnOnAssets", "returnOnEquity"):
            val = f"{val * 100:.1f}%" if isinstance(val, (int, float)) else "N/A"
        else:
            val = _fmt(val)
        lines.append(f"  {label:<28} {val}")

    # Append business summary (truncated)
    summary = info.get("longBusinessSummary", "")
    if summary:
        if len(summary) > 1_500:
            summary = summary[:1_500] + "..."
        lines.append(f"\nBusiness Summary:\n{summary}")

    return "\n".join(lines)
