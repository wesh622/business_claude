"""Backtest bougie par bougie, sans look-ahead.

Signal calculé à la clôture de la bougie i-1 -> exécuté à l'ouverture de la bougie i.
Stop / take-profit vérifiés en intrabar (stop prioritaire, hypothèse prudente).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from .broker import PaperBroker
from .config import BotConfig
from .risk import DrawdownGuard, position_size
from .strategy import compute_signals, stop_and_target


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    qty: float
    entry_fee: float = 0.0
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    reason: str = ""
    pnl: float = 0.0


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity: pd.Series
    stats: dict = field(default_factory=dict)


def _bars_per_year(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 0.0
    step = (index[-1] - index[0]).total_seconds() / (len(index) - 1)
    return 365 * 24 * 3600 / step if step > 0 else 0.0


def compute_stats(trades: list[Trade], equity: pd.Series, start: float, df: pd.DataFrame) -> dict:
    final = float(equity.iloc[-1]) if len(equity) else start
    rets = equity.pct_change().dropna()
    bpy = _bars_per_year(equity.index)
    sharpe = float(rets.mean() / rets.std() * math.sqrt(bpy)) if len(rets) > 1 and rets.std() > 0 else 0.0
    max_dd = float((1 - equity / equity.cummax()).max()) if len(equity) else 0.0
    closed = [t for t in trades if t.exit_time is not None]
    wins = [t for t in closed if t.pnl > 0]
    gross_win = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in closed if t.pnl <= 0)
    return {
        "capital_initial": start,
        "capital_final": round(final, 2),
        "rendement_pct": round((final / start - 1) * 100, 2),
        "buy_and_hold_pct": round((df["close"].iloc[-1] / df["open"].iloc[0] - 1) * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe": round(sharpe, 2),
        "nb_trades": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 2) if closed else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf") if gross_win else 0.0,
    }


def run_backtest(df: pd.DataFrame, cfg: BotConfig) -> BacktestResult:
    sig = compute_signals(df, cfg.strategy)
    broker = PaperBroker(cfg.starting_cash, cfg.risk)
    guard = DrawdownGuard(cfg.risk, peak=cfg.starting_cash)
    trades: list[Trade] = []
    curve: list[float] = []
    open_trade: Trade | None = None
    stop = target = 0.0

    def close(ts, price, reason):
        nonlocal open_trade
        qty = broker.qty
        fill = broker.sell(qty, price)
        if fill and open_trade:
            open_trade.exit_time, open_trade.exit_price, open_trade.reason = ts, fill.price, reason
            open_trade.pnl = (fill.price - open_trade.entry_price) * qty - fill.fee - open_trade.entry_fee
        open_trade = None

    for i in range(len(sig)):
        ts, bar = sig.index[i], sig.iloc[i]
        if i > 0:
            prev = sig.iloc[i - 1]
            # 1) Ordres à l'ouverture issus des signaux de la bougie précédente
            if open_trade and prev["exit"]:
                close(ts, bar["open"], "signal")
            elif not open_trade and prev["entry"] and not guard.halted(broker.equity(bar["open"])):
                s, t = stop_and_target(bar["open"], prev["atr"], cfg.strategy)
                qty = position_size(broker.equity(bar["open"]), bar["open"], s, cfg.risk)
                fill = broker.buy(qty, bar["open"])
                if fill:
                    stop, target = s, t
                    open_trade = Trade(ts, fill.price, fill.qty, entry_fee=fill.fee)
                    trades.append(open_trade)
            # 2) Stop / take-profit en intrabar (gap compris)
            if open_trade:
                if bar["low"] <= stop:
                    close(ts, min(stop, bar["open"]), "stop")
                elif bar["high"] >= target:
                    close(ts, max(target, bar["open"]), "take_profit")
        eq = broker.equity(bar["close"])
        guard.update(eq)
        curve.append(eq)

    if open_trade:  # clôture de fin de test
        close(sig.index[-1], sig["close"].iloc[-1], "fin")
        curve[-1] = broker.equity(sig["close"].iloc[-1])

    equity = pd.Series(curve, index=sig.index, name="equity")
    return BacktestResult(trades, equity, compute_stats(trades, equity, cfg.starting_cash, df))
