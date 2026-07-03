"""Load a strategy plugin from a file path.

Strategy directories (e.g. ``strategies/intraday-momentum/``) contain a hyphen
and are not importable packages, so we load ``strategy.py`` by path and call
its ``build(params)`` factory. This keeps strategies as pure plugins with no
package wiring.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from core.strategy import Strategy


def load_strategy(path: str | Path, params: dict) -> Strategy:
    path = Path(path)
    if path.is_dir():
        path = path / "strategy.py"
    spec = importlib.util.spec_from_file_location(f"strategy_{path.parent.name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise AttributeError(f"{path} must define build(params) -> Strategy")
    return module.build(params)
