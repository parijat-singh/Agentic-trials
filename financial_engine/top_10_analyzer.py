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

        # P/E Check
        pe = info.get('trailingPE')
        if pe is None:
            pe = info.get('forwardPE')
            
        max_pe = params.get('Max_PE')
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
            
    # 3. Fetch Top 10 US Stocks
    # Reuse scraper logic to get raw list, then filter for first 10 US
    print("Fetching current Top Market Cap list...")
    # Fetch enough to get 10 US stocks (page 1 has 100 usually)
    companies = market_cap_scraper.get_companies_from_page(1)
    
    top_10_us = []
    for c in companies:
        if market_cap_scraper.is_likely_us_stock(c['symbol']):
            top_10_us.append(c)
            if len(top_10_us) >= 10:
                break
                
    # 4. Analyze Each
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
        
    # 5. Save Results
    output_file = os.path.join(config.DATA_DIR, "top_10_exclusion.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
        
    print(f"Analysis saved to {output_file}")

if __name__ == "__main__":
    analyze_top_10()
