"""CLI : python -m trading_bot {backtest,paper,live}"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import BotConfig


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="trading_bot", description="Bot de trading crypto EMA/RSI/ATR")
    sub = p.add_subparsers(dest="cmd", required=True)

    bt = sub.add_parser("backtest", help="tester la stratégie sur l'historique")
    bt.add_argument("--csv", help="fichier OHLCV local (sinon téléchargement via l'exchange)")
    bt.add_argument("--bars", type=int, default=5000, help="nombre de bougies à télécharger")
    bt.add_argument("--trades", action="store_true", help="afficher le détail des trades")

    for name in ("paper", "live"):
        sp = sub.add_parser(name, help=f"trading en temps réel ({name})")
        sp.add_argument("--poll", type=int, default=30, help="secondes entre deux vérifications")
    sub.choices["live"].add_argument("--i-understand-the-risks", action="store_true", dest="confirmed")

    for sp in sub.choices.values():
        sp.add_argument("--symbol")
        sp.add_argument("--timeframe")
        sp.add_argument("--exchange")
        sp.add_argument("-v", "--verbose", action="store_true")

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    cfg = BotConfig()
    for attr in ("symbol", "timeframe", "exchange"):
        if getattr(args, attr):
            setattr(cfg, attr, getattr(args, attr))

    if args.cmd == "backtest":
        from .backtest import run_backtest
        from .data import fetch_ohlcv, load_csv, make_exchange

        df = load_csv(args.csv) if args.csv else fetch_ohlcv(make_exchange(cfg.exchange), cfg.symbol, cfg.timeframe, args.bars)
        print(f"{len(df)} bougies {cfg.symbol} {cfg.timeframe} : {df.index[0]} -> {df.index[-1]}")
        res = run_backtest(df, cfg)
        if args.trades:
            for t in res.trades:
                print(f"{t.entry_time} -> {t.exit_time}  {t.entry_price:.2f} -> {t.exit_price:.2f}  "
                      f"{t.reason:<12} PnL {t.pnl:+.2f}")
        for k, v in res.stats.items():
            print(f"{k:>18} : {v}")
        return 0

    from .bot import TradingBot

    live = args.cmd == "live"
    if live:
        if not (args.confirmed and cfg.live_trading):
            print("Refusé : le mode live exige LIVE_TRADING=true dans .env ET --i-understand-the-risks.")
            return 2
        if not (cfg.api_key and cfg.api_secret):
            print("Refusé : API_KEY / API_SECRET manquants.")
            return 2
    try:
        TradingBot(cfg, live=live, poll_seconds=args.poll).run()
    except KeyboardInterrupt:
        print("\nArrêt demandé. État sauvegardé dans", cfg.state_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
