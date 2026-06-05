"""Characterization — turn a daily OHLCV history into the statistics used to
classify a stock's behavior (T-002).

The headline metric is the Hurst exponent (rescaled-range method) computed on
*daily returns*: a random-walk return series gives H ≈ 0.5, persistent
(trending) returns give H > 0.5, and mean-reverting returns give H < 0.5.

See BACKLOG.md T-002 for the full specification.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

# 14-period ATR is the conventional default.
_ATR_PERIOD = 14


def _daily_returns(close: pd.Series) -> pd.Series:
    """Simple daily returns, with the leading NaN dropped."""
    return close.pct_change().dropna()


def hurst_exponent(returns: pd.Series | np.ndarray) -> float:
    """Hurst exponent of a return series via rescaled-range (R/S) analysis.

    Returns ``nan`` when there are too few points to estimate a slope.
    """
    series = np.asarray(returns, dtype=float)
    series = series[np.isfinite(series)]
    n = len(series)
    if n < 20:
        return float("nan")

    # Window sizes spaced ~evenly in log space, from 8 up to half the series.
    max_window = n // 2
    windows = np.unique(np.floor(np.logspace(np.log10(8), np.log10(max_window), 12)))
    windows = windows[windows >= 8].astype(int)

    log_w: list[float] = []
    log_rs: list[float] = []
    for w in windows:
        n_chunks = n // w
        if n_chunks < 1:
            continue
        rs_values = []
        for i in range(n_chunks):
            chunk = series[i * w : (i + 1) * w]
            deviations = np.cumsum(chunk - chunk.mean())
            spread = deviations.max() - deviations.min()
            scale = chunk.std()
            if scale > 0:
                rs_values.append(spread / scale)
        if rs_values:
            log_w.append(np.log(w))
            log_rs.append(np.log(np.mean(rs_values)))

    if len(log_rs) < 2:
        return float("nan")
    slope = np.polyfit(log_w, log_rs, 1)[0]
    return float(slope)


def avg_atr_pct(df: pd.DataFrame, period: int = _ATR_PERIOD) -> float:
    """Average True Range over ``period`` bars, expressed as a % of close.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|).
    """
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(period).mean()
    return float((atr / df["close"]).mean() * 100)


def lag1_autocorr(returns: pd.Series) -> float:
    """Lag-1 autocorrelation of a return series."""
    return float(returns.autocorr(lag=1))


def max_drawdown(close: pd.Series) -> float:
    """Largest peak-to-trough decline, as a negative fraction (e.g. -0.42)."""
    running_max = close.cummax()
    drawdown = close / running_max - 1.0
    return float(drawdown.min())


def classify_hurst(hurst: float) -> str:
    """Map a Hurst exponent to a behavior label using config thresholds."""
    if not np.isfinite(hurst):
        return "Unknown"
    if hurst >= config.HURST_TREND_MIN:
        return "Trending"
    if hurst <= config.HURST_REVERT_MAX:
        return "Mean-Reverting"
    return "Random"


def characterize(df: pd.DataFrame) -> dict | None:
    """Compute behavior statistics for one ticker's daily OHLCV history.

    Args:
        df: Daily OHLCV with columns ``open, high, low, close, volume``.

    Returns:
        A dict of metrics, or ``None`` when there are fewer than
        ``config.MIN_HISTORY_DAYS`` rows to characterize reliably.

        Keys: ``hurst``, ``avg_atr_pct``, ``autocorr``, ``avg_volume``,
        ``max_drawdown``, ``history_days``, ``classification``.
    """
    if len(df) < config.MIN_HISTORY_DAYS:
        return None

    returns = _daily_returns(df["close"])
    hurst = hurst_exponent(returns)

    return {
        "hurst": hurst,
        "avg_atr_pct": avg_atr_pct(df),
        "autocorr": lag1_autocorr(returns),
        "avg_volume": float(df["volume"].mean()),
        "max_drawdown": max_drawdown(df["close"]),
        "history_days": len(df),
        "classification": classify_hurst(hurst),
    }
