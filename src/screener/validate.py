"""Walk-forward validation — does a simple, class-matched strategy hold up
out-of-sample on a candidate's history? (T-006)

This module is a *research filter*, not a money machine. Its job is to make it
hard to fool yourself: split a candidate's daily history into rolling folds,
run a deliberately simple long-only strategy on each, charge realistic trading
costs, and report how many folds were profitable. A candidate "passes" only if
at least ``config.WFV_MIN_FOLDS_PASSING`` folds were profitable with at least
``config.WFV_MIN_TRADES_PER_FOLD`` trades each — surviving in one lucky period
is not enough.

Design choices, kept honest on purpose:

* **Long-only, fixed parameters.** No shorting, no per-fold optimization. With
  nothing fit in-sample there is nothing to overfit; the folds are pure
  out-of-sample segments. (A future version could optimize on a train window
  and test on the next — the engine is structured to allow it.)
* **Class-matched rules.** Trending names (Hurst high) get a Donchian
  breakout; mean-reverting names get a z-score reversion. ``Random`` names are
  skipped — the screener claims no edge there, so neither do we.
* **Costs first.** Every change in exposure is charged ``WFV_COST_PER_TRADE``.
  Omitting costs is the classic way a losing strategy looks like a winner.
* **No lookahead.** A signal computed from a day's close is acted on the *next*
  day (positions are shifted one bar before returns accrue).

See BACKLOG.md T-006 for the full specification.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config

logger = logging.getLogger(__name__)

# A strategy maps a daily OHLCV frame to a target-position series in {0, 1}
# (1 = long, 0 = flat), indexed like the input.
Strategy = Callable[[pd.DataFrame], pd.Series]


# ── Strategies ───────────────────────────────────────────────────────────────


def _positions_from_signals(
    entries: np.ndarray, exits: np.ndarray, index: pd.Index
) -> pd.Series:
    """Turn entry/exit boolean signals into a held 0/1 position series.

    Flat until an entry fires, then long until an exit fires. Entries while
    already long and exits while already flat are no-ops — this is what makes a
    breakout "hold" between the entry and exit signals.
    """
    held = np.zeros(len(index))
    holding = False
    for i in range(len(index)):
        if holding and exits[i]:
            holding = False
        elif not holding and entries[i]:
            holding = True
        held[i] = 1.0 if holding else 0.0
    return pd.Series(held, index=index)


def breakout_strategy(
    df: pd.DataFrame,
    lookback: int = config.BREAKOUT_LOOKBACK,
    exit_lookback: int = config.BREAKOUT_EXIT_LOOKBACK,
) -> pd.Series:
    """Donchian-channel breakout for trending names (long-only).

    Go long when the close makes a new ``lookback``-day high; exit when it falls
    to a new ``exit_lookback``-day low. Channels use only *prior* closes
    (``shift(1)``) so the current bar never peeks at itself.
    """
    close = df["close"]
    upper = close.rolling(lookback).max().shift(1)
    lower = close.rolling(exit_lookback).min().shift(1)
    # Strict inequalities: a breakout is a *new* high, not merely matching the
    # prior high. Otherwise a flat series "breaks out" every single day.
    entries = (close > upper).fillna(False).to_numpy()
    exits = (close < lower).fillna(False).to_numpy()
    return _positions_from_signals(entries, exits, df.index)


def mean_reversion_strategy(
    df: pd.DataFrame,
    lookback: int = config.MEANREV_LOOKBACK,
    z_entry: float = config.MEANREV_Z_ENTRY,
    z_exit: float = config.MEANREV_Z_EXIT,
) -> pd.Series:
    """Z-score reversion for mean-reverting names (long-only).

    Go long when the close is stretched ``z_entry`` standard deviations *below*
    its rolling mean (oversold); exit when it reverts back up to ``z_exit``
    (typically the mean). Buys weakness, sells the bounce.
    """
    close = df["close"]
    mean = close.rolling(lookback).mean()
    std = close.rolling(lookback).std()
    z = (close - mean) / std
    entries = (z <= z_entry).fillna(False).to_numpy()
    exits = (z >= z_exit).fillna(False).to_numpy()
    return _positions_from_signals(entries, exits, df.index)


# Strategy chosen per screener classification. ``Random``/``Unknown`` are absent
# on purpose — no claimed edge, nothing to validate.
STRATEGY_BY_CLASS: dict[str, tuple[str, Strategy]] = {
    "Trending": ("breakout", breakout_strategy),
    "Mean-Reverting": ("mean_reversion", mean_reversion_strategy),
}


# ── Engine ───────────────────────────────────────────────────────────────────


@dataclass
class FoldResult:
    """Outcome of one out-of-sample fold."""

    fold: int
    start: dt.date
    end: dt.date
    n_trades: int
    total_return: float       # strategy return, net of costs (0.05 = +5%)
    buy_hold_return: float    # holding the stock over the same window
    excess_return: float      # total_return - buy_hold_return
    passing: bool             # beat buy-and-hold AND enough trades to count


@dataclass
class WFVResult:
    """Walk-forward validation result for one candidate + strategy."""

    strategy: str
    folds: list[FoldResult] = field(default_factory=list)
    folds_passing: int = 0
    n_folds: int = 0
    passed: bool = False
    total_trades: int = 0
    mean_fold_return: float = float("nan")
    mean_buy_hold: float = float("nan")
    mean_excess_return: float = float("nan")

    def to_row(self, ticker: str, classification: str) -> dict:
        """Flatten to a CSV/DataFrame row."""
        return {
            "ticker": ticker,
            "classification": classification,
            "strategy": self.strategy,
            "folds_passing": self.folds_passing,
            "n_folds": self.n_folds,
            "total_trades": self.total_trades,
            "mean_fold_return": self.mean_fold_return,
            "mean_buy_hold": self.mean_buy_hold,
            "mean_excess_return": self.mean_excess_return,
            "passed": self.passed,
        }


def _fold_bounds(n: int, n_folds: int) -> list[tuple[int, int]]:
    """Split ``n`` rows into up to ``n_folds`` contiguous, near-equal folds."""
    edges = np.linspace(0, n, n_folds + 1).astype(int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(n_folds) if edges[i + 1] > edges[i]]


def _strategy_returns(
    df: pd.DataFrame, strategy: Strategy, cost: float
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Strategy net daily returns, entry flags, and the stock's daily returns.

    Positions are shifted one bar (act on the *next* day's open-to-open move, no
    lookahead) and every change in exposure is charged ``cost``. Returns
    ``(net_return, entries, daily_ret)`` aligned to ``df.index``: ``net_return``
    is the strategy's daily P&L net of cost, ``entries`` marks bars where a new
    long is opened (trade count), and ``daily_ret`` is the underlying's daily
    return — the buy-and-hold benchmark each fold must be beaten.
    """
    positions = strategy(df).reindex(df.index).fillna(0.0).clip(0.0, 1.0)
    exposure = positions.shift(1).fillna(0.0)          # act next bar
    daily_ret = df["close"].pct_change().fillna(0.0)

    turnover = exposure.diff().abs().fillna(exposure.abs())
    net_return = exposure * daily_ret - turnover * cost
    entries = exposure.diff().fillna(exposure) > 0      # 0 -> 1 transitions
    return net_return, entries, daily_ret


def walk_forward(
    df: pd.DataFrame,
    strategy: Strategy,
    *,
    n_folds: int = config.WFV_FOLDS,
    min_trades: int = config.WFV_MIN_TRADES_PER_FOLD,
    min_folds_passing: int = config.WFV_MIN_FOLDS_PASSING,
    cost: float = config.WFV_COST_PER_TRADE,
    strategy_name: str | None = None,
) -> WFVResult:
    """Run ``strategy`` across rolling folds of ``df`` and score it.

    A fold *passes* when the strategy **beats buy-and-hold** over that fold (net
    of costs) **and** has at least ``min_trades`` trades. Requiring an edge over
    simply holding the stock — rather than just any positive return — is what
    separates skill from riding a rising market. The candidate passes when at
    least ``min_folds_passing`` folds pass.

    Returns:
        A :class:`WFVResult`. With fewer rows than ``n_folds`` (or an empty
        frame) it returns a non-passing result with whatever folds fit.
    """
    name = strategy_name or getattr(strategy, "__name__", "strategy")
    if df.empty:
        return WFVResult(strategy=name)

    net_return, entries, daily_ret = _strategy_returns(df, strategy, cost)
    bounds = _fold_bounds(len(df), n_folds)

    folds: list[FoldResult] = []
    for k, (a, b) in enumerate(bounds, start=1):
        n_trades = int(entries.iloc[a:b].sum())
        total_return = float((1.0 + net_return.iloc[a:b]).prod() - 1.0)
        buy_hold = float((1.0 + daily_ret.iloc[a:b]).prod() - 1.0)
        excess = total_return - buy_hold
        passing = excess > 0 and n_trades >= min_trades
        folds.append(
            FoldResult(
                fold=k,
                start=df.index[a].date(),
                end=df.index[b - 1].date(),
                n_trades=n_trades,
                total_return=total_return,
                buy_hold_return=buy_hold,
                excess_return=excess,
                passing=passing,
            )
        )

    folds_passing = sum(f.passing for f in folds)

    def mean(vals: list[float]) -> float:
        return float(np.mean(vals)) if folds else float("nan")

    return WFVResult(
        strategy=name,
        folds=folds,
        folds_passing=folds_passing,
        n_folds=len(folds),
        passed=folds_passing >= min_folds_passing,
        total_trades=sum(f.n_trades for f in folds),
        mean_fold_return=mean([f.total_return for f in folds]),
        mean_buy_hold=mean([f.buy_hold_return for f in folds]),
        mean_excess_return=mean([f.excess_return for f in folds]),
    )


def cost_for_dollar_volume(avg_dollar_volume: float) -> float:
    """Round-trip cost for a name, scaled to its liquidity (``config.WFV_COST_TIERS``).

    Thinner names pay more because their real spread/slippage is wider — this is
    the liquidity-aware alternative to charging every name the same flat fee.
    """
    for threshold, cost in config.WFV_COST_TIERS:
        if avg_dollar_volume >= threshold:
            return cost
    return config.WFV_COST_TIERS[-1][1]


def validate_candidate(df: pd.DataFrame, classification: str, **kwargs) -> WFVResult | None:
    """Validate one candidate with the strategy matched to its classification.

    Returns ``None`` for classifications with no matched strategy (``Random`` /
    ``Unknown``) — there is no claimed edge to test. Extra keyword args are
    forwarded to :func:`walk_forward`.
    """
    matched = STRATEGY_BY_CLASS.get(classification)
    if matched is None:
        return None
    name, strategy = matched
    return walk_forward(df, strategy, strategy_name=name, **kwargs)


# ── Pipeline ─────────────────────────────────────────────────────────────────

# Column order of the validation output CSV.
VALIDATION_COLUMNS = [
    "ticker",
    "classification",
    "strategy",
    "folds_passing",
    "n_folds",
    "total_trades",
    "mean_fold_return",
    "mean_buy_hold",
    "mean_excess_return",
    "passed",
]


def validate_universe(
    drive_path=None,
    tickers: list[str] | None = None,
    start=None,
    end=None,
    min_avg_volume: float = config.MIN_AVG_VOLUME,
    cache_dir=None,
) -> pd.DataFrame:
    """Characterize, then walk-forward-validate every ticker on the drive.

    Reads from the daily cache when built (else scans the drive). For each
    ticker: load daily bars, characterize it (to get its volume and
    classification), drop it if below ``min_avg_volume`` or too short to
    characterize, then validate it with the class-matched strategy. ``Random``
    names (no matched strategy) are skipped. Returns a frame with the passing
    candidates first, then by how many folds they cleared.
    """
    # Imported here so the lightweight engine/strategy API above has no hard
    # dependency on drive I/O.
    from pathlib import Path

    from . import cache
    from .characterize import characterize
    from .screen import available_date_range

    drive_path = config.DRIVE_PATH if drive_path is None else Path(drive_path)
    using_cache = cache.cache_available(cache_dir)

    if start is None or end is None:
        span = available_date_range(drive_path)
        if span is None:
            logger.warning("No data files found under %s", drive_path)
            return pd.DataFrame(columns=VALIDATION_COLUMNS)
        start = start or span[0]
        end = end or span[1]

    if tickers is None:
        tickers = cache.universe_tickers(drive_path, cache_dir)
    logger.info(
        "Validating %d tickers from %s to %s (source: %s)",
        len(tickers), start, end, "cache" if using_cache else "drive",
    )

    rows: list[dict] = []
    for ticker in tickers:
        df = cache.load_daily(ticker, start, end, drive_path=drive_path, cache_dir=cache_dir)
        metrics = characterize(df)
        if metrics is None:
            continue
        # Gate on *dollar* volume (real liquidity) so the cost model is credible;
        # the legacy share-volume floor is kept as a secondary guard.
        if (
            metrics["avg_dollar_volume"] < config.MIN_DOLLAR_VOLUME
            or metrics["avg_volume"] < min_avg_volume
        ):
            continue
        # Charge a liquidity-aware cost for this name rather than a flat fee.
        cost = cost_for_dollar_volume(metrics["avg_dollar_volume"])
        result = validate_candidate(df, metrics["classification"], cost=cost)
        if result is None:  # Random/Unknown — no strategy to test
            continue
        rows.append(result.to_row(ticker, metrics["classification"]))

    frame = pd.DataFrame(rows, columns=VALIDATION_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["passed", "folds_passing", "mean_excess_return"], ascending=False
    ).reset_index(drop=True)


def write_validation(df: pd.DataFrame, outputs_dir=None):
    """Write the validation frame to ``outputs/validation_results_YYYY-MM-DD.csv``."""
    from pathlib import Path

    outputs_dir = config.OUTPUTS if outputs_dir is None else Path(outputs_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    path = outputs_dir / f"validation_results_{dt.date.today():%Y-%m-%d}.csv"
    df.to_csv(path, index=False)
    n_passed = int(df["passed"].sum()) if not df.empty else 0
    logger.info("Wrote %d validated tickers (%d passed) to %s", len(df), n_passed, path)
    return path
