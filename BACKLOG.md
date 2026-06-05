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
- **Status:** ✅ Done
- **Priority:** P1
- **Type:** Feature
- **Description:** Write `src/screener/characterize.py`. Given a daily OHLCV DataFrame, compute the stats used to classify a stock's behavior. Output a dict of metrics for that ticker.
- **Acceptance criteria:**
  - [x] `characterize(df: pd.DataFrame) -> dict` in `src/screener/characterize.py`
  - [x] Computes Hurst exponent (use rescaled range method)
  - [x] Computes average ATR as % of close price (14-period)
  - [x] Computes lag-1 autocorrelation of daily returns
  - [x] Computes average daily volume
  - [x] Computes max drawdown
  - [x] Returns `None` (or raises) if DataFrame has fewer than `MIN_HISTORY_DAYS` rows
  - [x] Tests cover normal input and short input
  - [x] `ruff check .` passes, `pytest` passes
- **Files likely involved:** `src/screener/characterize.py`, `tests/test_characterize.py`
- **Notes:** Hurst exponent: H > 0.55 = trending, H < 0.45 = mean-reverting, 0.45–0.55 = random walk. Thresholds live in `config.py`.
- **Completion note:** Implemented `characterize()` plus standalone, individually-tested metric helpers (`hurst_exponent`, `avg_atr_pct`, `lag1_autocorr`, `max_drawdown`, `classify_hurst`). The Hurst exponent uses rescaled-range (R/S) analysis applied to *daily returns* — so a random-walk price gives H≈0.5, trending returns >0.5, mean-reverting <0.5 — with log-spaced window sizes and a log-log slope fit. ATR is the 14-period mean True Range expressed as a % of close; max drawdown is returned as a negative fraction. `characterize()` returns `None` below `config.MIN_HISTORY_DAYS`. Classification thresholds read from `config`. 14 tests in `tests/test_characterize.py` (28 total); `ruff` clean, `pytest` 28 passed.

---

### T-003: Build screener script — run characterization across full universe
- **Status:** ✅ Done
- **Priority:** P2
- **Type:** Feature
- **Description:** Write `scripts/run_screen.py`. Load all tickers found on the drive, run `characterize()` on each, filter by `MIN_AVG_VOLUME`, and write a ranked CSV to `outputs/screen_results_YYYY-MM-DD.csv`. Log progress as it runs (it will be slow).
- **Acceptance criteria:**
  - [x] Script reads all unique tickers from drive file headers (or a cached list)
  - [x] Runs `characterize()` on each ticker with full history
  - [x] Filters out tickers below `MIN_AVG_VOLUME`
  - [x] Outputs ranked CSV sorted by Hurst exponent descending
  - [x] CSV columns: `ticker`, `hurst`, `avg_atr_pct`, `autocorr`, `avg_volume`, `max_drawdown`, `history_days`, `classification` (Trending / Mean-Reverting / Random)
  - [x] Logs progress every 100 tickers
  - [x] `ruff check .` passes
- **Files likely involved:** `scripts/run_screen.py`, `src/screener/data.py`, `src/screener/characterize.py`
- **Notes:** This script will take a long time on the full ~8,700 ticker universe. Consider adding a `--tickers` flag to test on a subset.
- **Completion note:** Logic lives in a new testable `src/screener/screen.py` (`discover_tickers`, `available_date_range`, `screen_universe`, `results_frame`, `write_results`); `scripts/run_screen.py` is a thin argparse CLI over it with `--tickers`, `--start`, `--end`, `--drive-path`, and `--min-volume` flags. Tickers come from the `ticker` column of the most recent day's file (one day spans the universe); the full date range is inferred from the drive's filenames. Progress logs every 100 tickers. Output sorts by Hurst descending (NaN last) after the `MIN_AVG_VOLUME` filter. Smoke-tested via the CLI against the sample drive. 9 tests in `tests/test_screen.py` (37 total); `ruff` clean, `pytest` 37 passed.

---

### T-004: Top-up recent data from Alpaca
- **Status:** ✅ Done
- **Priority:** P3
- **Type:** Feature
- **Description:** The drive ends at Oct 2025. Write `scripts/run_topup.py` to fetch daily bars from Alpaca (IEX feed) for Oct 2025 → present and cache them in `data/processed/` so `load_daily_bars()` can append them seamlessly.
- **Acceptance criteria:**
  - [x] `topup_ticker(ticker, since) -> pd.DataFrame` in `src/screener/data.py`
  - [x] Uses Alpaca `StockHistoricalDataClient` with `feed="iex"`
  - [x] Saves result to `data/processed/{ticker}_topup.csv`
  - [x] `load_daily_bars()` appends topup data if file exists
  - [x] Tests mock the Alpaca client
  - [x] `ruff check .` passes, `pytest` passes
- **Files likely involved:** `src/screener/data.py`, `scripts/run_topup.py`, `tests/test_data.py`
- **Notes:** Alpaca API key comes from `config.ALPACA_API_KEY`. Always use `feed="iex"` — the free tier does not support SIP.
- **Completion note:** Added `topup_ticker(ticker, since, client=None)` to `data.py`: builds a `StockBarsRequest` with `feed="iex"` and daily timeframe, reduces Alpaca's `(symbol, timestamp)` MultiIndex to tz-naive dates, and caches OHLCV to `data/processed/{ticker}_topup.csv`. The optional `client` arg makes it injectable so tests use a stub instead of the network. `load_daily_bars` now appends any cached top-up rows within the requested window (drive wins on overlap). Added `scripts/run_topup.py` (`--tickers`, `--since`, default 2025-10-01). 6 tests in `tests/test_data.py` cover save/return, empty response, append, and end-date clipping. `ruff` clean, `pytest` 41 passed.

---

### T-005: Fix entry-point scripts — `ModuleNotFoundError: No module named 'src'`
- **Status:** ✅ Done
- **Priority:** P1
- **Type:** Bug
- **Description:** Running the documented entry points directly (`python scripts/run_screen.py`, `python scripts/run_topup.py`) crashes immediately with `ModuleNotFoundError: No module named 'src'`. Both scripts import `from src.screener... import ...` at module top, but running a file directly puts `scripts/` (not the repo root) on `sys.path[0]`, so `src` is not importable. The test suite masked this because pytest injects the repo root onto `sys.path`; there is no `pyproject.toml`/`pytest.ini`/root `conftest.py` to make the package importable otherwise.
- **Acceptance criteria:**
  - [x] `python scripts/run_screen.py ...` runs without an import error
  - [x] `python scripts/run_topup.py ...` runs without an import error
  - [x] Fix keeps `ruff check .` clean with no `# noqa` suppressions (per CLAUDE.md)
  - [x] `pytest` still passes
- **Files likely involved:** `scripts/run_screen.py`, `scripts/run_topup.py`
- **Notes:** Found during a post-merge status check after PR #3. The pipeline logic itself was correct; only the script-launch path was broken.
- **Completion note:** Added a `sys.path.insert(0, <repo root>)` bootstrap at the top of each script and moved the `src.screener` import into `main()` so it resolves after the bootstrap — avoiding an E402 lint error without suppressing it. Smoke-tested `run_screen.py` end-to-end against the sample drive (writes the CSV; 0 rows as expected for the 2-day sample). `ruff` clean, `pytest` 41 passed.

---

### T-006: Walk-forward validation harness
- **Status:** ✅ Done
- **Priority:** P2
- **Type:** Feature
- **Description:** Build the walk-forward validation step the project purpose calls for. For each screener candidate, run a simple, class-matched, long-only strategy across rolling out-of-sample folds, charge realistic trading costs, and report whether it holds up. The reserved `WFV_*` config params (folds, min-folds-passing, min-trades-per-fold) define the pass rule. This is a research *filter*, not a profit engine — expect most candidates to fail.
- **Acceptance criteria:**
  - [x] `walk_forward(df, strategy, ...) -> WFVResult` engine in `src/screener/validate.py`
  - [x] Splits history into `config.WFV_FOLDS` contiguous out-of-sample folds
  - [x] Charges `config.WFV_COST_PER_TRADE` on every change in exposure
  - [x] No lookahead — signals act on the next bar (positions shifted)
  - [x] Class-matched strategies: breakout (Trending), z-score reversion (Mean-Reverting); `Random`/`Unknown` skipped
  - [x] Pass rule: ≥ `WFV_MIN_FOLDS_PASSING` folds profitable with ≥ `WFV_MIN_TRADES_PER_FOLD` trades each
  - [x] `validate_universe(...)` + `write_validation(...)` pipeline and `scripts/run_validate.py` CLI (`--tickers/--start/--end/--drive-path/--min-volume`)
  - [x] Tests on synthetic series (sample drive is only 2 days)
  - [x] `ruff check .` passes, `pytest` passes
- **Files likely involved:** `src/screener/validate.py`, `scripts/run_validate.py`, `tests/test_validate.py`, `src/screener/config.py`
- **Notes:** Strategy params live in `config.py`. Fixed params, no per-fold optimization — with nothing fit in-sample there's nothing to overfit. Long-only by design (beginner-appropriate, no shorting). Real validation needs the mounted drive; the sample can only exercise the logic.
- **Completion note:** Added `src/screener/validate.py` — a pluggable `walk_forward` engine plus two deliberately simple long-only strategies (`breakout_strategy` Donchian breakout for trending names, `mean_reversion_strategy` z-score reversion for mean-reverting names) dispatched by classification via `validate_candidate`; `Random`/`Unknown` are skipped. Returns use a one-bar execution lag (no lookahead) and `WFV_COST_PER_TRADE` is charged on every exposure change. A fold passes only if profitable **and** it has ≥ `WFV_MIN_TRADES_PER_FOLD` trades; a candidate passes with ≥ `WFV_MIN_FOLDS_PASSING` passing folds. `validate_universe`/`write_validation` mirror the screener pipeline (reusing `discover_tickers`/`available_date_range`); `scripts/run_validate.py` is the thin CLI. Breakout uses **strict** new-high/new-low inequalities so a flat series doesn't "break out" every day. 17 tests in `tests/test_validate.py` cover fold splitting, cost accounting, the no-lookahead guarantee, both strategies, the pass/fail gate (incl. costs flipping a winner to a loser), dispatch, and the pipeline. Added `WFV_COST_PER_TRADE` and strategy params to `config.py`. Smoke-tested the CLI against the sample drive. `ruff` clean, `pytest` 58 passed.

---

## Completed Tickets

- **T-001** — Data loader (`load_daily_bars`), 2026-06-02. See the ticket above for the completion note.
- **T-002** — Characterization module (`characterize`), 2026-06-02. See the ticket above for the completion note.
- **T-003** — Screener pipeline (`screen.py` + `run_screen.py`), 2026-06-02. See the ticket above for the completion note.
- **T-004** — Alpaca top-up (`topup_ticker` + `run_topup.py`), 2026-06-02. See the ticket above for the completion note.
- **T-005** — Fix entry-point script imports (`No module named 'src'`), 2026-06-05. See the ticket above for the completion note.
- **T-006** — Walk-forward validation harness (`validate.py` + `run_validate.py`), 2026-06-05. See the ticket above for the completion note.

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
