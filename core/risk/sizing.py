"""Volatility-targeted position sizing and account-level limits.

Sizing rule (per SPEC): risk a fixed fraction ``R`` of equity on the stop
distance. For a per-share instrument (SPY), one share loses ``stop_distance``
dollars if stopped, so::

    qty = floor( (R * equity) / stop_distance )

capped so notional never exceeds equity (no leverage in v1). Contract-based
instruments pass ``point_value`` to scale dollar risk per unit.

Limits are the spec's locked circuit breakers:
- daily loss limit at ``2 * R`` of equity -> no new entries for the rest of day
- drawdown kill switch at 15% peak-to-trough -> halt new entries entirely
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.strategy import Action, Context, Order


@dataclass
class RiskLimits:
    risk_per_trade: float = 0.005  # R = 0.5% of equity per trade
    daily_loss_limit_r: float = 2.0  # halt new entries after losing 2*R in a day
    max_drawdown: float = 0.15  # 15% peak-to-trough kill switch
    point_value: float = 1.0  # $ per 1.0 price point per unit (1.0 for shares)
    allow_leverage: bool = False
    # Whether tripping the kill switch vetoes all further entries. True is the
    # paper/live behavior (a tripped switch halts the book for manual review
    # and must survive restarts). Backtests measuring a strategy against a
    # locked max-drawdown CRITERION set this False: a permanent mid-simulation
    # halt would censor the very drawdown the criterion judges (and make the
    # bar self-fulfilling). ``halted`` is still set either way and is always
    # reported.
    halt_on_drawdown: bool = True


class RiskManager:
    """Sizes entry intents and enforces account-level limits."""

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()
        self.peak_equity = 0.0
        self.halted = False  # drawdown kill switch tripped
        self._day = None
        self._day_start_equity = 0.0
        self._day_locked = False  # daily loss limit tripped
        self._last_equity: float | None = None

    # --- state persistence (live/paper: one process per overnight cycle) ---
    # The breakers are only meaningful if peak equity, the day anchor, and the
    # last session's closing mark survive process restarts; a fresh in-memory
    # RiskManager every launch silently disarms them.
    def to_state(self) -> dict:
        return {
            "peak_equity": self.peak_equity,
            "halted": self.halted,
            "day": self._day.isoformat() if self._day else None,
            "day_start_equity": self._day_start_equity,
            "day_locked": self._day_locked,
            "last_equity": self._last_equity,
        }

    def restore_state(self, state: dict) -> None:
        from datetime import date as _date

        self.peak_equity = float(state.get("peak_equity", 0.0))
        self.halted = bool(state.get("halted", False))
        day = state.get("day")
        self._day = _date.fromisoformat(day) if day else None
        self._day_start_equity = float(state.get("day_start_equity", 0.0))
        self._day_locked = bool(state.get("day_locked", False))
        last = state.get("last_equity")
        self._last_equity = float(last) if last is not None else None

    def on_bar(self, ctx: Context) -> None:
        """Day-roll + circuit-breaker check. The engine/runner calls this on
        EVERY bar — not only order-emitting ones — so day-start equity is
        captured before the day's fills distort it. Idempotent within a bar.
        """
        self._roll_day(ctx)
        self._update_circuit_breakers(ctx)
        self._last_equity = ctx.equity

    def _roll_day(self, ctx: Context) -> None:
        day = ctx.now_et.date()
        if day != self._day:
            self._day = day
            # Anchor the day at the prior session's closing equity so a loss
            # realized by the first fills of the morning (e.g. an overnight
            # gap closed at the open) still counts against today's 2*R limit.
            # On the very first bar ever there is no prior mark; use current.
            self._day_start_equity = (
                self._last_equity if self._last_equity is not None else ctx.equity
            )
            self._day_locked = False

    def _update_circuit_breakers(self, ctx: Context) -> None:
        self.peak_equity = max(self.peak_equity, ctx.equity)
        if self.peak_equity > 0 and ctx.equity <= self.peak_equity * (1 - self.limits.max_drawdown):
            self.halted = True
        loss = self._day_start_equity - ctx.equity
        day_loss_cap = (
            self.limits.daily_loss_limit_r * self.limits.risk_per_trade * self._day_start_equity
        )
        if loss >= day_loss_cap:
            self._day_locked = True

    def size(self, order: Order, ctx: Context, ref_price: float) -> Order | None:
        """Return a sized order, or ``None`` to veto it.

        ``ref_price`` is the best current estimate of the fill price (used only
        for the no-leverage notional cap).
        """
        # Re-run the hook defensively: correct even if a caller only invokes
        # size() on order bars (the sparse-order case that killed the 2*R
        # limit when the day-roll lived exclusively here).
        self.on_bar(ctx)

        # Closing is always permitted — never trap an open position.
        if order.action is Action.CLOSE:
            return order

        if (self.halted and self.limits.halt_on_drawdown) or self._day_locked:
            return None
        if order.stop_distance is None or order.stop_distance <= 0:
            return None

        dollar_risk = self.limits.risk_per_trade * ctx.equity
        per_unit_risk = order.stop_distance * self.limits.point_value
        qty = math.floor(dollar_risk / per_unit_risk)

        if not self.limits.allow_leverage and ref_price > 0:
            max_qty = math.floor(ctx.equity / (ref_price * self.limits.point_value))
            qty = min(qty, max_qty)

        if qty <= 0:
            return None  # stop too wide for the account -> skip the trade

        order.qty = float(qty)
        return order
