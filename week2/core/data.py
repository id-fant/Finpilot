"""Market-data access for FinPilot — a thin wrapper over yfinance.

WHY a wrapper: the rest of the codebase never imports yfinance directly. One
wrapper means one place to add retries, caching, or to swap to a paid data
provider later — the strategy engine and Celery tasks stay provider-agnostic.

Ported from week1/01_data_foundations.py.
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import yfinance as yf

# Logger name is "core.data" — the LOGGING config routes "core" to the console.
logger = logging.getLogger(__name__)

OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def fetch_ohlcv(symbol: str, period: str = "1y", retries: int = 3) -> pd.DataFrame:
    """Fetch OHLCV price history for one ticker.

    Args:
        symbol: NSE ticker, e.g. "RELIANCE.NS".
        period: yfinance period string ("6mo", "1y", "2y", ...).
        retries: attempts before giving up; each failure backs off longer.

    Returns:
        DataFrame indexed by tz-naive Date, columns Open/High/Low/Close/Volume.

    Raises:
        RuntimeError: if the data could not be fetched after all retries.
    """
    logger.debug("fetch_ohlcv(%s): requesting period=%s, retries=%d",
                 symbol, period, retries)
    last_error = "unknown error"
    for attempt in range(1, retries + 1):
        try:
            df = yf.Ticker(symbol).history(period=period)
            if not df.empty:
                # WHY drop NaN-Close rows: Yahoo sometimes appends a PARTIAL
                # trailing bar (the current session before prices consolidate)
                # carrying volume but NaN OHLC. A NaN close poisons the
                # last-bar signal (price=NaN fails the DecimalField) and every
                # indicator after it. A bar without a close is not a bar.
                df = df.dropna(subset=["Close"])
            if not df.empty:
                # WHY normalise the index: yfinance returns a timezone-AWARE
                # index. pandas comparisons/joins fail when mixing tz-aware and
                # tz-naive timestamps, so we strip the tz to a plain date index.
                df.index = pd.to_datetime(df.index).tz_localize(None)
                df.index.name = "Date"
                # `Index.__getitem__` is `Index | scalar` per stubs; on a
                # DatetimeIndex the scalar is always a Timestamp. Wrap to
                # convince the checker without changing runtime behaviour.
                logger.info("fetch_ohlcv(%s): %d rows, %s to %s (attempt %d)",
                            symbol, len(df),
                            pd.Timestamp(df.index[0]).date(),  # pyright: ignore[reportArgumentType]
                            pd.Timestamp(df.index[-1]).date(),  # pyright: ignore[reportArgumentType]
                            attempt)
                # pandas stubs union `df[list]` as `Series | DataFrame`;
                # list-of-cols lookup is always DataFrame at runtime.
                return df[OHLCV]  # pyright: ignore[reportReturnType]
            last_error = "empty response"
        except Exception as e:  # noqa: BLE001 - yfinance raises many error types
            last_error = str(e)

        # WARNING per attempt — recoverable, a retry follows.
        logger.warning("fetch_ohlcv(%s) attempt %d/%d failed: %s",
                        symbol, attempt, retries, last_error)
        # WHY back off: yfinance is rate-limited. A longer pause after each
        # failure gives the rate limiter time to recover.
        time.sleep(2 * attempt)

    # ERROR — every retry is exhausted; this call is giving up.
    logger.error("fetch_ohlcv(%s): all %d attempts failed, last error: %s",
                  symbol, retries, last_error)
    raise RuntimeError(
        f"Could not fetch {symbol} after {retries} attempts ({last_error})")


def fetch_universe(symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for several tickers, skipping any that fail.

    WHY sequential, not concurrent: Yahoo Finance rate-limits aggressively, and
    a parallel batch tends to get the whole set throttled. A slower loop that
    succeeds beats a fast one that gets 429-ed.

    Args:
        symbols: list of NSE tickers.
        period: yfinance period string applied to every ticker.

    Returns:
        {symbol: DataFrame} for every ticker that fetched successfully. Tickers
        that fail are logged and omitted — one bad symbol never aborts the run.
    """
    logger.info("fetch_universe: fetching %d ticker(s), period=%s",
                len(symbols), period)
    result: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        try:
            result[symbol] = fetch_ohlcv(symbol, period)
        except RuntimeError as e:
            logger.error("fetch_universe: skipping %s — %s", symbol, e)

    failed = len(symbols) - len(result)
    log = logger.warning if failed else logger.info
    log("fetch_universe: %d/%d ticker(s) fetched, %d failed",
        len(result), len(symbols), failed)
    return result
