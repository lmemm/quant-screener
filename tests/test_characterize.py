"""Tests for the characterization module (T-002).

These build synthetic in-memory OHLCV frames (never the real drive). Random
series use a fixed seed so the statistical assertions are deterministic.
"""

import numpy as np
import pandas as pd
import pytest

from src.screener import config
from src.screener.characterize import (
    _expected_rs,
    avg_atr_pct,
    characterize,
    classify_hurst,
    hurst_exponent,
    lag1_autocorr,
    max_drawdown,
)


def _fgn(n: int, H: float, seed: int) -> np.ndarray:
    """Exact fractional Gaussian noise of length n with Hurst H (Cholesky).

    fGn is the increment series of fractional Brownian motion; its theoretical
    Hurst exponent is exactly H, so it is the right synthetic test bed for the
    estimator (daily returns are such an increment series). Kept small (single
    series, modest n) so the suite stays fast — see scratch/ for the full sweep.
    """
    k = np.arange(n)
    gamma = 0.5 * (
        np.abs(k - 1) ** (2 * H) - 2 * np.abs(k) ** (2 * H) + np.abs(k + 1) ** (2 * H)
    )
    cov = np.empty((n, n))
    for i in range(n):
        cov[i] = gamma[np.abs(np.arange(n) - i)]
    chol = np.linalg.cholesky(cov)
    return chol @ np.random.default_rng(seed).standard_normal(n)


def _ohlcv_from_close(close: np.ndarray, volume: float = 1_000_000) -> pd.DataFrame:
    """Wrap a close-price path in a plausible OHLCV frame."""
    close = pd.Series(close)
    idx = pd.bdate_range("2020-01-01", periods=len(close), name="date")
    high = close * 1.01
    low = close * 0.99
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]).to_numpy(),
            "high": high.to_numpy(),
            "low": low.to_numpy(),
            "close": close.to_numpy(),
            "volume": np.full(len(close), volume),
        },
        index=idx,
    )


def _random_walk(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100 + np.cumsum(rng.normal(0, 1, n))


def _trending(n: int, seed: int) -> np.ndarray:
    """Persistent returns (AR(1), phi>0) → trending price."""
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = 0.6 * r[i - 1] + rng.normal(0, 1)
    return 100 + np.cumsum(r)


def _mean_reverting(n: int, seed: int) -> np.ndarray:
    """Anti-persistent returns (AR(1), phi<0) → choppy price."""
    rng = np.random.default_rng(seed)
    r = np.zeros(n)
    for i in range(1, n):
        r[i] = -0.6 * r[i - 1] + rng.normal(0, 1)
    return 100 + np.cumsum(r)


# ── characterize() contract ──────────────────────────────────────────────────

def test_short_input_returns_none():
    df = _ohlcv_from_close(_random_walk(config.MIN_HISTORY_DAYS - 1, seed=1))
    assert characterize(df) is None


def test_normal_input_returns_all_metrics():
    df = _ohlcv_from_close(_random_walk(config.MIN_HISTORY_DAYS + 100, seed=2))
    result = characterize(df)
    assert result is not None
    assert set(result) == {
        "hurst", "avg_atr_pct", "autocorr", "avg_volume", "avg_dollar_volume",
        "max_drawdown", "history_days", "classification",
    }
    assert result["history_days"] == len(df)


def test_avg_volume_is_the_mean():
    df = _ohlcv_from_close(_random_walk(600, seed=3), volume=750_000)
    assert characterize(df)["avg_volume"] == pytest.approx(750_000)


def test_avg_dollar_volume_is_price_times_shares():
    df = _ohlcv_from_close(_random_walk(600, seed=4), volume=1_000_000)
    expected = float((df["close"] * df["volume"]).mean())
    assert characterize(df)["avg_dollar_volume"] == pytest.approx(expected)


# ── individual metrics ───────────────────────────────────────────────────────

def test_max_drawdown_on_known_series():
    # Rise to 100, fall to 60 → -40% drawdown.
    close = pd.Series([50, 80, 100, 90, 60, 70])
    assert max_drawdown(close) == pytest.approx(-0.4)


def test_max_drawdown_monotonic_increase_is_zero():
    close = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert max_drawdown(close) == pytest.approx(0.0)


def test_avg_atr_pct_is_positive():
    df = _ohlcv_from_close(_random_walk(600, seed=4))
    assert avg_atr_pct(df) > 0


def test_lag1_autocorr_detects_persistence():
    # Strongly persistent returns → positive lag-1 autocorrelation.
    trending = pd.Series(_trending(600, seed=5))
    reverting = pd.Series(_mean_reverting(600, seed=5))
    assert lag1_autocorr(trending.pct_change().dropna()) > 0
    assert lag1_autocorr(reverting.pct_change().dropna()) < 0


def test_hurst_orders_trending_above_mean_reverting():
    # Test the estimator on return series directly: persistent (AR(1) phi>0),
    # i.i.d., and anti-persistent (phi<0) returns must order H high→low.
    n = 2000
    rng = np.random.default_rng(7)
    iid = rng.normal(0, 1, n)
    persistent = np.zeros(n)
    anti = np.zeros(n)
    for i in range(1, n):
        persistent[i] = 0.6 * persistent[i - 1] + rng.normal(0, 1)
        anti[i] = -0.6 * anti[i - 1] + rng.normal(0, 1)

    h_trend = hurst_exponent(persistent)
    h_rand = hurst_exponent(iid)
    h_revert = hurst_exponent(anti)
    assert h_trend > h_rand > h_revert
    # i.i.d. returns should land near 0.5.
    assert 0.4 < h_rand < 0.6


def test_hurst_too_short_is_nan():
    assert np.isnan(hurst_exponent(np.array([0.1, -0.2, 0.05])))


# ── Hurst bias correction (T-009) ────────────────────────────────────────────

def test_hurst_unbiased_on_random_walk():
    """A true random walk must estimate near 0.5, not the ~0.55 a naive R/S
    slope returns. This is the regression guard for the T-009 upward bias that
    mislabeled ~half of all random walks as 'Trending'."""
    estimates = [
        hurst_exponent(np.random.default_rng(s).normal(0, 1, 2000))
        for s in range(20)
    ]
    mean_est = float(np.mean(estimates))
    # Pre-fix this averaged ~0.548 (well above the 0.55 trending threshold);
    # the corrected estimator centers just under 0.5.
    assert 0.44 < mean_est < 0.52, mean_est


def test_random_walks_rarely_labeled_trending():
    """The whole pipeline keys off the label: genuine noise must not flood the
    'Trending' bucket (pre-fix ~46–62% did)."""
    labels = [
        classify_hurst(hurst_exponent(np.random.default_rng(s).normal(0, 1, 1500)))
        for s in range(30)
    ]
    trending = labels.count("Trending")
    assert trending <= 6, f"{trending}/30 random walks labeled Trending"


def test_hurst_tracks_known_fgn():
    """On fractional Gaussian noise of known H, the estimate tracks the truth:
    persistent H=0.6 reads higher than anti-persistent H=0.4, and the mean over
    a few draws stays within a reasonable band of each true value. Averaged over
    seeds because a single fGn draw has ~±0.05 estimator variance — the bias
    correction targets the central tendency, which is what this guards."""
    mean_low = float(np.mean([hurst_exponent(_fgn(1000, H=0.40, seed=s)) for s in range(6)]))
    mean_high = float(np.mean([hurst_exponent(_fgn(1000, H=0.60, seed=s)) for s in range(6)]))
    assert mean_high > mean_low
    assert abs(mean_low - 0.40) < 0.10, mean_low
    assert abs(mean_high - 0.60) < 0.10, mean_high


def test_expected_rs_grows_with_window():
    """The Anis-Lloyd expectation is positive and increasing in window size."""
    vals = [_expected_rs(w) for w in (8, 16, 32, 64, 128)]
    assert all(v > 0 for v in vals)
    assert all(b > a for a, b in zip(vals, vals[1:]))


# ── classification ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "hurst,label",
    [
        (0.70, "Trending"),
        (config.HURST_TREND_MIN, "Trending"),
        (0.50, "Random"),
        (config.HURST_REVERT_MAX, "Mean-Reverting"),
        (0.30, "Mean-Reverting"),
        (float("nan"), "Unknown"),
    ],
)
def test_classify_hurst(hurst, label):
    assert classify_hurst(hurst) == label
