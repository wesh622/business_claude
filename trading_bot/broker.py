"""Exécution des ordres : PaperBroker (simulation) et LiveBroker (ccxt)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import RiskConfig

log = logging.getLogger(__name__)


@dataclass
class Fill:
    side: str
    qty: float
    price: float
    fee: float


class PaperBroker:
    """Simule un compte spot avec frais et slippage."""

    def __init__(self, cash: float, risk: RiskConfig, qty: float = 0.0):
        self.cash = cash
        self.qty = qty
        self.risk = risk

    def equity(self, price: float) -> float:
        return self.cash + self.qty * price

    def buy(self, qty: float, price: float) -> Fill | None:
        px = price * (1 + self.risk.slippage)
        cost = qty * px
        fee = cost * self.risk.fee_rate
        if qty <= 0 or cost + fee > self.cash + 1e-9:
            return None
        self.cash -= cost + fee
        self.qty += qty
        return Fill("buy", qty, px, fee)

    def sell(self, qty: float, price: float) -> Fill | None:
        qty = min(qty, self.qty)
        if qty <= 0:
            return None
        px = price * (1 - self.risk.slippage)
        proceeds = qty * px
        fee = proceeds * self.risk.fee_rate
        self.cash += proceeds - fee
        self.qty -= qty
        return Fill("sell", qty, px, fee)


class LiveBroker:
    """Envoie de vrais ordres au marché via ccxt. À utiliser en connaissance de cause."""

    def __init__(self, exchange, symbol: str, risk: RiskConfig):
        self.ex = exchange
        self.symbol = symbol
        self.risk = risk
        self.ex.load_markets()
        market = self.ex.market(symbol)
        self.base, self.quote = market["base"], market["quote"]

    def _balances(self) -> tuple[float, float]:
        bal = self.ex.fetch_balance()
        return float(bal["free"].get(self.quote, 0) or 0), float(bal["free"].get(self.base, 0) or 0)

    @property
    def cash(self) -> float:
        return self._balances()[0]

    @property
    def qty(self) -> float:
        return self._balances()[1]

    def equity(self, price: float) -> float:
        cash, qty = self._balances()
        return cash + qty * price

    def _fill(self, order, side: str, fallback_price: float) -> Fill | None:
        filled = float(order.get("filled") or order.get("amount") or 0)
        if filled <= 0:
            return None
        price = float(order.get("average") or order.get("price") or fallback_price)
        fee = float((order.get("fee") or {}).get("cost") or 0)
        return Fill(side, filled, price, fee)

    def buy(self, qty: float, price: float) -> Fill | None:
        amount = float(self.ex.amount_to_precision(self.symbol, qty))
        if amount <= 0:
            return None
        log.warning("ORDRE RÉEL : achat %s %s", amount, self.symbol)
        return self._fill(self.ex.create_market_buy_order(self.symbol, amount), "buy", price)

    def sell(self, qty: float, price: float) -> Fill | None:
        amount = float(self.ex.amount_to_precision(self.symbol, min(qty, self.qty)))
        if amount <= 0:
            return None
        log.warning("ORDRE RÉEL : vente %s %s", amount, self.symbol)
        return self._fill(self.ex.create_market_sell_order(self.symbol, amount), "sell", price)
