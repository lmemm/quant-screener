#!/usr/bin/env python
"""Entry point: top up recent daily bars from Alpaca (IEX) into the cache.

The drive ends in Oct 2025; this fetches bars from ``--since`` to present for
the given tickers and writes them to ``data/processed/{ticker}_topup.csv`` so
``load_daily_bars`` can append them. Requires ``ALPACA_API_KEY`` /
``ALPACA_API_SECRET`` in ``.env``. Example:

    python scripts/run_topup.py --tickers AAPL,MSFT --since 2025-10-01
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running directly (``python scripts/run_topup.py``): put the project
# root on the path so the ``src`` package resolves regardless of cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Top up recent bars from Alpaca.")
    parser.add_argument(
        "--tickers",
        required=True,
        help="Comma-separated tickers to top up (e.g. AAPL,MSFT).",
    )
    parser.add_argument(
        "--since",
        default="2025-10-01",
        help="Fetch daily bars from this date forward (default: 2025-10-01).",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = _parse_args()

    from src.screener.data import topup_ticker

    for ticker in args.tickers.split(","):
        ticker = ticker.strip()
        bars = topup_ticker(ticker, args.since)
        print(f"{ticker}: {len(bars)} top-up bars since {args.since}")


if __name__ == "__main__":
    main()
