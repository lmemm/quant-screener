"""Data loading — read 1-minute bars from the external drive and resample
them to daily OHLCV.

The drive stores one gzipped CSV per trading day at
``DRIVE_PATH / YYYY / MM / YYYY-MM-DD.csv.gz`` with the columns
``ticker, volume, open, close, high, low, window_start, transactions`` where
``window_start`` is a nanosecond epoch timestamp.

See BACKLOG.md T-001 for the full specification.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import pandas as pd

from . import config

logger = logging.getLogger(__name__)

# Columns aggregated from 1-minute bars into a daily bar.
_OHLCV = ["open", "high", "low", "close", "volume"]

# How each daily field is derived from the minute bars within a day.
_DAILY_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}


def _to_date(value: str | dt.date | dt.datetime | pd.Timestamp) -> dt.date:
    """Coerce a date-like value to a ``datetime.date``."""
    return pd.Timestamp(value).date()


def _day_path(drive_path: Path, day: dt.date) -> Path:
    """Path to a single day's file: ``<drive>/YYYY/MM/YYYY-MM-DD.csv.gz``."""
    return (
        drive_path
        / f"{day:%Y}"
        / f"{day:%m}"
        / f"{day:%Y-%m-%d}.csv.gz"
    )


def _empty_daily() -> pd.DataFrame:
    """An empty daily-bar frame with the right columns and a DatetimeIndex."""
    return pd.DataFrame(
        {col: pd.Series(dtype="float64") for col in _OHLCV},
        index=pd.DatetimeIndex([], name="date"),
    )


def _read_day(path: Path, ticker: str) -> pd.DataFrame | None:
    """Read one day's file and return only ``ticker``'s rows.

    Returns ``None`` (and logs) when the file is missing or unreadable, so the
    caller can skip the day without crashing.
    """
    if not path.exists():
        # Missing files are normal (weekends/holidays); keep this quiet so a
        # multi-year range does not emit thousands of warnings.
        logger.debug("No data file for %s, skipping", path.name)
        return None
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 — corrupt file: skip, don't crash
        logger.warning("Could not read %s (%s), skipping", path.name, exc)
        return None
    return df[df["ticker"] == ticker]


def load_daily_bars(
    ticker: str,
    start: str | dt.date | dt.datetime | pd.Timestamp,
    end: str | dt.date | dt.datetime | pd.Timestamp,
    drive_path: Path | None = None,
) -> pd.DataFrame:
    """Load and resample 1-minute bars to daily OHLCV for one ticker.

    Args:
        ticker: Symbol to load (e.g. ``"AAPL"``).
        start: First calendar date to read (inclusive).
        end: Last calendar date to read (inclusive).
        drive_path: Root of the bar archive. Defaults to ``config.DRIVE_PATH``;
            tests point this at the committed sample drive.

    Returns:
        A DataFrame indexed by date (DatetimeIndex named ``date``) with columns
        ``open, high, low, close, volume`` — one row per day that had data.
        Empty if nothing was found.

    Missing and corrupt files are skipped with a log message rather than
    raising. The 15 known-corrupt December 2024 dates (``config.CORRUPT_DATES``)
    are skipped with a warning before any file access.
    """
    drive_path = config.DRIVE_PATH if drive_path is None else Path(drive_path)
    start_date, end_date = _to_date(start), _to_date(end)

    frames: list[pd.DataFrame] = []
    for day in pd.date_range(start_date, end_date, freq="D"):
        day = day.date()
        if day in config.CORRUPT_DATES:
            logger.warning("Skipping known corrupt date %s", day)
            continue
        rows = _read_day(_day_path(drive_path, day), ticker)
        if rows is not None and not rows.empty:
            frames.append(rows)

    if not frames:
        return _empty_daily()

    bars = pd.concat(frames, ignore_index=True)

    # De-duplicate identical bars (data summary §5e) and drop rows with any
    # missing OHLCV value (§5b) before aggregating.
    bars = bars.drop_duplicates(subset=["ticker", "window_start"], keep="first")
    bars = bars.dropna(subset=_OHLCV)
    if bars.empty:
        return _empty_daily()

    bars = bars.sort_values("window_start")
    bars.index = pd.to_datetime(bars["window_start"], unit="ns")

    daily = bars.resample("1D").agg(_DAILY_AGG).dropna(subset=["open"])
    daily.index.name = "date"
    daily["volume"] = daily["volume"].astype("int64")
    return daily[_OHLCV]
