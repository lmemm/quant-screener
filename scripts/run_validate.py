#!/usr/bin/env python
"""Entry point: walk-forward-validate screener candidates and write a CSV.

For each ticker, this runs the class-matched strategy (breakout for trending
names, z-score reversion for mean-reverting names) across rolling out-of-sample
folds, charging realistic trading costs, and reports which candidates hold up.
The external drive must be mounted (see CLAUDE.md). Examples:

    # Validate a few tickers over the full available history
    python scripts/run_validate.py --tickers AAPL,MSFT,NVDA

    # Validate the whole universe (slow — it backtests every candidate)
    python scripts/run_validate.py

A "pass" is not a recommendation to trade — it means a simple rule survived
out-of-sample here. Paper-trade survivors before risking real money.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running directly (``python scripts/run_validate.py``): put the project
# root on the path so the ``src`` package resolves regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk-forward-validate candidates.")
    parser.add_argument(
        "--tickers",
        help="Comma-separated subset to validate (default: whole drive).",
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

    from src.screener.validate import validate_universe, write_validation

    tickers = args.tickers.split(",") if args.tickers else None
    kwargs = dict(
        drive_path=args.drive_path,
        tickers=tickers,
        start=args.start,
        end=args.end,
    )
    if args.min_volume is not None:
        kwargs["min_avg_volume"] = args.min_volume

    results = validate_universe(**kwargs)
    path = write_validation(results)
    n_passed = int(results["passed"].sum()) if not results.empty else 0
    print(f"Validated {len(results)} candidates ({n_passed} passed) → {path}")


if __name__ == "__main__":
    main()
