# Changelog

## [2026-06-02]

### Added
- Initial project scaffold: folder structure, CLAUDE.md, BACKLOG.md, config.py, ARCHITECTURE.md
- `.env.example` with `DATA_DRIVE_PATH` and Alpaca keys
- T-001 through T-004 tickets covering data loader, characterization, screener script, and Alpaca top-up
- Pushed scaffold to GitHub and set `main` as the default branch so Claude Code on the Web can work the backlog
- Sample test dataset under `data/sample/` mirroring the drive layout (`YYYY/MM/YYYY-MM-DD.csv.gz`), with a seeded duplicate bar (§5e) and null-close row (§5b)
- `tests/` scaffold: `conftest.py` with `sample_drive` and `expected_daily` fixtures, plus baseline tests validating the fixture (green `pytest`)

### Fixed
- `config.ROOT` pointed above the project root (`parents[3]`); corrected to `parents[2]` so `DATA_RAW`/`DATA_PROCESSED`/`OUTPUTS` resolve correctly
