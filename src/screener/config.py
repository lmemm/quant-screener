"""Central config — all paths and thresholds live here."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"

# External drive — override via .env
DRIVE_PATH = Path(os.getenv("DATA_DRIVE_PATH", "/Volumes/Extreme Pro/stock data from Emery"))

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
