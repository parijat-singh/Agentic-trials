"""
SEC EDGAR Filings Downloader
============================
Downloads the most recent annual and quarterly report for each stock in the
optimized portfolio and saves them to SEC_FILINGS_DIR.

Annual  (in priority order): 10-K  →  20-F  →  40-F
Quarterly (in priority order): 10-Q  →  6-K

Filename format : {SYMBOL}_{FORM}_{YYYY-MM-DD}.htm
                  e.g. VIST_20-F_2026-04-28.htm
                       HWM_10-K_2025-02-06.htm

Skip logic      : if ANY file matching {SYMBOL}_10-K_*  OR  {SYMBOL}_20-F_*
                  (etc.) already exists for that report category, skip it.
                  Re-running is safe as the portfolio evolves.

SEC EDGAR APIs used (public, no auth required):
  • https://www.sec.gov/files/company_tickers.json   – ticker → CIK mapping
  • https://data.sec.gov/submissions/CIK{cik10}.json – filing history per CIK
  • https://www.sec.gov/Archives/edgar/data/…        – actual filing document

SEC rate-limit guidance: ≤ 10 req/s, identify yourself in User-Agent.
"""

import glob
import os
import sys
import time

import requests
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Allow running as a standalone script or imported from api_server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EDGAR_HEADERS = {
    # SEC requires a descriptive User-Agent with contact info.
    "User-Agent": "Agentic-trials mailparijat@gmail.com",
    "Accept-Encoding": "gzip, deflate",
    "Accept": "application/json, text/html, */*",
}

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
ARCHIVE_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"
)

# Form categories: try each list in order; use the first match found.
# 10-K  = US domestic annual report
# 20-F  = foreign private issuer annual report
# 40-F  = Canadian issuer annual report
# 10-Q  = US domestic quarterly report
# 6-K   = foreign private issuer interim / current report
ANNUAL_FORMS    = ["10-K", "20-F", "40-F"]
QUARTERLY_FORMS = ["10-Q", "6-K"]

# All form variants per category (used for skip-detection glob patterns)
ALL_ANNUAL_FORMS    = ["10-K", "20-F", "40-F"]
ALL_QUARTERLY_FORMS = ["10-Q", "6-K"]

# Human-readable category labels (used in log messages)
CATEGORY_LABEL = {
    "10-K": "Annual",  "20-F": "Annual",  "40-F": "Annual",
    "10-Q": "Quarterly", "6-K": "Quarterly",
}

# Request timeouts
CONNECT_TIMEOUT = 15   # seconds
READ_TIMEOUT    = 120  # seconds (filings can be large)

# Polite pause between SEC requests (stay well under 10 req/s)
REQUEST_DELAY = 0.4    # seconds


# ---------------------------------------------------------------------------
# EDGAR helpers
# ---------------------------------------------------------------------------

def _get(url: str, **kwargs) -> requests.Response:
    """GET with retry on transient errors (429, 503)."""
    for attempt in range(3):
        r = requests.get(
            url,
            headers=EDGAR_HEADERS,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            verify=False,  # Windows intermediate-CA issue (same as rest of codebase)
            **kwargs,
        )
        if r.status_code in (429, 503):
            wait = 10 * (attempt + 1)
            print(f"  [SEC] Rate-limited ({r.status_code}), waiting {wait}s...", flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r  # unreachable, satisfies linters


def fetch_ticker_cik_map() -> dict:
    """Return {TICKER: cik_str} for all SEC-registered companies."""
    print("Fetching SEC company ticker->CIK map...", flush=True)
    r = _get(COMPANY_TICKERS_URL)
    data = r.json()
    # SEC format: {"0": {"cik_str": "789019", "ticker": "MSFT", "title": "..."}, …}
    return {v["ticker"].upper(): str(v["cik_str"]) for v in data.values()}


def fetch_submissions(cik_str: str) -> dict:
    """Return the submissions JSON for a company CIK."""
    cik10 = cik_str.zfill(10)
    url = SUBMISSIONS_URL.format(cik10=cik10)
    r = _get(url)
    return r.json()


def find_latest_filing(submissions: dict, form_types: list) -> dict | None:
    """
    Scan submissions['filings']['recent'] for the most recent filing whose
    form matches ANY entry in *form_types*.  Returns a dict with keys
    {date, accession, primary_doc, form} or None if not found.

    form_types is checked in order — the first match (earliest in the list)
    wins, which lets us prefer 10-K over 20-F when both exist.
    """
    recent   = submissions.get("filings", {}).get("recent", {})
    forms    = recent.get("form", [])
    dates    = recent.get("filingDate", [])
    accnos   = recent.get("accessionNumber", [])
    pri_docs = recent.get("primaryDocument", [])

    # Build per-form-type index of the most recent filing
    best: dict[str, dict] = {}
    for i, form in enumerate(forms):
        if form in form_types and form not in best:
            best[form] = {
                "date":        dates[i],
                "accession":   accnos[i],
                "primary_doc": pri_docs[i],
                "form":        form,
            }

    # Return the highest-priority form type found
    for ft in form_types:
        if ft in best:
            return best[ft]
    return None


def download_filing(cik_str: str, filing: dict, dest_path: str) -> str:
    """Download the primary document of a filing.  Returns the source URL."""
    accession_nodash = filing["accession"].replace("-", "")
    doc              = filing["primary_doc"]
    url = ARCHIVE_URL.format(
        cik=cik_str,
        accession_nodash=accession_nodash,
        doc=doc,
    )
    r = _get(url)
    with open(dest_path, "wb") as fh:
        fh.write(r.content)
    return url


# ---------------------------------------------------------------------------
# Skip-detection helpers
# ---------------------------------------------------------------------------

def _any_existing(output_dir: str, symbol: str, form_variants: list) -> str | None:
    """
    Return the basename of the first existing file that matches any variant
    of the given form category, or None if none found.
    e.g. checks VIST_10-K_*, VIST_20-F_*, VIST_40-F_* for ANNUAL_FORMS.
    """
    for fv in form_variants:
        hits = glob.glob(os.path.join(output_dir, f"{symbol}_{fv}_*"))
        if hits:
            return os.path.basename(hits[0])
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_downloader(
    portfolio_path: str | None = None,
    output_dir: str | None = None,
    log_callback=None,
) -> list[dict]:
    """
    Download annual (10-K / 20-F / 40-F) and quarterly (10-Q / 6-K) filings
    for every stock in the optimized portfolio.

    Args:
        portfolio_path: Path to optimal_portfolio.csv.  Defaults to
                        portfolio_optimizer/optimal_portfolio.csv relative to
                        the package root.
        output_dir:     Folder to save filings.  Defaults to config.SEC_FILINGS_DIR.
        log_callback:   Optional callable(str) for streaming log lines to a
                        caller (e.g. API background thread).

    Returns:
        List of result dicts — one entry per symbol+category:
            symbol, form, category, date, file, size_kb   – on success
            symbol, form, category, file, skipped=True     – already exists
            symbol, category, error                        – failure / not found
    """
    def _log(msg: str):
        print(msg, flush=True)
        if log_callback:
            log_callback(msg + "\n")

    # ── Resolve paths ────────────────────────────────────────────────────────
    if portfolio_path is None:
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        portfolio_path = os.path.join(_root, "portfolio_optimizer", "optimal_portfolio.csv")

    if output_dir is None:
        output_dir = config.SEC_FILINGS_DIR

    os.makedirs(output_dir, exist_ok=True)

    # ── Load portfolio ───────────────────────────────────────────────────────
    if not os.path.exists(portfolio_path):
        _log(f"ERROR: Portfolio file not found: {portfolio_path}")
        _log("Run the stock analysis pipeline first to generate the optimized portfolio.")
        return [{"error": f"Portfolio file not found: {portfolio_path}"}]

    df = pd.read_csv(portfolio_path)
    if "Symbol" not in df.columns:
        _log(f"ERROR: 'Symbol' column missing in {portfolio_path}")
        return [{"error": "Missing 'Symbol' column in portfolio CSV"}]

    symbols = df["Symbol"].str.upper().dropna().unique().tolist()
    _log(f"Optimized portfolio - {len(symbols)} stock(s): {', '.join(symbols)}")
    _log(f"Output folder: {output_dir}\n")
    _log("Annual  reports : will try 10-K -> 20-F -> 40-F (whichever is filed)")
    _log("Quarterly reports: will try 10-Q -> 6-K  (whichever is filed)\n")

    # ── Fetch ticker→CIK map (one request) ───────────────────────────────────
    try:
        ticker_cik = fetch_ticker_cik_map()
        time.sleep(REQUEST_DELAY)
    except Exception as exc:
        _log(f"ERROR fetching SEC ticker map: {exc}")
        return [{"error": f"Failed to fetch SEC ticker map: {exc}"}]

    # ── Process each symbol ──────────────────────────────────────────────────
    results: list[dict] = []

    CATEGORIES = [
        ("Annual",    ANNUAL_FORMS,    ALL_ANNUAL_FORMS),
        ("Quarterly", QUARTERLY_FORMS, ALL_QUARTERLY_FORMS),
    ]

    for symbol in symbols:
        _log(f"--- {symbol} ---")

        cik_str = ticker_cik.get(symbol)
        if not cik_str:
            _log(f"  WARNING: {symbol} not found in SEC EDGAR - skipping")
            results.append({"symbol": symbol, "error": "Ticker not in SEC EDGAR database"})
            continue

        # Fetch filing submissions for this company
        try:
            submissions = fetch_submissions(cik_str)
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            _log(f"  ERROR fetching submissions (CIK {cik_str}): {exc}")
            results.append({"symbol": symbol, "error": str(exc)})
            continue

        for category, form_priority, all_variants in CATEGORIES:
            # ── Skip-if-exists: check ALL variants for this category ──────────
            existing_name = _any_existing(output_dir, symbol, all_variants)
            if existing_name:
                _log(f"  {category}: already have {existing_name} - skipping")
                results.append({
                    "symbol":   symbol,
                    "category": category,
                    "form":     existing_name.split("_")[1] if "_" in existing_name else "",
                    "file":     existing_name,
                    "skipped":  True,
                })
                continue

            # ── Find latest filing (tries each form type in priority order) ──
            filing = find_latest_filing(submissions, form_priority)
            if not filing:
                tried = " / ".join(form_priority)
                _log(f"  {category}: no filing found ({tried}) in SEC EDGAR - skipping")
                results.append({
                    "symbol":   symbol,
                    "category": category,
                    "error":    f"No {category.lower()} filing found ({tried})",
                })
                continue

            # ── Build destination path ───────────────────────────────────────
            actual_form = filing["form"]   # e.g. "20-F", "6-K", "10-K"
            date_str    = filing["date"]   # e.g. "2024-11-14"
            pri_doc     = filing["primary_doc"]
            ext = os.path.splitext(pri_doc)[1] or ".htm"
            filename  = f"{symbol}_{actual_form}_{date_str}{ext}"
            dest_path = os.path.join(output_dir, filename)

            # ── Download ─────────────────────────────────────────────────────
            try:
                source_url = download_filing(cik_str, filing, dest_path)
                size_kb    = os.path.getsize(dest_path) // 1024
                _log(f"  {category} ({actual_form}): saved {filename} ({size_kb:,} KB)")
                _log(f"           source: {source_url}")
                results.append({
                    "symbol":   symbol,
                    "category": category,
                    "form":     actual_form,
                    "date":     date_str,
                    "file":     filename,
                    "size_kb":  size_kb,
                })
                time.sleep(REQUEST_DELAY)
            except Exception as exc:
                _log(f"  {category} ({actual_form}): ERROR downloading - {exc}")
                # Remove partial file
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                results.append({
                    "symbol":   symbol,
                    "category": category,
                    "form":     actual_form,
                    "error":    str(exc),
                })

    # ── Summary ──────────────────────────────────────────────────────────────
    downloaded = [r for r in results if "file" in r and not r.get("skipped")]
    skipped    = [r for r in results if r.get("skipped")]
    errors     = [r for r in results if "error" in r]

    _log(f"\n{'='*50}")
    _log(
        f"Done.  Downloaded: {len(downloaded)}"
        f"  |  Skipped (existing): {len(skipped)}"
        f"  |  Errors / not found: {len(errors)}"
    )
    _log(f"Files saved to: {output_dir}")
    if errors:
        _log("Issues:")
        for e in errors:
            _log(f"  {e.get('symbol','?')} {e.get('category','')} - {e.get('error','')}")

    return results


if __name__ == "__main__":
    run_downloader()
