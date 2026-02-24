import pandas as pd
import sys
import os
import json
import yfinance as yf
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from stock_agent import market_cap_scraper

def get_exclusion_reason(symbol, params, portfolio_symbols):
    """
    Determines why a stock is excluded based on params.
    """
    # 1. Check if in Portfolio
    if symbol in portfolio_symbols:
        return "Included in Portfolio"

    # 2. Fetch Data for Checks
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info

        # IPO Check
        ipo_timestamp = info.get('firstTradeDateEpochUtc')
        years_since_ipo = None
        
        if ipo_timestamp:
            ipo_date = datetime.fromtimestamp(ipo_timestamp)
            years_since_ipo = (datetime.now() - ipo_date).days / 365.25
        else:
            # Fallback: Fetch history to determine start date
            try:
                hist = ticker.history(period="max")
                if not hist.empty:
                    start_date = hist.index[0]
                    # Convert to datetime if it's tz-aware
                    if start_date.tzinfo:
                        start_date = start_date.tz_localize(None)
                    years_since_ipo = (datetime.now() - start_date).days / 365.25
            except:
                pass
                
        if years_since_ipo is not None:
            min_ipo = params.get('Min_IPO', 0)
            max_ipo = params.get('Max_IPO', 999)
            
            if years_since_ipo < min_ipo:
                return f"Excluded: Too New (IPO {years_since_ipo:.1f}y < {min_ipo}y)"
            if years_since_ipo > max_ipo:
                return f"Excluded: Too Old (IPO {years_since_ipo:.1f}y > {max_ipo}y)"
        else:
             # Fallback if no IPO date (common for some datasets) - Assume old if giant?
             # Or just skip IPO check if data missing.
             pass

        # P/E Check (sector-specific)
        pe = info.get('trailingPE')
        if pe is None:
            pe = info.get('forwardPE')
        sector = info.get('sector')
        max_pe_by_sector = params.get('Max_PE_By_Sector')
        max_pe = max_pe_by_sector.get(sector) if (max_pe_by_sector and sector and isinstance(max_pe_by_sector, dict)) else None
        if max_pe and pe:
            if pe > max_pe:
                return f"Excluded: High P/E ({pe:.2f} > {max_pe})"
            if pe < 0:
                return f"Excluded: Negative P/E ({pe:.2f})"
                
        # Market Cap Check (Implicitly passed since it's Top 10, but check config)
        mcap = info.get('marketCap')
        min_cap_b = params.get('Min_Market_Cap')
        if min_cap_b and mcap:
            mcap_b = mcap / 1e9
            if mcap_b < min_cap_b:
                return f"Excluded: Market Cap too low ({mcap_b:.1f}B < {min_cap_b}B)"

        # If it passed all filters but verified effectively
        return "Excluded: Lower Sharpe Ratio / Optimization"

    except Exception as e:
        return f"Error analyzing: {e}"


def _get_top_10_per_sector_from_csv(csv_path, params, portfolio_symbols):
    """
    Get top 10 by market cap per sector from top_100_new_stocks.csv.
    Returns dict { "Sector": [ { Rank, Symbol, Name, Reason }, ... ] } or None if fallback needed.
    """
    if not os.path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    sym_col = 'symbol' if 'symbol' in df.columns else 'Symbol'
    name_col = 'name' if 'name' in df.columns else ('Name' if 'Name' in df.columns else None)
    mcap_col = 'market_cap' if 'market_cap' in df.columns else ('Market_Cap' if 'Market_Cap' in df.columns else None)
    sector_col = 'sector' if 'sector' in df.columns else ('Sector' if 'Sector' in df.columns else None)

    if sym_col not in df.columns:
        return None
    name_col = name_col or sym_col
    mcap_col = mcap_col or 'market_cap'

    # Enrich sector from DB if missing
    if sector_col is None or (sector_col in df.columns and df[sector_col].isna().all()):
        try:
            from stock_agent.db_manager import DBManager
            db = DBManager()
            sector_col = 'sector'
            df[sector_col] = df[sym_col].map(lambda s: db.get_sector(s) if isinstance(s, str) else None)
        except Exception:
            sector_col = None

    if sector_col not in df.columns or df[sector_col].isna().all():
        return None

    # Get selected sectors
    industries = params.get('Industries')
    if industries:
        industries = [s.strip() for s in industries if s and str(s).strip()]
        if not isinstance(industries, list):
            industries = [s.strip() for s in str(industries).split(',') if s.strip()]
    if not industries:
        industries = [str(s) for s in df[sector_col].dropna().unique().tolist()]

    # Normalize sector names for comparison; filter to selected sectors
    inds_lower = [str(s).strip().lower() for s in industries]
    df = df[df[sector_col].notna() & df[sector_col].apply(lambda s: str(s).strip().lower() in inds_lower if pd.notna(s) else False)]
    if df.empty:
        return None

    # Parse market cap for sorting
    def mcap_val(row):
        m = row.get(mcap_col) if mcap_col in df.columns else None
        if m is None or pd.isna(m):
            return -1.0
        v = market_cap_scraper.parse_market_cap(str(m))
        return v if v is not None else -1.0

    df['_mcap_b'] = df.apply(mcap_val, axis=1)
    result = {}

    for sector in industries:
        sector_lower = str(sector).strip().lower()
        sector_display = next((str(s) for s in df[sector_col].unique() if str(s).strip().lower() == sector_lower), sector)
        sector_df = df[df[sector_col].apply(lambda s: str(s).strip().lower() == sector_lower if pd.notna(s) else False)]
        sector_df = sector_df.sort_values('_mcap_b', ascending=False).head(10)
        if sector_df.empty:
            continue
        items = []
        for rank, (_, row) in enumerate(sector_df.iterrows(), 1):
            sym = str(row[sym_col]).strip()
            name = str(row.get(name_col, sym)) if name_col in df.columns else sym
            reason = get_exclusion_reason(sym, params, portfolio_symbols)
            items.append({"Rank": rank, "Symbol": sym, "Name": name, "Reason": reason})
            print(f"[{sector_display}] {sym} #{rank}: {reason}")
        result[sector_display] = items

    return result if result else None


def _get_global_top_10_fallback(params, portfolio_symbols):
    """Fallback: global top 10 US stocks from scraper (legacy behavior)."""
    print("Using fallback: global top 10 from market cap list...")
    companies = market_cap_scraper.get_companies_from_page(1)
    top_10_us = []
    for c in companies:
        if market_cap_scraper.is_likely_us_stock(c['symbol']):
            top_10_us.append(c)
            if len(top_10_us) >= 10:
                break
    results = []
    for c in top_10_us:
        reason = get_exclusion_reason(c['symbol'], params, portfolio_symbols)
        results.append({
            "Rank": len(results) + 1,
            "Symbol": c['symbol'],
            "Name": c['name'],
            "Reason": reason
        })
        print(f"[{c['symbol']}] {reason}")
    return results


def analyze_top_10():
    print("Running Top 10 Exclusion Analysis...")
    
    # 1. Load Parameters
    stats_file = os.path.join(config.DATA_DIR, "scraping_stats.json")
    params = {}
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            stats = json.load(f)
            params = stats.get("Parameters", {})
            
    print(f"Loaded Params: {params}")

    # 2. Identify Portfolio Stocks
    portfolio_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "portfolio_optimizer", "optimal_portfolio.csv")
    portfolio_symbols = []
    if os.path.exists(portfolio_file):
        df = pd.read_csv(portfolio_file)
        if 'Symbol' in df.columns:
            portfolio_symbols = df['Symbol'].tolist()
        elif 'symbol' in df.columns:
            portfolio_symbols = df['symbol'].tolist()

    # 3. Try per-sector from top_100_new_stocks.csv
    csv_path = os.path.join(config.DATA_DIR, "top_100_new_stocks.csv")
    per_sector = _get_top_10_per_sector_from_csv(csv_path, params, portfolio_symbols)

    if per_sector:
        output = {"per_sector": per_sector}
    else:
        results = _get_global_top_10_fallback(params, portfolio_symbols)
        output = {"legacy": results}

    # 4. Save Results
    output_file = os.path.join(config.DATA_DIR, "top_10_exclusion.json")
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
        
    print(f"Analysis saved to {output_file}")


if __name__ == "__main__":
    analyze_top_10()
