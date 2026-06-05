"""Tests for the walk-forward validation harness (T-006).

The committed sample drive is only two days, so these tests build deterministic
synthetic price series to exercise the engine, the strategies, costs, and the
no-lookahead guarantee.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.screener import config
from src.screener.validate import (
    FoldResult,
    WFVResult,
    _fold_bounds,
    _strategy_returns,
    breakout_strategy,
    mean_reversion_strategy,
    validate_candidate,
    validate_universe,
    walk_forward,
    write_validation,
)


def _frame(closes: list[float] | np.ndarray) -> pd.DataFrame:
    """Daily OHLCV frame from a close series (high/low/open = close here)."""
    closes = np.asarray(closes, dtype=float)
    index = pd.date_range("2020-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": np.full(len(closes), 1_000_000.0),
        },
        index=index,
    )


# ── fold splitting ───────────────────────────────────────────────────────────


def test_fold_bounds_partitions_contiguously():
    bounds = _fold_bounds(120, 6)
    assert len(bounds) == 6
    # Contiguous, non-overlapping, covering the whole range.
    assert bounds[0][0] == 0 and bounds[-1][1] == 120
    for (a, b), (c, _d) in zip(bounds, bounds[1:]):
        assert b == c and b > a
    assert sum(b - a for a, b in bounds) == 120


def test_fold_bounds_drops_empty_folds_when_short():
    # Fewer rows than folds -> at most one fold per row, no empties.
    bounds = _fold_bounds(3, 6)
    assert all(b > a for a, b in bounds)
    assert sum(b - a for a, b in bounds) == 3


# ── engine: costs and no lookahead ───────────────────────────────────────────


def test_positions_act_next_bar_no_lookahead():
    # A strategy that only goes long once the close hits 110. The signal fires
    # on the jump day (index 2), but exposure is shifted one bar, so the +10%
    # jump itself is NOT earned — we're only positioned from the next day.
    df = _frame([100.0, 100.0, 110.0, 110.0])

    def strat(d):
        return (d["close"] >= 110).astype(float)

    net, entries = _strategy_returns(df, strat, cost=0.0)
    assert net.iloc[2] == pytest.approx(0.0)  # breakout day's jump not captured
    assert int(entries.sum()) == 1


def test_cost_is_charged_on_entry():
    # Flat then enter long on day 2 (signal day 1, acts day 2). With a flat
    # price the only P&L is the entry cost.
    def enter_day1(d):
        pos = pd.Series(0.0, index=d.index)
        pos.iloc[1:] = 1.0
        return pos

    df = _frame([100.0, 100.0, 100.0, 100.0])
    net, entries = _strategy_returns(df, enter_day1, cost=0.01)
    assert int(entries.sum()) == 1
    assert net.sum() == pytest.approx(-0.01)  # one entry, charged once


# ── strategies ───────────────────────────────────────────────────────────────


def test_breakout_goes_long_on_new_high_and_holds():
    # Flat base, then a sustained step up: breakout should enter and stay long.
    closes = [100.0] * 25 + [105.0] * 25
    pos = breakout_strategy(_frame(closes), lookback=20, exit_lookback=10)
    assert pos.iloc[:20].sum() == 0  # no signal during warmup/flat base
    assert pos.iloc[-1] == 1.0       # long at the end of the uptrend


def test_breakout_captures_an_uptrend():
    # On a clean monotonic uptrend the breakout enters once and holds: every
    # fold is profitable, but only the first fold trades — so it does NOT pass
    # the per-fold trade gate. That's the honest behaviour; assert the parts we
    # can rely on (positive returns, captured the move with a single trade).
    closes = np.linspace(100.0, 200.0, 200)
    res = walk_forward(_frame(closes), breakout_strategy, cost=0.0)
    assert res.mean_fold_return > 0
    assert res.total_trades == 1
    assert not res.passed  # buy-and-hold isn't re-validated each fold


def test_mean_reversion_buys_dips():
    # A clean down-then-up V: the strategy should be long near the trough.
    closes = list(np.linspace(100, 80, 30)) + list(np.linspace(80, 100, 30))
    pos = mean_reversion_strategy(_frame(closes), lookback=20, z_entry=-1.0, z_exit=0.0)
    assert pos.sum() > 0  # it took at least some long exposure on the dip


def test_mean_reversion_passes_on_repeated_oscillation():
    # A fast symmetric oscillation trades several times per fold (buy the dip,
    # sell at the mean) and profits each time — this is the kind of series that
    # should clear walk-forward validation.
    t = np.arange(360)
    closes = 100 + 8 * np.sin(t / 2.0)
    res = walk_forward(_frame(closes), mean_reversion_strategy, cost=0.0)
    assert res.mean_fold_return > 0
    assert res.total_trades >= res.n_folds  # multiple trades, spread across folds
    assert res.passed


# ── pass/fail accounting ─────────────────────────────────────────────────────


def test_min_trades_gate_blocks_thin_folds():
    # Profitable but a single trade: with min_trades=2 the fold must not pass.
    closes = np.linspace(100.0, 130.0, 60)
    df = _frame(closes)
    res = walk_forward(df, breakout_strategy, n_folds=1, min_trades=2, min_folds_passing=1)
    assert res.n_folds == 1
    if res.total_trades < 2:
        assert not res.folds[0].passing
        assert not res.passed


def test_costs_can_flip_a_winner_to_a_loser():
    closes = np.linspace(100.0, 200.0, 200)
    cheap = walk_forward(_frame(closes), breakout_strategy, cost=0.0)
    pricey = walk_forward(_frame(closes), breakout_strategy, cost=0.5)  # absurd cost
    assert cheap.mean_fold_return > pricey.mean_fold_return
    assert not pricey.passed


def test_empty_frame_returns_non_passing():
    res = walk_forward(pd.DataFrame(columns=["close"]), breakout_strategy)
    assert isinstance(res, WFVResult)
    assert not res.passed and res.n_folds == 0


# ── dispatch by classification ───────────────────────────────────────────────


def test_validate_candidate_dispatches_by_class():
    df = _frame(np.linspace(100.0, 200.0, 200))
    assert validate_candidate(df, "Trending").strategy == "breakout"
    assert validate_candidate(df, "Mean-Reverting").strategy == "mean_reversion"


def test_validate_candidate_skips_random():
    df = _frame(np.linspace(100.0, 200.0, 200))
    assert validate_candidate(df, "Random") is None
    assert validate_candidate(df, "Unknown") is None


def test_wfvresult_to_row_has_all_columns():
    res = WFVResult(
        strategy="breakout",
        folds=[FoldResult(1, None, None, 3, 0.1, True)],
        folds_passing=1,
        n_folds=1,
        passed=True,
        total_trades=3,
        mean_fold_return=0.1,
    )
    row = res.to_row("AAPL", "Trending")
    assert row["ticker"] == "AAPL"
    assert row["classification"] == "Trending"
    assert row["passed"] is True


# ── pipeline ─────────────────────────────────────────────────────────────────


def test_validate_universe_handles_empty_drive(tmp_path):
    frame = validate_universe(drive_path=tmp_path)
    assert list(frame.columns) == [
        "ticker",
        "classification",
        "strategy",
        "folds_passing",
        "n_folds",
        "total_trades",
        "mean_fold_return",
        "passed",
    ]
    assert frame.empty


def test_write_validation_roundtrip(tmp_path):
    res = WFVResult(strategy="breakout", n_folds=6, folds_passing=4, passed=True, total_trades=12)
    df = pd.DataFrame([res.to_row("AAPL", "Trending")])
    path = write_validation(df, outputs_dir=tmp_path)
    assert path.exists()
    reloaded = pd.read_csv(path)
    assert reloaded.loc[0, "ticker"] == "AAPL"
    assert bool(reloaded.loc[0, "passed"]) is True


def test_config_thresholds_are_wired():
    # The engine should default to the config knobs the project reserved.
    res = walk_forward(_frame(np.linspace(100.0, 200.0, 240)), breakout_strategy)
    assert res.n_folds == config.WFV_FOLDS
