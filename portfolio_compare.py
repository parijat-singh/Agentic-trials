"""
Portfolio comparative analysis: fetch prices, compute metrics vs S&P 500 (SPY),
and return time series for charting.
Also: last 3 years return (with IPO handling), mean-variance optimal allocation.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # applies curl_cffi SSL patch for yfinance
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from scipy.optimize import minimize

BENCHMARK_SYMBOL = "SPY"
TRADING_DAYS_PER_YEAR = 252


def _fetch_prices(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily Close prices for symbols and SPY. Returns DataFrame with date index."""
    all_syms = list(set(symbols + [BENCHMARK_SYMBOL]))
    data = {}
    for sym in all_syms:
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(start=start_date, end=end_date, auto_adjust=True)
            if hist.empty or "Close" not in hist.columns:
                continue
            series = hist["Close"].copy()
            series.index = pd.to_datetime(series.index).normalize()
            data[sym] = series
        except Exception:
            continue
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df = df.dropna(how="all").ffill().bfill()
    return df


def _get_rf_rate() -> float:
    """Annual risk-free rate as decimal."""
    try:
        import sys
        import os
        _root = os.path.dirname(os.path.abspath(__file__))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from financial_engine.risk_free_rate import get_risk_free_rate
        return get_risk_free_rate()
    except Exception:
        return 0.04


def _compute_metrics(
    port_daily: pd.Series, bench_rets: pd.Series, rf_annual: float
) -> Dict[str, float]:
    """Compute return, volatility, sharpe, alpha, beta for a portfolio daily return series."""
    if port_daily.empty or len(port_daily) < 2:
        return {"return": 0.0, "volatility": 0.0, "sharpe": 0.0, "alpha": 0.0, "beta": 0.0}
    port_cum = (1 + port_daily).cumprod()
    port_total = float(port_cum.iloc[-1] / port_cum.iloc[0] - 1)
    port_vol = float(port_daily.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    days = (port_daily.index[-1] - port_daily.index[0]).days
    rf_period = (1 + rf_annual) ** (days / 365.0) - 1
    daily_rf = (1 + rf_annual) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1
    sharpe = (
        float(((port_daily.mean() - daily_rf) * TRADING_DAYS_PER_YEAR) / port_vol)
        if port_vol > 1e-9
        else 0.0
    )
    beta = 0.0
    alpha = 0.0
    if not bench_rets.empty and len(bench_rets) >= 2:
        common = port_daily.index.intersection(bench_rets.index)
        p = port_daily.loc[common].dropna()
        b = bench_rets.loc[common].dropna()
        common = p.index.intersection(b.index)
        if len(common) >= 2:
            p, b = p.loc[common], b.loc[common]
            cov = np.cov(p.values, b.values)[0, 1]
            var_b = np.var(b.values, ddof=1)
            if var_b > 1e-12:
                beta = float(cov / var_b)
            spy_total = float((1 + b).prod() - 1)
            alpha = float(port_total - (rf_period + beta * (spy_total - rf_period)))
    return {"return": port_total, "volatility": port_vol, "sharpe": sharpe, "alpha": alpha, "beta": beta}


def _compute_3y_per_year_metrics_with_ipo_handling(
    holdings: List[Dict[str, Any]], rf_annual: float
) -> Dict[str, Dict[str, Any]]:
    """
    Compute portfolio metrics per calendar year for last 3 years (2023, 2024, 2025).
    For stocks without history in a year: treat that portion as zero (daily renormalize).
    Returns: { "2023": {...}, "2024": {...}, "2025": {...} }
    """
    end_ts = pd.Timestamp.now().normalize()
    start_ts = end_ts - pd.Timedelta(days=3 * 365)
    start_str = start_ts.strftime("%Y-%m-%d")
    end_str = (end_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    symbols = [h["symbol"] for h in holdings]
    amounts = {h["symbol"]: h["amount"] for h in holdings}
    total_amount = sum(amounts.values())
    if total_amount <= 0:
        return {}
    df = _fetch_prices(symbols + [BENCHMARK_SYMBOL], start_str, end_str)
    if df.empty or BENCHMARK_SYMBOL not in df.columns:
        return {}
    price_cols = [c for c in symbols if c in df.columns]
    if not price_cols:
        return {}
    prices = df[price_cols].copy()
    bench = df[BENCHMARK_SYMBOL]
    prices = prices.dropna(how="all").ffill().bfill()
    bench = bench.reindex(prices.index).ffill().bfill()
    rets = prices.pct_change()
    bench_rets = bench.pct_change()
    port_daily_list = []
    for d in rets.index:
        row = rets.loc[d]
        valid = row.dropna()
        if valid.empty:
            continue
        w = pd.Series({s: amounts.get(s, 0) for s in valid.index if s in amounts})
        tot = w.sum()
        if tot <= 0:
            continue
        w = w / tot
        r = (valid * w.reindex(valid.index).fillna(0)).sum()
        if pd.notna(r):
            port_daily_list.append((d, r))
    if len(port_daily_list) < 2:
        return {}
    port_daily = pd.Series({d: r for d, r in port_daily_list}).sort_index()
    bench_rets = bench_rets.reindex(port_daily.index).dropna()
    common = port_daily.index.intersection(bench_rets.index)
    if len(common) < 2:
        port_daily = port_daily.loc[common] if len(common) >= 2 else port_daily
        bench_rets = bench_rets.loc[common] if len(common) >= 2 else pd.Series(dtype=float)
    else:
        port_daily = port_daily.loc[common]
        bench_rets = bench_rets.loc[common]

    target_years = ["2023", "2024", "2025"]
    data_years = sorted(port_daily.index.year.unique())
    result = {y: {"return": None, "volatility": None, "sharpe": None, "alpha": None, "beta": None} for y in target_years}
    for year in data_years:
        mask = port_daily.index.year == year
        year_port = port_daily.loc[mask]
        year_bench = bench_rets.reindex(year_port.index).dropna()
        year_common = year_port.index.intersection(year_bench.index)
        if len(year_common) < 5:
            if str(year) in result:
                result[str(year)] = {"return": None, "volatility": None, "sharpe": None, "alpha": None, "beta": None}
            continue
        year_port = year_port.loc[year_common]
        year_bench = year_bench.loc[year_common]
        if str(year) in result:
            result[str(year)] = _compute_metrics(year_port, year_bench, rf_annual)
    return result


def _run_max_sharpe_optimization(
    prices: pd.DataFrame, rf_annual: float
) -> Tuple[Optional[Dict[str, float]], Optional[pd.Series]]:
    """Max Sharpe weights. Returns (optimal_weights_dict, optimal_weights_series) or (None, None)."""
    if prices.empty or len(prices.columns) < 1 or len(prices) < 2:
        return None, None
    rets = prices.pct_change().dropna()
    if rets.empty or len(rets) < 10:
        return None, None
    mean_ret = rets.mean()
    cov = rets.cov()
    n = len(mean_ret)

    def neg_sharpe(w):
        pr = np.dot(mean_ret, w) * TRADING_DAYS_PER_YEAR
        pv = np.sqrt(np.dot(w, np.dot(cov, w))) * np.sqrt(TRADING_DAYS_PER_YEAR)
        if pv < 1e-12:
            return 0.0
        return -(pr - rf_annual) / pv

    constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
    bounds = [(0.0, 1.0)] * n
    x0 = np.ones(n) / n
    try:
        res = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints)
        if not res.success:
            return None, None
        w_series = pd.Series(res.x, index=prices.columns)
        w_dict = {s: float(w_series[s]) for s in prices.columns}
        return w_dict, w_series
    except Exception:
        return None, None


def _validate_inputs(holdings: List[Dict[str, Any]], start_date: str, end_date: str) -> Optional[str]:
    """Validate inputs. Returns error message or None."""
    if not holdings:
        return "At least one holding is required."
    valid = [(h.get("symbol", "").strip().upper(), float(h.get("amount", 0))) for h in holdings]
    valid = [(s, a) for s, a in valid if s and a > 0]
    if not valid:
        return "At least one holding with a valid symbol and positive amount is required."
    try:
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
    except Exception:
        return "Invalid start_date or end_date format. Use YYYY-MM-DD."
    if start >= end:
        return "start_date must be before end_date."
    return None


def run_portfolio_compare(
    holdings: List[Dict[str, Any]], start_date: str, end_date: str
) -> Dict[str, Any]:
    """
    Compute portfolio metrics vs S&P 500 and time series for chart.
    holdings: [ { "symbol": "AAPL", "amount": 1000 }, ... ]
    Returns: { portfolio: {...}, spy: {...}, series: [...] } or raises ValueError.
    """
    err = _validate_inputs(holdings, start_date, end_date)
    if err:
        raise ValueError(err)

    # Normalize holdings
    valid_holdings = []
    for h in holdings:
        s = str(h.get("symbol", "")).strip().upper()
        a = float(h.get("amount", 0))
        if s and a > 0:
            valid_holdings.append({"symbol": s, "amount": a})

    symbols = [h["symbol"] for h in valid_holdings]
    amounts = np.array([h["amount"] for h in valid_holdings])
    total = amounts.sum()
    weights = {s: a / total for s, a in zip(symbols, amounts)}

    # Fetch prices
    df = _fetch_prices(symbols, start_date, end_date)
    if df.empty:
        raise ValueError("Could not fetch price data for any symbol.")

    missing = [s for s in symbols if s not in df.columns]
    if missing:
        raise ValueError(f"No data for symbol(s) {', '.join(missing)} in date range.")

    if BENCHMARK_SYMBOL not in df.columns:
        raise ValueError("Insufficient data for S&P 500 (SPY) benchmark.")

    # Filter to symbols we have and align dates
    price_cols = [c for c in symbols if c in df.columns]
    prices = df[price_cols].dropna(how="all").ffill().bfill()
    bench = df[BENCHMARK_SYMBOL].reindex(prices.index).ffill().bfill()

    if prices.empty or len(prices) < 2:
        raise ValueError("Insufficient price data for analysis.")

    # Portfolio daily returns (weighted)
    rets = prices.pct_change().dropna()
    common_idx = rets.index
    bench_rets = bench.pct_change().loc[common_idx].dropna()
    common_idx = common_idx.intersection(bench_rets.index)
    rets = rets.loc[common_idx]
    bench_rets = bench_rets.loc[common_idx]

    w_series = pd.Series({s: weights.get(s, 0) for s in rets.columns if s in weights})
    port_daily = rets.dot(w_series).dropna()
    common_idx = port_daily.index.intersection(bench_rets.index)
    port_daily = port_daily.loc[common_idx]
    bench_rets = bench_rets.loc[common_idx]

    if len(port_daily) < 2:
        raise ValueError("Insufficient aligned data for metrics.")

    # Cumulative growth (normalized to 1 at start)
    port_cum = (1 + port_daily).cumprod()
    bench_cum = (1 + bench_rets).cumprod()

    # Total returns
    port_total = float(port_cum.iloc[-1] / port_cum.iloc[0] - 1) if len(port_cum) > 0 else 0.0
    spy_total = float(bench_cum.iloc[-1] / bench_cum.iloc[0] - 1) if len(bench_cum) > 0 else 0.0

    # Volatility (annualized)
    port_vol = float(port_daily.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    spy_vol = float(bench_rets.std() * np.sqrt(TRADING_DAYS_PER_YEAR))

    rf_annual = _get_rf_rate()
    days = (port_daily.index[-1] - port_daily.index[0]).days
    rf_period = (1 + rf_annual) ** (days / 365.0) - 1
    daily_rf = (1 + rf_annual) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1

    # Sharpe (annualized)
    if port_vol > 1e-9:
        sharpe = float(((port_daily.mean() - daily_rf) * TRADING_DAYS_PER_YEAR) / port_vol)
    else:
        sharpe = 0.0

    # Beta
    cov = np.cov(port_daily.values, bench_rets.values)[0, 1]
    var_bench = np.var(bench_rets.values, ddof=1)
    beta = float(cov / var_bench) if var_bench > 1e-12 else 0.0

    # Alpha: Rp - (Rf + beta * (Rm - Rf))
    alpha = float(port_total - (rf_period + beta * (spy_total - rf_period)))

    # Series for chart: date, portfolio_cum, spy_cum (normalized to 1 at first date)
    base_port = float(port_cum.iloc[0])
    base_spy = float(bench_cum.iloc[0])
    series = [
        {
            "date": d.strftime("%Y-%m-%d"),
            "portfolio_cum": float(port_cum.loc[d] / base_port),
            "spy_cum": float(bench_cum.loc[d] / base_spy),
        }
        for d in port_cum.index
    ]

    # Last 3 years metrics per year (with IPO handling)
    portfolio_3y_by_year = _compute_3y_per_year_metrics_with_ipo_handling(valid_holdings, rf_annual)

    # Mean-variance optimization (max Sharpe) on user period
    opt_weights_dict, opt_weights_series = _run_max_sharpe_optimization(prices, rf_annual)
    optimal_weights = opt_weights_dict if opt_weights_dict else {s: 0.0 for s in symbols}
    optimal_portfolio = None
    optimal_portfolio_3y_by_year = {}

    if opt_weights_series is not None and not opt_weights_series.empty:
        # Optimal portfolio daily returns for user period
        opt_port_daily = rets.dot(opt_weights_series).dropna()
        common_opt = opt_port_daily.index.intersection(bench_rets.index)
        if len(common_opt) >= 2:
            opt_port_daily = opt_port_daily.loc[common_opt]
            opt_bench = bench_rets.loc[common_opt]
            optimal_portfolio = _compute_metrics(opt_port_daily, opt_bench, rf_annual)

        # Optimal portfolio last 3 years per year
        end_ts = pd.Timestamp.now().normalize()
        start_3y = (end_ts - pd.Timedelta(days=3 * 365)).strftime("%Y-%m-%d")
        end_3y = (end_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        df_3y = _fetch_prices(symbols + [BENCHMARK_SYMBOL], start_3y, end_3y)
        if not df_3y.empty and BENCHMARK_SYMBOL in df_3y.columns:
            price_cols_3y = [c for c in symbols if c in df_3y.columns]
            if price_cols_3y:
                prices_3y = df_3y[price_cols_3y].dropna(how="all").ffill().bfill()
                bench_3y = df_3y[BENCHMARK_SYMBOL].reindex(prices_3y.index).ffill().bfill()
                rets_3y = prices_3y.pct_change().dropna()
                bench_rets_3y = bench_3y.pct_change().dropna()
                w_3y = opt_weights_series.reindex(price_cols_3y).fillna(0)
                tot_w = w_3y.sum()
                if tot_w > 1e-9:
                    w_3y = w_3y / tot_w
                    opt_port_3y = rets_3y.dot(w_3y).dropna()
                    common_3y = opt_port_3y.index.intersection(bench_rets_3y.index)
                    if len(common_3y) >= 2:
                        opt_port_3y = opt_port_3y.loc[common_3y]
                        bench_rets_3y = bench_rets_3y.loc[common_3y]
                        target_years_opt = {"2023", "2024", "2025"}
                        for year in sorted(opt_port_3y.index.year.unique()):
                            if str(year) not in target_years_opt:
                                continue
                            mask = opt_port_3y.index.year == year
                            yp = opt_port_3y.loc[mask]
                            yb = bench_rets_3y.reindex(yp.index).dropna()
                            yc = yp.index.intersection(yb.index)
                            if len(yc) >= 5:
                                optimal_portfolio_3y_by_year[str(year)] = _compute_metrics(
                                    yp.loc[yc], yb.loc[yc], rf_annual
                                )
                            else:
                                optimal_portfolio_3y_by_year[str(year)] = {
                                    "return": None, "volatility": None, "sharpe": None, "alpha": None, "beta": None
                                }

    if optimal_portfolio is None:
        optimal_portfolio = {"return": None, "volatility": None, "sharpe": None, "alpha": None, "beta": None}

    for y in ["2023", "2024", "2025"]:
        if y not in optimal_portfolio_3y_by_year:
            optimal_portfolio_3y_by_year[y] = {
                "return": None, "volatility": None, "sharpe": None, "alpha": None, "beta": None
            }

    return {
        "portfolio": {
            "return": port_total,
            "volatility": port_vol,
            "sharpe": sharpe,
            "alpha": alpha,
            "beta": beta,
        },
        "spy": {"return": spy_total, "volatility": spy_vol},
        "series": series,
        "portfolio_3y_by_year": portfolio_3y_by_year,
        "optimal_weights": optimal_weights,
        "optimal_portfolio": optimal_portfolio,
        "optimal_portfolio_3y_by_year": optimal_portfolio_3y_by_year,
    }
