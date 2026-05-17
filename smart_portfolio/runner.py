"""
Smart Portfolio orchestrator
============================
Runs the full stock pipeline, then AI deep-analyses every candidate, filters
to buy-signal stocks, and re-optimises the portfolio using only those stocks.

Called in a background thread by the /smart-portfolio API endpoint.
"""

from __future__ import annotations

import os
import sys
import subprocess
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config  # noqa: E402 — must be after sys.path fix
from smart_portfolio.verdict_extractor import find_latest_report, extract_verdict, is_buy_signal


def run_smart_portfolio(
    session_id: str,
    pipeline_cmd: list[str],
    target_size: int,
    sessions: dict,
    root_dir: str,
) -> None:
    """
    Background worker for the Smart Portfolio tab.

    Mutates sessions[session_id] throughout so the status endpoint can stream
    live progress back to the browser.

    Phases (stored in sess["phase"]):
      pipeline   → analyzing → optimizing → completed
    """
    sess = sessions[session_id]

    def _log(msg: str) -> None:
        line = msg if msg.endswith("\n") else msg + "\n"
        sess["logs"].append(line)

    # ── Phase 1: Full stock pipeline ─────────────────────────────────────────
    sess["phase"] = "pipeline"
    _log("[Smart Portfolio] Phase 1: Running full stock pipeline…")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        p = subprocess.Popen(
            pipeline_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=root_dir,
            bufsize=1,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        for line in iter(p.stdout.readline, ""):
            if line:
                _log(line)
        p.stdout.close()
        rc = p.wait()
    except Exception as exc:
        sess["status"] = "error"
        _log(f"\n[Smart Portfolio] Pipeline launch error: {exc}\n")
        return

    if rc != 0:
        sess["status"] = "error"
        _log(f"\n[Smart Portfolio] Pipeline exited with code {rc}. Check logs above.\n")
        return

    # Read candidate list from top_50_stocks.csv
    top_50_path = os.path.join(root_dir, "financial_engine", "top_50_stocks.csv")
    if not os.path.exists(top_50_path):
        sess["status"] = "error"
        _log(f"\n[Smart Portfolio] top_50_stocks.csv not found at {top_50_path}\n")
        return

    try:
        import pandas as pd
        top_50_df = pd.read_csv(top_50_path)
        sym_col = "Symbol" if "Symbol" in top_50_df.columns else "symbol"
        sharpe_col = "Sharpe Ratio" if "Sharpe Ratio" in top_50_df.columns else None
        candidates_raw = top_50_df[sym_col].dropna().tolist()
        sharpe_map: dict[str, float] = {}
        if sharpe_col:
            sharpe_map = dict(zip(top_50_df[sym_col], top_50_df[sharpe_col]))
    except Exception as exc:
        sess["status"] = "error"
        _log(f"\n[Smart Portfolio] Error reading top_50_stocks.csv: {exc}\n")
        return

    preview = ", ".join(candidates_raw[:10]) + ("…" if len(candidates_raw) > 10 else "")
    _log(f"\n[Smart Portfolio] {len(candidates_raw)} candidates: {preview}\n")

    # ── Phase 2: Deep AI analysis (one stock at a time for live updates) ─────
    sess["phase"] = "analyzing"
    _log(f"\n[Smart Portfolio] Phase 2: AI deep analysis on {len(candidates_raw)} candidates…\n")

    from deep_analysis.main import run_deep_analysis  # noqa: PLC0415
    from deep_analysis.sec_downloader import run_downloader  # noqa: PLC0415

    reports_dir = config.DEEP_ANALYSIS_DIR

    # Download SEC filings for ALL candidates upfront using a temp CSV.
    # run_deep_analysis internally calls run_downloader with the OLD portfolio
    # file, so without this step stocks not in that file get no filings.
    try:
        import tempfile, pandas as pd
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        pd.DataFrame({"Symbol": candidates_raw}).to_csv(tmp.name, index=False)
        tmp.close()
        _log(f"\n[Smart Portfolio] Downloading SEC filings for {len(candidates_raw)} candidates…\n")
        run_downloader(portfolio_path=tmp.name, output_dir=config.SEC_FILINGS_DIR, log_callback=_log)
        os.unlink(tmp.name)
    except Exception as exc:
        _log(f"\n[Smart Portfolio] SEC bulk download warning: {exc} — continuing.\n")

    for symbol in candidates_raw:
        _log(f"\n[Smart Portfolio] ── Analyzing {symbol} ──\n")
        try:
            results = run_deep_analysis(
                symbols=[symbol],
                reports_dir=reports_dir,
                log_callback=_log,
            )
        except Exception as exc:
            _log(f"[Smart Portfolio] Error analyzing {symbol}: {exc}\n")
            results = []

        # Extract verdict from the saved .md report
        md_path: str | None = None
        if results and results[0].get("md_path"):
            md_path = results[0]["md_path"]
        else:
            md_path = find_latest_report(symbol, reports_dir)

        verdict = extract_verdict(md_path) if md_path else "unknown"
        approved = is_buy_signal(verdict)

        sess["candidates"].append({
            "symbol": symbol,
            "sharpe": round(float(sharpe_map.get(symbol, 0)), 4),
            "verdict": verdict,
            "approved": approved,
        })
        status_label = "✓ APPROVED" if approved else "✗ REJECTED"
        _log(f"[Smart Portfolio] {symbol}: '{verdict}' → {status_label}\n")

    # ── Phase 3: Filter to buy signals ───────────────────────────────────────
    sess["phase"] = "optimizing"
    approved_list = [c for c in sess["candidates"] if c["approved"]]
    approved_symbols = [c["symbol"] for c in approved_list][:target_size]

    _log(
        f"\n[Smart Portfolio] Phase 3: {len(approved_list)} buy-signal stocks"
        f" → using top {len(approved_symbols)} for optimisation\n"
    )
    _log(f"Approved: {', '.join(approved_symbols)}\n")

    rejected_list = [c for c in sess["candidates"] if not c["approved"]]
    if rejected_list:
        _log(
            "Rejected: "
            + ", ".join(f"{c['symbol']}({c['verdict']})" for c in rejected_list)
            + "\n"
        )

    if not approved_symbols:
        sess["status"] = "error"
        _log(
            "\n[Smart Portfolio] No stocks passed the AI buy-signal filter. "
            "Try relaxing pipeline filters or running with different parameters.\n"
        )
        return

    # ── Phase 4: Re-optimise with approved stocks only ───────────────────────
    _log(
        f"\n[Smart Portfolio] Phase 4: Re-optimising with {len(approved_symbols)} approved stocks…\n"
    )

    try:
        from portfolio_optimizer.optimizer import load_data, optimize_portfolio  # noqa: PLC0415
        from financial_engine.risk_free_rate import get_risk_free_rate  # noqa: PLC0415

        top_50_file = os.path.join(root_dir, "financial_engine", "top_50_stocks.csv")
        rf_rate = get_risk_free_rate()
        _log(f"Risk-free rate: {rf_rate:.2%}\n")

        prices_df = load_data(top_50_file, config.DATA_DIR, symbols_override=approved_symbols)
        if prices_df.empty:
            sess["status"] = "error"
            _log("\n[Smart Portfolio] No price data available for approved symbols.\n")
            return

        portfolio_df = optimize_portfolio(prices_df, rf_rate)
        if portfolio_df is None:
            sess["status"] = "error"
            _log("\n[Smart Portfolio] Portfolio optimisation failed.\n")
            return

        # Persist optimal portfolio CSV (same location the normal pipeline uses)
        opt_path = os.path.join(root_dir, "portfolio_optimizer", "smart_optimal_portfolio.csv")
        portfolio_df.to_csv(opt_path, index=False)
        _log(f"\nSmart portfolio saved to {opt_path}\n")

        # Serialise numpy scalars so the dict is JSON-safe
        records = portfolio_df.to_dict(orient="records")
        for entry in records:
            for k, v in entry.items():
                if hasattr(v, "item"):
                    entry[k] = v.item()
        sess["portfolio"] = records

    except Exception as exc:
        sess["status"] = "error"
        _log(f"\n[Smart Portfolio] Optimisation error: {exc}\n")
        _log(traceback.format_exc())
        return

    # ── Done ─────────────────────────────────────────────────────────────────
    sess["phase"] = "completed"
    sess["status"] = "completed"
    _log(f"\n{'=' * 60}\n")
    _log(f"[Smart Portfolio] Done!  Final portfolio ({len(sess['portfolio'])} stocks):\n")
    for entry in sess["portfolio"]:
        w = entry.get("Weight", 0)
        _log(f"  {entry['Symbol']:8s}  {w:.1%}\n")
    _log(f"{'=' * 60}\n")
