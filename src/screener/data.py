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

    daily = _resample_drive_bars(frames)
    return _append_topup(daily, ticker, start_date, end_date)


def _resample_drive_bars(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """De-duplicate, drop nulls, and resample raw minute bars to daily OHLCV."""
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


def _topup_path(ticker: str) -> Path:
    """Location of a ticker's cached Alpaca top-up file."""
    return config.DATA_PROCESSED / f"{ticker}_topup.csv"


def _normalize_to_dates(index: pd.Index) -> pd.DatetimeIndex:
    """Coerce a (possibly tz-aware) timestamp index to tz-naive dates."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return idx.normalize()


def _append_topup(
    daily: pd.DataFrame,
    ticker: str,
    start_date: dt.date,
    end_date: dt.date,
) -> pd.DataFrame:
    """Append cached Alpaca top-up bars (if any) to drive-sourced daily bars.

    Top-up data extends the drive past its last date. On any overlapping date
    the drive value wins (it is the authoritative historical source).
    """
    path = _topup_path(ticker)
    if not path.exists():
        return daily

    topup = pd.read_csv(path, index_col="date", parse_dates=["date"])
    topup.index = _normalize_to_dates(topup.index)
    topup.index.name = "date"
    mask = (topup.index >= pd.Timestamp(start_date)) & (
        topup.index <= pd.Timestamp(end_date)
    )
    topup = topup.loc[mask, _OHLCV]
    if topup.empty:
        return daily

    combined = pd.concat([daily, topup])
    combined = combined[~combined.index.duplicated(keep="first")].sort_index()
    combined["volume"] = combined["volume"].astype("int64")
    return combined[_OHLCV]


def topup_ticker(
    ticker: str,
    since: str | dt.date | dt.datetime | pd.Timestamp,
    client=None,
) -> pd.DataFrame:
    """Fetch daily bars from Alpaca (IEX feed) since ``since`` and cache them.

    The result is written to ``data/processed/{ticker}_topup.csv`` so that
    ``load_daily_bars`` can append it seamlessly. Pass ``client`` to inject a
    pre-built (or mocked) ``StockHistoricalDataClient``.

    Returns the fetched daily OHLCV frame (empty if Alpaca returned nothing).
    """
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    if client is None:
        client = StockHistoricalDataClient(
            config.ALPACA_API_KEY, config.ALPACA_API_SECRET
        )

    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=pd.Timestamp(since),
        feed="iex",  # free tier does not support SIP
    )
    raw = client.get_stock_bars(request).df

    if raw is None or raw.empty:
        return _empty_daily()

    # Alpaca returns a (symbol, timestamp) MultiIndex; reduce to this ticker.
    if isinstance(raw.index, pd.MultiIndex):
        raw = raw.xs(ticker, level=0)

    daily = raw[_OHLCV].copy()
    daily.index = _normalize_to_dates(raw.index)
    daily.index.name = "date"
    daily["volume"] = daily["volume"].astype("int64")
    daily = daily[_OHLCV]

    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    daily.to_csv(_topup_path(ticker))
    logger.info("Wrote %d top-up bars for %s to %s", len(daily), ticker, _topup_path(ticker))
    return daily
