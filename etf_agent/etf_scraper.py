"""
ETF Universe Scraper - scrapes largest ETFs from companiesmarketcap.com.
Writes etf_universe.csv to ETF_STORAGE_ROOT/etf/
"""
import os
import re
import sys
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

ETF_PAGE_URL = "https://companiesmarketcap.com/etfs/largest-etfs-by-marketcap/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _parse_symbol_from_link_text(text):
    """Extract symbol from link text, e.g. 'Vanguard S&P 500 ETFVOO' -> VOO, 'iShares ... IUSQ.DE' -> IUSQ.DE."""
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    # Prefer 2-5 letter ticker at end (optionally .XX)
    m = re.search(r"([A-Z]{2,5}(\.[A-Z]{2})?)$", text, re.IGNORECASE)
    if m:
        s = m.group(1).upper()
        # Site concatenates word+ticker: "ETFVOO", "TFVOO", "TrustQQQ"->STQQQ, "SharesVTI"->ESVTI
        for prefix in ("ETF", "TF", "ST", "ES"):
            if len(s) > len(prefix) and s.startswith(prefix) and s[len(prefix):].isalpha() and len(s[len(prefix):]) <= 5:
                return s[len(prefix):].upper()
        return s
    # Fallback: 1-6 alphanumeric at end
    m = re.search(r"([A-Z0-9]{1,6}(\.[A-Z]{2})?)$", text, re.IGNORECASE)
    if m:
        s = m.group(1).upper()
        for prefix in ("ETF", "TF", "ST", "ES"):
            if len(s) > len(prefix) and s.startswith(prefix) and s[len(prefix):].isalpha() and len(s[len(prefix):]) <= 5:
                return s[len(prefix):].upper()
        return s
    return None


def scrape_etf_page(url):
    """Scrape a single page, return list of {symbol, name}."""
    out = []
    try:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # ETF links: /name-slug/marketcap/ or full URL (site uses no "etfs" in path)
        for a in soup.find_all("a", href=re.compile(r"/[^/]+/marketcap/?(\?|$)")):
            txt = a.get_text(strip=True)
            if not txt:
                continue
            sym = _parse_symbol_from_link_text(txt)
            if not sym:
                continue
            name = re.sub(r"[A-Z0-9]{1,6}(\.[A-Z]{2})?$", "", txt, flags=re.IGNORECASE).strip() or sym
            out.append({"symbol": sym, "name": name})
    except Exception as e:
        print(f"Scrape error: {e}", flush=True)
    return out


def run_scraper(max_pages=40):
    """Scrape ETF universe from companiesmarketcap (all pages) and save to etf_universe.csv.
    Site has ~3900 ETFs; max_pages=40 gives ~4000 (100 per page). NYSE/NASDAQ filter applied later."""
    etf_dir = os.path.join(config.ETF_STORAGE_ROOT, "etf")
    os.makedirs(etf_dir, exist_ok=True)
    path = os.path.join(etf_dir, "etf_universe.csv")
    seen = set()
    unique_rows = []
    # Page 1: base URL; pages 2..N: ?page=N
    for p in range(1, max_pages + 1):
        if p == 1:
            url = ETF_PAGE_URL
        else:
            url = f"https://companiesmarketcap.com/etfs/largest-etfs-by-marketcap/?page={p}"
        print(f"Scraping page {p}/{max_pages}...", flush=True)
        page_rows = scrape_etf_page(url)
        print(f"  -> got {len(page_rows)} ETFs from page", flush=True)
        for r in page_rows:
            if r["symbol"] not in seen:
                seen.add(r["symbol"])
                unique_rows.append(r)
        time.sleep(0.8)
    df = pd.DataFrame(unique_rows)
    if df.empty:
        print("WARNING: No ETFs scraped (check site or network). Using 38-ETF fallback list.", flush=True)
        fallback = [
            ("SPY", "SPDR S&P 500"), ("IVV", "iShares Core S&P 500"), ("VOO", "Vanguard S&P 500"),
            ("VTI", "Vanguard Total Stock Market"), ("QQQ", "Invesco QQQ"), ("VEA", "Vanguard FTSE Developed"),
            ("VUG", "Vanguard Growth"), ("GLD", "SPDR Gold"), ("IEFA", "iShares Core MSCI EAFE"),
            ("VTV", "Vanguard Value"), ("BND", "Vanguard Total Bond"), ("IEMG", "iShares Core MSCI EM"),
            ("AGG", "iShares Core US Aggregate Bond"), ("VXUS", "Vanguard Total International"),
            ("VWO", "Vanguard Emerging Markets"), ("IWF", "iShares Russell 1000 Growth"),
            ("IJH", "iShares Core S&P Mid-Cap"), ("VGT", "Vanguard Information Technology"),
            ("VIG", "Vanguard Dividend Appreciation"), ("IJR", "iShares Core S&P Small-Cap"),
            ("VO", "Vanguard Mid-Cap"), ("XLK", "Technology Select Sector SPDR"),
            ("SCHD", "Schwab US Dividend Equity"), ("IAU", "iShares Gold Trust"),
            ("ITOT", "iShares Core S&P Total US Stock"), ("EFA", "iShares MSCI EAFE"),
            ("BNDX", "Vanguard Total International Bond"), ("IWM", "iShares Russell 2000"),
            ("VYM", "Vanguard High Dividend Yield"), ("VB", "Vanguard Small-Cap"),
            ("QQQM", "Invesco NASDAQ 100"), ("IWD", "iShares Russell 1000 Value"),
            ("TLT", "iShares 20+ Year Treasury Bond"), ("SLV", "iShares Silver Trust"),
            ("DIA", "SPDR Dow Jones Industrial Average"), ("VNQ", "Vanguard Real Estate"),
            ("XLE", "Energy Select Sector SPDR"), ("XLF", "Financial Select Sector SPDR"),
        ]
        df = pd.DataFrame([{"symbol": s, "name": n} for s, n in fallback])
    df = df.drop_duplicates(subset=["symbol"])
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} ETFs to {path}", flush=True)
    return path


if __name__ == "__main__":
    run_scraper()
