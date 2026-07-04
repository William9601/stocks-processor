"""OvernightAuctionRunner: MOC/MOO submission, fill logging, cutoff behavior.

Driven by a fake broker and an injected clock — no Alpaca, no real sleeps.
Uses the overnight-long strategy on a known full session (2024-06-03, close
16:00, decision bar 15:40).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from core.execution.live_runner import OvernightAuctionRunner
from core.loader import load_strategy
from core.risk.sizing import RiskLimits, RiskManager
from core.strategy import Position, Side

SESSION = "2024-06-03"  # a regular Monday, 16:00 ET close


def _day_bars(date=SESSION, end="15:40") -> pd.DataFrame:
    idx = pd.date_range(f"{date} 09:35", f"{date} {end}", freq="5min",
                        tz="America/New_York").tz_convert("UTC")
    n = len(idx)
    close = np.linspace(500.0, 501.0, n)
    open_ = np.concatenate([[499.9], close[:-1]])
    return pd.DataFrame(
        {"open": open_, "high": close + 0.1, "low": open_ - 0.1, "close": close,
         "volume": np.full(n, 1e5)}, index=idx)


def _daily_file(tmp_path, uptrend=True):
    n = 10
    closes = np.arange(n, dtype=float) + 100.0
    if not uptrend:
        closes = closes[::-1].copy()
    dates = pd.date_range("2024-05-17", periods=n, freq="B", tz="America/New_York")
    open_ = np.concatenate([[closes[0]], closes[:-1]])
    df = pd.DataFrame({"open": open_, "high": closes + 0.5, "low": closes - 0.5,
                       "close": closes, "volume": np.full(n, 1e6)},
                      index=dates.tz_convert("UTC"))
    df.index.name = "ts"
    path = tmp_path / "daily.parquet"
    df.to_parquet(path)
    return path


class FakeAuctionBroker:
    def __init__(self, bars: pd.DataFrame):
        self.bars = bars
        self.calls: list[tuple] = []
        self._position = Position()
        self._oid = 0

    def recent_bars(self, symbol, start, end):
        return self.bars[self.bars.index <= end]

    def account(self):
        return 100_000.0, 100_000.0

    def position(self, symbol):
        return self._position

    def submit_market(self, symbol, qty, is_buy, tif="day"):
        self._oid += 1
        self.calls.append(("market", qty, is_buy, tif))
        if is_buy:
            self._position = Position(side=Side.LONG, qty=qty, avg_price=501.0)
        else:
            self._position = Position()
        return f"o{self._oid}"

    def wait_fill(self, order_id, timeout=30.0):
        return 501.05

    def submit_stop(self, symbol, qty, is_buy, stop_price):
        raise AssertionError("overnight runner must never place a stop")

    def cancel(self, order_id):
        self.calls.append(("cancel", order_id))

    def close_position(self, symbol):
        self.calls.append(("close",))
        self._position = Position()

    def auction_prints(self, symbol, day):
        return 500.20, 501.00  # official open, official close


def _runner(tmp_path, broker, uptrend=True):
    strat = load_strategy(
        "strategies/overnight-long",
        {"daily_source": str(_daily_file(tmp_path, uptrend)),
         "sma_window": 3, "overnight_vol_window": 3},
    )
    return OvernightAuctionRunner(
        strat, RiskManager(RiskLimits()), broker, "QQQ",
        fill_log=str(tmp_path / "fills.jsonl"),
    )


def _et(hhmm: str, date=SESSION) -> pd.Timestamp:
    return pd.Timestamp(f"{date} {hhmm}", tz="America/New_York").tz_convert("UTC")


def test_decision_bar_submits_sized_moc_before_cutoff(tmp_path):
    broker = FakeAuctionBroker(_day_bars(end="15:40"))
    runner = _runner(tmp_path, broker)
    clock = iter([_et("15:41")])
    runner._now = lambda: next(clock)
    close_et = pd.Timestamp(f"{SESSION} 16:00", tz="America/New_York")

    oid = runner._afternoon(pd.Timestamp(SESSION).date(), close_et)
    assert oid == "o1"
    kind, qty, is_buy, tif = broker.calls[0]
    assert (kind, is_buy, tif) == ("market", True, "cls")
    # Gap-budget sizing on the $100k account: G = 5% floor -> ~$10k notional.
    assert 0 < qty <= 100_000 / 501.0
    assert qty == int(qty)  # whole shares


def test_gate_off_means_no_order_and_cutoff_ends_afternoon(tmp_path):
    broker = FakeAuctionBroker(_day_bars(end="15:40"))
    runner = _runner(tmp_path, broker, uptrend=False)  # regime gate off
    clock = iter([_et("15:41"), _et("15:42"), _et("15:46")])  # cutoff 15:45
    runner._now = lambda: next(clock)
    runner._sleep = lambda s: None
    close_et = pd.Timestamp(f"{SESSION} 16:00", tz="America/New_York")

    assert runner._afternoon(pd.Timestamp(SESSION).date(), close_et) is None
    assert broker.calls == []


def test_no_moc_submission_after_cutoff(tmp_path):
    """Even if the decision bar were available, past the cutoff nothing goes out."""
    broker = FakeAuctionBroker(_day_bars(end="15:40"))
    runner = _runner(tmp_path, broker)
    clock = iter([_et("15:46")])  # first look is already past the 15:45 cutoff
    runner._now = lambda: next(clock)
    close_et = pd.Timestamp(f"{SESSION} 16:00", tz="America/New_York")

    assert runner._afternoon(pd.Timestamp(SESSION).date(), close_et) is None
    assert broker.calls == []


def test_fill_log_records_cost_vs_official_print(tmp_path):
    broker = FakeAuctionBroker(_day_bars())
    runner = _runner(tmp_path, broker)

    # MOC buy filled 501.05 vs official close 501.00 -> ~+1.0 bps cost.
    runner._log_fill(SESSION, "MOC", True, 20.0, "o1", 501.05, 501.00)
    # MOO sell filled 500.10 vs official open 500.20 -> ~+2.0 bps cost.
    runner._log_fill("2024-06-04", "MOO", False, 20.0, "o2", 500.10, 500.20)

    lines = [json.loads(x) for x in (tmp_path / "fills.jsonl").read_text().splitlines()]
    assert len(lines) == 2
    moc, moo = lines
    assert moc["order_type"] == "MOC" and moc["side"] == "buy"
    assert abs(moc["diff_bps"] - (501.05 - 501.00) / 501.00 * 1e4) < 1e-9
    assert moo["order_type"] == "MOO" and moo["side"] == "sell"
    assert abs(moo["diff_bps"] - (500.20 - 500.10) / 500.20 * 1e4) < 1e-9
    # Append-only: a third entry adds a line, nothing is rewritten.
    runner._log_fill("2024-06-04", "MOC", True, 20.0, "o3", 500.0, None)
    assert len((tmp_path / "fills.jsonl").read_text().splitlines()) == 3


def test_missing_official_print_logs_none_not_crash(tmp_path):
    broker = FakeAuctionBroker(_day_bars())
    runner = _runner(tmp_path, broker)
    runner._log_fill(SESSION, "MOC", True, 20.0, "o1", 501.05, None)
    (line,) = (tmp_path / "fills.jsonl").read_text().splitlines()
    entry = json.loads(line)
    assert entry["fill_price"] == 501.05
    assert entry["official_auction_price"] is None and entry["diff_bps"] is None
