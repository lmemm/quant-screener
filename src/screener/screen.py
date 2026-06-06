"""Screening pipeline — run characterization across the ticker universe and
produce a ranked CSV of candidates (T-003).

The heavy lifting (drive I/O, per-ticker characterization) lives here so it can
be unit-tested; ``scripts/run_screen.py`` is a thin CLI wrapper around
``screen_universe`` + ``write_results``.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import pandas as pd

from . import config
from .characterize import characterize

logger = logging.getLogger(__name__)

# Column order of the ranked output CSV.
RESULT_COLUMNS = [
    "ticker",
    "hurst",
    "avg_atr_pct",
    "autocorr",
    "avg_volume",
    "avg_dollar_volume",
    "max_drawdown",
    "history_days",
    "classification",
]

_PROGRESS_EVERY = 100


def _day_files(drive_path: Path) -> list[Path]:
    """All per-day bar files on the drive, sorted by date."""
    return sorted(drive_path.glob("*/*/*.csv.gz"))


def discover_tickers(drive_path: Path | None = None) -> list[str]:
    """Unique tickers present on the drive.

    Reads the ``ticker`` column from the most recent day's file (a single day
    spans the full universe), avoiding a scan of the entire archive.
    """
    drive_path = config.DRIVE_PATH if drive_path is None else Path(drive_path)
    files = _day_files(drive_path)
    if not files:
        return []
    latest = pd.read_csv(files[-1], usecols=["ticker"])
    return sorted(latest["ticker"].dropna().unique().tolist())


def available_date_range(drive_path: Path | None = None) -> tuple[dt.date, dt.date] | None:
    """Earliest and latest dates with a file on the drive, or ``None`` if empty."""
    drive_path = config.DRIVE_PATH if drive_path is None else Path(drive_path)
    files = _day_files(drive_path)
    if not files:
        return None
    dates = [dt.date.fromisoformat(f.stem.replace(".csv", "")) for f in files]
    return min(dates), max(dates)


def results_frame(records: list[dict], min_avg_volume: float) -> pd.DataFrame:
    """Build the ranked result frame: filter by volume, sort by Hurst desc."""
    df = pd.DataFrame(records, columns=RESULT_COLUMNS)
    if df.empty:
        return df
    df = df[df["avg_volume"] >= min_avg_volume]
    return df.sort_values(
        "hurst", ascending=False, na_position="last"
    ).reset_index(drop=True)


def screen_universe(
    drive_path: Path | None = None,
    tickers: list[str] | None = None,
    start: str | dt.date | None = None,
    end: str | dt.date | None = None,
    min_avg_volume: float = config.MIN_AVG_VOLUME,
    cache_dir: Path | None = None,
) -> pd.DataFrame:
    """Characterize every ticker and return a ranked, volume-filtered frame.

    Reads from the daily cache when one is built (see ``cache.build_daily_cache``)
    and falls back to scanning the drive otherwise — the result is identical
    either way, the cache is just far faster. Tickers with fewer than
    ``config.MIN_HISTORY_DAYS`` of history (where ``characterize`` returns
    ``None``) are skipped.
    """
    from . import cache

    drive_path = config.DRIVE_PATH if drive_path is None else Path(drive_path)
    using_cache = cache.cache_available(cache_dir)

    if start is None or end is None:
        span = available_date_range(drive_path)
        if span is None:
            logger.warning("No data files found under %s", drive_path)
            return results_frame([], min_avg_volume)
        start = start or span[0]
        end = end or span[1]

    if tickers is None:
        tickers = cache.universe_tickers(drive_path, cache_dir)
    logger.info(
        "Screening %d tickers from %s to %s (source: %s)",
        len(tickers), start, end, "cache" if using_cache else "drive",
    )

    records: list[dict] = []
    for i, ticker in enumerate(tickers, start=1):
        if i % _PROGRESS_EVERY == 0:
            logger.info("  ...%d/%d tickers processed", i, len(tickers))
        df = cache.load_daily(ticker, start, end, drive_path=drive_path, cache_dir=cache_dir)
        metrics = characterize(df)
        if metrics is None:
            continue
        records.append({"ticker": ticker, **metrics})

    logger.info("Characterized %d/%d tickers with sufficient history", len(records), len(tickers))
    return results_frame(records, min_avg_volume)


def write_results(df: pd.DataFrame, outputs_dir: Path | None = None) -> Path:
    """Write the ranked frame to ``outputs/screen_results_YYYY-MM-DD.csv``."""
    outputs_dir = config.OUTPUTS if outputs_dir is None else Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    path = outputs_dir / f"screen_results_{dt.date.today():%Y-%m-%d}.csv"
    df.to_csv(path, index=False)
    logger.info("Wrote %d candidates to %s", len(df), path)
    return path
