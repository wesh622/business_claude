import numpy as np
import pandas as pd
import pytest

from trading_bot.backtest import run_backtest
from trading_bot.broker import PaperBroker
from trading_bot.config import BotConfig, RiskConfig, StrategyConfig
from trading_bot.data import drop_open_candle
from trading_bot.indicators import rsi
from trading_bot.risk import DrawdownGuard, position_size
from trading_bot.strategy import compute_signals


def synthetic(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    # tendance haussière + cycles + bruit : génère des croisements
    t = np.arange(n)
    close = 100 * np.exp(0.0002 * t + 0.05 * np.sin(t / 60) + np.cumsum(rng.normal(0, 0.004, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.003, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.003, n))
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": 1.0}, index=idx)


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.arange(1, 100, dtype=float))
    assert rsi(up).iloc[-1] == pytest.approx(100)
    r = rsi(synthetic()["close"])
    assert r.between(0, 100).all()


def test_position_size_respects_risk_and_cap():
    qty = position_size(10_000, entry=100, stop=98, cfg=RiskConfig(risk_per_trade=0.01))
    assert qty == pytest.approx(50)  # 1 % de 10 000 $ / 2 $ de risque par unité
    cfg = RiskConfig(risk_per_trade=0.01, max_position_pct=0.5)
    qty = position_size(10_000, entry=100, stop=99.9, cfg=cfg)  # plafonné à 50 % du capital
    assert qty * 100 <= 5_000
    assert position_size(10_000, entry=100, stop=101, cfg=cfg) == 0


def test_paper_broker_fees_and_insufficient_funds():
    b = PaperBroker(1000, RiskConfig(fee_rate=0.001, slippage=0))
    assert b.buy(20, 100) is None  # 2000 $ > 1000 $
    fill = b.buy(5, 100)
    assert fill.fee == pytest.approx(0.5)
    assert b.cash == pytest.approx(499.5)
    b.sell(5, 110)
    assert b.qty == 0
    assert b.cash == pytest.approx(499.5 + 550 - 0.55)


def test_drawdown_guard():
    g = DrawdownGuard(RiskConfig(max_drawdown=0.2), peak=1000)
    assert not g.halted(850)
    assert g.halted(800)


def test_signals_have_no_lookahead():
    df = synthetic()
    full = compute_signals(df, StrategyConfig())
    partial = compute_signals(df.iloc[:2000], StrategyConfig())
    cols = ["entry", "exit", "ema_fast", "rsi", "atr"]
    pd.testing.assert_frame_equal(full[cols].iloc[:2000], partial[cols])


def test_backtest_runs_and_accounts_consistently():
    cfg = BotConfig(starting_cash=1000)
    res = run_backtest(synthetic(), cfg)
    assert res.stats["nb_trades"] > 0
    pnl = sum(t.pnl for t in res.trades)
    assert res.equity.iloc[-1] == pytest.approx(1000 + pnl, rel=1e-9)
    assert all(t.exit_time is not None for t in res.trades)


def test_drop_open_candle():
    df = synthetic(10)
    last_open_ms = int(df.index[-1].timestamp() * 1000)
    assert len(drop_open_candle(df, 3600, last_open_ms + 1000)) == 9
    assert len(drop_open_candle(df, 3600, last_open_ms + 3600_000)) == 10
