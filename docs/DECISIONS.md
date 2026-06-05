# Decisions

## [2026-06-05] — Single-pass daily cache for universe-scale reads

- **Decision:** Add a one-time `build_daily_cache` that reads the by-day archive once and writes a per-ticker daily parquet store under `data/processed/daily_cache/`. `screen`/`validate` read it via `load_daily`/`universe_tickers`, falling back to the live drive scan when no cache exists. The per-file aggregation is `groupby([ticker, day-floor]).agg(...)`, not `groupby(ticker).resample("1D")`.
- **Reason:** The archive is partitioned by day but the screener queries by ticker, so `load_daily_bars` re-reads the whole 23 GB archive once per ticker — benchmarked at ~17 min/ticker, making the ~12k-name universe infeasible (thousands of hours). Reading once and fanning out to all tickers turns that into a single ~28-min pass; subsequent screens read the cache in seconds. The output is provably identical to the loader (an `assert_frame_equal` test is the trust anchor, verified on real data), so there's no quality trade-off — only memory during the build and disk for the cache (a few hundred MB, gitignored). The cache is a *derived* artifact: rebuild when the drive gains new days; top-ups are appended at read time so they don't require a rebuild. `groupby+resample` was chosen first and benchmarked ~8× slower (it materializes an empty date range per ticker per file); the two-key groupby is the same result, far cheaper.

## [2026-06-05] — Walk-forward validation: simple, fixed-parameter, long-only, cost-charged

- **Decision:** The WFV harness validates each candidate with a single fixed-parameter, long-only strategy matched to its screener classification (Donchian breakout for Trending, z-score reversion for Mean-Reverting; Random/Unknown skipped). No per-fold parameter optimization. Every change in exposure is charged `WFV_COST_PER_TRADE` (default 0.1%), and signals act on the next bar (no lookahead). A fold passes only if profitable **and** it has ≥ `WFV_MIN_TRADES_PER_FOLD` trades; a candidate passes with ≥ `WFV_MIN_FOLDS_PASSING` passing folds.
- **Reason:** The point of validation is to *not fool ourselves*, so the design favors honesty over flattering results. Fixed params mean nothing is fit in-sample, so there is nothing to overfit — the folds are pure out-of-sample segments. Costs are charged up front because omitting them is the classic way a losing strategy looks like a winner. Long-only keeps it understandable for a beginner and avoids borrow/short mechanics. The per-fold trade gate intentionally fails buy-and-hold (one trade, then coast): WFV is meant to validate a *trading* rule repeatedly, not a single lucky entry. A real, faithful backtest of a live swing-trading strategy can replace these placeholder rules later — the engine takes any `strategy(df) -> positions` function.

## [2026-06-02] — Use IEX feed for Alpaca stock data

- **Decision:** Always pass `feed="iex"` to Alpaca `StockBarsRequest`.
- **Reason:** Free Alpaca tier does not permit SIP data. IEX is sufficient for daily bars.

## [2026-06-02] — Screener runs manually, no automation

- **Decision:** No GitHub Actions or cron job for the screener.
- **Reason:** The primary data source is a local external drive that GitHub's cloud runners cannot access. Screening is a periodic research task (monthly/quarterly), not a nightly signal check. Candidates discovered by the screener are promoted manually into swing-trader's TICKERS.

## [2026-06-02] — Drive is authoritative over Alpaca top-up on overlapping dates

- **Decision:** When `load_daily_bars` merges cached Alpaca top-up bars with drive bars, the drive value wins for any date present in both.
- **Reason:** The top-up exists only to extend history past the drive's last date (Oct 2025 →). The drive is the trusted historical source; IEX top-up bars are lower-coverage and should not overwrite it where they overlap.

## [2026-06-02] — Loader warns on corrupt dates, stays quiet on missing files

- **Decision:** In `load_daily_bars()`, the 15 known-corrupt Dec-2024 dates (`config.CORRUPT_DATES`) and unreadable files are logged at WARNING; simply-missing files are logged at DEBUG.
- **Reason:** Over a multi-year range, most calendar days have no file (weekends/holidays). Warning on every missing file would bury the genuinely actionable corrupt-file warnings under thousands of expected ones. The acceptance criterion (skip without crashing) is still met for both cases.

## [2026-06-02] — External drive is read-only

- **Decision:** Never write to the external drive. All processed data and outputs go to `data/processed/` and `outputs/` in the project directory.
- **Reason:** Drive data is shared and treated as a trusted source. Writing back risks corruption.
