# business_claude — Bot de trading crypto

Bot spot (long uniquement) en Python, basé sur [ccxt](https://github.com/ccxt/ccxt) : fonctionne avec Binance, Kraken, Bybit, Coinbase, etc.

## Stratégie

| Élément | Règle |
|---|---|
| Entrée | EMA 12 croise au-dessus de l'EMA 26, **et** prix > EMA 200 (tendance haussière), **et** RSI 14 < 70 |
| Sortie | EMA 12 recroise sous l'EMA 26, **ou** stop à 2×ATR, **ou** take-profit à 4×ATR (ratio 1:2) |
| Taille | 1 % du capital risqué par trade (distance au stop), plafonné à 95 % du capital |
| Coupe-circuit | Plus aucune entrée si le drawdown dépasse 20 % depuis le pic |

Les signaux sont calculés sur des bougies **clôturées** et exécutés à l'ouverture suivante (pas de look-ahead). Frais (0,1 %) et slippage (0,05 %) sont inclus dans le backtest et le paper trading. Paramètres modifiables dans `trading_bot/config.py`.

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
```

## Utilisation

```bash
# 1. Backtest sur l'historique (téléchargé depuis l'exchange, ou --csv fichier.csv)
python -m trading_bot backtest --symbol BTC/USDT --timeframe 1h --bars 5000 --trades

# 2. Paper trading : prix réels, argent fictif (état sauvé dans bot_state.json)
python -m trading_bot paper

# 3. Live : argent réel. Exige LIVE_TRADING=true dans .env ET le flag ci-dessous
python -m trading_bot live --i-understand-the-risks
```

## Tests

```bash
python -m pytest -q
```

## Structure

```
trading_bot/
  config.py      paramètres (stratégie, risque, .env)
  indicators.py  EMA, RSI, ATR
  strategy.py    signaux d'entrée / sortie, stop & objectif
  risk.py        taille de position, coupe-circuit drawdown
  broker.py      PaperBroker (simulation) et LiveBroker (ordres ccxt)
  data.py        téléchargement OHLCV, chargement CSV
  backtest.py    moteur de backtest + statistiques
  bot.py         boucle temps réel avec état persistant
  __main__.py    CLI
```

## Avertissement

Aucune stratégie n'est rentable par défaut. Backteste, compare au buy & hold, fais tourner en paper plusieurs semaines avant de mettre de l'argent réel — et seulement de l'argent que tu peux perdre. Utilise une clé API sans droit de retrait.
