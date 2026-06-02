# Backlog

**Statuses:** `⬚ Open` → `🔵 In Progress` → `✅ Done` | `🟡 Blocked` | `❌ Won't Do`

---

## Active Tickets

### T-001: Build data loader — read and resample 1-min bars from external drive
- **Status:** ✅ Done
- **Priority:** P1
- **Type:** Feature
- **Description:** Write `src/screener/data.py`. Given a ticker and date range, locate the relevant `.csv.gz` files on the external drive, load them, filter to that ticker, and resample 1-minute bars to daily OHLCV (first open, last close, max high, min low, sum volume). Return a DataFrame with a DatetimeIndex. Handle missing files, corrupt files, and the known December 2024 corrupt dates gracefully.
- **Acceptance criteria:**
  - [x] `load_daily_bars(ticker, start, end) -> pd.DataFrame` in `src/screener/data.py`
  - [x] Reads from `DRIVE_PATH / YYYY / MM / YYYY-MM-DD.csv.gz`
  - [x] Resamples 1-min bars to daily OHLCV correctly
  - [x] Skips corrupt/missing files with a warning, does not crash
  - [x] De-duplicates bars before resampling (per data summary §5e)
  - [x] Drops nulls before resampling (per data summary §5b)
  - [x] Returns empty DataFrame if no data found
  - [x] Tests use a small sample CSV (not the real drive)
  - [x] `ruff check .` passes, `pytest` passes
- **Files likely involved:** `src/screener/data.py`, `tests/test_data.py`
- **Notes:** Drive path comes from `config.DRIVE_PATH`. The 15 corrupt December 2024 dates are: Dec 10–13, 16–20, 23–24, 26–27, 30–31. Skip them with a warning.
- **Completion note:** Implemented `load_daily_bars()` in `src/screener/data.py` with an optional `drive_path` arg so tests point at the sample drive. Per-day files are read, filtered to the ticker, de-duplicated on `(ticker, window_start)`, null-OHLCV rows dropped, then resampled to daily OHLCV via pandas `resample("1D")`. The 15 corrupt Dec-2024 dates were moved into `config.CORRUPT_DATES` and are skipped with a warning before any file access; missing files are skipped quietly (debug) to avoid thousands of weekend/holiday warnings over multi-year ranges — see DECISIONS.md. 7 tests in `tests/test_data.py` (13 total); `ruff` clean, `pytest` 13 passed.

---

### T-002: Build characterization module — Hurst, ATR, autocorrelation, volume
- **Status:** ⬚ Open
- **Priority:** P1
- **Type:** Feature
- **Description:** Write `src/screener/characterize.py`. Given a daily OHLCV DataFrame, compute the stats used to classify a stock's behavior. Output a dict of metrics for that ticker.
- **Acceptance criteria:**
  - [ ] `characterize(df: pd.DataFrame) -> dict` in `src/screener/characterize.py`
  - [ ] Computes Hurst exponent (use rescaled range method)
  - [ ] Computes average ATR as % of close price (14-period)
  - [ ] Computes lag-1 autocorrelation of daily returns
  - [ ] Computes average daily volume
  - [ ] Computes max drawdown
  - [ ] Returns `None` (or raises) if DataFrame has fewer than `MIN_HISTORY_DAYS` rows
  - [ ] Tests cover normal input and short input
  - [ ] `ruff check .` passes, `pytest` passes
- **Files likely involved:** `src/screener/characterize.py`, `tests/test_characterize.py`
- **Notes:** Hurst exponent: H > 0.55 = trending, H < 0.45 = mean-reverting, 0.45–0.55 = random walk. Thresholds live in `config.py`.
- **Completion note:**

---

### T-003: Build screener script — run characterization across full universe
- **Status:** ⬚ Open
- **Priority:** P2
- **Type:** Feature
- **Description:** Write `scripts/run_screen.py`. Load all tickers found on the drive, run `characterize()` on each, filter by `MIN_AVG_VOLUME`, and write a ranked CSV to `outputs/screen_results_YYYY-MM-DD.csv`. Log progress as it runs (it will be slow).
- **Acceptance criteria:**
  - [ ] Script reads all unique tickers from drive file headers (or a cached list)
  - [ ] Runs `characterize()` on each ticker with full history
  - [ ] Filters out tickers below `MIN_AVG_VOLUME`
  - [ ] Outputs ranked CSV sorted by Hurst exponent descending
  - [ ] CSV columns: `ticker`, `hurst`, `avg_atr_pct`, `autocorr`, `avg_volume`, `max_drawdown`, `history_days`, `classification` (Trending / Mean-Reverting / Random)
  - [ ] Logs progress every 100 tickers
  - [ ] `ruff check .` passes
- **Files likely involved:** `scripts/run_screen.py`, `src/screener/data.py`, `src/screener/characterize.py`
- **Notes:** This script will take a long time on the full ~8,700 ticker universe. Consider adding a `--tickers` flag to test on a subset.
- **Completion note:**

---

### T-004: Top-up recent data from Alpaca
- **Status:** ⬚ Open
- **Priority:** P3
- **Type:** Feature
- **Description:** The drive ends at Oct 2025. Write `scripts/run_topup.py` to fetch daily bars from Alpaca (IEX feed) for Oct 2025 → present and cache them in `data/processed/` so `load_daily_bars()` can append them seamlessly.
- **Acceptance criteria:**
  - [ ] `topup_ticker(ticker, since) -> pd.DataFrame` in `src/screener/data.py`
  - [ ] Uses Alpaca `StockHistoricalDataClient` with `feed="iex"`
  - [ ] Saves result to `data/processed/{ticker}_topup.csv`
  - [ ] `load_daily_bars()` appends topup data if file exists
  - [ ] Tests mock the Alpaca client
  - [ ] `ruff check .` passes, `pytest` passes
- **Files likely involved:** `src/screener/data.py`, `scripts/run_topup.py`, `tests/test_data.py`
- **Notes:** Alpaca API key comes from `config.ALPACA_API_KEY`. Always use `feed="iex"` — the free tier does not support SIP.
- **Completion note:**

---

## Completed Tickets

- **T-001** — Data loader (`load_daily_bars`), 2026-06-02. See the ticket above for the completion note.

---

## Ticket Template

```markdown
### T-XXX: [Title]
- **Status:** ⬚ Open
- **Priority:** P1 / P2 / P3
- **Type:** Feature / Bug / Refactor / Chore
- **Description:**
- **Acceptance criteria:**
  - [ ]
  - [ ] Tests pass
- **Files likely involved:**
- **Notes:**
- **Completion note:**
```
