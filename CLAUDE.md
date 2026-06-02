# CLAUDE.md — Instructions for Claude Code

Read this file completely before starting any work.

---

## Project Purpose

quant-screener finds stocks worth adding to the swing-trader pipeline. It reads
historical intraday data from a local external drive, resamples it to daily bars,
computes characterization statistics (Hurst exponent, ATR, autocorrelation,
volume), and runs walk-forward validation on candidates. Output is a ranked CSV
of stocks ready for manual review and promotion into swing-trader's TICKERS.

This project runs manually — there is no automated scheduler. The external drive
must be mounted before running any data scripts.

---

## Before You Start

1. Read this file completely.
2. Read `docs/ARCHITECTURE.md` to understand the system.
3. Read `BACKLOG.md` to find the current open ticket.
4. Read `docs/DECISIONS.md` for past architectural choices.
5. Check `docs/CHANGELOG.md` for recent changes.

---

## How to Work — Agent Workflow

### Picking Up a Ticket

- Open `BACKLOG.md` and find the highest-priority `⬚ Open` ticket.
- Change its status to `🔵 In Progress`.
- Create a feature branch: `feature/T-XXX-short-description`
- Read the ticket description and acceptance criteria carefully before writing code.
- If anything is ambiguous, mark the ticket `🟡 Blocked` and explain why.

### Implementing

- Work only on what the ticket describes — no scope creep.
- Follow the project conventions below.
- Write tests alongside the implementation, not after.
- Run `ruff check .` and `pytest` before considering the work done.
- Check off acceptance criteria as you go.

### Completing a Ticket

When all acceptance criteria are met:
1. Run `ruff check .` — fix any issues.
2. Run `pytest` — all tests must pass.
3. Update the ticket status in `BACKLOG.md` to `✅ Done`.
4. Add a completion note on the ticket.
5. Append an entry to `docs/CHANGELOG.md`.
6. Append an entry to `docs/PROJECT_LOG.md`.
7. If you made an architectural decision, document it in `docs/DECISIONS.md`.
8. If you added or changed a major component, update `docs/ARCHITECTURE.md`.
9. Commit with a message referencing the ticket: `T-XXX: short description`

---

## Secrets & Environment Variables

- All secrets and paths live in `.env` only — never commit `.env`
- `.env.example` is committed — update it when adding new variables
- All env loading happens in `src/screener/config.py` — nowhere else

---

## Data Sources

- **Primary:** External drive at `DRIVE_PATH` (set in `.env`) — 1-minute bars for
  ~8,700 US equities, 2020–2025, organized as `YYYY/MM/YYYY-MM-DD.csv.gz`
- **Top-up:** Alpaca IEX feed for recent bars not yet on the drive
- **Drive must be mounted** before running any data scripts — check with
  `ls "$DATA_DRIVE_PATH"` first

## Data Safety

- Never write to the external drive — read only
- `data/raw/` is gitignored — do not commit price data
- `data/processed/` and `outputs/` are gitignored

---

## Project Conventions

- **Python version**: 3.11+
- **Naming**: `snake_case` for files and functions, `PascalCase` for classes
- **Linting**: Run `ruff check .` before every commit — fix issues, never suppress
- **Commits**: Short imperative subject referencing ticket: `T-001: Add data loader`
- **Branching**: Feature branches only: `feature/T-XXX-short-description`
- **Config**: All parameters and paths live in `config.py` — no magic numbers elsewhere
- **Tests**: Use small sample CSVs in `data/` committed to the repo — never read from the drive in tests

---

## File Layout

| Directory | Purpose |
|:----------|:--------|
| `src/screener/` | All application code |
| `tests/` | Pytest tests |
| `scripts/` | Entry point scripts |
| `data/` | Small sample files for tests only (gitignored for large data) |
| `outputs/` | Gitignored — screening results and ranked CSVs |
| `docs/` | Architecture, changelog, decisions, project log |
| `scratch/` | Gitignored — local experiments only |
| `notebooks/` | Jupyter exploration |
| `BACKLOG.md` | All tickets and their status |

---

## Running & Testing

```bash
# Run the screener (drive must be mounted)
python scripts/run_screen.py

# Run tests
pytest

# Lint
ruff check .
```
