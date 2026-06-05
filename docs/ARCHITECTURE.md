# Architecture — quant-screener

quant-screener finds stocks worth adding to the swing-trader pipeline. It reads
historical intraday data from a local external drive, characterizes each stock's
statistical behavior, and outputs a ranked shortlist for manual review.

---

## Data Flow

```
External Drive (1-min bars, ~8,700 tickers, 2020–2025)
    │
    ▼
data.py — load_daily_bars()
    │  reads .csv.gz files, resamples 1-min → daily OHLCV
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

## Scripts

| Script | Purpose |
|:-------|:--------|
| `run_screen.py` | Run full characterization pass, output ranked CSV |
| `run_topup.py` | Fetch recent bars from Alpaca to extend drive data |
| `run_validate.py` | Walk-forward-validate candidates, output pass/fail CSV |

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
