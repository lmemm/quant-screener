"""Shared pytest fixtures for quant-screener tests.

Tests must never read from the real external drive (see CLAUDE.md). The
`sample_drive` fixture points at a tiny committed dataset under
`data/sample/`, laid out exactly like the real drive
(`YYYY/MM/YYYY-MM-DD.csv.gz`) so the data loader can be pointed at it
unchanged.
"""

from pathlib import Path

import pytest

# Repo root = two levels up from this file (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DRIVE = REPO_ROOT / "data" / "sample"


@pytest.fixture
def sample_drive() -> Path:
    """Path to the sample drive root (mirrors the real DRIVE_PATH layout)."""
    return SAMPLE_DRIVE


# Expected daily OHLCV after loading the sample, with the day-1 duplicate bar
# de-duplicated (§5e) and the day-1 null-close row dropped (§5b). The web agent
# implementing T-001 can assert against these.
EXPECTED_DAILY = {
    "AAPL": {
        "2025-01-02": dict(open=251.36, close=251.13, high=251.42, low=250.60, volume=5181),
        "2025-01-03": dict(open=243.80, close=243.60, high=243.99, low=243.60, volume=5299),
    },
    "MSFT": {
        "2025-01-02": dict(open=424.50, close=424.39, high=424.50, low=423.91, volume=6045),
        "2025-01-03": dict(open=420.58, close=420.91, high=420.91, low=420.58, volume=3210),
    },
}


@pytest.fixture
def expected_daily() -> dict:
    """Expected daily OHLCV values for the sample dataset (post dedup + dropna)."""
    return EXPECTED_DAILY
