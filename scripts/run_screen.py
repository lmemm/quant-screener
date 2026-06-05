#!/usr/bin/env python
"""Entry point: run the screener across the universe and write a ranked CSV.

The external drive must be mounted (see CLAUDE.md). Examples:

    # Full universe, full available history
    python scripts/run_screen.py

    # Quick test on a few tickers
    python scripts/run_screen.py --tickers AAPL,MSFT,NVDA
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running directly (``python scripts/run_screen.py``): put the project
# root on the path so the ``src`` package resolves regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Screen the ticker universe.")
    parser.add_argument(
        "--tickers",
        help="Comma-separated subset of tickers to screen (default: whole drive).",
    )
    parser.add_argument("--start", help="Start date YYYY-MM-DD (default: earliest on drive).")
    parser.add_argument("--end", help="End date YYYY-MM-DD (default: latest on drive).")
    parser.add_argument(
        "--drive-path",
        help="Override the bar archive root (default: config.DRIVE_PATH).",
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=None,
        help="Minimum average daily volume (default: config.MIN_AVG_VOLUME).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = _parse_args()

    from src.screener.screen import screen_universe, write_results

    tickers = args.tickers.split(",") if args.tickers else None
    kwargs = dict(
        drive_path=args.drive_path,
        tickers=tickers,
        start=args.start,
        end=args.end,
    )
    if args.min_volume is not None:
        kwargs["min_avg_volume"] = args.min_volume

    results = screen_universe(**kwargs)
    path = write_results(results)
    print(f"Wrote {len(results)} candidates to {path}")


if __name__ == "__main__":
    main()
