"""Boucle de trading en temps réel (paper ou live).

- À chaque nouvelle bougie clôturée : calcul des signaux, entrée / sortie.
- Entre deux bougies : surveillance du stop et du take-profit sur le dernier prix.
- L'état (position, stop, pic d'equity...) est sauvegardé en JSON pour survivre à un redémarrage.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass

from .broker import LiveBroker, PaperBroker
from .config import BotConfig
from .data import drop_open_candle, fetch_ohlcv, make_exchange
from .risk import DrawdownGuard, position_size
from .strategy import compute_signals, stop_and_target

log = logging.getLogger(__name__)


@dataclass
class State:
    in_position: bool = False
    qty: float = 0.0
    entry_price: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    peak_equity: float = 0.0
    paper_cash: float | None = None
    last_candle_ms: int = 0

    @classmethod
    def load(cls, path: str) -> "State":
        if os.path.exists(path):
            with open(path) as f:
                return cls(**json.load(f))
        return cls()

    def save(self, path: str) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(asdict(self), f, indent=2)
        os.replace(tmp, path)


class TradingBot:
    def __init__(self, cfg: BotConfig, live: bool = False, poll_seconds: int = 30):
        self.cfg = cfg
        self.live = live
        self.poll_seconds = poll_seconds
        self.state = State.load(cfg.state_file)
        self.exchange = make_exchange(cfg.exchange, cfg.api_key if live else "", cfg.api_secret if live else "")
        if live:
            self.broker = LiveBroker(self.exchange, cfg.symbol, cfg.risk)
        else:
            cash = self.state.paper_cash if self.state.paper_cash is not None else cfg.starting_cash
            self.broker = PaperBroker(cash, cfg.risk, qty=self.state.qty)
        self.guard = DrawdownGuard(cfg.risk, peak=self.state.peak_equity)
        self.tf_seconds = self.exchange.parse_timeframe(cfg.timeframe)

    # ---------------------------------------------------------------- helpers
    def _price(self) -> float:
        return float(self.exchange.fetch_ticker(self.cfg.symbol)["last"])

    def _persist(self) -> None:
        if isinstance(self.broker, PaperBroker):
            self.state.paper_cash = self.broker.cash
        self.state.save(self.cfg.state_file)

    def _enter(self, price: float, atr_value: float) -> None:
        equity = self.broker.equity(price)
        if self.guard.halted(equity):
            log.error("Coupe-circuit actif (drawdown %.1f %%) : aucune nouvelle entrée.",
                      self.guard.drawdown(equity) * 100)
            return
        stop, target = stop_and_target(price, atr_value, self.cfg.strategy)
        qty = position_size(equity, price, stop, self.cfg.risk)
        fill = self.broker.buy(qty, price)
        if not fill:
            log.info("Entrée ignorée (quantité trop faible ou fonds insuffisants).")
            return
        self.state.in_position = True
        self.state.qty, self.state.entry_price = fill.qty, fill.price
        self.state.stop, self.state.target = stop, target
        log.info("ACHAT %.6f @ %.2f | stop %.2f | objectif %.2f", fill.qty, fill.price, stop, target)

    def _exit(self, price: float, reason: str) -> None:
        fill = self.broker.sell(self.state.qty, price)
        if fill:
            pnl = (fill.price - self.state.entry_price) * fill.qty - fill.fee
            log.info("VENTE (%s) %.6f @ %.2f | PnL ≈ %.2f", reason, fill.qty, fill.price, pnl)
        self.state.in_position = False
        self.state.qty = self.state.entry_price = self.state.stop = self.state.target = 0.0

    # ------------------------------------------------------------------- loop
    def on_new_candle(self) -> None:
        now = self.exchange.milliseconds()
        need = self.cfg.strategy.ema_trend * 3 + 10
        df = drop_open_candle(fetch_ohlcv(self.exchange, self.cfg.symbol, self.cfg.timeframe, need),
                              self.tf_seconds, now)
        last_ms = int(df.index[-1].timestamp() * 1000)
        if last_ms <= self.state.last_candle_ms:
            return
        self.state.last_candle_ms = last_ms
        bar = compute_signals(df, self.cfg.strategy).iloc[-1]
        price = self._price()
        log.info("Bougie %s | close %.2f | RSI %.1f | EMA %.2f/%.2f",
                 df.index[-1], bar["close"], bar["rsi"], bar["ema_fast"], bar["ema_slow"])
        if self.state.in_position and bar["exit"]:
            self._exit(price, "signal")
        elif not self.state.in_position and bar["entry"]:
            self._enter(price, bar["atr"])

    def check_stops(self) -> None:
        if not self.state.in_position:
            return
        price = self._price()
        if price <= self.state.stop:
            self._exit(price, "stop")
        elif price >= self.state.target:
            self._exit(price, "take_profit")

    def step(self) -> None:
        self.on_new_candle()
        self.check_stops()
        equity = self.broker.equity(self._price())
        self.guard.update(equity)
        self.state.peak_equity = self.guard.peak
        self._persist()
        log.debug("Equity %.2f", equity)

    def run(self) -> None:
        mode = "LIVE (argent réel)" if self.live else "PAPER (simulation)"
        log.info("Démarrage %s sur %s %s %s", mode, self.cfg.exchange, self.cfg.symbol, self.cfg.timeframe)
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                raise
            except Exception:  # réseau, API... on log et on réessaie
                log.exception("Erreur pendant l'itération, nouvelle tentative au prochain cycle")
            time.sleep(self.poll_seconds)
