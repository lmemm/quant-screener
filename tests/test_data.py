"""Tests for the daily-bar loader (T-001).

All tests read from the committed sample drive via the ``sample_drive``
fixture — never the real external drive (see CLAUDE.md).
"""

import datetime as dt

import pandas as pd
import pytest

from src.screener import config
from src.screener.data import load_daily_bars

START = "2025-01-02"
END = "2025-01-03"


@pytest.mark.parametrize("ticker", ["AAPL", "MSFT"])
def test_resamples_to_expected_daily(sample_drive, expected_daily, ticker):
    """Daily OHLCV matches the pinned expectations (post dedup + dropna)."""
    daily = load_daily_bars(ticker, START, END, drive_path=sample_drive)

    assert isinstance(daily.index, pd.DatetimeIndex)
    assert list(daily.columns) == ["open", "high", "low", "close", "volume"]
    assert len(daily) == 2

    for date_str, exp in expected_daily[ticker].items():
        row = daily.loc[date_str]
        for field, value in exp.items():
            assert row[field] == pytest.approx(value), f"{ticker} {date_str} {field}"


def test_dedup_does_not_double_count_volume(sample_drive):
    """The duplicated AAPL day-1 bar (§5e) is counted once, not twice."""
    daily = load_daily_bars("AAPL", START, START, drive_path=sample_drive)
    # 5181 includes the 847-volume bar exactly once.
    assert daily.loc["2025-01-02", "volume"] == 5181


def test_null_close_row_is_dropped(sample_drive):
    """The AAPL day-1 null-close row (§5b) does not pollute the daily close."""
    daily = load_daily_bars("AAPL", START, START, drive_path=sample_drive)
    # Last *valid* close on day 1 is 251.13, not the dropped null row.
    assert daily.loc["2025-01-02", "close"] == pytest.approx(251.13)


def test_missing_files_are_skipped(sample_drive):
    """A range covering dates with no file returns only the available days."""
    # 2025-01-04/05 are a weekend with no file; should not crash.
    daily = load_daily_bars("AAPL", "2025-01-02", "2025-01-06", drive_path=sample_drive)
    assert len(daily) == 2
    assert list(daily.index.date) == [dt.date(2025, 1, 2), dt.date(2025, 1, 3)]


def test_corrupt_dates_skipped_with_warning(sample_drive, caplog):
    """Known corrupt December 2024 dates are skipped and warned about."""
    corrupt = sorted(config.CORRUPT_DATES)[0]  # 2024-12-10
    with caplog.at_level("WARNING"):
        daily = load_daily_bars("AAPL", corrupt, corrupt, drive_path=sample_drive)
    assert daily.empty
    assert any("corrupt" in rec.message.lower() for rec in caplog.records)


def test_unknown_ticker_returns_empty(sample_drive):
    """A ticker with no rows yields an empty, well-formed frame."""
    daily = load_daily_bars("NOPE", START, END, drive_path=sample_drive)
    assert daily.empty
    assert list(daily.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(daily.index, pd.DatetimeIndex)


def test_no_files_in_range_returns_empty(sample_drive):
    """A range with no files at all yields an empty frame, not an error."""
    daily = load_daily_bars("AAPL", "2030-01-01", "2030-01-02", drive_path=sample_drive)
    assert daily.empty
