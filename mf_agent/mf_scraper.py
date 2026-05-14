"""
Mutual Fund Scraper - discovers MF universe via Yahoo Finance screener API.
Falls back to a curated seed list if the API is unavailable.
Saves to mf_universe.csv: symbol, name, category, aum, fund_family.
"""
import os
import sys
import time

import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# Curated fallback: well-known US mutual funds covering major families & categories
_SEED_UNIVERSE = [
    # Vanguard index & active
    "VFIAX", "VTSAX", "VBTLX", "VTIAX", "VEXAX", "VIGAX", "VDIGX", "VWIGX",
    "VWELX", "VWENX", "VPMCX", "VPMAX", "VSMAX", "VMVAX", "VGSTX",
    # Fidelity index & active
    "FXAIX", "FZROX", "FSKAX", "FZILX", "FXNAX", "FBGRX", "FCNTX", "FBALX",
    "FMILX", "FDIVX", "FSCSX", "FGRIX", "FOCPX", "FMAGX", "FDGRX", "FLPSX",
    "FSRPX", "FSELX", "FSPHX",
    # American Funds (Class A / Class F)
    "AGTHX", "AIVSX", "CAIBX", "ABALX", "AMRMX", "AMCPX", "ANWPX", "AWSHX",
    "RGAFX", "ABNDX", "AFIFX", "AAEPX",
    # T. Rowe Price
    "PRGFX", "TRBCX", "PRWAX", "PRFDX", "RPMGX", "PRNHX", "TRREX", "TRQBX",
    "PRMSX", "TRPBX",
    # PIMCO
    "PTTAX", "PIMIX", "PTTRX", "PDMIX", "PFUIX", "PTRAX",
    # Dodge & Cox
    "DODFX", "DODGX", "DODIX", "DODWX",
    # Schwab
    "SWPPX", "SWLGX", "SCHBX", "SWJRX",
    # Harbor
    "HACAX", "HCAIX",
    # Oakmark
    "OAKMX", "OAKIX", "OAKHX", "OAKBX",
    # Sequoia / other value
    "SEQUX", "FAIRX",
    # MFS
    "MFEGX", "MFECX",
    # Baird
    "BAGSX", "BIMSX",
    # JPMorgan
    "JLGMX", "OGLIX",
    # Franklin Templeton
    "TEMGX", "TEPLX", "TGRIX",
    # Cohen & Steers (REIT)
    "CSRSX",
    # Parnassus (ESG)
    "PARNX", "PARWX",
    # Baron
    "BGRFX", "BPTRX",
    # Artisan
    "ARTGX", "ARTMX",
    # Wasatch
    "WAAEX", "WAGRX",
    # Bond / Fixed Income
    "DODIX", "LSBRX", "MWHYX", "PUBDX", "VBLTX", "VBILX",
]

_UNIVERSE_PATH = os.path.join(config.MF_STORAGE_ROOT, "mf", "mf_universe.csv")


def _get_yahoo_session_and_crumb():
    """Return (curl_cffi session, crumb string) or (None, None) on failure."""
    try:
        import certifi
        import curl_cffi.requests as cr
        session = cr.Session(verify=certifi.where(), impersonate="chrome110")
        session.get("https://finance.yahoo.com/", timeout=15)
        r = session.get(
            "https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=10
        )
        if r.status_code == 200 and r.text and len(r.text) < 100:
            return session, r.text.strip()
    except Exception as e:
        print(f"  [scraper] crumb fetch failed: {e}", flush=True)
    return None, None


def _scrape_yahoo_screener(max_pages=20):
    """
    Scrape MF universe via Yahoo Finance screener API.
    Returns list of dicts: {symbol, name, category, aum, fund_family}.
    """
    session, crumb = _get_yahoo_session_and_crumb()
    if not session or not crumb:
        return []

    results = []
    page_size = 100
    for page in range(max_pages):
        offset = page * page_size
        body = {
            "size": page_size,
            "offset": offset,
            "sortField": "fundnetassets",
            "sortType": "DESC",
            "quoteType": "MUTUALFUND",
            "query": {
                "operator": "AND",
                "operands": [
                    {"operator": "GT", "operands": ["fundnetassets", 10_000_000]},
                    {"operator": "EQ", "operands": ["region", "us"]},
                ],
            },
            "userId": "",
            "userIdType": "guid",
        }
        try:
            r = session.post(
                "https://query1.finance.yahoo.com/v1/finance/screener",
                params={"crumb": crumb, "lang": "en-US", "region": "US",
                        "formatted": "false"},
                json=body,
                timeout=20,
            )
            data = r.json()
            quotes = (
                data.get("finance", {})
                    .get("result", [{}])[0]
                    .get("quotes", [])
            )
            if not quotes:
                break
            for q in quotes:
                sym = q.get("symbol", "").strip()
                if not sym:
                    continue
                results.append({
                    "symbol": sym,
                    "name": q.get("shortName") or q.get("longName") or sym,
                    "category": q.get("fundFamilyName") or "",
                    "aum": q.get("fundNetAssets") or 0,
                    "fund_family": q.get("fundFamilyName") or "",
                })
            print(f"  Page {page+1}: {len(quotes)} funds", flush=True)
            if len(quotes) < page_size:
                break
            time.sleep(0.5)
        except Exception as e:
            print(f"  Screener page {page+1} error: {e}", flush=True)
            break

    return results


def run_scraper(max_pages=20):
    """
    Build MF universe. Primary: Yahoo Finance screener. Fallback: seed list.
    Saves to mf_universe.csv and returns list of symbols.
    """
    os.makedirs(os.path.dirname(_UNIVERSE_PATH), exist_ok=True)

    print(f"Scraping MF universe (up to {max_pages} pages)...", flush=True)
    records = _scrape_yahoo_screener(max_pages=max_pages)

    if len(records) < 50:
        print(
            f"  Yahoo screener returned only {len(records)} funds; "
            "using curated seed list as supplement.",
            flush=True,
        )
        # Merge: add seed symbols not already found
        found_syms = {r["symbol"] for r in records}
        for sym in _SEED_UNIVERSE:
            if sym not in found_syms:
                records.append({
                    "symbol": sym, "name": sym, "category": "",
                    "aum": 0, "fund_family": "",
                })

    df = pd.DataFrame(records).drop_duplicates(subset="symbol")

    # Drop symbols that yfinance cannot handle:
    #  - Morningstar IDs (start with 0P) — not valid Yahoo Finance tickers
    #  - Foreign-exchange tickers (contain a dot, e.g. "FUND.DE")
    #  - Symbols with spaces or other unusual characters
    def _is_valid_ticker(sym: str) -> bool:
        sym = str(sym).strip()
        if sym.startswith("0P"):
            return False
        if "." in sym or " " in sym:
            return False
        if len(sym) < 2 or len(sym) > 10:
            return False
        return True

    before = len(df)
    df = df[df["symbol"].apply(_is_valid_ticker)].reset_index(drop=True)
    print(f"Filtered {before - len(df)} invalid tickers; {len(df)} remain.", flush=True)

    df.to_csv(_UNIVERSE_PATH, index=False)
    print(f"Saved {len(df)} mutual funds to {_UNIVERSE_PATH}", flush=True)
    return df["symbol"].tolist()


if __name__ == "__main__":
    run_scraper()
