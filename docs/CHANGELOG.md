# Changelog

## [2026-06-02]

### Added
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
