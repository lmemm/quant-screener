# Sample dataset (for tests only)

A tiny, committed stand-in for the real external drive. It mirrors the drive's
layout exactly — `YYYY/MM/YYYY-MM-DD.csv.gz` with the documented columns
`ticker, volume, open, close, high, low, window_start, transactions` and
nanosecond-epoch `window_start` — so the data loader can be pointed here in
tests without any special-casing. **Tests must never read the real drive**
(see `CLAUDE.md`).

Rows are real 1-minute bars for `AAPL` and `MSFT` pulled from
`2025-01-02` and `2025-01-03`, trimmed to the first few minutes each. Two
deliberate quirks were seeded into **day 1** to exercise the loader:

- **Duplicate bar (§5e):** the `AAPL` bar at `1735808520000000000` appears
  twice and must be de-duplicated before resampling.
- **Null value (§5b):** one `AAPL` row has an empty `close` and must be dropped.

Day 2 is clean.

## Expected daily OHLCV (after dedup + dropna)

These are asserted via the `expected_daily` fixture in `tests/conftest.py`.

| Ticker | Date | open | close | high | low | volume |
|---|---|---|---|---|---|---|
| AAPL | 2025-01-02 | 251.36 | 251.13 | 251.42 | 250.60 | 5181 |
| AAPL | 2025-01-03 | 243.80 | 243.60 | 243.99 | 243.60 | 5299 |
| MSFT | 2025-01-02 | 424.50 | 424.39 | 424.50 | 423.91 | 6045 |
| MSFT | 2025-01-03 | 420.58 | 420.91 | 420.91 | 420.58 | 3210 |

Resampling rule: daily `open` = first bar's open, `close` = last bar's close,
`high` = max, `low` = min, `volume` = sum.
