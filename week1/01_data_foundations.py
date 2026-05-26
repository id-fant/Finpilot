"""Week 1, Day 1-2 — Financial data foundations.

Fetches OHLCV data and computes returns, moving averages, volatility,
Sharpe ratio, max drawdown and volume analytics.

Run:  python 01_data_foundations.py
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

TRADING_DAYS = 252
RISK_FREE_RATE = 0.065  # Indian 10-yr G-Sec
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


# ── Data fetching ────────────────────────────────────────────────────────────

def fetch_stock_data(symbol: str, period: str = "1y", retries: int = 3) -> pd.DataFrame:
    """Fetch OHLCV data for one ticker, retrying on empty/failed responses."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            df = yf.Ticker(symbol).history(period=period)
            if len(df) > 0:
                df.index = pd.to_datetime(df.index).tz_localize(None)
                df.index.name = "Date"
                # pandas stubs union `df[list_of_cols]` as `Series | DataFrame`;
                # at runtime a list-of-columns lookup is always a DataFrame.
                return df[OHLCV]  # pyright: ignore[reportReturnType]
            last_err = "empty response"
        except Exception as e:  # noqa: BLE001 - surface any fetch failure
            last_err = str(e)
        time.sleep(2 * attempt)
    raise RuntimeError(f"Could not fetch {symbol} after {retries} attempts ({last_err})")


def fetch_many(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch several tickers sequentially. Returns {symbol: DataFrame}, skipping failures.

    Sequential on purpose: Yahoo Finance rate-limits concurrent requests, so a
    parallel batch tends to get the whole set throttled. fetch_stock_data's
    retry/backoff covers transient failures.
    """
    results: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            results[symbol] = fetch_stock_data(symbol, period)
        except Exception as e:  # noqa: BLE001
            print(f"  [WARN] skipping {symbol}: {e}")
    return results


# ── Enrichment ───────────────────────────────────────────────────────────────

def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add returns, moving averages, volatility and volume analytics in one pass."""
    df = df.copy()

    df["Daily_Return"] = df["Close"].pct_change()
    df["Cumulative_Return"] = (1 + df["Daily_Return"]).cumprod() - 1
    df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1))

    close = df["Close"]
    df["SMA_20"] = close.rolling(20).mean()
    df["SMA_50"] = close.rolling(50).mean()
    df["SMA_200"] = close.rolling(200).mean()
    df["Volatility_20d"] = df["Daily_Return"].rolling(20).std()

    vol = df["Volume"]
    df["Volume_SMA_20"] = vol.rolling(20).mean()
    df["Volume_Ratio"] = vol / df["Volume_SMA_20"]
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = (typical_price * vol).cumsum() / vol.cumsum()

    return df


# ── Metrics ──────────────────────────────────────────────────────────────────

def compute_sharpe_ratio(returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """Annualised Sharpe ratio from a daily return series."""
    returns = returns.dropna()
    if returns.empty or returns.std() == 0:
        return 0.0
    excess = returns - risk_free_rate / TRADING_DAYS
    return round(excess.mean() / excess.std() * np.sqrt(TRADING_DAYS), 3)


def compute_max_drawdown(cumulative_returns: pd.Series) -> dict:
    """Largest peak-to-trough drop, with the dates it occurred."""
    wealth = 1 + cumulative_returns
    drawdown = (wealth - wealth.cummax()) / wealth.cummax()
    trough = drawdown.idxmin()
    return {
        "max_drawdown": round(drawdown.min() * 100, 2),
        # pandas stubs union idxmin/idxmax return as Hashable (int|str|Timestamp);
        # for a DatetimeIndex it is always a Timestamp at runtime, so coerce.
        "peak_date": pd.Timestamp(wealth[:trough].idxmax()).date(),
        "trough_date": pd.Timestamp(trough).date(),
        "drawdown_series": drawdown,
    }


# ── Analysis ─────────────────────────────────────────────────────────────────

def run_analysis(symbol: str, df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Full single-stock pipeline: enrich, report, plot. Pass `df` to skip refetch."""
    print(f"\n{'=' * 60}\n  Analysing {symbol}\n{'=' * 60}")
    if df is None:
        df = fetch_stock_data(symbol, period="1y")
    df = enrich(df)

    # pandas stubs union `df[col]` as `Series | DataFrame`; for a single
    # string key it is always a Series at runtime.
    sharpe = compute_sharpe_ratio(df["Daily_Return"])  # pyright: ignore[reportArgumentType]
    dd = compute_max_drawdown(df["Cumulative_Return"])  # pyright: ignore[reportArgumentType]

    # `Index.__getitem__` returns `Index | scalar`; stubs union the two so
    # the scalar (always Timestamp here on a DatetimeIndex) can't be inferred.
    print(f"  Period:               "
          f"{pd.Timestamp(df.index[0]).date()} -> "  # pyright: ignore[reportArgumentType]
          f"{pd.Timestamp(df.index[-1]).date()}")  # pyright: ignore[reportArgumentType]
    print(f"  Total Return:         {df['Cumulative_Return'].iloc[-1] * 100:.1f}%")
    print(f"  Annualised Vol:       {df['Daily_Return'].std() * np.sqrt(TRADING_DAYS) * 100:.1f}%")
    print(f"  Sharpe Ratio:         {sharpe}")
    print(f"  Max Drawdown:         {dd['max_drawdown']}%  ({dd['peak_date']} -> {dd['trough_date']})")
    print(f"  Avg Daily Volume:     {df['Volume'].mean():,.0f} shares")
    print(f"  Close vs SMA-200:     {'ABOVE' if df['Close'].iloc[-1] > df['SMA_200'].iloc[-1] else 'BELOW'}")

    plot_analysis(df, symbol)
    return df


def compare_stocks(symbols: list[str], frames: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Compare several stocks on key metrics, sorted by Sharpe. Foundation of a screener."""
    if frames is None:
        frames = fetch_many(symbols)

    results = []
    for symbol, raw in frames.items():
        df = enrich(raw)
        # pandas stubs union `df[col]` as `Series | DataFrame`; always Series
        # for a single string key. See run_analysis() above for the same pattern.
        dd = compute_max_drawdown(df["Cumulative_Return"])  # pyright: ignore[reportArgumentType]
        results.append({
            "Symbol": symbol,
            "Total_Return_%": round(df["Cumulative_Return"].iloc[-1] * 100, 1),
            "Annualised_Vol_%": round(df["Daily_Return"].std() * np.sqrt(TRADING_DAYS) * 100, 1),
            "Sharpe": compute_sharpe_ratio(df["Daily_Return"]),  # pyright: ignore[reportArgumentType]
            "Max_Drawdown_%": dd["max_drawdown"],
            "Avg_Volume_M": round(df["Volume"].mean() / 1e6, 2),
            "Above_SMA200": bool(df["Close"].iloc[-1] > df["SMA_200"].iloc[-1]),
        })

    if not results:
        print("  [WARN] No stocks succeeded.")
        return pd.DataFrame()

    comparison = pd.DataFrame(results).set_index("Symbol").sort_values("Sharpe", ascending=False)
    print(f"\n  STOCK COMPARISON (by Sharpe)\n{comparison.to_string()}")
    return comparison


# ── Plotting ─────────────────────────────────────────────────────────────────

def plot_analysis(df: pd.DataFrame, symbol: str) -> None:
    """4-panel chart: price+MAs, cumulative return, drawdown, volume."""
    fig, axes = plt.subplots(4, 1, figsize=(12, 14), sharex=True)
    fig.suptitle(f"{symbol} - Week 1 Analysis", fontsize=14, fontweight="bold")

    ax1 = axes[0]
    ax1.plot(df.index, df["Close"], label="Close", color="#2563EB", linewidth=1.2)
    ax1.plot(df.index, df["SMA_20"], label="SMA-20", color="#F59E0B", linewidth=1, linestyle="--")
    ax1.plot(df.index, df["SMA_50"], label="SMA-50", color="#10B981", linewidth=1, linestyle="--")
    ax1.set_ylabel("Price")
    ax1.legend(fontsize=8)
    ax1.set_title("Price with Moving Averages")
    ax1.grid(alpha=0.3)

    ax2 = axes[1]
    cum_ret = df["Cumulative_Return"] * 100
    ax2.fill_between(df.index, cum_ret, 0, where=(cum_ret >= 0), color="#10B981", alpha=0.3)
    ax2.fill_between(df.index, cum_ret, 0, where=(cum_ret < 0), color="#EF4444", alpha=0.3)
    ax2.plot(df.index, cum_ret, color="#1F2937", linewidth=1)
    ax2.axhline(0, color="#6B7280", linewidth=0.5)
    ax2.set_ylabel("Return (%)")
    ax2.set_title("Cumulative Return")
    ax2.grid(alpha=0.3)

    ax3 = axes[2]
    dd_series = df["Cumulative_Return"].pipe(lambda cr: (1 + cr) / (1 + cr).cummax() - 1) * 100
    ax3.fill_between(df.index, dd_series, 0, color="#EF4444", alpha=0.4)
    ax3.plot(df.index, dd_series, color="#DC2626", linewidth=0.8)
    ax3.set_ylabel("Drawdown (%)")
    ax3.set_title("Drawdown")
    ax3.grid(alpha=0.3)

    ax4 = axes[3]
    colors = ["#EF4444" if r > 2 else "#93C5FD" for r in df["Volume_Ratio"].fillna(1)]
    ax4.bar(df.index, df["Volume"] / 1e6, color=colors, width=1, alpha=0.8)
    ax4.plot(df.index, df["Volume_SMA_20"] / 1e6, color="#1D4ED8", linewidth=1, label="20d avg")
    ax4.set_ylabel("Volume (M)")
    ax4.set_title("Volume (red = spike > 2x average)")
    ax4.legend(fontsize=8)
    ax4.grid(alpha=0.3)

    plt.tight_layout()
    filename = f"{symbol.replace('.', '_')}_week1_analysis.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  [CHART] saved -> {filename}")
    plt.close(fig)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    nifty_sample = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS",
        "INFY.NS", "ICICIBANK.NS", "WIPRO.NS",
    ]

    # One concurrent batch fetch, reused for both per-stock analysis and comparison.
    frames = fetch_many(nifty_sample, period="1y")

    for symbol, raw in frames.items():
        run_analysis(symbol, df=raw)

    print(f"\n{'=' * 60}\n  COMPARISON: NIFTY 50 large caps\n{'=' * 60}")
    comparison_df = compare_stocks(nifty_sample, frames=frames)
    comparison_df.to_csv("nifty_comparison.csv")
    print("\n[SAVED] nifty_comparison.csv")
