"""Week 1, Day 5-7 — Backtesting & overfitting prevention.

Uses vectorbt for look-ahead-safe backtests with transaction costs, plus
in-sample/out-of-sample parameter optimisation and walk-forward validation.

Run:  python 03_backtesting.py
"""
from __future__ import annotations

import warnings
from typing import Any

import pandas as pd
# vectorbt is intentionally not installed in CI (numba wheels lag on the very
# latest Python); the `vbt: Any = _vbt` alias below means callers don't need
# the real types. Both checkers get suppressions so a clean local install
# AND a CI-without-vectorbt path both pass.
import vectorbt as _vbt  # pyrefly: ignore[missing-import]  # pyright: ignore[reportMissingImports]
import yfinance as yf
import matplotlib.pyplot as plt

# vectorbt's bundled type stubs are wrong in multiple places — e.g. IndicatorFactory
# .RSI.run() returns the wrong type, Portfolio is missing sharpe_ratio / max_drawdown
# / drawdown / win_rate, and Trades is mistyped as a function. The runtime is fine;
# re-binding through `Any` here silences every site at once instead of sprinkling
# 13 # pyrefly: ignore[missing-attribute] comments through the file.
vbt: Any = _vbt

warnings.filterwarnings("ignore")

FEES = 0.0003       # 0.03% per trade (Zerodha flat fee)
SLIPPAGE = 0.001    # 0.1% real-world execution cost
INIT_CASH = 100_000


def fetch_data(symbol: str, period: str = "3y") -> pd.Series:
    """Fetch the Close-price series for one ticker."""
    df = yf.Ticker(symbol).history(period=period)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    # pandas stubs union `df[col]` as `Series | DataFrame`; single string key
    # is always Series at runtime.
    return df["Close"]  # pyright: ignore[reportReturnType]


# Return type is annotated as `Any` (not `vbt.Portfolio`): `vbt` is `Any`-typed
# at the top of the module so the wrong vectorbt stubs don't poison every site,
# and you can't use a value of type `Any` as a type annotation. The actual
# returned object IS a `vectorbt.Portfolio` at runtime.
def _run_portfolio(close: pd.Series, entries: pd.Series, exits: pd.Series) -> Any:
    """Build a vectorbt portfolio with standard costs applied."""
    return vbt.Portfolio.from_signals(
        close=close, entries=entries, exits=exits,
        fees=FEES, slippage=SLIPPAGE, init_cash=INIT_CASH, freq="1D",
    )


# ── Parameter optimisation ───────────────────────────────────────────────────

def run_parameter_optimisation(symbol: str) -> tuple[pd.DataFrame, int, int]:
    """Grid-search RSI thresholds in-sample, then validate the best out-of-sample."""
    print(f"\n{'=' * 55}\n  PARAMETER OPTIMISATION: {symbol}\n{'=' * 55}")

    close = fetch_data(symbol, period="4y")
    split_idx = int(len(close) * 0.70)
    is_close, oos_close = close.iloc[:split_idx], close.iloc[split_idx:]
    print(f"  In-sample:     {is_close.index[0].date()} -> {is_close.index[-1].date()} "
          f"({len(is_close)}d)")
    print(f"  Out-of-sample: {oos_close.index[0].date()} -> {oos_close.index[-1].date()} "
          f"({len(oos_close)}d)")

    # RSI(14) is independent of the buy/sell thresholds — compute it ONCE,
    # not once per grid cell.
    rsi_is = vbt.RSI.run(is_close, window=14).rsi

    results = []
    for buy_th in (25, 30, 35, 40):
        for sell_th in (60, 65, 70, 75):
            if buy_th >= sell_th:
                continue
            pf = _run_portfolio(is_close, rsi_is < buy_th, rsi_is > sell_th)
            results.append({
                "buy_threshold": buy_th,
                "sell_threshold": sell_th,
                "IS_sharpe": round(pf.sharpe_ratio(), 3),
                "IS_return_%": round(pf.total_return() * 100, 1),
                "IS_max_dd_%": round(pf.max_drawdown() * 100, 1),
                "IS_trades": pf.trades.count(),
            })

    results_df = pd.DataFrame(results).sort_values("IS_sharpe", ascending=False)
    print(f"\n  IN-SAMPLE RESULTS (top 8 by Sharpe)")
    print(results_df.head(8).to_string(index=False))

    best = results_df.iloc[0]
    best_buy, best_sell = int(best["buy_threshold"]), int(best["sell_threshold"])
    print(f"\n  Best parameters: Buy < {best_buy}, Sell > {best_sell} "
          f"(IS Sharpe {best['IS_sharpe']})")

    rsi_oos = vbt.RSI.run(oos_close, window=14).rsi
    pf_oos = _run_portfolio(oos_close, rsi_oos < best_buy, rsi_oos > best_sell)
    oos_sharpe = round(pf_oos.sharpe_ratio(), 3)
    print(f"  OUT-OF-SAMPLE: Sharpe {oos_sharpe} | Return {pf_oos.total_return() * 100:.1f}%")

    degradation = (best["IS_sharpe"] - oos_sharpe) / abs(best["IS_sharpe"]) * 100 \
        if best["IS_sharpe"] else 0
    verdict = ("ROBUST" if degradation < 30 else
               "MODERATE degradation - use with caution" if degradation < 60 else
               "HIGH degradation - likely OVERFITTED")
    print(f"  IS->OOS degradation: {degradation:.0f}%  =>  {verdict}")
    return results_df, best_buy, best_sell


# ── Walk-forward validation ──────────────────────────────────────────────────

def walk_forward_validation(symbol: str, n_windows: int = 5) -> pd.DataFrame:
    """Repeat the IS/OOS split across rolling windows to test consistency over time."""
    print(f"\n{'=' * 55}\n  WALK-FORWARD VALIDATION: {symbol} ({n_windows} windows)\n{'=' * 55}")

    close = fetch_data(symbol, period="4y")
    window_size = len(close) // (n_windows + 1)

    rows = []
    for w in range(n_windows):
        start = w * (window_size // 2)
        end = start + window_size
        if end > len(close):
            break
        window = close.iloc[start:end]
        train_end = int(len(window) * 0.70)
        train, test = window.iloc[:train_end], window.iloc[train_end:]

        for data, label in ((train, "IS"), (test, "OOS")):
            rsi = vbt.RSI.run(data, window=14).rsi
            pf = _run_portfolio(data, rsi < 35, rsi > 65)
            rows.append({
                "window": w + 1, "type": label,
                "start": data.index[0].date(), "end": data.index[-1].date(),
                "sharpe": round(pf.sharpe_ratio(), 3),
                "return_%": round(pf.total_return() * 100, 1),
            })

    wf_df = pd.DataFrame(rows)
    print(wf_df.to_string(index=False))

    oos = wf_df[wf_df["type"] == "OOS"]
    consistency = (oos["sharpe"] > 0).mean()
    verdict = ("CONSISTENT" if consistency >= 0.8 else
               "MIXED" if consistency >= 0.6 else "INCONSISTENT")
    print(f"\n  OOS avg Sharpe: {oos['sharpe'].mean():.3f} | "
          f"Profitable windows: {(oos['sharpe'] > 0).sum()}/{len(oos)}  =>  {verdict}")
    return wf_df


# ── Full backtest ────────────────────────────────────────────────────────────

def run_full_backtest(symbol: str, buy_rsi: int = 30, sell_rsi: int = 70) -> Any:
    """Complete backtest with key metrics and an equity-curve chart."""
    print(f"\n{'=' * 55}\n  FULL BACKTEST: {symbol} (RSI {buy_rsi}/{sell_rsi})\n{'=' * 55}")

    close = fetch_data(symbol, period="3y")
    rsi = vbt.RSI.run(close, window=14).rsi
    pf = _run_portfolio(close, rsi < buy_rsi, rsi > sell_rsi)

    bnh_return = (close.iloc[-1] / close.iloc[0] - 1) * 100
    print(f"  Total Return:  {pf.total_return() * 100:.1f}%   Sharpe: {pf.sharpe_ratio():.3f}")
    print(f"  Max Drawdown:  {pf.max_drawdown() * 100:.1f}%   Trades: {pf.trades.count()}")
    print(f"  Win Rate:      {pf.trades.win_rate() * 100:.1f}%")
    print(f"  Buy&Hold:      {bnh_return:.1f}%   Alpha: {pf.total_return() * 100 - bnh_return:.1f}%")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    equity = pf.value()
    ax1.plot(equity.index, equity, label="Strategy", color="#2563EB", linewidth=1.5)
    ax1.plot(close.index, close / close.iloc[0] * INIT_CASH, label="Buy & Hold",
             color="#9CA3AF", linestyle="--", linewidth=1)
    ax1.set_ylabel("Portfolio Value")
    ax1.set_title(f"{symbol} - Strategy vs Buy & Hold")
    ax1.legend()
    ax1.grid(alpha=0.3)

    dd = pf.drawdown() * 100
    ax2.fill_between(dd.index, dd, 0, color="#EF4444", alpha=0.4)
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    filename = f"{symbol.replace('.', '_')}_backtest.png"
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  [CHART] saved -> {filename}")
    plt.close(fig)
    return pf


if __name__ == "__main__":
    symbol = "INFY.NS"
    _, best_buy, best_sell = run_parameter_optimisation(symbol)
    walk_forward_validation(symbol)
    run_full_backtest(symbol, buy_rsi=best_buy, sell_rsi=best_sell)
