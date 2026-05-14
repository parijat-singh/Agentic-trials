"""ETF Report - waterfall, top 10, portfolio table, yearly performance."""
import json
import os
import shutil
import sys
from datetime import datetime

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from etf_agent.etf_db import ETFDB
from financial_engine.sharpe_ranker import calculate_sharpe_ratio


def _yearly_metrics(df, year, risk_free=0.05):
    dfy = df[(df.index >= f"{year}-01-01") & (df.index <= f"{year}-12-31")]
    if dfy.empty or len(dfy) < 20:
        return None
    sharpe, ann_ret, ann_vol = calculate_sharpe_ratio(dfy, risk_free)
    return {"return": ann_ret, "volatility": ann_vol, "sharpe": sharpe} if sharpe is not None else None


def generate_etf_report(session_dir):
    os.makedirs(session_dir, exist_ok=True)
    db = ETFDB()
    lines = ["# ETF Analysis Report\n", f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]

    stats_path = os.path.join(session_dir, "etf_stats.json")
    if os.path.exists(stats_path):
        with open(stats_path) as f:
            data = json.load(f)
        wf = data.get("Waterfall", {})
        lines.append("## Selection Waterfall\n| Stage | Count |\n|:---|---:|\n")
        lines.append(f"| Scanned | {wf.get('Scanned', 'N/A')} |\n")
        lines.append(f"| Filter: Expense | -{wf.get('Expense', 0)} |\n")
        lines.append(f"| Filter: AUM | -{wf.get('AUM', 0)} |\n")
        lines.append(f"| Filter: History | -{wf.get('History', 0)} |\n")
        lines.append(f"| Filter: Exchange | -{wf.get('Exchange', 0)} |\n")
        lines.append(f"| **Passed** | **{wf.get('Passed', 0)}** |\n\n")

    top_path = os.path.join(session_dir, "etf_top_50.csv")
    if os.path.exists(top_path):
        top_df = pd.read_csv(top_path)
        top10 = top_df.head(10)
        lines.append("## Top 10 ETFs by Sharpe\n| Symbol | Sharpe | Return | Volatility |\n|:---|:---|:---|:---|\n")
        for _, r in top10.iterrows():
            lines.append(f"| {r['Symbol']} | {r['Sharpe Ratio']:.3f} | {r['Annualized Return']:.2%} | {r['Annualized Volatility']:.2%} |\n")
        lines.append("\n")

    opt_path = os.path.join(session_dir, "optimal_portfolio.csv")
    if os.path.exists(opt_path):
        opt_df = pd.read_csv(opt_path)
        lines.append("## Optimized Portfolio\n")
        rows = []
        for _, row in opt_df.iterrows():
            meta = db.get_etf_metadata(row["Symbol"])
            aum = (meta.get("aum") or 0) if meta else 0
            er = (meta.get("expense_ratio") or 0) if meta else 0
            rows.append({
                "Symbol": row["Symbol"],
                "Weight": row["Weight"],
                "Ret Stream": row.get("Return Contrib", 0),
                "Risk Alloc": row.get("Risk Contrib", 0),
                "Corr Vs Port": row.get("Correlation", 0),
                "AUM": aum,
                "Expense Ratio": er,
            })
        lines.append(pd.DataFrame(rows).to_string() + "\n\n")

    year_end = datetime.now().year
    perf_rows = []
    if os.path.exists(top_path):
        top_df = pd.read_csv(top_path)
        for sym in top_df["Symbol"].tolist()[:10]:
            hist = db.load_history(sym)
            if hist.empty or "Close" not in hist.columns:
                continue
            row = {"Symbol": sym}
            for y in range(3):
                ys = year_end - 3 + y
                m = _yearly_metrics(hist, ys)
                if m:
                    row[f"{ys}_Return"] = m["return"]
                    row[f"{ys}_Vol"] = m["volatility"]
                    row[f"{ys}_Sharpe"] = m["sharpe"]
            if len(row) > 1:
                perf_rows.append(row)
    if perf_rows:
        perf_df = pd.DataFrame(perf_rows)
        perf_df.to_csv(os.path.join(session_dir, "etf_yearly_performance.csv"), index=False)
        lines.append("## Yearly Performance (Last 3 Years)\n" + perf_df.to_string() + "\n")

    report_path = os.path.join(session_dir, "ETF_REPORT.md")
    with open(report_path, "w") as f:
        f.writelines(lines)

    # Archive — same pattern as stock reports
    os.makedirs(config.ETF_ARCHIVE_DIR, exist_ok=True)
    archive_name = f"ETF_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    archive_path = os.path.join(config.ETF_ARCHIVE_DIR, archive_name)
    shutil.copy(report_path, archive_path)
    print(f"Report archived to {archive_path}", flush=True)

    return report_path
