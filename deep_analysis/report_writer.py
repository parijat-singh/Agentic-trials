"""
Report Writer
=============
Saves per-stock AI analysis reports as both Markdown and styled HTML files.
Implements 60-day skip logic so reports are not regenerated unnecessarily.
"""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_REPORT_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
    line-height: 1.65;
    margin: 0;
    padding: 0;
}

/* ── Header ── */
.rpt-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #0c4a8f 100%);
    color: white;
    padding: 2.5rem 3rem 2rem;
}
.rpt-header .ticker {
    font-size: 2.8rem;
    font-weight: 800;
    letter-spacing: -1px;
}
.rpt-header .rpt-meta {
    font-size: 0.88rem;
    color: #94a3b8;
    margin-top: 0.25rem;
}
.verdict-pill {
    display: inline-block;
    padding: 0.35rem 1.1rem;
    border-radius: 999px;
    font-weight: 700;
    font-size: 1rem;
    margin-top: 0.9rem;
}
.verd-buy      { background: #dcfce7; color: #166534; }
.verd-cautious { background: #cffafe; color: #164e63; }
.verd-hold     { background: #fef9c3; color: #78350f; }
.verd-avoid    { background: #fee2e2; color: #991b1b; }

.metric-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.85rem;
    margin-top: 1.2rem;
}
.metric-chip {
    background: rgba(255,255,255,0.09);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 8px;
    padding: 0.5rem 0.9rem;
    min-width: 130px;
}
.mc-label {
    font-size: 0.66rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: #94a3b8;
}
.mc-value {
    font-size: 1.05rem;
    font-weight: 700;
    color: #fff;
    margin-top: 0.1rem;
}
.header-thesis {
    margin-top: 0.85rem;
    font-size: 0.87rem;
    color: #94a3b8;
    max-width: 860px;
}
.header-thesis strong { color: #e2e8f0; }

/* ── Layout ── */
.rpt-inner {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0;
}
.rpt-container {
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}

/* ── Section cards ── */
.section-card {
    background: white;
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.07), 0 2px 8px rgba(0,0,0,.04);
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
    border-top: 3px solid #94a3b8;
}
.section-card.s-verdict   { border-top-color: #3b82f6; }
.section-card.s-overview  { border-top-color: #06b6d4; }
.section-card.s-revenue   { border-top-color: #10b981; }
.section-card.s-profit    { border-top-color: #f59e0b; }
.section-card.s-cashflow  { border-top-color: #8b5cf6; }
.section-card.s-balance   { border-top-color: #0ea5e9; }
.section-card.s-dilution  { border-top-color: #6366f1; }
.section-card.s-mgmt      { border-top-color: #a78bfa; }
.section-card.s-compete   { border-top-color: #14b8a6; }
.section-card.s-risk      { border-top-color: #ef4444; }
.section-card.s-accounting{ border-top-color: #f97316; }
.section-card.s-valuation { border-top-color: #84cc16; }
.section-card.s-scenarios { border-top-color: #64748b; }
.section-card.s-redflags  { border-top-color: #ef4444; }
.section-card.s-swot      { border-top-color: #10b981; }
.section-card.s-catalysts { border-top-color: #3b82f6; }
.section-card.s-scorecard { border-top-color: #8b5cf6; }

/* Section headings */
.section-card h2 {
    font-size: 1.13rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.55rem;
}
.sec-num {
    background: #0f172a;
    color: white;
    border-radius: 50%;
    width: 1.7rem;
    height: 1.7rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.74rem;
    font-weight: 700;
    flex-shrink: 0;
}
h3 { font-size: 0.97rem; font-weight: 600; color: #334155; margin: 1.1rem 0 0.4rem; }
p  { margin: 0.5rem 0; }

/* ── Tables ── */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 0.75rem 0;
    font-size: 0.91rem;
    border-radius: 8px;
    overflow: hidden;
}
thead th {
    background: #0f172a;
    color: #e2e8f0;
    padding: 0.6rem 0.9rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.83rem;
    letter-spacing: 0.02em;
}
tbody tr:hover td { background: #eff6ff !important; transition: background 0.15s; }
td { padding: 0.52rem 0.9rem; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr:nth-child(even) td { background: #f8fafc; }

/* Score + severity classes applied by JS */
.sc-high { background: #dcfce7 !important; color: #166534 !important; font-weight: 700; text-align: center; }
.sc-mid  { background: #fef9c3 !important; color: #78350f !important; font-weight: 700; text-align: center; }
.sc-low  { background: #fee2e2 !important; color: #991b1b !important; font-weight: 700; text-align: center; }
.sev-h   { background: #fee2e2 !important; color: #991b1b !important; font-weight: 600; border-radius: 4px; }
.sev-m   { background: #ffedd5 !important; color: #9a3412 !important; font-weight: 600; border-radius: 4px; }
.sev-l   { background: #fef9c3 !important; color: #854d0e !important; font-weight: 600; border-radius: 4px; }
.tb-yes  { color: #991b1b !important; font-weight: 700; }
.tb-no   { color: #166534 !important; font-weight: 600; }

/* ── Chart ── */
.chart-wrap {
    position: relative;
    height: 340px;
    margin-top: 1.25rem;
    margin-bottom: 0.5rem;
}

/* ── Final Decision card ── */
.decision-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
    color: white;
    border-radius: 12px;
    padding: 2rem 2rem 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 16px rgba(15,23,42,0.25);
}
.decision-card h2 {
    color: white;
    font-size: 1.13rem;
    font-weight: 700;
    margin: 0 0 1rem;
    display: flex;
    align-items: center;
    gap: 0.55rem;
}
.decision-card .sec-num { background: rgba(255,255,255,0.15); }
.decision-card p  { color: #cbd5e1; margin: 0.4rem 0; }
.decision-card strong { color: white; }
.decision-card ul { color: #cbd5e1; }
.decision-meta {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
    gap: 0.75rem;
    margin-top: 1.1rem;
}
.dm-chip {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 0.55rem 0.9rem;
}
.dm-label { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.07em; color: #64748b; }
.dm-val   { font-size: 0.95rem; font-weight: 600; color: #e2e8f0; margin-top: 0.15rem; }

/* ── Lists ── */
ul, ol { padding-left: 1.4rem; }
li { margin: 0.28rem 0; }

/* ── Inline code ── */
code {
    background: #f1f5f9;
    border-radius: 4px;
    padding: 0.1em 0.4em;
    font-family: 'Courier New', monospace;
    font-size: 0.87em;
    color: #be123c;
}
pre code { display: block; padding: 0.75rem 1rem; overflow-x: auto; }

/* ── Responsive ── */
@media (max-width: 640px) {
    .rpt-header { padding: 1.5rem; }
    .rpt-header .ticker { font-size: 2.1rem; }
    .rpt-container { padding: 1rem 0.75rem; }
    .section-card { padding: 1.2rem 1rem; }
    .decision-card { padding: 1.25rem 1rem; }
}
"""

# ---------------------------------------------------------------------------
# Section-number → CSS class map
# ---------------------------------------------------------------------------

_SEC_CLASS = {
    1:  "s-verdict",
    2:  "s-overview",
    3:  "s-revenue",
    4:  "s-profit",
    5:  "s-cashflow",
    6:  "s-balance",
    7:  "s-dilution",
    8:  "s-mgmt",
    9:  "s-compete",
    10: "s-risk",
    11: "s-accounting",
    12: "s-valuation",
    13: "s-scenarios",
    14: "s-redflags",
    15: "s-swot",
    16: "s-catalysts",
    17: "s-scorecard",
}

_VERDICT_MAP = [
    ("strong buy",  "verd-buy"),
    ("cautious buy","verd-cautious"),
    ("buy",         "verd-buy"),
    ("watchlist",   "verd-hold"),
    ("hold",        "verd-hold"),
    ("high risk",   "verd-avoid"),
    ("sell",        "verd-avoid"),
    ("avoid",       "verd-avoid"),
]


def _verdict_class(verdict: str) -> str:
    v = verdict.lower()
    for key, cls in _VERDICT_MAP:
        if key in v:
            return cls
    return "verd-hold"


def _find_field(content: str, *keys: str) -> str:
    """Extract a bold-label field value from markdown content."""
    for key in keys:
        pat = r'\*\*' + re.escape(key) + r'[:\*\s]*\*\*[:\s]*(.+?)(?:\n|$)'
        m = re.search(pat, content, re.IGNORECASE)
        if m:
            return m.group(1).strip().strip('*').strip()
        # Also handle "**Key:** value" (colon inside bold)
        pat2 = r'\*\*' + re.escape(key) + r'[:\s]+(.+?)(?:\*\*|  |\n|$)'
        m = re.search(pat2, content, re.IGNORECASE)
        if m:
            return m.group(1).strip().strip('*').strip()
    return ""


def _inline_md(text: str) -> str:
    """Apply inline markdown (bold, italic, code) to a single text string."""
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*',     r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*\n]+?)\*',    r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+?)`',        r'<code>\1</code>', text)
    return text


def _simple_md_to_html(md: str) -> str:
    """
    Minimal markdown → HTML converter used as fallback when the 'markdown'
    package is unavailable.  Handles: headings, bold/italic, bullet lists,
    pipe tables, and hard line-breaks.
    """
    lines = md.split('\n')
    out: list[str] = []
    para: list[str] = []
    in_list  = False
    in_table = False
    tbl_rows: list[str] = []

    def flush_para():
        nonlocal para
        if para:
            out.append('<p>' + ' '.join(_inline_md(l.rstrip('  ')) for l in para) + '</p>')
            para = []

    def flush_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>')
            in_list = False

    def flush_table():
        nonlocal tbl_rows, in_table
        if not tbl_rows:
            return
        rows = [r for r in tbl_rows if not re.match(r'^\|[-\s|:]+\|$', r.strip())]
        if not rows:
            tbl_rows = []; in_table = False; return
        html = ['<table><thead><tr>']
        for cell in [c.strip() for c in rows[0].split('|') if c.strip()]:
            html.append(f'<th>{_inline_md(cell)}</th>')
        html.append('</tr></thead><tbody>')
        for row in rows[1:]:
            cols = [c.strip() for c in row.split('|') if c.strip()]
            if not cols: continue
            html.append('<tr>' + ''.join(f'<td>{_inline_md(c)}</td>' for c in cols) + '</tr>')
        html.append('</tbody></table>')
        out.append(''.join(html))
        tbl_rows = []; in_table = False

    for i, raw in enumerate(lines):
        stripped = raw.strip()

        # Table row detection
        if stripped.startswith('|') and stripped.endswith('|'):
            flush_para(); flush_list()
            in_table = True
            tbl_rows.append(stripped)
            continue
        elif in_table:
            flush_table()

        # Heading
        hm = re.match(r'^(#{1,4})\s+(.+)$', stripped)
        if hm:
            flush_para(); flush_list()
            n = len(hm.group(1))
            out.append(f'<h{n}>{_inline_md(hm.group(2))}</h{n}>')
            continue

        # Bullet list
        bm = re.match(r'^[-*•]\s+(.+)$', stripped)
        if bm:
            flush_para()
            if not in_list:
                out.append('<ul>'); in_list = True
            out.append(f'<li>{_inline_md(bm.group(1))}</li>')
            continue

        # Blank line
        if not stripped:
            flush_para(); flush_list()
            continue

        # Regular text — accumulate for paragraph
        flush_list()
        if raw.endswith('  ') or raw.endswith('  \r'):
            # Hard line-break
            para.append(stripped)
            flush_para()
            out.append('<br>')
        else:
            para.append(stripped)

    flush_para(); flush_list(); flush_table()
    return '\n'.join(out)


def _md_fragment(md: str) -> str:
    """Convert a markdown string to an HTML fragment."""
    try:
        import markdown as md_lib
        return md_lib.markdown(md, extensions=["tables", "fenced_code"])
    except Exception:
        return _simple_md_to_html(md)


def _parse_sections(md_text: str) -> list[tuple[int, str, str]]:
    """Split markdown into (section_num, title, content) tuples."""
    pattern = re.compile(r'^##\s+(\d+)\.\s+(.+?)$', re.MULTILINE)
    matches = list(pattern.finditer(md_text))
    if not matches:
        return []
    sections = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        title = m.group(2).strip()
        content_start = m.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        content = md_text[content_start:content_end].strip()
        sections.append((num, title, content))
    return sections


def _extract_scorecard(content: str) -> dict[str, int]:
    """Parse the scorecard markdown table into {category: score} dict."""
    scores: dict[str, int] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or '|' not in line:
            continue
        if re.match(r'^\|[-\s|]+\|$', line):
            continue
        cols = [c.strip().strip('*') for c in line.split('|') if c.strip()]
        if len(cols) < 2:
            continue
        label = cols[0]
        raw_score = cols[-1]
        if label.lower() in ('category', 'overall score', 'total', ''):
            continue
        m = re.search(r'(\d+)', raw_score)
        if m:
            scores[label] = int(m.group(1))
    return scores


def _extract_decision_meta(content: str) -> dict[str, str]:
    """Extract structured fields from section 18 for the meta chips."""
    fields = {
        "Recommendation": ("Recommendation", "Final Recommendation"),
        "Position Sizing": ("Position Sizing", "Position Size"),
        "Time Horizon": ("Time Horizon",),
        "Entry Price": ("Ideal Entry Price", "Entry Price", "Valuation Range"),
    }
    result = {}
    for display_key, search_keys in fields.items():
        val = _find_field(content, *search_keys)
        if val:
            result[display_key] = val[:80]
    return result


def _build_section_card(num: int, title: str, content: str, scores_json: str) -> str:
    inner = _md_fragment(content)
    card_cls = _SEC_CLASS.get(num, "s-default")

    chart_block = ""
    if num == 17:
        chart_block = f"""
        <div class="chart-wrap"><canvas id="scoreChart"></canvas></div>
        <script>
        (function() {{
          var scores = {scores_json};
          var labels = Object.keys(scores);
          var values = Object.values(scores);
          var bg = values.map(function(v) {{
            return v >= 8 ? '#16a34a' : v >= 5 ? '#d97706' : '#dc2626';
          }});
          var ctx = document.getElementById('scoreChart').getContext('2d');
          new Chart(ctx, {{
            type: 'bar',
            data: {{
              labels: labels,
              datasets: [{{
                label: 'Score / 10',
                data: values,
                backgroundColor: bg,
                borderRadius: 6,
                borderSkipped: false,
              }}]
            }},
            options: {{
              indexAxis: 'y',
              responsive: true,
              maintainAspectRatio: false,
              scales: {{
                x: {{
                  min: 0, max: 10,
                  ticks: {{ stepSize: 1, font: {{ size: 11 }} }},
                  grid: {{ color: '#f1f5f9' }}
                }},
                y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 12 }} }} }}
              }},
              plugins: {{
                legend: {{ display: false }},
                tooltip: {{
                  callbacks: {{
                    label: function(ctx) {{ return '  Score: ' + ctx.raw + ' / 10'; }}
                  }}
                }}
              }}
            }}
          }});
        }})();
        </script>"""

    return (
        f'<div class="section-card {card_cls}">'
        f'<h2><span class="sec-num">{num}</span>{title}</h2>'
        f'{inner}'
        f'{chart_block}'
        f'</div>'
    )


def _build_decision_card(num: int, title: str, content: str) -> str:
    meta = _extract_decision_meta(content)
    inner = _md_fragment(content)
    chips = ""
    if meta:
        chip_html = "".join(
            f'<div class="dm-chip"><div class="dm-label">{k}</div><div class="dm-val">{v}</div></div>'
            for k, v in meta.items()
        )
        chips = f'<div class="decision-meta">{chip_html}</div>'
    return (
        f'<div class="decision-card">'
        f'<h2><span class="sec-num">{num}</span>{title}</h2>'
        f'{inner}'
        f'{chips}'
        f'</div>'
    )


def _build_report_html(symbol: str, report_date: str, md_text: str) -> str:
    """Convert the full markdown analysis into a polished HTML page."""
    sections = _parse_sections(md_text)

    # ── Extract header metadata from section 1 ──────────────────────────────
    verdict_text = "N/A"
    price = market_cap = ev = "—"
    thesis = main_risk = ""

    for num, _title, content in sections:
        if num == 1:
            verdict_text = (
                _find_field(content, "Recommendation", "Verdict", "Investment Verdict")
                or verdict_text
            )
            raw_price = _find_field(content, "Current Price")
            if raw_price:
                price = ("$" if not raw_price.startswith("$") else "") + raw_price

            raw_mc = _find_field(content, "Market Cap")
            if raw_mc:
                market_cap = ("$" if not raw_mc.startswith("$") else "") + raw_mc

            raw_ev = _find_field(content, "Enterprise Value")
            if raw_ev:
                ev = ("$" if not raw_ev.startswith("$") else "") + raw_ev

            thesis = _find_field(content, "Thesis", "One-sentence thesis")
            main_risk = _find_field(content, "Main Risk", "One-sentence main risk", "Main Risk")
            break

    # ── Extract scorecard for chart ─────────────────────────────────────────
    scores: dict[str, int] = {}
    for num, _title, content in sections:
        if num == 17:
            scores = _extract_scorecard(content)
            break
    scores_json = json.dumps(scores)

    # ── Build header ────────────────────────────────────────────────────────
    vpill = _verdict_class(verdict_text)
    thesis_html = (
        f'<div class="header-thesis"><strong>Thesis:</strong> {thesis}</div>'
        if thesis else ""
    )
    risk_html = (
        f'<div class="header-thesis" style="margin-top:.3rem;"><strong>Main Risk:</strong> {main_risk}</div>'
        if main_risk else ""
    )
    header = f"""
<div class="rpt-header">
  <div style="max-width:1100px;margin:0 auto;">
    <div class="ticker">{symbol.upper()}</div>
    <div class="rpt-meta">Deep Portfolio Analysis &nbsp;·&nbsp; {report_date}</div>
    <div class="verdict-pill {vpill}">{verdict_text}</div>
    <div class="metric-row">
      <div class="metric-chip"><div class="mc-label">Price</div><div class="mc-value">{price}</div></div>
      <div class="metric-chip"><div class="mc-label">Market Cap</div><div class="mc-value">{market_cap}</div></div>
      <div class="metric-chip"><div class="mc-label">Enterprise Value</div><div class="mc-value">{ev}</div></div>
    </div>
    {thesis_html}
    {risk_html}
  </div>
</div>"""

    # ── Build section cards ─────────────────────────────────────────────────
    if sections:
        cards = []
        for num, title, content in sections:
            if num == 18:
                cards.append(_build_decision_card(num, title, content))
            else:
                cards.append(_build_section_card(num, title, content, scores_json))
        body_html = "\n".join(cards)
    else:
        body_html = f'<div class="section-card">{_md_fragment(md_text)}</div>'

    # ── Post-processing JS ──────────────────────────────────────────────────
    post_js = """
<script>
document.addEventListener('DOMContentLoaded', function() {
  // Color severity cells (Red Flags table)
  document.querySelectorAll('td').forEach(function(td) {
    var t = td.textContent.trim().toLowerCase();
    if (t === 'high')   { td.classList.add('sev-h'); }
    else if (t === 'medium') { td.classList.add('sev-m'); }
    else if (t === 'low')    { td.classList.add('sev-l'); }
    else if (t === 'yes')    { td.classList.add('tb-yes'); }
    else if (t === 'no')     { td.classList.add('tb-no'); }
  });

  // Color numeric score cells (Scorecard table — integers 1-10 only)
  document.querySelectorAll('td').forEach(function(td) {
    var t = td.textContent.trim();
    if (/^\\d+$/.test(t)) {
      var n = parseInt(t, 10);
      if (n >= 1 && n <= 10) {
        if (n >= 8) td.classList.add('sc-high');
        else if (n >= 5) td.classList.add('sc-mid');
        else td.classList.add('sc-low');
      }
    }
  });
});
</script>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{symbol.upper()} — Deep Portfolio Analysis</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
{_REPORT_CSS}
</style>
</head>
<body>
{header}
<div class="rpt-container">
{body_html}
</div>
{post_js}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API (unchanged signatures)
# ---------------------------------------------------------------------------

def report_exists(symbol: str, output_dir: str, max_age_days: int = 60) -> str | None:
    """Return the filename of the most recent fresh report for *symbol*, or None."""
    pattern = os.path.join(output_dir, f"{symbol.upper()}_deep_analysis_*.md")
    matches = sorted(glob.glob(pattern), reverse=True)
    cutoff  = date.today() - timedelta(days=max_age_days)

    for path in matches:
        basename = os.path.basename(path)
        parts    = basename.replace(".md", "").split("_")
        date_str = parts[-1]
        try:
            report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if report_date >= cutoff:
                return basename
        except ValueError:
            continue
    return None


def save_report(symbol: str, analysis_md: str, output_dir: str) -> tuple[str, str]:
    """Save *analysis_md* as both a .md and styled .html file. Returns (md_path, html_path)."""
    os.makedirs(output_dir, exist_ok=True)

    today     = date.today().strftime("%Y-%m-%d")
    stem      = f"{symbol.upper()}_deep_analysis_{today}"
    md_path   = os.path.join(output_dir, f"{stem}.md")
    html_path = os.path.join(output_dir, f"{stem}.html")

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(analysis_md)

    html_full = _build_report_html(symbol.upper(), today, analysis_md)
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html_full)

    return md_path, html_path


def regenerate_html_reports(output_dir: str) -> int:
    """Re-render all existing .md reports to HTML with the new template. Returns count."""
    pattern = os.path.join(output_dir, "*_deep_analysis_*.md")
    md_files = glob.glob(pattern)
    count = 0
    for md_path in md_files:
        basename = os.path.basename(md_path)
        parts    = basename.replace(".md", "").split("_")
        # parts: SYMBOL _deep_analysis_ YYYY-MM-DD → symbol is first part(s)
        date_str = parts[-1]
        symbol   = parts[0]
        try:
            with open(md_path, encoding="utf-8") as fh:
                md_text = fh.read()
            html_path = md_path.replace(".md", ".html")
            html_full = _build_report_html(symbol, date_str, md_text)
            with open(html_path, "w", encoding="utf-8") as fh:
                fh.write(html_full)
            count += 1
        except Exception as e:
            print(f"  WARNING: Could not regenerate {basename}: {e}")
    return count
