# Decisions

## [2026-06-02] — Use IEX feed for Alpaca stock data

- **Decision:** Always pass `feed="iex"` to Alpaca `StockBarsRequest`.
- **Reason:** Free Alpaca tier does not permit SIP data. IEX is sufficient for daily bars.

## [2026-06-02] — Screener runs manually, no automation

- **Decision:** No GitHub Actions or cron job for the screener.
- **Reason:** The primary data source is a local external drive that GitHub's cloud runners cannot access. Screening is a periodic research task (monthly/quarterly), not a nightly signal check. Candidates discovered by the screener are promoted manually into swing-trader's TICKERS.

## [2026-06-02] — External drive is read-only

- **Decision:** Never write to the external drive. All processed data and outputs go to `data/processed/` and `outputs/` in the project directory.
- **Reason:** Drive data is shared and treated as a trusted source. Writing back risks corruption.
