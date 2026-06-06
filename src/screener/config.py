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
MIN_AVG_VOLUME = 500_000       # minimum average daily *share* volume
MIN_HISTORY_DAYS = 500         # minimum trading days of history required
# Thresholds calibrated to the bias-corrected R/S estimator against synthetic
# series of *known* Hurst (T-009): the estimator reads a true-H=0.55 series at
# ~0.51 and a true-H=0.45 series at ~0.43 (n≈1000), so these bands map back to
# the intended "true H within ±0.05 of 0.5" split. Asymmetric because a small
# residual negative bias remains after the Anis-Lloyd correction.
HURST_TREND_MIN = 0.51         # Hurst >= this → trending candidate
HURST_REVERT_MAX = 0.43        # Hurst <= this → mean-reversion candidate

# Minimum average daily *dollar* volume (close × shares). Share count alone is a
# poor liquidity proxy — 500k shares of a $0.50 stock is $250k/day (thin, wide
# spreads), 500k shares of a $300 stock is $150M/day (deep). Dollar volume is
# what determines whether the backtest's fill/cost assumptions are realistic, so
# validation gates on this. $5M/day filters the illiquid tail where slippage
# would dwarf the modelled cost (see DECISIONS.md, T-008).
MIN_DOLLAR_VOLUME = 5_000_000

# ── Walk-forward validation ────────────────────────────────────────────────
WFV_FOLDS = 6                  # number of rolling folds
WFV_MIN_FOLDS_PASSING = 3      # folds that must BEAT BUY-AND-HOLD to pass
WFV_MIN_TRADES_PER_FOLD = 2    # minimum trades per fold to count

# Round-trip trading friction charged on every change in exposure (commission +
# slippage), as a fraction of notional. Default used by the bare engine/tests.
WFV_COST_PER_TRADE = 0.001

# Liquidity-aware cost tiers used by the pipeline: thinner names pay more, since
# their real spread/slippage is wider than a flat fee. Each entry is
# (min avg daily dollar volume, round-trip cost fraction), checked top-down.
# This replaces the flat fee with something that stops flattering illiquid names
# instead of excluding them outright (see DECISIONS.md, T-008).
WFV_COST_TIERS = (
    (50_000_000, 0.0005),   # >= $50M/day: ~5 bps (deep, tight spreads)
    (10_000_000, 0.0015),   # >= $10M/day: ~15 bps
    (0,          0.0030),   # below that (down to MIN_DOLLAR_VOLUME): ~30 bps
)

# ── Strategy parameters (long-only, deliberately simple — fewer knobs means
# less room to overfit). Trending names get a Donchian breakout; mean-reverting
# names get a z-score reversion. ─────────────────────────────────────────────
BREAKOUT_LOOKBACK = 20         # enter long on a 20-day closing-price high
BREAKOUT_EXIT_LOOKBACK = 10    # exit when price drops to a 10-day closing low
MEANREV_LOOKBACK = 20          # window for the mean / std z-score
MEANREV_Z_ENTRY = -1.0         # enter long when z-score <= this (oversold)
MEANREV_Z_EXIT = 0.0           # exit when z-score reverts up to this (the mean)
