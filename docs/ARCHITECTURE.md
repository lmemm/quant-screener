# Architecture — quant-screener

quant-screener finds stocks worth adding to the swing-trader pipeline. It reads
historical intraday data from a local external drive, characterizes each stock's
statistical behavior, and outputs a ranked shortlist for manual review.

---

## Data Flow

```
External Drive (1-min bars, ~12,000 tickers, 2020–2025)
    │
    ├─ data.py — load_daily_bars()  (per-ticker scan; correct but slow at scale)
    │
    └─ cache.py — build_daily_cache()  (ONE pass → data/processed/daily_cache/)
    │     screen/validate read the cache in seconds; identical daily bars
    │
    ▼
characterize.py — characterize()
    │  Hurst exponent, ATR%, autocorrelation, volume, max drawdown
    │
    ▼
scripts/run_screen.py
    │  filters by volume, classifies trending/mean-reverting
    │
    ▼
outputs/screen_results_YYYY-MM-DD.csv
    │
    ▼
validate.py — validate_candidate()  (scripts/run_validate.py)
    │  walk-forward backtest of a class-matched, cost-charged strategy;
    │  reports which candidates survive out-of-sample
    │
    ▼
outputs/validation_results_YYYY-MM-DD.csv
    │
    ▼
Manual review + paper trading → promote to swing-trader TICKERS
```

---

## Modules

| Module | Responsibility |
|:-------|:--------------|
| `config.py` | All paths, thresholds, and env variables |
| `data.py` | Read from drive, resample to daily, top-up from Alpaca |
| `characterize.py` | Compute Hurst, ATR, autocorrelation, volume, drawdown |
| `screen.py` | Discover the universe, characterize every ticker, rank + filter, write CSV |
| `validate.py` | Walk-forward validation: class-matched long-only strategies (breakout / z-score reversion), rolling-fold backtest with trading costs, pass/fail per candidate |
| `cache.py` | Single-pass daily cache: read the by-day archive once, write a per-ticker daily store to `data/processed/daily_cache/`; `load_daily`/`universe_tickers` transparently use it (drive fallback). Output is identical to `load_daily_bars` (asserted by tests) |

## Scripts

| Script | Purpose |
|:-------|:--------|
| `run_screen.py` | Run full characterization pass, output ranked CSV |
| `run_topup.py` | Fetch recent bars from Alpaca to extend drive data |
| `run_validate.py` | Walk-forward-validate candidates, output pass/fail CSV |
| `build_cache.py` | Build the single-pass daily cache from the drive (one-time, ~30 min) |

---

## Data Source

- **Primary:** External drive at `DRIVE_PATH` — 1-minute aggregate bars for ~8,700
  US equities, organized as `YYYY/MM/YYYY-MM-DD.csv.gz`
- **Columns:** `ticker`, `volume`, `open`, `close`, `high`, `low`, `window_start`, `transactions`
- **Date range:** 2020-10-02 through 2025-10-02 (15 corrupt days in Dec 2024)
- **Top-up:** Alpaca IEX feed for Oct 2025 → present

---

## Key Decisions

See `docs/DECISIONS.md` for the full log. Summary:
- IEX feed (not SIP) for Alpaca stock data — free tier constraint
- Drive data is read-only — never written to
- Screener runs manually — no automation needed at this stage
