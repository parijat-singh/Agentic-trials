"""MF Report - waterfall, top 10, optimized portfolio, yearly performance."""
import json
import os
import shutil
import sys
from datetime import datetime

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from mf_agent.mf_db import MFDB
from financial_engine.sharpe_ranker import calculate_sharpe_ratio


def _yearly_metrics(df, year, risk_free=0.05):
    dfy = df[(df.index >= f"{year}-01-01") & (df.index <= f"{year}-12-31")]
    if dfy.empty or len(dfy) < 20:
        return None
    sharpe, ann_ret, ann_vol = calculate_sharpe_ratio(dfy, risk_free)
    return {"return": ann_ret, "volatility": ann_vol, "sharpe": sharpe} if sharpe is not None else None


def _fmt_aum(aum):
    if aum is None:
        return "N/A"
    b = aum / 1e9
    if b >= 1:
        return f"${b:.1f}B"
    m = aum / 1e6
    return f"${m:.0f}M"


def _fmt_er(er):
    if er is None:
        return "N/A"
    return f"{float(er)*100:.2f}%"


def generate_mf_report(session_dir):
    os.makedirs(session_dir, exist_ok=True)
    db = MFDB()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# Mutual Fund Analysis Report\n", f"Generated: {now_str}\n\n"]

    # --- Waterfall ---
    stats_path = os.path.join(session_dir, "mf_stats.json")
    if os.path.exists(stats_path):
        with open(stats_path) as f:
            data = json.load(f)
        wf = data.get("Waterfall", {})
        params = data.get("Parameters", {})
        lines.append("## Filter Parameters\n")
        lines.append(f"- Max Expense Ratio: {_fmt_er(params.get('max_expense_ratio'))}\n")
        aum = params.get("min_aum")
        lines.append(f"- Min AUM: {_fmt_aum(aum)}\n")
        lines.append(f"- Min History: {params.get('min_history_years', 'N/A')} years\n")
        cats = params.get("categories")
        lines.append(f"- Categories: {', '.join(cats) if cats else 'All'}\n\n")

        lines.append("## Selection Waterfall\n| Stage | Count |\n|:---|---:|\n")
        lines.append(f"| Scanned | {wf.get('Scanned', 'N/A')} |\n")
        lines.append(f"| Filter: Expense Ratio | -{wf.get('Expense', 0)} |\n")
        lines.append(f"| Filter: AUM | -{wf.get('AUM', 0)} |\n")
        lines.append(f"| Filter: History | -{wf.get('History', 0)} |\n")
        lines.append(f"| Filter: Category | -{wf.get('Category', 0)} |\n")
        lines.append(f"| **Passed** | **{wf.get('Passed', 0)}** |\n\n")

    # --- Top 10 by Sharpe ---
    top_path = os.path.join(session_dir, "mf_top_50.csv")
    if os.path.exists(top_path):
        top_df = pd.read_csv(top_path)
        top10 = top_df.head(10)
        lines.append(
            "## Top 10 Mutual Funds by Sharpe Ratio\n"
            "| Symbol | Name | Category | Sharpe | Return | Vol | Exp. Ratio | AUM |\n"
            "|:---|:---|:---|---:|---:|---:|---:|---:|\n"
        )
        for _, r in top10.iterrows():
            er = _fmt_er(r.get("ExpenseRatio"))
            aum = _fmt_aum(r.get("AUM"))
            name = str(r.get("Name", r["Symbol"]))[:35]
            cat = str(r.get("Category", ""))[:20]
            lines.append(
                f"| {r['Symbol']} | {name} | {cat} "
                f"| {r['Sharpe Ratio']:.3f} | {r['Annualized Return']:.2%} "
                f"| {r['Annualized Volatility']:.2%} | {er} | {aum} |\n"
            )
        lines.append("\n")

    # --- Optimized Portfolio ---
    opt_path = os.path.join(session_dir, "optimal_portfolio.csv")
    if os.path.exists(opt_path):
        opt_df = pd.read_csv(opt_path)
        all_meta = db.get_all_metadata()
        lines.append(
            "## Optimized Portfolio (Max Sharpe)\n"
            "| Symbol | Name | Weight | Ret Contrib | Risk Contrib | Exp. Ratio | AUM |\n"
            "|:---|:---|---:|---:|---:|---:|---:|\n"
        )
        for _, row in opt_df.iterrows():
            sym = row["Symbol"]
            meta = all_meta.get(sym, {})
            name = str(meta.get("name") or sym)[:35]
            er = _fmt_er(meta.get("expense_ratio"))
            aum = _fmt_aum(meta.get("aum"))
            lines.append(
                f"| {sym} | {name} | {row['Weight']:.1%} "
                f"| {row.get('Return Contrib', 0):.2%} "
                f"| {row.get('Risk Contrib', 0):.2%} "
                f"| {er} | {aum} |\n"
            )
        # Summary stats
        if "Weight" in opt_df.columns:
            top_sym = opt_df.iloc[0]["Symbol"]
            meta0 = all_meta.get(top_sym, {})
            lines.append(f"\n**Largest holding:** {top_sym} ({opt_df.iloc[0]['Weight']:.1%})")
            # Weighted expense ratio
            wer_parts = []
            for _, row in opt_df.iterrows():
                m = all_meta.get(row["Symbol"], {})
                er_val = m.get("expense_ratio")
                if er_val is not None:
                    try:
                        wer_parts.append(float(er_val) * float(row["Weight"]))
                    except Exception:
                        pass
            if wer_parts:
                wer = sum(wer_parts)
                lines.append(f"  |  **Weighted expense ratio:** {wer*100:.3f}%\n\n")
            else:
                lines.append("\n\n")

    # --- Yearly Performance ---
    year_end = datetime.now().year
    perf_rows = []
    if os.path.exists(top_path):
        top_df = pd.read_csv(top_path)
        top10_syms = top_df["Symbol"].tolist()[:10]
        # Single bulk DB query instead of N individual load_history calls
        histories = db.load_history_bulk(top10_syms)
        for sym in top10_syms:
            hist = histories.get(sym, pd.DataFrame())
            if hist.empty or "Close" not in hist.columns:
                continue
            row = {"Symbol": sym}
            for offset in range(3):
                yr = year_end - 3 + offset
                m = _yearly_metrics(hist, yr)
                if m:
                    row[f"{yr} Return"] = f"{m['return']:.2%}"
                    row[f"{yr} Sharpe"] = f"{m['sharpe']:.2f}"
            if len(row) > 1:
                perf_rows.append(row)

    if perf_rows:
        perf_df = pd.DataFrame(perf_rows).set_index("Symbol")
        perf_path = os.path.join(session_dir, "mf_yearly_performance.csv")
        perf_df.to_csv(perf_path)
        lines.append("## Yearly Performance (Last 3 Years)\n\n")
        try:
            lines.append(perf_df.to_markdown() + "\n\n")
        except ImportError:
            # tabulate not installed — fall back to plain text
            lines.append(perf_df.to_string() + "\n\n")

    report_path = os.path.join(session_dir, "MF_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Archive — same pattern as stock and ETF reports
    os.makedirs(config.MF_ARCHIVE_DIR, exist_ok=True)
    archive_name = f"MF_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    archive_path = os.path.join(config.MF_ARCHIVE_DIR, archive_name)
    shutil.copy(report_path, archive_path)
    print(f"Report archived to {archive_path}", flush=True)

    return report_path
