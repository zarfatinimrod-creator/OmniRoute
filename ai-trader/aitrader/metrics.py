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


# config.json "bootstrap" overrides key by key. min_blocks: under min_blocks x block_days days no range is computed
BOOT_DEFAULTS = {"block_days": 20, "draws": 2000, "seed": 0, "level": 0.95, "min_blocks": 40}
BOOT_CELLS = 4_000_000  # array cells (resamples x days x series) handled at once: memory, not a model assumption


class BootRefused(ValueError):
    """The ranges were refused on purpose; str() is the reason a report prints (boot_error)."""


def boot_error(e: Exception) -> str:
    """What follows "Ranges: not computed": the reason of a refusal, the type name of any other error."""
    return str(e) if isinstance(e, BootRefused) else type(e).__name__


def boot_cfg(cfg: dict | None) -> dict:
    return {**BOOT_DEFAULTS, **((cfg or {}).get("bootstrap") or {})}


def boot_index(n: int, block: float, draws: int, seed: int) -> np.ndarray:
    """Day positions of `draws` resamples of an n-day history, shape (draws, n): the stationary bootstrap (Politis and
    Romano 1994). A block starts on a random day, runs on day after day and ends with probability 1/block (mean
    length `block`); it wraps past the last day to the first, so every day is drawn equally often. Blocks keep the
    day-to-day dependence of returns that drawing single days would throw away."""
    if n < 2 or block < 1 or draws < 1:
        raise BootRefused(f"bootstrap needs n >= 2, block >= 1 and draws >= 1, got {n}, {block}, {draws}")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:  # None would run unseeded
        raise BootRefused(f"bootstrap.seed must be a whole number >= 0, got {seed!r}: without it the ranges differ on every run")
    rng = np.random.default_rng(seed)
    pos = np.arange(n)
    new = rng.random((draws, n)) < 1.0 / block
    new[:, 0] = True
    began = np.maximum.accumulate(np.where(new, pos, 0), axis=1)  # where the block covering each position began
    first = np.take_along_axis(rng.integers(0, n, (draws, n)), began, axis=1)  # the day that block starts on
    return (first + pos - began) % n


def boot_stats(returns: np.ndarray, idx: np.ndarray, rf_daily: float, periods_per_year: int = TD) -> dict:
    """Sharpe (annualised, excess of cash), CAGR and max drawdown of every series on every resample, as summary()
    defines them. returns: (days, series); idx: boot_index(); each result: (draws, series). A resample without
    variance has Sharpe 0. Every series is read on the same resampled days, so their differences are paired."""
    n, k = returns.shape
    step = max(1, BOOT_CELLS // (n * k))
    out = {name: np.empty((len(idx), k)) for name in ("sharpe", "cagr", "maxdd")}
    for a in range(0, len(idx), step):
        x = returns[idx[a:a + step]]  # (resamples, days, series)
        ex = x - rf_daily
        sd = ex.std(axis=1, ddof=1)
        out["sharpe"][a:a + step] = np.divide(ex.mean(axis=1), sd, out=np.zeros_like(sd), where=sd > 0) * math.sqrt(periods_per_year)
        eq = np.cumprod(1 + x, axis=1)
        out["cagr"][a:a + step] = eq[:, -1] ** (periods_per_year / n) - 1
        peak = np.maximum(np.maximum.accumulate(eq, axis=1), 1.0)  # the path starts at 1, before the first return
        out["maxdd"][a:a + step] = (eq / peak - 1).min(axis=1)
    return out


def p_above(d) -> float:
    """Share of resamples with d > 0. A tie counts half, so a row identical to its reference reads 0.5, not 0."""
    d = np.asarray(d, dtype=float)
    return float((d > 0).mean() + 0.5 * (d == 0).mean())


def boot_rows(daily: pd.DataFrame, rf_daily: float, periods_per_year: int, settings: dict, pairs: dict | None = None,
              bench: str | None = None) -> dict:
    """Ranges and paired probabilities for the rows of a sweep. daily: days x runs with columns (row, phase); days
    missing in any column are dropped, so every run is read on the same days. A row's number is the median over its
    phases (what the sweep table prints) and its range is the central `level` share of that median over the
    resamples; "phases" holds the same for each single run.
    p_gt_bench: share of resamples where the Sharpe is above the bench row's on the same resampled days.
    p_gt_base: the same for the median paired difference with pairs[row], each phase k against that row's phase
    k % (its number of phases). Both are probabilities under resampling, not tests: nothing here says "significant".
    The max-drawdown range is approximate: reshuffled days break the path a drawdown breaker reacted to.
    Refused (BootRefused) under settings["min_blocks"] x block_days days: on few blocks the range comes out narrower
    than its label (at 6 blocks of 20 days a 95% range held a known Sharpe 353 times in 400:
    research/2026-11-10-time-machine-honesty.md, "After the gate review")."""
    d = daily.dropna()
    need = settings["min_blocks"] * settings["block_days"]
    if len(d) < need:
        raise BootRefused(f"{len(d)} days of returns, under the floor of bootstrap.min_blocks x block_days = "
                          f"{settings['min_blocks']} x {settings['block_days']} = {need} days: on fewer blocks the range "
                          "is narrower than its label")
    cols = list(d.columns)
    at = {c: i for i, c in enumerate(cols)}
    st = boot_stats(d.to_numpy(dtype=float), boot_index(len(d), settings["block_days"], settings["draws"], settings["seed"]),
                    rf_daily, periods_per_year)
    q = [(1 - settings["level"]) / 2, (1 + settings["level"]) / 2]
    phases = {r: [k for name, k in cols if name == r] for r in dict.fromkeys(name for name, _ in cols)}
    pairs = pairs or {}

    def describe(row: str, ks: list) -> dict:
        sel = [at[(row, k)] for k in ks]
        out = {}
        for name, nd in (("sharpe", 3), ("cagr", 4), ("maxdd", 4)):
            lo, hi = np.quantile(np.median(st[name][:, sel], axis=1), q)
            out[f"{name}_lo"], out[f"{name}_hi"] = round(float(lo), nd), round(float(hi), nd)
        s = st["sharpe"][:, sel]
        out["p_gt_bench"] = out["p_gt_base"] = None
        if bench in phases and row != bench:
            out["p_gt_bench"] = round(p_above(np.median(s, axis=1) - st["sharpe"][:, at[(bench, phases[bench][0])]]), 3)
        if pairs.get(row) in phases:
            m = len(phases[pairs[row]])
            out["p_gt_base"] = round(p_above(np.median(s - st["sharpe"][:, [at[(pairs[row], k % m)] for k in ks]], axis=1)), 3)
        return out

    return {"rows": {r: describe(r, ks) for r, ks in phases.items()},
            "phases": {(r, k): describe(r, [k]) for r, ks in phases.items() for k in ks},
            "settings": {**settings, "days": len(d), "method": "stationary bootstrap, circular"}}


def summary(equity: pd.Series, turnover: pd.Series | None = None, rf_annual: float = 0.0, periods_per_year: int = TD) -> dict:
    """Sharpe/Sortino/PSR use returns in EXCESS of the cash rate, so earning interest on idle cash
    does not flatter a low-exposure strategy against SPY."""
    eq = equity.dropna()
    r = eq.pct_change().dropna()
    if len(r) < 2:
        return {}
    years = len(r) / periods_per_year
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else float("nan")
    vol = r.std() * math.sqrt(periods_per_year)
    ex = r - ((1 + rf_annual) ** (1 / periods_per_year) - 1)
    sharpe = ex.mean() / ex.std() * math.sqrt(periods_per_year) if ex.std() > 0 else float("nan")
    down = math.sqrt(float((ex.clip(upper=0) ** 2).mean())) * math.sqrt(periods_per_year)
    sortino = ex.mean() * periods_per_year / down if down > 0 else float("nan")
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
