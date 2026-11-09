"""Performance statistics, including Probabilistic and Deflated Sharpe (Bailey & Lopez de Prado)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

TD = 252


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_ppf(p: float) -> float:
    # Acklam's rational approximation, good to ~1e-9
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - pl:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def psr(daily: pd.Series, sr_benchmark: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: P(true SR > benchmark SR), per-period SRs, skew/kurtosis aware."""
    r = daily.dropna()
    n = len(r)
    if n < 30 or r.std() == 0:
        return float("nan")
    sr = r.mean() / r.std()
    g3 = float(r.skew())
    g4 = float(r.kurt()) + 3.0
    denom = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr**2, 1e-12))
    return _norm_cdf((sr - sr_benchmark) * math.sqrt(n - 1) / denom)


def dsr(daily: pd.Series, n_trials: int, sr_trials_std: float) -> float:
    """Deflated Sharpe Ratio: PSR against the expected max SR of n_trials noise strategies.

    sr_trials_std: std of the per-period Sharpe ratios across the trials you tried.
    """
    if n_trials <= 1:
        return psr(daily, 0.0)
    emc = 0.5772156649
    sr0 = sr_trials_std * ((1 - emc) * _norm_ppf(1 - 1 / n_trials) + emc * _norm_ppf(1 - 1 / (n_trials * math.e)))
    return psr(daily, sr0)


def summary(equity: pd.Series, turnover: pd.Series | None = None, rf_annual: float = 0.0) -> dict:
    """Sharpe/Sortino/PSR use returns in EXCESS of the cash rate, so earning interest on idle cash
    does not flatter a low-exposure strategy against SPY."""
    eq = equity.dropna()
    r = eq.pct_change().dropna()
    if len(r) < 2:
        return {}
    years = len(r) / TD
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else float("nan")
    vol = r.std() * math.sqrt(TD)
    ex = r - ((1 + rf_annual) ** (1 / TD) - 1)
    sharpe = ex.mean() / ex.std() * math.sqrt(TD) if ex.std() > 0 else float("nan")
    down = math.sqrt(float((ex.clip(upper=0) ** 2).mean())) * math.sqrt(TD)
    sortino = ex.mean() * TD / down if down > 0 else float("nan")
    dd = eq / eq.cummax() - 1
    mdd = dd.min()
    out = {
        "start": str(eq.index[0].date()),
        "end": str(eq.index[-1].date()),
        "years": round(years, 2),
        "total_return": round(eq.iloc[-1] / eq.iloc[0] - 1, 4),
        "cagr": round(cagr, 4),
        "vol": round(vol, 4),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_drawdown": round(mdd, 4),
        "calmar": round(cagr / abs(mdd), 3) if mdd < 0 else float("nan"),
        "hit_rate_days": round(float((r > 0).mean()), 3),
        "psr_vs_0": round(psr(ex), 3),
    }
    if turnover is not None and len(turnover):
        out["turnover_annual"] = round(float(turnover.sum() / years), 2)
    return out
