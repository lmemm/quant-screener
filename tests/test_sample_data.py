"""Baseline tests that validate the committed sample dataset.

These do not depend on any screener module yet, so they give a green
`pytest` baseline before T-001 is implemented. They also pin down the
intentional data-quality quirks the loader must handle.
"""

import gzip

import pandas as pd

COLUMNS = [
    "ticker", "volume", "open", "close",
    "high", "low", "window_start", "transactions",
]


def _read(path):
    with gzip.open(path, "rt") as fh:
        return pd.read_csv(fh)


def test_sample_drive_layout(sample_drive):
    """Sample mirrors the real drive layout: <root>/YYYY/MM/YYYY-MM-DD.csv.gz."""
    files = sorted(sample_drive.glob("2025/01/*.csv.gz"))
    assert [f.name for f in files] == ["2025-01-02.csv.gz", "2025-01-03.csv.gz"]


def test_sample_columns(sample_drive):
    """Both files carry the documented column schema."""
    for f in sample_drive.glob("2025/01/*.csv.gz"):
        assert list(_read(f).columns) == COLUMNS


def test_day1_has_a_duplicate_bar(sample_drive):
    """Day 1 seeds one duplicate (ticker, window_start) pair (data summary §5e)."""
    df = _read(sample_drive / "2025/01/2025-01-02.csv.gz")
    dupes = df.duplicated(subset=["ticker", "window_start"]).sum()
    assert dupes == 1


def test_day1_has_a_null_row(sample_drive):
    """Day 1 seeds one null value to exercise dropna (data summary §5b)."""
    df = _read(sample_drive / "2025/01/2025-01-02.csv.gz")
    assert df.isnull().any(axis=1).sum() == 1


def test_day2_is_clean(sample_drive):
    """Day 2 has no duplicates and no nulls."""
    df = _read(sample_drive / "2025/01/2025-01-03.csv.gz")
    assert df.duplicated(subset=["ticker", "window_start"]).sum() == 0
    assert df.isnull().sum().sum() == 0
