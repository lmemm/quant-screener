"""Single-pass daily cache (T-007).

The raw archive is partitioned **by day** — each ``YYYY-MM-DD.csv.gz`` holds the
1-minute bars for *every* ticker that day (~1.8M rows). But screening wants data
**by ticker**. ``data.load_daily_bars`` bridges that gap by scanning every day
file and keeping one ticker's rows — so screening the whole universe re-reads
the entire 23 GB archive once *per ticker* (measured: ~17 min/ticker, which makes
the full ~11,000-name universe infeasible).

This module reads the archive **once**, resampling every ticker's minute bars to
daily OHLCV in the same pass, and writes a compact per-ticker daily store under
``data/processed/daily_cache/{TICKER}.parquet`` (hundreds of MB vs 23 GB). After
that one build, ``load_cached_daily`` returns a ticker's daily history in
milliseconds, and a full-universe screen is a single fast pass instead of months.

**No quality loss by construction.** The daily bars are produced with the exact
same recipe as ``data.load_daily_bars`` — dedup on ``(ticker, window_start)``,
drop null OHLCV, then ``resample("1D")`` for first-open / max-high / min-low /
last-close / sum-volume. ``tests/test_cache.py`` asserts the cache output is
*identical* (``assert_frame_equal``) to the live loader for the sample tickers.

The cache is a derived artifact: rebuild it when the drive gains new days or
Alpaca top-ups land (top-ups are still appended at read time, exactly as the
live loader does, so they need no rebuild).

See BACKLOG.md T-007.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import pandas as pd

from . import config
from .data import (
    _DAILY_AGG,
    _OHLCV,
    _append_topup,
    _empty_daily,
    _to_date,
)
from .screen import _day_files

logger = logging.getLogger(__name__)


def default_cache_dir() -> Path:
    """Where the per-ticker daily parquet files live."""
    return config.DATA_PROCESSED / "daily_cache"


def _safe_name(ticker: str) -> str:
    """Filesystem-safe stem for a ticker (symbols can contain ``/``, ``.``)."""
    return ticker.replace("/", "_")


def _ticker_path(ticker: str, cache_dir: Path) -> Path:
    return cache_dir / f"{_safe_name(ticker)}.parquet"


def cache_available(cache_dir: Path | None = None) -> bool:
    """True if a built cache (at least one ticker file) exists."""
    cache_dir = default_cache_dir() if cache_dir is None else Path(cache_dir)
    return cache_dir.exists() and any(cache_dir.glob("*.parquet"))


def cached_tickers(cache_dir: Path | None = None) -> list[str]:
    """Tickers present in the cache, sorted."""
    cache_dir = default_cache_dir() if cache_dir is None else Path(cache_dir)
    if not cache_dir.exists():
        return []
    return sorted(p.stem for p in cache_dir.glob("*.parquet"))


def _file_date(path: Path) -> dt.date:
    """Trading date encoded in a ``YYYY-MM-DD.csv.gz`` filename."""
    return dt.date.fromisoformat(path.stem.replace(".csv", ""))


def _daily_from_day_file(path: Path) -> pd.DataFrame | None:
    """Resample one day's minute bars to one daily bar **per ticker**.

    Mirrors ``data._resample_drive_bars`` applied per file: dedup, drop nulls,
    then ``resample("1D")`` within each ticker. Returns a MultiIndex
    ``(ticker, date)`` frame of daily OHLCV, or ``None`` if the file is
    unreadable/empty.
    """
    try:
        bars = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001 — corrupt file: skip, don't crash
        logger.warning("Could not read %s (%s), skipping", path.name, exc)
        return None

    bars = bars.drop_duplicates(subset=["ticker", "window_start"], keep="first")
    bars = bars.dropna(subset=_OHLCV)
    if bars.empty:
        return None

    # Sort by time so 'first'/'last' pick the earliest open / latest close, then
    # aggregate each (ticker, calendar-day) into one bar. A plain two-key
    # groupby on the floored day is far cheaper than ``groupby(ticker).resample``
    # (which materializes an empty date range for each of ~12k tickers per file)
    # and produces the identical result — verified by tests/test_cache.py.
    bars = bars.sort_values("window_start")
    day = pd.to_datetime(bars["window_start"], unit="ns").dt.floor("D")
    daily = bars.groupby([bars["ticker"], day.rename("date")]).agg(_DAILY_AGG)
    daily.index = daily.index.set_names(["ticker", "date"])
    return daily


def build_daily_cache(
    drive_path: Path | None = None,
    start: str | dt.date | None = None,
    end: str | dt.date | None = None,
    cache_dir: Path | None = None,
    progress_every: int = 100,
) -> Path:
    """Read the archive once and write a per-ticker daily parquet store.

    Args:
        drive_path: Root of the bar archive (default ``config.DRIVE_PATH``).
        start, end: Optional inclusive date bounds; default to the full range
            present on the drive.
        cache_dir: Output directory (default ``default_cache_dir()``).
        progress_every: Log progress every N files.

    Returns:
        The cache directory that was written.
    """
    drive_path = config.DRIVE_PATH if drive_path is None else Path(drive_path)
    cache_dir = default_cache_dir() if cache_dir is None else Path(cache_dir)

    files = _day_files(drive_path)
    if start is not None or end is not None:
        lo = _to_date(start) if start is not None else dt.date.min
        hi = _to_date(end) if end is not None else dt.date.max
        files = [f for f in files if lo <= _file_date(f) <= hi]

    logger.info("Building daily cache from %d day files under %s", len(files), drive_path)

    frames: list[pd.DataFrame] = []
    for i, path in enumerate(files, start=1):
        if _file_date(path) in config.CORRUPT_DATES:
            logger.warning("Skipping known corrupt date %s", _file_date(path))
            continue
        daily = _daily_from_day_file(path)
        if daily is not None:
            frames.append(daily)
        if i % progress_every == 0:
            logger.info("  ...%d/%d day files read", i, len(files))

    cache_dir.mkdir(parents=True, exist_ok=True)
    if not frames:
        logger.warning("No usable data found; cache is empty")
        return cache_dir

    # Collapse any (ticker, date) that landed in two files (e.g. extended-hours
    # bars spilling across a UTC day boundary) back into a single daily bar —
    # exactly what the whole-range loader would produce.
    allbars = pd.concat(frames)
    allbars = allbars.groupby(level=["ticker", "date"]).agg(_DAILY_AGG)
    allbars["volume"] = allbars["volume"].astype("int64")

    n_written = 0
    for ticker, group in allbars.groupby(level="ticker"):
        daily = group.reset_index(level="ticker", drop=True)[_OHLCV]
        daily.index.name = "date"
        daily.to_parquet(_ticker_path(ticker, cache_dir))
        n_written += 1
    logger.info("Wrote daily cache for %d tickers to %s", n_written, cache_dir)
    return cache_dir


def load_cached_daily(
    ticker: str,
    start: str | dt.date,
    end: str | dt.date,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Return a ticker's daily OHLCV from the cache, same shape as the loader.

    Output matches ``data.load_daily_bars`` exactly: a date-indexed OHLCV frame
    restricted to ``[start, end]``, with any cached Alpaca top-up rows appended
    (drive wins on overlap). Returns an empty frame if the ticker is not cached.
    """
    cache_dir = default_cache_dir() if cache_dir is None else Path(cache_dir)
    start_date, end_date = _to_date(start), _to_date(end)

    path = _ticker_path(ticker, cache_dir)
    if not path.exists():
        daily = _empty_daily()
    else:
        daily = pd.read_parquet(path)
        daily.index = pd.DatetimeIndex(daily.index)
        daily.index.name = "date"
        mask = (daily.index >= pd.Timestamp(start_date)) & (
            daily.index <= pd.Timestamp(end_date)
        )
        daily = daily.loc[mask, _OHLCV]
        if not daily.empty:
            daily["volume"] = daily["volume"].astype("int64")

    return _append_topup(daily, ticker, start_date, end_date)


# ── Unified access (cache when built, drive otherwise) ───────────────────────


def load_daily(
    ticker: str,
    start: str | dt.date,
    end: str | dt.date,
    drive_path: Path | None = None,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Daily bars for one ticker, preferring the cache when it's built.

    Falls back to the live ``data.load_daily_bars`` drive scan when no cache is
    present, so callers get the fast path automatically once a cache exists and
    correct behaviour when it doesn't.
    """
    if cache_available(cache_dir):
        return load_cached_daily(ticker, start, end, cache_dir=cache_dir)
    from .data import load_daily_bars

    return load_daily_bars(ticker, start, end, drive_path=drive_path)


def universe_tickers(
    drive_path: Path | None = None, cache_dir: Path | None = None
) -> list[str]:
    """Universe of tickers — from the cache when built, else from the drive."""
    if cache_available(cache_dir):
        return cached_tickers(cache_dir)
    from .screen import discover_tickers

    return discover_tickers(drive_path)
