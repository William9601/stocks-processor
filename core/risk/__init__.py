"""Risk: position sizing and limits, enforced OUTSIDE strategies.

Strategies emit unsized intents; ``RiskManager`` turns them into sized orders
or vetoes them. This is where the spec's locked risk parameters live.
"""

from core.risk.sizing import RiskLimits, RiskManager

__all__ = ["RiskLimits", "RiskManager"]
