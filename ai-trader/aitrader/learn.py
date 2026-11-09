"""Learning loop: grade every signal against what actually happened, then re-weight with guardrails.

Quant side (automatic): cross-sectional rank IC of each signal vs forward excess return,
exponentially weighted, turned into a t-stat, then a multiplicative (Hedge-style) update that is
shrunk to the prior, floored/capped, and step-limited so noise cannot whipsaw the weights.
Only matured outcomes are used: an IC for date d with horizon h is known only at d+h.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def forward_excess(close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Return from close(d) to close(d+h), minus the cross-sectional mean (so the market move cancels)."""
    fwd = close.shift(-horizon) / close - 1.0
    return fwd.sub(fwd.mean(axis=1), axis=0)


def _row_spearman(a: np.ndarray, b: np.ndarray, min_n: int = 10) -> float:
    m = ~(np.isnan(a) | np.isnan(b))
    if m.sum() < min_n:
        return np.nan
    ra = pd.Series(a[m]).rank().values
    rb = pd.Series(b[m]).rank().values
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def ic_table(signals: dict[str, pd.DataFrame], close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Dates x signals of rank IC. Row d is only *knowable* at trading day d+horizon."""
    fwd = forward_excess(close, horizon)
    out = {}
    for name, sig in signals.items():
        s = sig.reindex(index=fwd.index, columns=fwd.columns).values
        f = fwd.values
        out[name] = [_row_spearman(s[i], f[i]) for i in range(len(fwd.index))]
    return pd.DataFrame(out, index=fwd.index)


def signal_stats(ic: pd.DataFrame, asof_pos: int, horizon: int, half_life: float) -> pd.DataFrame:
    """EW mean IC, EW std, effective N and t-stat using only rows matured by position asof_pos."""
    last = asof_pos - horizon
    if last < 1:
        return pd.DataFrame()
    hist = ic.iloc[: last + 1].dropna(how="all")
    if hist.empty:
        return pd.DataFrame()
    age = np.arange(len(hist))[::-1]
    wts = 0.5 ** (age / half_life)
    rows = {}
    for name in hist.columns:
        x = hist[name].values
        m = ~np.isnan(x)
        if m.sum() < 2:
            rows[name] = {"ic": np.nan, "ic_std": np.nan, "n_eff": 0.0, "t": 0.0, "n": int(m.sum())}
            continue
        w = wts[m]
        mu = float(np.sum(w * x[m]) / w.sum())
        var = float(np.sum(w * (x[m] - mu) ** 2) / w.sum())
        # overlapping horizons: divide effective sample by horizon (Newey-West style haircut)
        n_eff = float(w.sum() ** 2 / np.sum(w**2)) / max(horizon, 1)
        t = mu / (np.sqrt(var) / np.sqrt(max(n_eff, 1.0))) if var > 0 else 0.0
        rows[name] = {"ic": mu, "ic_std": float(np.sqrt(var)), "n_eff": n_eff, "t": float(t), "n": int(m.sum())}
    return pd.DataFrame(rows).T


def update_weights(current: dict, prior: dict, stats: pd.DataFrame, cfg: dict) -> tuple[dict, dict]:
    """Guarded multiplicative update. Returns (new_weights, explanation per signal)."""
    L = cfg["learning"]
    if stats.empty:
        return dict(current), {"note": "no matured outcomes yet"}
    target, why = {}, {}
    for name, p in prior.items():
        row = stats.loc[name] if name in stats.index else None
        if row is None or row["n"] < L["min_eval_dates"] or not np.isfinite(row["t"]):
            target[name] = current.get(name, p)
            why[name] = "insufficient evidence - unchanged"
            continue
        t = float(np.clip(row["t"], -3, 3))
        learned = p * np.exp(L["eta"] * t)
        target[name] = L["shrink_to_prior"] * p + (1 - L["shrink_to_prior"]) * learned
        why[name] = f"IC={row['ic']:+.3f} t={row['t']:+.2f} n={int(row['n'])}"
    # floor/cap then normalise
    tw = {k: float(np.clip(v, L["weight_floor"], L["weight_cap"])) for k, v in target.items()}
    s = sum(tw.values())
    tw = {k: v / s for k, v in tw.items()}
    # step limit toward target, then renormalise
    new = {}
    for k, v in tw.items():
        c = current.get(k, prior[k])
        new[k] = c + float(np.clip(v - c, -L["max_step"], L["max_step"]))
    s = sum(new.values())
    new = {k: round(v / s, 4) for k, v in new.items()}
    return new, why


def walk_forward_weights(signals, close, prior, cfg, dates, every: int = 21) -> dict:
    """Weights as they would have been learned through time (for the time machine). {date: weights}."""
    L = cfg["learning"]
    h = L["primary_horizon_days"]
    ic = ic_table(signals, close, h)
    pos_of = {d: i for i, d in enumerate(close.index)}
    w = dict(prior)
    out = {}
    for j, d in enumerate(dates):
        if j % every == 0:
            st = signal_stats(ic, pos_of[d], h, L["ic_half_life_days"])
            w, _ = update_weights(w, prior, st, cfg)
        out[d] = dict(w)
    return out
