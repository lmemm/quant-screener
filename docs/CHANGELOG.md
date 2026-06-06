# Changelog

## [2026-06-05]

### Changed
- **T-008:** Validation is now honest about edge. A fold passes only if the strategy is **both profitable and beats buy-and-hold** over that fold — positive-return alone is bull-market beta (the first run's 45%), while positive-excess alone rewards a long-only strategy for merely losing less than a crashing stock (that raised it to ~55%); the intersection is the honest bar. Added a **dollar-volume gate** (`config.MIN_DOLLAR_VOLUME`, with `characterize.avg_dollar_volume`) and **liquidity-aware costs** (`config.WFV_COST_TIERS` / `cost_for_dollar_volume`) replacing the flat fee, so illiquid names stop being flattered (no arbitrary price floor). Output gains `mean_buy_hold` / `mean_excess_return` and ranks by excess. Also fixed a test-isolation bug (sample-drive screen tests now pass an explicit empty `cache_dir` so they don't pick up the machine's real cache).

### Added
- **T-007:** `src/screener/cache.py` — single-pass daily cache. `build_daily_cache` reads the by-day archive once and writes a compact per-ticker daily store to `data/processed/daily_cache/{TICKER}.parquet`; `load_cached_daily` returns a ticker's daily history (identical to `load_daily_bars`) in milliseconds. `load_daily`/`universe_tickers` dispatch to the cache when built, else the drive; `screen_universe`/`validate_universe` use them transparently. New `scripts/build_cache.py` CLI. Verified on the real drive: output bit-for-bit identical to the live loader; full build ~28 min, then sub-second reads (vs ~3,400 hr for a per-ticker full-universe screen). 14 tests in `tests/test_cache.py`, incl. the `assert_frame_equal` trust anchor.
- **T-006:** `src/screener/validate.py` — walk-forward validation. A pluggable `walk_forward(df, strategy, ...)` engine splits a candidate's history into `WFV_FOLDS` out-of-sample folds, charges `WFV_COST_PER_TRADE` on every exposure change, and scores it (a fold passes if profitable with ≥ `WFV_MIN_TRADES_PER_FOLD` trades; a candidate passes with ≥ `WFV_MIN_FOLDS_PASSING` passing folds). Two simple long-only strategies — `breakout_strategy` (Donchian, for Trending names) and `mean_reversion_strategy` (z-score, for Mean-Reverting names) — are dispatched by classification via `validate_candidate`; `Random`/`Unknown` are skipped. Signals act on the next bar (no lookahead). Plus `validate_universe`/`write_validation` and the `scripts/run_validate.py` CLI (`--tickers/--start/--end/--drive-path/--min-volume`) writing `outputs/validation_results_YYYY-MM-DD.csv`.
- `config.WFV_COST_PER_TRADE` and strategy parameters (`BREAKOUT_LOOKBACK`, `BREAKOUT_EXIT_LOOKBACK`, `MEANREV_LOOKBACK`, `MEANREV_Z_ENTRY`, `MEANREV_Z_EXIT`).
- `tests/test_validate.py` — 17 tests (synthetic series): fold splitting, cost accounting, the no-lookahead guarantee, both strategies, the pass/fail gate (incl. costs flipping a winner to a loser), classification dispatch, and the pipeline.

### Fixed
- **T-005:** Entry-point scripts crashed with `ModuleNotFoundError: No module named 'src'` when run directly (`python scripts/run_screen.py`, `python scripts/run_topup.py`) because `scripts/`, not the repo root, lands on `sys.path[0]`. Added a `sys.path` bootstrap to each script (and moved the `src.screener` import into `main()`) so the package resolves regardless of cwd; lint stays clean with no suppressions. Tests had hidden this since pytest injects the repo root onto the path.

## [2026-06-02]

### Added
- **T-004:** `topup_ticker(ticker, since, client=None)` in `src/screener/data.py` (Alpaca IEX daily bars → `data/processed/{ticker}_topup.csv`), top-up append wired into `load_daily_bars`, and the `scripts/run_topup.py` CLI (`--tickers/--since`). Tests mock the Alpaca client.
- **T-003:** `src/screener/screen.py` (`discover_tickers`, `available_date_range`, `screen_universe`, `results_frame`, `write_results`) and the `scripts/run_screen.py` CLI (`--tickers/--start/--end/--drive-path/--min-volume`). Ranks candidates by Hurst descending after the `MIN_AVG_VOLUME` filter and writes `outputs/screen_results_YYYY-MM-DD.csv`.
- `tests/test_screen.py` — 9 tests for ticker discovery, date-range inference, volume filter + ranking, end-to-end screening against the sample drive, and CSV roundtrip.
- **T-002:** `src/screener/characterize.py` with `characterize(df)` and standalone metric helpers (`hurst_exponent`, `avg_atr_pct`, `lag1_autocorr`, `max_drawdown`, `classify_hurst`). Hurst uses rescaled-range analysis on daily returns; ATR is 14-period mean True Range as % of close; max drawdown is a negative fraction. Returns `None` below `config.MIN_HISTORY_DAYS`.
- `tests/test_characterize.py` — 14 tests covering the `characterize()` contract, each metric, the Hurst trending/random/mean-reverting ordering, and classification.
- **T-001:** `src/screener/data.py` with `load_daily_bars(ticker, start, end, drive_path=None)` — reads `YYYY/MM/YYYY-MM-DD.csv.gz` files, filters to a ticker, de-duplicates and drops null OHLCV rows, and resamples 1-minute bars to daily OHLCV. Skips missing/corrupt files without crashing; skips the 15 known Dec-2024 corrupt dates with a warning.
- `config.CORRUPT_DATES` — the 15 known-bad December 2024 dates, skipped by the loader.
- `tests/test_data.py` — 7 tests covering resampling, dedup, dropna, missing files, corrupt-date warnings, and empty results (against the sample drive).
- SessionStart hook (`.claude/hooks/session-start.sh` + `.claude/settings.json`) that installs `requirements.txt` into the system interpreter for Claude Code on the web, so `python -m pytest`/`python -m ruff` resolve project libraries.
- Initial project scaffold: folder structure, CLAUDE.md, BACKLOG.md, config.py, ARCHITECTURE.md
- `.env.example` with `DATA_DRIVE_PATH` and Alpaca keys
- T-001 through T-004 tickets covering data loader, characterization, screener script, and Alpaca top-up
- Pushed scaffold to GitHub and set `main` as the default branch so Claude Code on the Web can work the backlog
- Sample test dataset under `data/sample/` mirroring the drive layout (`YYYY/MM/YYYY-MM-DD.csv.gz`), with a seeded duplicate bar (§5e) and null-close row (§5b)
- `tests/` scaffold: `conftest.py` with `sample_drive` and `expected_daily` fixtures, plus baseline tests validating the fixture (green `pytest`)

### Fixed
- `config.ROOT` pointed above the project root (`parents[3]`); corrected to `parents[2]` so `DATA_RAW`/`DATA_PROCESSED`/`OUTPUTS` resolve correctly
