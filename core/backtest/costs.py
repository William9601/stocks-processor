"""Transaction cost model. Costs are mandatory on every backtest.

A fill's all-in cost has three parts, charged per side:
- commission: flat $/unit (0 for commission-free SPY)
- half-spread: modeled as a fraction of price (crossing the book)
- slippage: fraction of price; stop exits are more adverse (separate factor)

``adverse_price`` returns the price actually paid/received after spread +
slippage are pushed against you, given trade direction. Commission is charged
separately (it is a cash cost, not a price adjustment).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostModel:
    commission_per_unit: float = 0.0  # $/share/side (SPY commission-free)
    half_spread_bps: float = 1.0  # half the bid/ask spread, in basis points
    slippage_bps: float = 1.0  # extra adverse move on market fills, bps
    stop_slippage_bps: float = 3.0  # stops fill worse (gap-through risk)

    def _frac(self, is_stop: bool) -> float:
        bps = self.half_spread_bps + (self.stop_slippage_bps if is_stop else self.slippage_bps)
        return bps / 10_000.0

    def adverse_price(self, price: float, is_buy: bool, is_stop: bool = False) -> float:
        """Price after spread+slippage are pushed against the trade direction."""
        f = self._frac(is_stop)
        return price * (1 + f) if is_buy else price * (1 - f)

    def commission(self, qty: float) -> float:
        return self.commission_per_unit * abs(qty)
