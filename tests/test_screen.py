"""Tests for the screening pipeline (T-003), all against the sample drive."""

import datetime as dt

import pandas as pd

from src.screener import config
from src.screener.screen import (
    RESULT_COLUMNS,
    available_date_range,
    discover_tickers,
    results_frame,
    screen_universe,
    write_results,
)


def test_discover_tickers(sample_drive):
    assert discover_tickers(sample_drive) == ["AAPL", "MSFT"]


def test_discover_tickers_empty(tmp_path):
    assert discover_tickers(tmp_path) == []


def test_available_date_range(sample_drive):
    assert available_date_range(sample_drive) == (
        dt.date(2025, 1, 2),
        dt.date(2025, 1, 3),
    )


def test_available_date_range_empty(tmp_path):
    assert available_date_range(tmp_path) is None


def test_results_frame_filters_and_ranks():
    records = [
        {"ticker": "LOWVOL", "hurst": 0.9, "avg_volume": 100, "avg_atr_pct": 1,
         "autocorr": 0, "max_drawdown": -0.1, "history_days": 600,
         "classification": "Trending"},
        {"ticker": "MID", "hurst": 0.40, "avg_volume": 1_000_000, "avg_atr_pct": 1,
         "autocorr": 0, "max_drawdown": -0.1, "history_days": 600,
         "classification": "Mean-Reverting"},
        {"ticker": "TOP", "hurst": 0.70, "avg_volume": 2_000_000, "avg_atr_pct": 1,
         "autocorr": 0, "max_drawdown": -0.1, "history_days": 600,
         "classification": "Trending"},
    ]
    df = results_frame(records, min_avg_volume=500_000)

    assert list(df.columns) == RESULT_COLUMNS
    # LOWVOL dropped by the volume filter; remainder sorted by Hurst desc.
    assert df["ticker"].tolist() == ["TOP", "MID"]


def test_results_frame_empty():
    df = results_frame([], min_avg_volume=500_000)
    assert df.empty
    assert list(df.columns) == RESULT_COLUMNS


def test_screen_universe_skips_short_history(sample_drive, tmp_path):
    """With the real 500-day minimum, the 2-day sample yields no candidates."""
    # cache_dir=tmp_path (empty) forces the sample-drive path, isolating the
    # test from any real daily cache built on this machine.
    df = screen_universe(sample_drive, min_avg_volume=0, cache_dir=tmp_path)
    assert df.empty
    assert list(df.columns) == RESULT_COLUMNS


def test_screen_universe_builds_rows(sample_drive, tmp_path, monkeypatch):
    """Lowering the history floor lets the sample tickers through end-to-end."""
    monkeypatch.setattr(config, "MIN_HISTORY_DAYS", 1)
    df = screen_universe(sample_drive, min_avg_volume=0, cache_dir=tmp_path)

    assert set(df["ticker"]) == {"AAPL", "MSFT"}
    assert list(df.columns) == RESULT_COLUMNS
    assert df.loc[df["ticker"] == "AAPL", "avg_volume"].iloc[0] == (5181 + 5299) / 2


def test_write_results_roundtrip(tmp_path):
    df = pd.DataFrame(
        [{col: 0 for col in RESULT_COLUMNS} | {"ticker": "AAPL"}],
        columns=RESULT_COLUMNS,
    )
    path = write_results(df, outputs_dir=tmp_path)
    assert path.exists()
    assert path.name.startswith("screen_results_")
    reloaded = pd.read_csv(path)
    assert reloaded["ticker"].tolist() == ["AAPL"]
