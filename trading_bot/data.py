"""Récupération des bougies OHLCV (ccxt ou CSV)."""
from __future__ import annotations

import time

import pandas as pd

COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def make_exchange(name: str, api_key: str = "", api_secret: str = ""):
    import ccxt

    params = {"enableRateLimit": True}
    if api_key and api_secret:
        params.update(apiKey=api_key, secret=api_secret)
    return getattr(ccxt, name)(params)


def to_frame(rows: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.drop_duplicates("timestamp").set_index("timestamp").astype(float)


def fetch_ohlcv(exchange, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
    """Récupère les `limit` dernières bougies, en paginant si besoin."""
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - limit * tf_ms
    rows: list[list] = []
    while len(rows) < limit:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=min(1000, limit - len(rows)))
        if not batch:
            break
        rows.extend(batch)
        since = batch[-1][0] + tf_ms
        if since >= exchange.milliseconds():
            break
        time.sleep(exchange.rateLimit / 1000)
    return to_frame(rows)


def drop_open_candle(df: pd.DataFrame, timeframe_seconds: int, now_ms: int) -> pd.DataFrame:
    """Retire la dernière bougie si elle n'est pas encore clôturée."""
    if df.empty:
        return df
    last_open_ms = int(df.index[-1].timestamp() * 1000)
    if last_open_ms + timeframe_seconds * 1000 > now_ms:
        return df.iloc[:-1]
    return df


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    ts = df["timestamp"]
    if pd.api.types.is_numeric_dtype(ts):  # epoch en millisecondes (ccxt) ou en secondes
        df["timestamp"] = pd.to_datetime(ts, unit="ms" if ts.max() > 1e11 else "s", utc=True)
    else:
        df["timestamp"] = pd.to_datetime(ts, utc=True)
    return df.set_index("timestamp")[COLUMNS[1:]].astype(float)
