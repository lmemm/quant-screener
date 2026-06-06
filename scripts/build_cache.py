#!/usr/bin/env python
"""Entry point: build the single-pass daily cache from the drive.

Reads the raw 1-minute archive **once** and writes a compact per-ticker daily
store to ``data/processed/daily_cache/``. After this one build, the screener and
validator read the cache in seconds instead of re-scanning the whole 23 GB
archive per ticker. The external drive must be mounted (see CLAUDE.md). Examples:

    # Build the full cache (all dates on the drive) — one-time, ~30 min
    python scripts/build_cache.py

    # Build only a date range (e.g. to refresh recent data)
    python scripts/build_cache.py --start 2025-01-01 --end 2025-10-02

The cache is a derived artifact: rebuild it when the drive gains new days.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running directly (``python scripts/build_cache.py``): put the project
# root on the path so the ``src`` package resolves regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the daily cache from the drive.")
    parser.add_argument("--start", help="First date to cache YYYY-MM-DD (default: earliest on drive).")
    parser.add_argument("--end", help="Last date to cache YYYY-MM-DD (default: latest on drive).")
    parser.add_argument(
        "--drive-path",
        help="Override the bar archive root (default: config.DRIVE_PATH).",
    )
    parser.add_argument(
        "--cache-dir",
        help="Override the output cache directory (default: data/processed/daily_cache).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = _parse_args()

    from src.screener.cache import build_daily_cache, cached_tickers

    cache_dir = build_daily_cache(
        drive_path=args.drive_path,
        start=args.start,
        end=args.end,
        cache_dir=args.cache_dir,
    )
    print(f"Built daily cache for {len(cached_tickers(cache_dir)):,} tickers → {cache_dir}")


if __name__ == "__main__":
    main()
