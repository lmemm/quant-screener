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
