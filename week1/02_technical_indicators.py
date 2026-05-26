"""Week 1, Day 3-4 — Technical indicators & signal generation.

RSI, MACD and Bollinger Bands implemented from scratch (no pandas-ta
dependency: its column names drift between versions), plus a confluence-based
buy/sell signal generator and a strategy evaluator.

Run:  python 02_technical_indicators.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

TRADING_DAYS = 252
RISK_FREE_RATE = 0.065


# ── Indicators ───────────────────────────────────────────────────────────────

# File-level Pyright relaxation. Reasons:
#  - `df["col"]` is typed as `Series | DataFrame` (duplicate-column paranoia)
#    -> reportArgumentType / reportReturnType / reportAssignmentType.
#  - `ewm(...).mean()` is typed as `float | Series` -> reportAttributeAccessIssue
#    on .fillna() / .pct_change() etc.
#  - `Index.__getitem__` returns `Index | scalar` -> .date() unknown on Index.
# Every site is a stub bug — runtime is correct. week1/ is educational code,
# not the production path (that's week2/core/), so relaxing the strict pandas
# checks here keeps the file readable while keeping the strict checks for the
# rest of the project.
# pyright: reportArgumentType=false, reportReturnType=false, reportAttributeAccessIssue=false


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (0-100). EMA-smoothed gains/losses."""
    delta = close.diff()
    avg_gain = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    avg_loss = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD line, signal line and histogram."""
    macd_line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({
        "MACD": macd_line,
        "MACD_Signal": signal_line,
        "MACD_Histogram": macd_line - signal_line,
    })


def compute_bollinger(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands plus %B (position in band) and bandwidth (squeeze)."""
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper, lower = middle + std_dev * std, middle - std_dev * std
    return pd.DataFrame({
        "BB_Upper": upper,
        "BB_Middle": middle,
        "BB_Lower": lower,
        "BB_PercentB": (close - lower) / (upper - lower),
        "BB_Bandwidth": (upper - lower) / middle,
    })


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Attach RSI, MACD and Bollinger columns to an OHLCV frame."""
    df = df.copy()
    df["RSI"] = compute_rsi(df["Close"])
    return df.join(compute_macd(df["Close"])).join(compute_bollinger(df["Close"]))


# ── Signal generation ────────────────────────────────────────────────────────

def generate_signals(df: pd.DataFrame, rsi_buy: float = 35, rsi_sell: float = 65) -> pd.DataFrame:
    """Confluence signals: BUY = RSI oversold + MACD cross up; SELL = inverse.

    Position is derived vectorially: set 1 on a buy, 0 on a sell, then
    forward-fill — no per-row Python loop.
    """
    df = df.copy()

    macd, sig = df["MACD"], df["MACD_Signal"]
    macd_cross_up = (macd > sig) & (macd.shift(1) <= sig.shift(1))
    macd_cross_down = (macd < sig) & (macd.shift(1) >= sig.shift(1))

    df["Buy_Signal"] = (df["RSI"] < rsi_buy) & macd_cross_up
    df["Sell_Signal"] = (df["RSI"] > rsi_sell) & macd_cross_down

    position = pd.Series(np.nan, index=df.index)
    position[df["Buy_Signal"]] = 1.0
    position[df["Sell_Signal"]] = 0.0
    df["Position"] = position.ffill().fillna(0.0)

    df["Strategy_Return"] = df["Daily_Return"] * df["Position"].shift(1)
    df["Strategy_Cumulative"] = (1 + df["Strategy_Return"].fillna(0)).cumprod() - 1
    return df


# ── Metrics ──────────────────────────────────────────────────────────────────

def compute_sharpe_ratio(returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    returns = returns.dropna()
    if returns.empty or returns.std() == 0:
        return 0.0
    excess = returns - risk_free_rate / TRADING_DAYS
    return round(excess.mean() / excess.std() * np.sqrt(TRADING_DAYS), 3)


def compute_max_drawdown(cumulative_returns: pd.Series) -> dict:
    wealth = 1 + cumulative_returns
    drawdown = (wealth - wealth.cummax()) / wealth.cummax()
    return {"max_drawdown": round(drawdown.min() * 100, 2)}


def extract_trades(df: pd.DataFrame) -> pd.DataFrame:
    """Pair each entry with its next exit into a per-trade DataFrame."""
    entries = df.index[df["Buy_Signal"] & (df["Position"].shift(1).fillna(0) == 0)]
    exits = df.index[df["Sell_Signal"] & (df["Position"].shift(1).fillna(0) == 1)]

    trades = []
    for entry in entries:
        future_exits = exits[exits > entry]
        if len(future_exits) == 0:
            continue
        exit_date = future_exits[0]
        entry_price, exit_price = df.loc[entry, "Close"], df.loc[exit_date, "Close"]
        trades.append({
            "entry": entry.date(),
            "exit": exit_date.date(),
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "return_%": round((exit_price - entry_price) / entry_price * 100, 2),
            "holding_days": (exit_date - entry).days,
        })
    return pd.DataFrame(trades)


def evaluate_strategy(df: pd.DataFrame, symbol: str) -> tuple[dict, pd.DataFrame]:
    """Score the strategy against a buy-and-hold benchmark."""
    trades_df = extract_trades(df)

    if len(trades_df) > 0:
        wins = trades_df[trades_df["return_%"] > 0]["return_%"]
        losses = trades_df[trades_df["return_%"] < 0]["return_%"]
        win_rate = (trades_df["return_%"] > 0).mean() * 100
        avg_win = wins.mean() if len(wins) else 0.0
        avg_loss = losses.mean() if len(losses) else 0.0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")
    else:
        win_rate = profit_factor = avg_win = avg_loss = 0.0

    results = {
        "Symbol": symbol,
        "Total Trades": len(trades_df),
        "Win Rate %": round(win_rate, 1),
        "Profit Factor": round(profit_factor, 2),
        "Strategy Return %": round(df["Strategy_Cumulative"].iloc[-1] * 100, 1),
        "Buy&Hold Return %": round(df["Cumulative_Return"].iloc[-1] * 100, 1),
        "Strategy Sharpe": compute_sharpe_ratio(df["Strategy_Return"]),
        "Buy&Hold Sharpe": compute_sharpe_ratio(df["Daily_Return"]),
        "Strategy Max DD %": compute_max_drawdown(df["Strategy_Cumulative"])["max_drawdown"],
        "Buy&Hold Max DD %": compute_max_drawdown(df["Cumulative_Return"])["max_drawdown"],
    }

    print(f"\n{'=' * 50}\n  STRATEGY EVALUATION: {symbol}\n{'=' * 50}")
    print(f"  Trades: {results['Total Trades']} | Win Rate: {results['Win Rate %']}% "
          f"| Profit Factor: {results['Profit Factor']}")
    print(f"  {'':16}{'STRATEGY':>10}{'BUY&HOLD':>11}")
    print(f"  Total Return:   {results['Strategy Return %']:>9.1f}%{results['Buy&Hold Return %']:>10.1f}%")
    print(f"  Sharpe Ratio:   {results['Strategy Sharpe']:>10.3f}{results['Buy&Hold Sharpe']:>11.3f}")
    print(f"  Max Drawdown:   {results['Strategy Max DD %']:>9.2f}%{results['Buy&Hold Max DD %']:>10.2f}%")
    return results, trades_df


# ── Plotting ─────────────────────────────────────────────────────────────────

def plot_signals(df: pd.DataFrame, symbol: str) -> None:
    """Price+signals, RSI, MACD and strategy-vs-benchmark panels."""
    fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1.5, 1.5, 1.5]})
    fig.suptitle(f"{symbol} - Signal Generation", fontsize=14, fontweight="bold")

    ax1 = axes[0]
    ax1.plot(df.index, df["Close"], color="#1F2937", linewidth=1.2, label="Close", zorder=3)
    for band, style in [("BB_Upper", "--"), ("BB_Middle", "--"), ("BB_Lower", "--")]:
        ax1.plot(df.index, df[band], color="#93C5FD", linewidth=0.8, linestyle=style)
    buys, sells = df[df["Buy_Signal"]], df[df["Sell_Signal"]]
    ax1.scatter(buys.index, buys["Close"], marker="^", color="#10B981", s=100, zorder=5,
                label=f"Buy ({len(buys)})")
    ax1.scatter(sells.index, sells["Close"], marker="v", color="#EF4444", s=100, zorder=5,
                label=f"Sell ({len(sells)})")
    ax1.set_ylabel("Price")
    ax1.legend(fontsize=8, loc="upper left")
    ax1.grid(alpha=0.3)

    ax2 = axes[1]
    ax2.plot(df.index, df["RSI"], color="#8B5CF6", linewidth=1.2)
    ax2.axhline(70, color="#EF4444", linewidth=0.8, linestyle="--", alpha=0.7)
    ax2.axhline(30, color="#10B981", linewidth=0.8, linestyle="--", alpha=0.7)
    ax2.set_ylabel("RSI")
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.3)

    ax3 = axes[2]
    ax3.plot(df.index, df["MACD"], color="#2563EB", linewidth=1.2, label="MACD")
    ax3.plot(df.index, df["MACD_Signal"], color="#F59E0B", linewidth=1.0, label="Signal")
    hist = df["MACD_Histogram"]
    ax3.bar(df.index, hist, color=["#10B981" if v >= 0 else "#EF4444" for v in hist],
            alpha=0.5, width=1)
    ax3.axhline(0, color="#6B7280", linewidth=0.5)
    ax3.set_ylabel("MACD")
    ax3.legend(fontsize=8)
    ax3.grid(alpha=0.3)

    ax4 = axes[3]
    ax4.plot(df.index, df["Cumulative_Return"] * 100, color="#6B7280", linewidth=1.2,
             label="Buy & Hold", linestyle="--")
    ax4.plot(df.index, df["Strategy_Cumulative"] * 100, color="#2563EB", linewidth=1.4,
             label="Strategy")
    ax4.axhline(0, color="#6B7280", linewidth=0.5)
    ax4.set_ylabel("Return (%)")
    ax4.legend(fontsize=8)
    ax4.grid(alpha=0.3)

    plt.tight_layout()
    filename = f"{symbol.replace('.', '_')}_signals.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  [CHART] saved -> {filename}")
    plt.close(fig)


# ── Main ─────────────────────────────────────────────────────────────────────

def run_indicator_analysis(symbol: str = "INFY.NS") -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    print(f"{'=' * 60}\n  Week 1 Day 3-4 - Indicators & Signals: {symbol}\n{'=' * 60}")

    df = yf.Ticker(symbol).history(period="2y")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df["Daily_Return"] = df["Close"].pct_change()
    df["Cumulative_Return"] = (1 + df["Daily_Return"]).cumprod() - 1

    df = add_indicators(df)
    df = generate_signals(df)

    latest = df.iloc[-1]
    signal = "BUY" if latest["Buy_Signal"] else "SELL" if latest["Sell_Signal"] else "HOLD"
    print(f"  Buy signals: {int(df['Buy_Signal'].sum())} | "
          f"Sell signals: {int(df['Sell_Signal'].sum())} (2y)")
    print(f"  Latest: RSI {latest['RSI']:.1f} | MACD {latest['MACD']:.4f} | Signal -> {signal}")

    results, trades_df = evaluate_strategy(df, symbol)
    plot_signals(df, symbol)
    return df, results, trades_df


if __name__ == "__main__":
    run_indicator_analysis("INFY.NS")
