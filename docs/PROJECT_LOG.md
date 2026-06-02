# Project Log

## [2026-06-02] — Project scaffolded

- Created quant-screener from the 00_Python_Project_Structure template
- Data source: external drive with 1-min bars for ~8,700 US equities (2020–2025, ~23 GB compressed)
- Four tickets written covering the full pipeline: data loader → characterization → screener script → Alpaca top-up
- Decisions logged: IEX feed, manual-only operation, read-only drive access
- Next: pick up T-001 (data loader)

## [2026-06-02] — Set up for Claude Code on the Web

- Diagnosed why the web agent saw an empty repo: the scaffold was committed locally on a branch with no remote and had never been pushed. Added the `origin` remote, pushed as `main`, and set `main` as the default branch.
- Built a tiny real-derived sample dataset under `data/sample/` (AAPL/MSFT, 2025-01-02/03) mirroring the drive layout so the loader can be tested without the 23 GB external SSD. Seeded a duplicate bar and a null-close row to exercise dedup/dropna.
- Added a `tests/` scaffold with reusable fixtures (`sample_drive`, `expected_daily`) and baseline tests; `ruff` clean, `pytest` 5 passed.
- Fixed a path bug in `config.ROOT` (`parents[3]` → `parents[2]`).
- Created local `.env` (gitignored) pointing at the mounted SSD. Confirmed the 23 GB stays on the SSD — no move needed.
- Next: pick up T-001 (data loader) — fixtures and expected values are ready in `tests/conftest.py`.

## [2026-06-02] — T-001 data loader

- First web session found the deps weren't installed and that the pre-provisioned `pytest`/`ruff` are isolated uv tools that can't see project libraries (bare `pytest` → `ModuleNotFoundError: pandas`). Added a SessionStart hook to `pip install -r requirements.txt` into the system interpreter; standardized on `python -m pytest` / `python -m ruff`.
- Implemented `load_daily_bars()` in `src/screener/data.py`: per-day file reads, dedup on `(ticker, window_start)`, dropna on OHLCV, then `resample("1D")` for first-open/max-high/min-low/last-close/sum-volume. Optional `drive_path` arg keeps tests off the real drive.
- Moved the 15 Dec-2024 corrupt dates into `config.CORRUPT_DATES`; loader warns and skips them. Missing files skipped quietly (debug) — decision logged.
- `ruff` clean, `pytest` 13 passed. Verified output against the `expected_daily` fixture.
- Note: `git push` to the branch returned HTTP 403 (permission denied) this session — commits are local, pending a push-access fix.
- Next: T-002 (characterization) — `data.py` now feeds it daily OHLCV.

## [2026-06-02] — T-002 characterization

- Push access restored mid-session; pushed the hook + T-001, then continued straight into T-002/T-003/T-004.
- Built `characterize()` and standalone metric helpers so each is unit-testable. Key call: the Hurst exponent (R/S method) is applied to **daily returns**, not the price level — that's what makes random-walk prices land at H≈0.5 and gives the trending(>0.5)/mean-reverting(<0.5) split the project relies on.
- Tested the Hurst estimator directly on AR(1) return series (phi=±0.6) and i.i.d. noise for a deterministic trending > random > mean-reverting ordering, sidestepping estimator variance from price→pct_change dilution.
- `ruff` clean, `pytest` 28 passed.
- Next: T-003 (screener script) — wires `data.load_daily_bars` + `characterize` across the universe into a ranked CSV.

## [2026-06-02] — T-003 screener pipeline

- Put the screening logic in a new `src/screener/screen.py` (testable) and kept `scripts/run_screen.py` a thin argparse CLI over it — consistent with "scripts are entry points, logic lives in src/". Added `screen.py` to ARCHITECTURE.
- `discover_tickers` reads the `ticker` column of just the latest day's file rather than scanning ~5 years of archives; `available_date_range` infers the span from filenames.
- Smoke-tested the CLI end-to-end on the sample drive: runs cleanly, writes `outputs/screen_results_<today>.csv` with 0 rows (sample has 2 days < the 500-day history floor — correct).
- `ruff` clean, `pytest` 37 passed.
- Next: T-004 (Alpaca top-up).
