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


def ic_table(signals: dict[str, pd.DataFrame], close: pd.DataFrame, horizon: int, min_n: int = 10) -> pd.DataFrame:
    """Dates x signals of rank IC. Row d is only *knowable* at trading day d+horizon."""
    fwd = forward_excess(close, horizon)
    out = {}
    for name, sig in signals.items():
        s = sig.reindex(index=fwd.index, columns=fwd.columns).values
        f = fwd.values
        out[name] = [_row_spearman(s[i], f[i], min_n) for i in range(len(fwd.index))]
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


def shrunk_z(row, L: dict) -> float:
    """Empirical-Bayes shrinkage of the mean IC toward 0 (prior sd tau); returns a capped z-score."""
    n = float(row["n_eff"])
    if not np.isfinite(row["ic"]) or n <= 0:
        return 0.0
    sd = max(float(row["ic_std"]) if np.isfinite(row["ic_std"]) else 0.0, L["ic_sd_floor"])
    tau = L["tau"]
    lam = n / (n + sd**2 / tau**2)
    mu = lam * float(row["ic"])
    se = (n / sd**2 + 1 / tau**2) ** -0.5
    return float(np.clip(mu / se, -L["z_cap"], L["z_cap"]))


def update_weights(current: dict, prior: dict, stats: pd.DataFrame, cfg: dict, gate: float | None = None) -> tuple[dict, dict]:
    """Guarded tilt away from the prior. A signal moves only with enough data (min_n_eff) AND a shrunk z beyond
    the placebo gate (the |z| that pure noise reaches 95% of the time). No gate computed yet = no tilt at all."""
    L = cfg["learning"]
    if stats.empty:
        return dict(current), {"note": "no matured outcomes yet"}
    target, why = {}, {}
    for name, p in prior.items():
        row = stats.loc[name] if name in stats.index else None
        if row is None or row["n_eff"] < L["min_n_eff"]:
            target[name] = p
            why[name] = "insufficient evidence - prior"
            continue
        z = shrunk_z(row, L)
        if gate is None or abs(z) < gate:
            target[name] = p
            why[name] = f"IC={row['ic']:+.3f} z={z:+.2f} below placebo gate {gate} - prior"
            continue
        target[name] = p * np.exp(L["eta"] * z)
        why[name] = f"IC={row['ic']:+.3f} z={z:+.2f} n_eff={row['n_eff']:.0f} passes gate {gate:.2f}"
    band = {k: (max(L["weight_floor"], 0.5 * p), min(L["weight_cap"], 2.0 * p)) for k, p in prior.items()}
    tw = {k: float(np.clip(v, *band[k])) if prior[k] > 0 else 0.0 for k, v in target.items()}
    s = sum(tw.values())
    tw = {k: v / s for k, v in tw.items()}
    new = {}
    for k, v in tw.items():
        c = current.get(k, prior[k])
        new[k] = max(0.0, c + float(np.clip(v - c, -L["max_step"], L["max_step"])))
    s = sum(new.values())
    return {k: round(v / s, 4) for k, v in new.items()}, why


def placebo_gate(signals: dict, close: pd.DataFrame, cfg: dict, k: int = 100, seed: int = 7) -> dict:
    """Shuffle which stock each signal column belongs to and record the largest |shrunk z| noise produces.
    The 95th percentile of that max is the gate a real signal must beat before the learner may tilt."""
    L = cfg["learning"]
    h = L["primary_horizon_days"]
    rng = np.random.default_rng(seed)
    maxes = []
    for _ in range(k):
        perm = rng.permutation(close.columns)
        shuffled = {n: s.reindex(columns=close.columns).set_axis(perm, axis=1).reindex(columns=close.columns) for n, s in signals.items()}
        ic = ic_table(shuffled, close, h, L.get("ic_min_names", 10))
        st = signal_stats(ic, len(ic) - 1, h, L["ic_half_life_days"])
        zs = [abs(shrunk_z(st.loc[n], L)) for n in st.index if st.loc[n, "n_eff"] >= L["min_n_eff"]]
        maxes.append(max(zs) if zs else 0.0)
    real = signal_stats(ic_table(signals, close, h, L.get("ic_min_names", 10)), len(close) - 1, h, L["ic_half_life_days"])
    real_z = {n: round(shrunk_z(real.loc[n], L), 3) for n in real.index}
    return {"k": k, "gate_z95": round(float(np.quantile(maxes, 0.95)), 3), "noise_max_z_median": round(float(np.median(maxes)), 3),
            "real_z": real_z, "passing": [n for n, z in real_z.items() if abs(z) >= float(np.quantile(maxes, 0.95))]}


def walk_forward_weights(signals, close, prior, cfg, dates, every: int | None = None, gate: float | None = None) -> dict:
    """Weights as they would have been learned through time (for the time machine). {date: weights}."""
    L = cfg["learning"]
    every = every or L.get("update_every_days", 21)
    h = L["primary_horizon_days"]
    ic = ic_table(signals, close, h, L.get("ic_min_names", 10))
    pos_of = {d: i for i, d in enumerate(close.index)}
    w = dict(prior)
    out = {}
    for j, d in enumerate(dates):
        if j % every == 0:
            st = signal_stats(ic, pos_of[d], h, L["ic_half_life_days"])
            w, _ = update_weights(w, prior, st, cfg, gate)
        out[d] = dict(w)
    return out
