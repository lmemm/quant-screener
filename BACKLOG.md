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

### T-007: Single-pass daily cache (universe screening is infeasible without it)
- **Status:** ✅ Done
- **Priority:** P1
- **Type:** Feature / Performance
- **Description:** `load_daily_bars` reads data **per ticker** by scanning every daily file and keeping one symbol's rows. The archive is partitioned **by day** (each file = all ~12k tickers for one day), so a full-universe screen re-reads the entire 23 GB archive once per ticker. Benchmarked on the real drive at **~17 min/ticker** → the full ~12k-name universe is infeasible (thousands of hours). Build a one-pass cache: read the archive **once**, resample every ticker to daily in that pass, and write a compact per-ticker daily store so screen/validate read in seconds.
- **Acceptance criteria:**
  - [x] `build_daily_cache(...)` in `src/screener/cache.py` — one pass over the archive → `data/processed/daily_cache/{TICKER}.parquet`
  - [x] `load_cached_daily(ticker, start, end)` returns the **identical** frame as `load_daily_bars` (asserted bit-for-bit by tests, incl. on real data)
  - [x] `load_daily`/`universe_tickers` dispatchers: use cache when built, fall back to the drive otherwise
  - [x] `screen_universe`/`validate_universe` read via the cache transparently
  - [x] `scripts/build_cache.py` CLI (`--start/--end/--drive-path/--cache-dir`)
  - [x] Tests incl. the equality (trust-anchor) test on the sample drive
  - [x] `ruff check .` passes, `pytest` passes
- **Files likely involved:** `src/screener/cache.py`, `scripts/build_cache.py`, `tests/test_cache.py`, `src/screener/screen.py`, `src/screener/validate.py`
- **Notes:** Cache lives under gitignored `data/processed/`. Derived artifact — rebuild when the drive gains new days; Alpaca top-ups are still appended at read time so they need no rebuild. The per-file aggregation is `groupby([ticker, day-floor]).agg(...)`, **not** `groupby(ticker).resample("1D")` — the latter materializes an empty date range per ticker and was ~8× slower in benchmarking.
- **Completion note:** Added `src/screener/cache.py`. `build_daily_cache` reads each day file once, dedups/dropna/aggregates to one daily bar per `(ticker, day)`, collapses any cross-file day-boundary spill, and writes per-ticker parquet. `load_cached_daily` mirrors `load_daily_bars` exactly (date filter + top-up append). `load_daily`/`universe_tickers` pick cache-or-drive; `screen_universe`/`validate_universe` use them (lazy import to avoid a cycle). Verified on the **real drive** (AAPL/MSFT/NVDA, Aug–Sep 2025): output bit-for-bit `IDENTICAL` to the live loader. Benchmark caught a slow first implementation (per-file `groupby+resample`, ~3.7 hr full build) and the `groupby([ticker, day])` rewrite brought it to **~28 min full build, then sub-second reads** (vs ~3,400 hr for a per-ticker full-universe screen). 14 tests in `tests/test_cache.py` (incl. the equality trust anchor); `ruff` clean, `pytest` 66 passed.

---

### T-008: Honest validation — beat buy-and-hold, dollar-volume gate, liquidity-aware costs
- **Status:** ✅ Done
- **Priority:** P1
- **Type:** Feature / Correctness
- **Description:** The first full validation run passed 476/1,053 candidates (~45%) — far too many. Investigation showed it was mostly **bull-market beta**: passers went up over 2020–2025 far more than non-passers (65% vs 36% positive buy-and-hold), the pass bar was merely "any positive return," and illiquid microcaps (fold returns up to +448%) dominated the top under an unrealistic flat 0.1% cost. Make validation honest.
- **Acceptance criteria:**
  - [x] A fold passes only if the strategy is **both profitable AND beats buy-and-hold** over that fold (return > 0 and excess > 0) — `walk_forward` computes per-fold buy-hold and excess
  - [x] Gate validation on **dollar volume** (`config.MIN_DOLLAR_VOLUME`), not share count; `characterize` reports `avg_dollar_volume`
  - [x] **Liquidity-aware cost** (`config.WFV_COST_TIERS` via `cost_for_dollar_volume`) instead of a flat fee — thin names pay more
  - [x] Output reports `mean_buy_hold` and `mean_excess_return`; ranking is by excess (skill), not raw return
  - [x] Tests for the beat-buy-hold gate, cost tiers, and new columns; `ruff`/`pytest` green
- **Files likely involved:** `src/screener/validate.py`, `src/screener/characterize.py`, `src/screener/config.py`, `src/screener/screen.py`, `tests/`
- **Notes:** Owner pushed back (correctly) on an arbitrary *price* floor — the real lever is dollar-volume + realistic costs, not excluding cheap stocks by fiat. No price floor was added; cheap names that genuinely clear an honest cost still pass.
- **Completion note:** `walk_forward` now benchmarks every fold against buy-and-hold and a fold passes only when the strategy is **both profitable and beats buy-and-hold** (return > 0 **and** excess > 0, + the trade-count gate). The re-run caught the in-between trap: requiring excess alone *raised* the pass rate (a long-only strategy "beats" a crashing stock by sitting in cash), so both conditions are required. `FoldResult`/`WFVResult` carry `buy_hold_return`/`excess_return` and the CSV gains `mean_buy_hold`/`mean_excess_return` (ranking by excess). `characterize` adds `avg_dollar_volume`; `validate_universe` gates on `MIN_DOLLAR_VOLUME` ($5M) and charges a per-ticker `cost_for_dollar_volume` from tiered `WFV_COST_TIERS` (5/15/30 bps by liquidity). Found and fixed a test-isolation bug surfaced by this work: `screen_universe(sample_drive)` had started auto-using the machine's real cache — sample-drive tests now pass an explicit empty `cache_dir`. `ruff` clean, `pytest` 69 passed. Re-run off the existing cache (no rebuild) to regenerate the CSVs.

---

## Completed Tickets

- **T-001** — Data loader (`load_daily_bars`), 2026-06-02. See the ticket above for the completion note.
- **T-002** — Characterization module (`characterize`), 2026-06-02. See the ticket above for the completion note.
- **T-003** — Screener pipeline (`screen.py` + `run_screen.py`), 2026-06-02. See the ticket above for the completion note.
- **T-004** — Alpaca top-up (`topup_ticker` + `run_topup.py`), 2026-06-02. See the ticket above for the completion note.
- **T-005** — Fix entry-point script imports (`No module named 'src'`), 2026-06-05. See the ticket above for the completion note.
- **T-006** — Walk-forward validation harness (`validate.py` + `run_validate.py`), 2026-06-05. See the ticket above for the completion note.
- **T-007** — Single-pass daily cache (`cache.py` + `build_cache.py`), 2026-06-05. See the ticket above for the completion note.
- **T-008** — Honest validation (beat buy-and-hold, dollar-volume gate, liquidity-aware costs), 2026-06-05. See the ticket above for the completion note.

---

## Open Tickets (next up)

### T-009: Investigate the Hurst classification skew
- **Status:** ⬚ Open
- **Priority:** P2
- **Type:** Investigation
- **Description:** The first full screen labelled 1,020 Trending vs only 33 Mean-Reverting (≈31:1). Daily-return Hurst shouldn't be that lopsided — the R/S estimator is known to bias high on short series. Verify the estimator against series of known Hurst, check the thresholds, and correct any bias so the trending/mean-reverting split is trustworthy (the whole pipeline keys off this label).
- **Acceptance criteria:**
  - [ ] Estimator validated against synthetic fractional series of known H
  - [ ] Bias quantified; thresholds and/or method adjusted if warranted
  - [ ] Tests; `ruff`/`pytest` green

### T-010: Collision-safe cache filenames
- **Status:** ⬚ Open
- **Priority:** P3
- **Type:** Bug
- **Description:** The full build wrote 19,301 ticker frames but only 19,285 distinct files — ~16 collisions from `_safe_name` mapping `/` → `_` (e.g. two symbols collapsing to the same stem). Use a collision-safe scheme so no ticker is silently overwritten.
- **Acceptance criteria:**
  - [ ] No two tickers map to the same cache file
  - [ ] Test covering a colliding pair; `ruff`/`pytest` green

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
