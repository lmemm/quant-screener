"""Central config — all paths and thresholds live here."""

import datetime as dt
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

# External drive — override via .env
DRIVE_PATH = Path(os.getenv("DATA_DRIVE_PATH", "/Volumes/Extreme Pro/stock data from Emery"))

# ── Known-bad data ─────────────────────────────────────────────────────────
# 15 corrupt days in December 2024 on the drive — skipped with a warning by the
# loader (see BACKLOG.md T-001 notes).
CORRUPT_DATES = frozenset(
    dt.date(2024, 12, day)
    for day in (10, 11, 12, 13, 16, 17, 18, 19, 20, 23, 24, 26, 27, 30, 31)
)

# ── Alpaca ─────────────────────────────────────────────────────────────────
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "")

# ── Screening thresholds ───────────────────────────────────────────────────
MIN_AVG_VOLUME = 500_000       # minimum average daily volume
MIN_HISTORY_DAYS = 500         # minimum trading days of history required
HURST_TREND_MIN = 0.55         # Hurst >= this → trending candidate
HURST_REVERT_MAX = 0.45        # Hurst <= this → mean-reversion candidate

# ── Walk-forward validation ────────────────────────────────────────────────
WFV_FOLDS = 6                  # number of rolling folds
WFV_MIN_FOLDS_PASSING = 3      # folds that must be profitable to pass
WFV_MIN_TRADES_PER_FOLD = 2    # minimum trades per fold to count

# Round-trip trading friction charged on every change in exposure (commission +
# slippage), as a fraction of notional. 0.001 = 0.1% — deliberately
# conservative so backtests are not flattered. The single most important knob
# for honest results; raise it if your broker/spread is worse.
WFV_COST_PER_TRADE = 0.001

# ── Strategy parameters (long-only, deliberately simple — fewer knobs means
# less room to overfit). Trending names get a Donchian breakout; mean-reverting
# names get a z-score reversion. ─────────────────────────────────────────────
BREAKOUT_LOOKBACK = 20         # enter long on a 20-day closing-price high
BREAKOUT_EXIT_LOOKBACK = 10    # exit when price drops to a 10-day closing low
MEANREV_LOOKBACK = 20          # window for the mean / std z-score
MEANREV_Z_ENTRY = -1.0         # enter long when z-score <= this (oversold)
MEANREV_Z_EXIT = 0.0           # exit when z-score reverts up to this (the mean)
