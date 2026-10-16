"""Configuration du bot, lue depuis les variables d'environnement (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv est optionnel
    pass


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class StrategyConfig:
    ema_fast: int = 12
    ema_slow: int = 26
    ema_trend: int = 200  # filtre de tendance : on n'achète que au-dessus
    rsi_period: int = 14
    rsi_max_entry: float = 70.0  # pas d'entrée si surachat
    atr_period: int = 14
    stop_atr_mult: float = 2.0
    take_profit_atr_mult: float = 4.0  # ratio risque/rendement 1:2


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.01  # 1 % du capital risqué par trade
    max_position_pct: float = 0.95  # jamais plus de 95 % du capital engagé
    max_drawdown: float = 0.20  # coupe-circuit à -20 % depuis le pic
    fee_rate: float = 0.001  # 0,1 % par ordre (Binance spot)
    slippage: float = 0.0005  # 0,05 %


@dataclass
class BotConfig:
    exchange: str = field(default_factory=lambda: _env("EXCHANGE", "binance"))
    symbol: str = field(default_factory=lambda: _env("SYMBOL", "BTC/USDT"))
    timeframe: str = field(default_factory=lambda: _env("TIMEFRAME", "1h"))
    api_key: str = field(default_factory=lambda: _env("API_KEY", ""))
    api_secret: str = field(default_factory=lambda: _env("API_SECRET", ""))
    starting_cash: float = field(default_factory=lambda: float(_env("STARTING_CASH", "1000")))
    state_file: str = field(default_factory=lambda: _env("STATE_FILE", "bot_state.json"))
    live_trading: bool = field(
        default_factory=lambda: _env("LIVE_TRADING", "false").lower() == "true"
    )
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
