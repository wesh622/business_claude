"""Gestion du risque : taille de position et coupe-circuit."""
from __future__ import annotations

from .config import RiskConfig


def position_size(equity: float, entry: float, stop: float, cfg: RiskConfig) -> float:
    """Quantité à acheter pour ne risquer que `risk_per_trade` du capital jusqu'au stop."""
    risk_per_unit = entry - stop
    if equity <= 0 or entry <= 0 or risk_per_unit <= 0:
        return 0.0
    qty_by_risk = equity * cfg.risk_per_trade / risk_per_unit
    qty_by_cap = equity * cfg.max_position_pct / (entry * (1 + cfg.fee_rate + cfg.slippage))
    return max(0.0, min(qty_by_risk, qty_by_cap))


class DrawdownGuard:
    """Bloque toute nouvelle entrée si le drawdown dépasse `max_drawdown`."""

    def __init__(self, cfg: RiskConfig, peak: float = 0.0):
        self.cfg = cfg
        self.peak = peak

    def update(self, equity: float) -> None:
        self.peak = max(self.peak, equity)

    def drawdown(self, equity: float) -> float:
        return 0.0 if self.peak <= 0 else 1 - equity / self.peak

    def halted(self, equity: float) -> bool:
        return self.drawdown(equity) >= self.cfg.max_drawdown - 1e-12
