"""Tests for the single-pass daily cache (T-007).

The headline test is the *equality* test: the cache must reproduce
``data.load_daily_bars`` bit-for-bit. If the single-pass build ever diverges
from the per-ticker loader, that test fails — which is the whole guarantee that
the speedup costs no quality.
"""

from __future__ import annotations

import pandas as pd

from src.screener.cache import (
    build_daily_cache,
    cache_available,
    cached_tickers,
    load_cached_daily,
    load_daily,
    universe_tickers,
)
from src.screener.data import load_daily_bars

START, END = "2025-01-01", "2025-01-31"


def test_cache_matches_loader_exactly(sample_drive, tmp_path):
    # Trust anchor: cache output == live loader output for every sample ticker.
    build_daily_cache(drive_path=sample_drive, cache_dir=tmp_path)
    for ticker in ("AAPL", "MSFT"):
        from_drive = load_daily_bars(ticker, START, END, drive_path=sample_drive)
        from_cache = load_cached_daily(ticker, START, END, cache_dir=tmp_path)
        # check_freq=False: index *freq metadata* is dropped by the parquet
        # round-trip, but every value, dtype, and label must match.
        pd.testing.assert_frame_equal(from_drive, from_cache, check_freq=False)


def test_cache_values_match_expected_fixture(sample_drive, tmp_path, expected_daily):
    build_daily_cache(drive_path=sample_drive, cache_dir=tmp_path)
    aapl = load_cached_daily("AAPL", START, END, cache_dir=tmp_path)
    for date_str, ohlcv in expected_daily["AAPL"].items():
        row = aapl.loc[date_str]
        for field, value in ohlcv.items():
            assert row[field] == value, f"AAPL {date_str} {field}"


def test_build_writes_per_ticker_files(sample_drive, tmp_path):
    assert not cache_available(tmp_path)
    build_daily_cache(drive_path=sample_drive, cache_dir=tmp_path)
    assert cache_available(tmp_path)
    assert cached_tickers(tmp_path) == ["AAPL", "MSFT"]


def test_load_uncached_ticker_returns_empty(sample_drive, tmp_path):
    build_daily_cache(drive_path=sample_drive, cache_dir=tmp_path)
    out = load_cached_daily("ZZZZ", START, END, cache_dir=tmp_path)
    assert out.empty
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]


def test_date_filter_on_read(sample_drive, tmp_path):
    build_daily_cache(drive_path=sample_drive, cache_dir=tmp_path)
    only_second = load_cached_daily("AAPL", "2025-01-03", "2025-01-31", cache_dir=tmp_path)
    assert list(only_second.index.strftime("%Y-%m-%d")) == ["2025-01-03"]


def test_load_daily_prefers_cache_then_falls_back(sample_drive, tmp_path):
    empty_cache = tmp_path / "no_cache"
    # No cache yet -> falls back to the drive and matches the live loader.
    from_drive = load_daily_bars("AAPL", START, END, drive_path=sample_drive)
    fallback = load_daily(
        "AAPL", START, END, drive_path=sample_drive, cache_dir=empty_cache
    )
    pd.testing.assert_frame_equal(from_drive, fallback, check_freq=False)

    # Build the cache -> now load_daily reads it, still identical.
    built = tmp_path / "cache"
    build_daily_cache(drive_path=sample_drive, cache_dir=built)
    from_cache = load_daily("AAPL", START, END, drive_path=sample_drive, cache_dir=built)
    pd.testing.assert_frame_equal(from_drive, from_cache, check_freq=False)


def test_universe_tickers_prefers_cache(sample_drive, tmp_path):
    built = tmp_path / "cache"
    build_daily_cache(drive_path=sample_drive, cache_dir=built)
    assert universe_tickers(sample_drive, built) == ["AAPL", "MSFT"]
    # Without a cache it discovers from the drive instead.
    assert not cache_available(tmp_path / "absent")
    assert universe_tickers(sample_drive, tmp_path / "absent") == ["AAPL", "MSFT"]


def test_empty_drive_builds_empty_cache(tmp_path):
    drive = tmp_path / "empty_drive"
    drive.mkdir()
    out = tmp_path / "cache"
    build_daily_cache(drive_path=drive, cache_dir=out)
    assert not cache_available(out)
    assert cached_tickers(out) == []
