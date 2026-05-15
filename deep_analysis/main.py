"""
Deep Portfolio Analysis — Orchestrator
=======================================
1. Downloads missing 10-K / 10-Q filings for every portfolio stock.
2. Calls the AI analyst for each stock (skips stocks with a fresh report).
3. Saves per-stock reports as .md + .html to DEEP_ANALYSIS_DIR.
"""

from __future__ import annotations

import glob
import os
import sys
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from deep_analysis.sec_downloader import run_downloader
from deep_analysis.stock_analyst import analyze_stock
from deep_analysis.report_writer import report_exists, save_report

# Filing glob patterns per category (annual and quarterly)
_ANNUAL_GLOBS    = ["*_10-K_*.htm", "*_10-K_*.html", "*_20-F_*.htm", "*_20-F_*.html",
                    "*_40-F_*.htm", "*_40-F_*.html"]
_QUARTERLY_GLOBS = ["*_10-Q_*.htm", "*_10-Q_*.html", "*_6-K_*.htm", "*_6-K_*.html"]


def _find_filing(sec_dir: str, symbol: str, patterns: list[str]) -> str | None:
    """Return the path of the most recent filing matching any of *patterns* for *symbol*."""
    candidates: list[str] = []
    for pat in patterns:
        # Prefix the pattern with the symbol so we only match this stock
        sym_pat = pat.replace("*", symbol.upper(), 1)
        candidates.extend(glob.glob(os.path.join(sec_dir, sym_pat)))
    if not candidates:
        return None
    # Sort descending by name (dates embedded in filenames are ISO-formatted)
    candidates.sort(reverse=True)
    return candidates[0]


def run_deep_analysis(
    portfolio_path: str | None = None,
    sec_filings_dir: str | None = None,
    reports_dir: str | None = None,
    symbols: list[str] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> list[dict]:
    """
    End-to-end deep analysis pipeline.

    Args:
        portfolio_path:  Path to optimal_portfolio.csv.
        sec_filings_dir: Folder containing SEC filings.  Defaults to config.SEC_FILINGS_DIR.
        reports_dir:     Folder to save analysis reports.  Defaults to config.DEEP_ANALYSIS_DIR.
        symbols:         Explicit list of tickers to analyse; if None, all portfolio stocks.
        log_callback:    Optional callable(str) for streaming log lines.

    Returns:
        List of result dicts per stock.
    """
    def _log(msg: str):
        print(msg, flush=True)
        if log_callback:
            log_callback(msg + "\n")

    # ── Resolve paths ────────────────────────────────────────────────────────
    if portfolio_path is None:
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        portfolio_path = os.path.join(_root, "portfolio_optimizer", "optimal_portfolio.csv")

    if sec_filings_dir is None:
        sec_filings_dir = config.SEC_FILINGS_DIR

    if reports_dir is None:
        reports_dir = config.DEEP_ANALYSIS_DIR

    os.makedirs(reports_dir, exist_ok=True)

    # ── Validate API keys early ──────────────────────────────────────────────
    openai_key    = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not openai_key and not anthropic_key:
        _log("ERROR: Neither OPENAI_API_KEY nor ANTHROPIC_API_KEY is set.")
        _log("Please set at least one API key before running deep analysis.")
        return [{"error": "No LLM API key configured"}]

    _log("=" * 60)
    _log("Deep Portfolio Analysis")
    _log("=" * 60)
    primary = "OpenAI" if openai_key else "Claude (fallback only)"
    _log(f"Primary LLM  : {primary}")
    _log(f"Reports dir  : {reports_dir}")
    _log(f"Filings dir  : {sec_filings_dir}\n")

    # ── Step 1: Download missing SEC filings ────────────────────────────────
    _log("Step 1 — Ensuring SEC filings are downloaded...\n")
    try:
        run_downloader(
            portfolio_path=portfolio_path,
            output_dir=sec_filings_dir,
            log_callback=log_callback,
        )
    except Exception as exc:
        _log(f"WARNING: SEC downloader encountered an error: {exc}")
        _log("Continuing with whatever filings are already present.\n")

    # ── Step 2: Determine stock list ─────────────────────────────────────────
    if symbols:
        stock_list = [s.upper() for s in symbols]
    else:
        import pandas as pd
        if not os.path.exists(portfolio_path):
            _log(f"ERROR: Portfolio file not found: {portfolio_path}")
            return [{"error": f"Portfolio file not found: {portfolio_path}"}]
        df = pd.read_csv(portfolio_path)
        if "Symbol" not in df.columns:
            _log("ERROR: 'Symbol' column missing in portfolio CSV")
            return [{"error": "Missing 'Symbol' column in portfolio CSV"}]
        stock_list = df["Symbol"].str.upper().dropna().unique().tolist()

    _log(f"\nStep 2 — AI analysis for {len(stock_list)} stock(s): {', '.join(stock_list)}\n")

    # ── Step 3: Analyse each stock ───────────────────────────────────────────
    results: list[dict] = []

    for symbol in stock_list:
        _log(f"--- {symbol} ---")

        # Skip if fresh report exists
        existing = report_exists(symbol, reports_dir, max_age_days=60)
        if existing:
            _log(f"  Skipping: fresh report found ({existing}, ≤60 days old)\n")
            html_name = existing.replace(".md", ".html")
            results.append({
                "symbol":    symbol,
                "status":    "skipped",
                "md_path":   os.path.join(reports_dir, existing),
                "html_path": os.path.join(reports_dir, html_name),
                "reports_dir": reports_dir,
            })
            continue

        # Locate filing files
        annual_path    = _find_filing(sec_filings_dir, symbol, _ANNUAL_GLOBS)
        quarterly_path = _find_filing(sec_filings_dir, symbol, _QUARTERLY_GLOBS)

        if annual_path:
            _log(f"  Annual filing   : {os.path.basename(annual_path)}")
        else:
            _log(f"  Annual filing   : not found (analysis will proceed without it)")

        if quarterly_path:
            _log(f"  Quarterly filing: {os.path.basename(quarterly_path)}")
        else:
            _log(f"  Quarterly filing: not found (analysis will proceed without it)")

        # Run AI analysis
        try:
            analysis_md = analyze_stock(
                symbol=symbol,
                annual_path=annual_path,
                quarterly_path=quarterly_path,
                log_callback=log_callback,
            )
        except Exception as exc:
            _log(f"  ERROR during analysis: {exc}\n")
            results.append({"symbol": symbol, "status": "error", "error": str(exc)})
            continue

        # Save reports
        try:
            md_path, html_path = save_report(symbol, analysis_md, reports_dir)
            _log(f"  Report saved: {os.path.basename(md_path)}")
            _log(f"               {os.path.basename(html_path)}\n")
            results.append({
                "symbol":    symbol,
                "status":    "completed",
                "md_path":   md_path,
                "html_path": html_path,
                "reports_dir": reports_dir,
            })
        except Exception as exc:
            _log(f"  ERROR saving report: {exc}\n")
            results.append({"symbol": symbol, "status": "error", "error": str(exc)})

    # ── Summary ──────────────────────────────────────────────────────────────
    completed = [r for r in results if r.get("status") == "completed"]
    skipped   = [r for r in results if r.get("status") == "skipped"]
    errors    = [r for r in results if r.get("status") == "error"]

    _log(f"\n{'=' * 60}")
    _log(
        f"Done.  Completed: {len(completed)}"
        f"  |  Skipped (fresh): {len(skipped)}"
        f"  |  Errors: {len(errors)}"
    )
    _log(f"Reports saved to: {reports_dir}")
    if errors:
        _log("Issues:")
        for e in errors:
            _log(f"  {e.get('symbol','?')} — {e.get('error','')}")

    return results


if __name__ == "__main__":
    run_deep_analysis()
