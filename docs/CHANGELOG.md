# Changelog

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
