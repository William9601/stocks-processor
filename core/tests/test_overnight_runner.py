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


class FakeClock:
    """Clock that only advances when the runner sleeps — run() completes instantly."""

    def __init__(self, start_et: str):
        self.t = pd.Timestamp(start_et, tz="America/New_York").tz_convert("UTC")

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += pd.Timedelta(seconds=seconds)


def _wire(runner, clock):
    runner._now = clock.now
    runner._sleep = clock.sleep
    return runner


def _read_log(tmp_path):
    return [json.loads(x) for x in (tmp_path / "fills.jsonl").read_text().splitlines()]


def test_run_recovery_on_exit_morning_exits_today_not_tomorrow(tmp_path):
    """Restarted before the open with an open position: the exit is TODAY's
    opening auction, never next_session (which would hold an extra night)."""
    broker = FakeAuctionBroker(_day_bars())
    broker._position = Position(side=Side.LONG, qty=20.0, avg_price=501.0)
    runner = _wire(_runner(tmp_path, broker), FakeClock("2024-06-04 08:50"))

    runner.run()

    assert broker.calls == [("market", 20.0, False, "opg")]
    (entry,) = _read_log(tmp_path)
    assert entry["order_type"] == "MOO" and entry["session_date"] == "2024-06-04"


def test_run_recovery_after_open_uses_degraded_market_exit(tmp_path):
    """Restarted with the market already open: flatten immediately at market,
    logged as MKT (not an auction fill), rather than holding another night."""
    broker = FakeAuctionBroker(_day_bars())
    broker._position = Position(side=Side.LONG, qty=20.0, avg_price=501.0)
    runner = _wire(_runner(tmp_path, broker), FakeClock("2024-06-04 10:15"))

    runner.run()

    assert broker.calls == [("market", 20.0, False, "day")]
    (entry,) = _read_log(tmp_path)
    assert entry["order_type"] == "MKT" and entry["official_auction_price"] is None


def test_run_moc_rejection_is_logged_and_cycle_ends_flat(tmp_path):
    """An MOC that never becomes a position (odd-lot rejection) must not crash
    and must leave a paper-gate observation in the log."""

    class RejectingBroker(FakeAuctionBroker):
        def submit_market(self, symbol, qty, is_buy, tif="day"):
            self._oid += 1
            self.calls.append(("market", qty, is_buy, tif))
            return f"o{self._oid}"  # no position materializes

        def wait_fill(self, order_id, timeout=30.0):
            raise TimeoutError("never filled")

    broker = RejectingBroker(_day_bars(end="15:40"))
    runner = _wire(_runner(tmp_path, broker), FakeClock("2024-06-03 15:41"))

    runner.run()

    assert [c[3] for c in broker.calls] == ["cls"]  # no exit leg followed
    (entry,) = _read_log(tmp_path)
    assert entry["order_type"] == "MOC" and entry["qty"] == 0.0
    assert entry["fill_price"] is None


def test_run_opg_failure_falls_back_to_market_sell(tmp_path):
    class StickyBroker(FakeAuctionBroker):
        def submit_market(self, symbol, qty, is_buy, tif="day"):
            self._oid += 1
            self.calls.append(("market", qty, is_buy, tif))
            if tif == "day" and not is_buy:
                self._position = Position()  # only the fallback flattens
            return f"o{self._oid}"

        def wait_fill(self, order_id, timeout=30.0):
            raise TimeoutError("opg rejected")

    broker = StickyBroker(_day_bars())
    broker._position = Position(side=Side.LONG, qty=20.0, avg_price=501.0)
    runner = _wire(_runner(tmp_path, broker), FakeClock("2024-06-04 08:50"))

    runner.run()

    assert [c[3] for c in broker.calls] == ["opg", "day"]
    moo, mkt = _read_log(tmp_path)
    assert moo["order_type"] == "MOO" and moo["fill_price"] is None
    assert mkt["order_type"] == "MKT"


def test_risk_state_survives_process_restart(tmp_path):
    """The 2*R day lock must work across the one-process-per-cycle lifetime:
    process N's closing equity anchors process N+1's daily-loss measurement."""
    from core.strategy import Action, Context, Order

    def _ctx(ts_et, equity):
        ts = pd.Timestamp(ts_et, tz="America/New_York").tz_convert("UTC")
        hist = pd.DataFrame(
            {"open": [500.0], "high": [500.0], "low": [500.0], "close": [500.0],
             "volume": [1e5]}, index=pd.DatetimeIndex([ts], name="ts"))
        return Context("QQQ", hist, Position(), cash=equity, equity=equity)

    state = tmp_path / "risk-state.json"

    # Process N: afternoon polling marks equity at 100k, then saves.
    broker = FakeAuctionBroker(_day_bars())
    r1 = _runner(tmp_path, broker)
    r1.risk_state = state
    r1.risk.on_bar(_ctx("2024-06-03 15:40", 100_000.0))
    r1._save_risk_state()

    # Process N+1 (next afternoon): overnight gap realized -1.2% (> 2R = 1%).
    r2 = _runner(tmp_path, broker)
    r2.risk_state = state
    r2._load_risk_state()
    assert r2.risk.size(
        Order(Action.ENTER_LONG, stop_distance=25.0, resting_stop=False),
        _ctx("2024-06-04 15:40", 98_800.0), ref_price=500.0,
    ) is None  # vetoed by the restored day-lock anchor

    # Without the state file the lock would have been silently disarmed.
    r3 = _runner(tmp_path, broker)
    assert r3.risk.size(
        Order(Action.ENTER_LONG, stop_distance=25.0, resting_stop=False),
        _ctx("2024-06-04 15:40", 98_800.0), ref_price=500.0,
    ) is not None


def test_missing_official_print_logs_none_not_crash(tmp_path):
    broker = FakeAuctionBroker(_day_bars())
    runner = _runner(tmp_path, broker)
    runner._log_fill(SESSION, "MOC", True, 20.0, "o1", 501.05, None)
    (line,) = (tmp_path / "fills.jsonl").read_text().splitlines()
    entry = json.loads(line)
    assert entry["fill_price"] == 501.05
    assert entry["official_auction_price"] is None and entry["diff_bps"] is None
