"""Signal library. Every signal returns a DataFrame (dates x symbols) of scores in [-1, 1].

Rule: only backward-looking rolling operations. The value on date t uses data up to the
close of t, and is traded no earlier than the next session (see backtest.py).
Cross-sectional z-scores are taken across the row (same date) only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _xs_z(df: pd.DataFrame, clip: float = 3.0) -> pd.DataFrame:
    """Cross-sectional z-score per date, squashed to [-1, 1]."""
    mu = df.mean(axis=1)
    sd = df.std(axis=1).replace(0, np.nan)
    z = df.sub(mu, axis=0).div(sd, axis=0).clip(-clip, clip)
    return np.tanh(z / 1.5)


def returns(close: pd.DataFrame) -> pd.DataFrame:
    return close.pct_change(fill_method=None)


def realized_vol(close: pd.DataFrame, days: int = 60) -> pd.DataFrame:
    return returns(close).rolling(days, min_periods=int(days * 0.7)).std() * np.sqrt(TRADING_DAYS)


def atr(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame, days: int = 14) -> pd.DataFrame:
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()]).groupby(level=0).max()
    tr = tr.reindex(close.index)
    return tr.rolling(days, min_periods=days).mean()


def tsmom(p: dict, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """Time-series momentum: 12-1 month return scaled by its own volatility (absolute, not ranked)."""
    c = p["close"]
    r = c.shift(skip) / c.shift(lookback) - 1.0
    vol = realized_vol(c, lookback).replace(0, np.nan)
    horizon_vol = vol * np.sqrt((lookback - skip) / TRADING_DAYS)
    return np.tanh(r / horizon_vol)


def xsmom(p: dict, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """Cross-sectional momentum: rank of 12-1 month return across the universe."""
    c = p["close"]
    return _xs_z(c.shift(skip) / c.shift(lookback) - 1.0)


def trend(p: dict, fast: int = 50, slow: int = 200) -> pd.DataFrame:
    """Trend filter: price vs slow SMA plus fast/slow SMA alignment."""
    c = p["close"]
    sma_f = c.rolling(fast, min_periods=fast).mean()
    sma_s = c.rolling(slow, min_periods=slow).mean()
    a = np.tanh((c / sma_s - 1.0) * 10)
    b = np.sign(sma_f - sma_s)
    return 0.6 * a + 0.4 * b


def reversal(p: dict, lookback: int = 5) -> pd.DataFrame:
    """Short-term reversal: recent losers tend to bounce (cross-sectional)."""
    c = p["close"]
    return -_xs_z(c / c.shift(lookback) - 1.0)


def lowvol(p: dict, lookback: int = 60) -> pd.DataFrame:
    """Low-volatility anomaly: lower realized vol scores higher (cross-sectional)."""
    return -_xs_z(realized_vol(p["close"], lookback))


def high52(p: dict, lookback: int = 252) -> pd.DataFrame:
    """Proximity to 52-week high (George & Hwang 2004)."""
    c = p["close"]
    hi = p["high"].rolling(lookback, min_periods=int(lookback * 0.8)).max()
    return _xs_z(c / hi)


def breakout(p: dict, lookback: int = 55) -> pd.DataFrame:
    """Donchian position: where the close sits in its N-day range, mapped to [-1, 1]."""
    c = p["close"]
    hi = p["high"].rolling(lookback, min_periods=lookback).max()
    lo = p["low"].rolling(lookback, min_periods=lookback).min()
    rng = (hi - lo).replace(0, np.nan)
    return ((c - lo) / rng) * 2.0 - 1.0


def rsi2(p: dict, period: int = 2, trend_sma: int = 200) -> pd.DataFrame:
    """Connors-style pullback: oversold RSI(2) inside a long-term uptrend is bullish; overbought is bearish."""
    c = p["close"]
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    uptrend = c > c.rolling(trend_sma, min_periods=trend_sma).mean()
    raw = (50 - rsi) / 50.0  # +1 at RSI 0, -1 at RSI 100
    return raw.where(uptrend, raw.clip(upper=0))


REGISTRY = {
    "tsmom": tsmom,
    "xsmom": xsmom,
    "trend": trend,
    "reversal": reversal,
    "lowvol": lowvol,
    "high52": high52,
    "breakout": breakout,
    "rsi2": rsi2,
}


def compute_all(panel: dict, cfg: dict) -> dict[str, pd.DataFrame]:
    """All registered signals with their config params. Values are NaN where history is too short."""
    out = {}
    for name, fn in REGISTRY.items():
        params = cfg.get("signals", {}).get(name, {})
        out[name] = fn(panel, **params).astype("float64").clip(-1, 1)
    return out
