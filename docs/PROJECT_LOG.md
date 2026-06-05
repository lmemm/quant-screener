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

## [2026-06-02] — T-004 Alpaca top-up

- `topup_ticker` takes an optional injected `client`, so tests exercise the full path (request construction, MultiIndex reduction, date normalization, CSV cache, append) with a stub and no network — satisfying "tests mock the Alpaca client".
- `load_daily_bars` now appends cached top-up rows within the requested window; the drive wins on any overlapping date (logged in DECISIONS).
- Confirmed `feed="iex"` is accepted by alpaca-py (coerced to `DataFeed.IEX`).
- Added `scripts/run_topup.py`. `ruff` clean, `pytest` 41 passed (one harmless third-party `websockets` deprecation warning from importing alpaca-py).
- All four backlog tickets (T-001–T-004) are now ✅ Done. The pipeline is complete end-to-end: drive → daily bars (+ Alpaca top-up) → characterization → ranked CSV.

## [2026-06-05] — T-005 fix entry-point script imports

- Post-merge status check after PR #3: pulled `main`, ran `ruff` (clean) and `pytest` (41 passed), then smoke-tested the documented entry points. Both `python scripts/run_screen.py` and `python scripts/run_topup.py` crashed immediately with `ModuleNotFoundError: No module named 'src'` — running a script directly puts `scripts/` on `sys.path[0]`, not the repo root, so the top-level `from src.screener...` import can't resolve. Tests passed only because pytest injects the repo root; there's no `pyproject.toml`/`pytest.ini`/root `conftest.py`.
- Fix: `sys.path.insert(0, <repo root>)` bootstrap in each script + moved the `src.screener` import into `main()` so it runs after the bootstrap (keeps `ruff` clean without a `# noqa`). Verified `run_screen.py` runs end-to-end on the sample drive. `ruff` clean, `pytest` 41 passed.
- Next: walk-forward validation (the one piece of the stated project purpose with config params but no module/ticket) — needs a strategy spec before implementing.

## [2026-06-05] — T-006 walk-forward validation

- The owner is new to quant trading and explicit that this is for learning, not a promised profit. Set expectations plainly: WFV is a filter to avoid fooling yourself, not a money machine, and a good one rejects most strategies. Chose a deliberately simple, honest design over anything fancy (logged in DECISIONS).
- Built `src/screener/validate.py`: pluggable `walk_forward` engine + class-matched long-only strategies (Donchian `breakout_strategy` for Trending, z-score `mean_reversion_strategy` for Mean-Reverting), dispatched by classification; Random/Unknown skipped. One-bar execution lag (no lookahead); `WFV_COST_PER_TRADE` charged on every exposure change. `validate_universe`/`write_validation` mirror the screener; `scripts/run_validate.py` is the CLI.
- Two things the tests caught and corrected: (1) breakout entry/exit must use **strict** new-high/new-low inequalities, else a flat series "breaks out" every day; (2) a clean monotonic trend legitimately makes one trade and holds, so it correctly *fails* the per-fold trade gate — the original test asserted the wrong thing. Validated the pass path on a fast symmetric oscillation (mean reversion trades and profits each fold).
- Sample drive is only 2 days, so all 17 new tests use synthetic series; the CLI smoke-tests to a 0-row CSV (history < 500-day floor), same as the screener. `ruff` clean, `pytest` 58 passed.
- Pipeline is now end-to-end: drive → daily bars (+top-up) → characterization → ranked CSV → walk-forward validation → pass/fail CSV → manual review + paper trading.
- Next (not started): run the real screen + validation on the mounted drive; consider a `--from-screen <csv>` flag so validation reads candidates directly from a screen result; later, port the actual swing-trader entry/exit rules in place of the placeholder strategies.

## [2026-06-05] — T-007 single-pass daily cache

- Connected the real drive and benchmarked before any big run (the owner was rightly skeptical of a "free" speedup). Measured on real data: `load_daily_bars` is **~17 min/ticker** because the archive is partitioned by day (each file = all ~12k tickers) but the loader queries by ticker — so a full-universe screen re-reads the whole 23 GB archive once per ticker (~3,400 hr, infeasible). The drive actually carries **11,963 tickers**, more than the ~8,700 assumed.
- Built `src/screener/cache.py`: `build_daily_cache` reads the archive **once** and writes per-ticker daily parquet to `data/processed/daily_cache/`; `load_cached_daily` mirrors `load_daily_bars` exactly. Wired `load_daily`/`universe_tickers` dispatchers (cache when built, drive fallback) into `screen_universe`/`validate_universe` via lazy import (avoids a cache↔screen cycle). Added `scripts/build_cache.py`.
- Proof-of-concept on the real drive (AAPL/MSFT/NVDA, Aug–Sep 2025) before committing: output **bit-for-bit identical** to the live loader. The PoC also caught that my first build was slow (~3.7 hr extrapolated) — bottleneck was a per-file `groupby(ticker).resample("1D")` over 12k tickers. Switched to `groupby([ticker, day-floor]).agg(...)` (same result, no empty date ranges): full build re-estimated at **~28 min**, then sub-second reads. Equality test stayed green through the rewrite.
- The `assert_frame_equal` equality test is the trust anchor for "no quality loss"; 14 cache tests total. `ruff` clean, `pytest` 66 passed.
- Owner had to step away; confirmed the data run must happen **locally** (Claude Code on the Web has no access to the external drive — see manual-only decision), so kicked off the full build → full screen → validation as an unattended `caffeinate`d background job, leaving result CSVs in `outputs/`.
- Next: review the first real `screen_results` / `validation_results` CSVs; expect most names to fail validation (that's the filter working).
