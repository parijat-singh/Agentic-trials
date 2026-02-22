import pandas as pd
import numpy as np
import os
import glob
import sys
import yfinance as yf

def get_pe_ratio(symbol):
    """Fetches P/E ratio for a single symbol."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        pe = info.get('trailingPE')
        if pe is None:
            pe = info.get('forwardPE')
        return pe
    except Exception:
        return None

def calculate_sharpe_ratio(df, risk_free_rate):
    """
    Calculates Annualized Sharpe Ratio for a given stock DataFrame.
    Assumes 'Close' is the adjusted close price.
    """
    if df.empty or len(df) < 30: # Need some history
        return None, None, None
        
    # Calculate Daily Returns
    # Formula: (P_t / P_t-1) - 1
    # This is equivalent to Total Return including dividends IF the 'Close' is adjusted (standard in yfinance)
    daily_returns = df['Close'].pct_change().dropna()
    
    if daily_returns.empty:
        return None, None, None

    # Annualize
    # Trading days per year = 252
    avg_daily_return = daily_returns.mean()
    std_dev_daily = daily_returns.std()
    
    if std_dev_daily == 0:
        return 0.0, 0.0, 0.0
        
    annualized_return = avg_daily_return * 252
    annualized_volatility = std_dev_daily * np.sqrt(252)
    
    # Sharpe Ratio
    sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility
    
    return sharpe_ratio, annualized_return, annualized_volatility

def rank_stocks(data_dir, risk_free_rate):
    """
    Iterates through CSVs in data_dir, calculates Sharpe, and ranks them.
    Returns: DataFrame of Top 50 Stocks.
    """
    results = []
    
    # Load Max_PE, Min_History, Industries from stats if available
    max_pe = None
    min_history = None
    industries_filter = None
    stats_file = os.path.join(data_dir, "scraping_stats.json")
    if os.path.exists(stats_file):
        try:
            import json
            with open(stats_file, 'r') as f:
                params = json.load(f).get("Parameters", {})
                max_pe = params.get("Max_PE")
                min_history = params.get("Min_History")
                industries_filter = params.get("Industries")
                if industries_filter is not None and not isinstance(industries_filter, list):
                    industries_filter = [s.strip() for s in str(industries_filter).split(",") if s.strip()] or None
                print(f"DEBUG: sharpe_ranker loaded Max_PE: {max_pe}, Min_History: {min_history}")
        except Exception as e: 
            print(f"DEBUG: sharpe_ranker failed to load stats: {e}")
            pass

    # Load symbols from metadata file (US Filter source of truth)
    meta_file = os.path.join(data_dir, "top_100_new_stocks.csv")
    symbols = []
    symbol_pe_map = {}

    if os.path.exists(meta_file):
        meta_df = pd.read_csv(meta_file)
        # Filter by industry/sector if specified in Parameters (case-insensitive)
        sector_col = 'sector' if 'sector' in meta_df.columns else ('Sector' if 'Sector' in meta_df.columns else None)
        if industries_filter and sector_col and sector_col in meta_df.columns:
            before = len(meta_df)
            inds_lower = [str(s).strip().lower() for s in industries_filter]
            meta_df = meta_df[meta_df[sector_col].notna() & meta_df[sector_col].apply(
                lambda s: str(s).strip().lower() in inds_lower if s is not None and str(s).strip() else False)]
            if len(meta_df) < before:
                print(f"Industry filter (sharpe_ranker): {before} -> {len(meta_df)} stocks")
        # Handle Symbol case and map PE
        sym_col = 'symbol' if 'symbol' in meta_df.columns else 'Symbol'
        if sym_col in meta_df.columns:
            symbols = meta_df[sym_col].tolist()
            if 'pe_ratio' in meta_df.columns:
                symbol_pe_map = meta_df.set_index(sym_col)['pe_ratio'].to_dict()
        else:
             print("Warning: 'symbol' column not found in metadata.")
    else:
        print("Warning: Metadata file not found.")

    if not symbols:
        # Fallback to scanning data dir if metadata missing (though we prefer DB)
        # But if we use DB, we need symbols. DB can list unique symbols?
        # Let's stick to metadata file as source of truth for "selected" stocks.
        print(f"Processing stocks from DB based on available CSVs in {data_dir}...")
        csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
        symbols = [os.path.basename(f).replace(".csv", "") for f in csv_files]

    print(f"Processing {len(symbols)} stocks...")
    
    # Initialize DB
    try:
        # Add parent to path to find stock_agent if not already there
        # logic likely handled by main.py but nice to be robust
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from stock_agent.db_manager import DBManager
        import config
        db = DBManager()
    except Exception as e:
        print(f"Error initializing DB: {e}")
        return pd.DataFrame()

    # Batch Processing
    # 1. Fetch Data in Batches
    print(f"Fetching data for {len(symbols)} stocks in batches...")
    
    # helper for chunks
    def chunked_iterable(iterable, size):
        for i in range(0, len(iterable), size):
            yield iterable[i:i + size]
            
    all_data = []
    
    import sqlite3 as sql
    # Use direct connection for batch read
    db_path = db.db_path
    
    processed_count = 0
    
    for chunk in chunked_iterable(symbols, 500):
        try:
            placeholders = ','.join(['?'] * len(chunk))
            query = f"SELECT Symbol, Date, Close FROM stock_history WHERE Symbol IN ({placeholders}) ORDER BY Date ASC"
            
            with sql.connect(db_path) as conn:
                 # Read SQL directly
                 df_chunk = pd.read_sql_query(query, conn, params=chunk)
            
            if not df_chunk.empty:
                all_data.append(df_chunk)
                
            processed_count += len(chunk)
            print(f"Fetched {processed_count}/{len(symbols)} stocks...", end='\r', flush=True)
            
        except Exception as e:
            print(f"Error fetching batch: {e}")
            
    print(f"\nFetched {processed_count} stocks. Processing...")
    
    if not all_data:
         return pd.DataFrame()
         
    # 2. Combine and Process
    full_df = pd.concat(all_data, ignore_index=True)
    full_df['Date'] = pd.to_datetime(full_df['Date'])
    
    # 3. Group by Symbol and Calculate
    # We can use groupby apply, but manual iteration might be safer for error handling/logging
    grouped = full_df.groupby('Symbol')
    
    print(f"Calculating Sharpe for {len(grouped)} groups...")
    
    for symbol, group in grouped:
        try:
            # Set index for calculation
            df_sym = group.set_index('Date')
            
            # REINFORCEMENT: Check History Length
            if min_history is not None:
                duration_days = (df_sym.index[-1] - df_sym.index[0]).days
                duration_years = duration_days / 365.25
                if duration_years < min_history:
                    continue

            # Calculate Metrics
            sharpe, ann_ret, ann_vol = calculate_sharpe_ratio(df_sym, risk_free_rate)
            
            if sharpe is not None:
                results.append({
                    'Symbol': symbol,
                    'Sharpe Ratio': sharpe,
                    'Annualized Return': ann_ret,
                    'Annualized Volatility': ann_vol
                })
        except Exception as e:
            continue
            
    # Processed all
    print(f"Processed {len(results)} valid stocks.")
            
    # Create DataFrame
    results_df = pd.DataFrame(results)
    if results_df.empty:
        print("No valid data processed.")
        return pd.DataFrame()
        
    # Stage 1: Sort by Sharpe Ratio
    ranked_df = results_df.sort_values(by='Sharpe Ratio', ascending=False)
    
    # Stage 2: Reinforcement Filter on Top Candidates
    # We only verify P/E for the top candidates to avoid fetching for thousands of low-Sharpe stocks
    candidate_limit = 200 
    top_candidates = ranked_df.head(candidate_limit).copy()
    
    final_results = []
    print(f"Verifying P/E for top {len(top_candidates)} candidates...")
    
    for _, row in top_candidates.iterrows():
        symbol = row['Symbol']
        pe = symbol_pe_map.get(symbol)
        
        if max_pe is not None and (pe is None or pd.isna(pe)):
            pe = get_pe_ratio(symbol)

        if max_pe is not None:
            # If we have a filter, exclude N/A or over-threshold
            is_na = pd.isna(pe)
            if is_na or pe > max_pe or pe < 0:
                continue
        
        # Add P/E to result
        row_dict = row.to_dict()
        row_dict['P/E Ratio'] = pe
        final_results.append(row_dict)
        
        if len(final_results) >= 50:
            break

    # Return Top 50 (After P/E Filtering)
    return pd.DataFrame(final_results).head(50)

if __name__ == "__main__":
    # Test with dummy data or just run imported
    pass
