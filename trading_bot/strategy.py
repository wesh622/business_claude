"""Stratégie : croisement d'EMA + filtre de tendance + filtre RSI, sorties sur ATR.

Long uniquement (spot). Les signaux sont calculés sur des bougies CLÔTURÉES ;
l'exécution se fait à l'ouverture de la bougie suivante (pas de look-ahead).
"""
from __future__ import annotations

import pandas as pd

from .config import StrategyConfig
from .indicators import atr, ema, rsi


def compute_signals(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """Ajoute les indicateurs et les colonnes `entry` / `exit` (booléens)."""
    out = df.copy()
    out["ema_fast"] = ema(out["close"], cfg.ema_fast)
    out["ema_slow"] = ema(out["close"], cfg.ema_slow)
    out["ema_trend"] = ema(out["close"], cfg.ema_trend)
    out["rsi"] = rsi(out["close"], cfg.rsi_period)
    out["atr"] = atr(out, cfg.atr_period)

    above = out["ema_fast"] > out["ema_slow"]
    cross_up = above & ~above.shift(1, fill_value=False)
    cross_down = ~above & above.shift(1, fill_value=False)

    warmup = max(cfg.ema_slow, cfg.ema_trend, cfg.rsi_period, cfg.atr_period)
    ready = pd.Series(range(len(out)), index=out.index) >= warmup

    out["entry"] = (
        ready
        & cross_up
        & (out["close"] > out["ema_trend"])
        & (out["rsi"] < cfg.rsi_max_entry)
    )
    out["exit"] = ready & cross_down
    return out


def stop_and_target(entry_price: float, atr_value: float, cfg: StrategyConfig) -> tuple[float, float]:
    stop = entry_price - cfg.stop_atr_mult * atr_value
    target = entry_price + cfg.take_profit_atr_mult * atr_value
    return stop, target
