"""Turn signal scores into risk-managed target weights. Same code path for live and the time machine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .signals import TRADING_DAYS, atr, realized_vol, returns

ETF_SECTORS = {"Index", "SectorETF", "Bonds", "Gold"}


def combine(signals: dict[str, pd.DataFrame], weights: dict[str, float], date) -> pd.Series:
    """Weighted ensemble score per symbol on one date. Needs at least half of the weight available."""
    num, den = None, None
    for name, w in weights.items():
        if name not in signals or w <= 0:
            continue
        row = signals[name].loc[date]
        avail = row.notna().astype(float) * w
        val = row.fillna(0.0) * w
        num = val if num is None else num.add(val, fill_value=0.0)
        den = avail if den is None else den.add(avail, fill_value=0.0)
    if num is None:
        return pd.Series(dtype=float)
    total = sum(w for n, w in weights.items() if n in signals and w > 0)
    score = num / den.replace(0, np.nan)
    score[den < 0.5 * total] = np.nan
    return score


def _cap_weights(w: pd.Series, caps: pd.Series, sectors: pd.Series, sector_cap: float, iters: int = 20) -> pd.Series:
    """Water-filling: clip to per-name and per-sector caps, redistribute excess to uncapped names."""
    w = w.copy()
    target_sum = w.sum()
    for _ in range(iters):
        w = np.minimum(w, caps)
        sec_tot = w.groupby(sectors).sum()
        over = sec_tot[sec_tot > sector_cap]
        for sec, tot in over.items():
            m = sectors == sec
            w[m] *= sector_cap / tot
        excess = target_sum - w.sum()
        if excess <= 1e-9:
            break
        sec_tot = w.groupby(sectors).sum()
        room = (caps - w).clip(lower=0)
        room[sectors.map(sec_tot).fillna(0) >= sector_cap - 1e-9] = 0
        if room.sum() <= 1e-9:
            break
        w = w + room / room.sum() * min(excess, room.sum())
    return w


def precompute_aux(panel: dict, cfg: dict) -> dict:
    """Panels reused every day (vol, ATR, benchmark SMA). Backward-looking only."""
    r = cfg["risk"]
    close = panel["close"]
    bench = cfg.get("benchmark", "SPY")
    aux = {
        "vol": realized_vol(close, r["vol_lookback_days"]),
        "atr": atr(panel["high"], panel["low"], close, r["atr_days"]),
        "rets": returns(close),
    }
    if bench in close:
        aux["bench_sma"] = close[bench].rolling(r["regime_sma_days"], min_periods=r["regime_sma_days"]).mean()
    return aux


def build_targets(
    date,
    panel: dict,
    signals: dict[str, pd.DataFrame],
    weights: dict[str, float],
    cfg: dict,
    equity_peak_ratio: float,
    held: dict,
    blocked: set | None = None,
    aux: dict | None = None,
) -> tuple[dict[str, float], dict]:
    """Target portfolio weights for `date`.

    equity_peak_ratio: current equity / running peak (1.0 = at peak).
    held: {sym: {"peak_close": float, ...}} current positions for stop checks.
    blocked: symbols in stop-loss cooldown.
    Returns (targets, diagnostics).
    """
    r = cfg["risk"]
    sectors_map = cfg["universe"]
    close = panel["close"]
    px = close.loc[date]
    bench = cfg.get("benchmark", "SPY")
    blocked = blocked or set()

    aux = aux or precompute_aux(panel, cfg)
    score = combine(signals, weights, date).dropna()
    vol = aux["vol"].loc[date]

    # Stops: trailing ATR stop from the peak close since entry.
    a = aux["atr"].loc[date]
    stopped = []
    for sym, pos in held.items():
        if sym in px and pd.notna(px[sym]) and pd.notna(a.get(sym)):
            stop = pos.get("peak_close", px[sym]) - r["atr_stop_mult"] * a[sym]
            if px[sym] < stop:
                stopped.append(sym)

    # Hysteresis to cut turnover: new names need score > min_score and a top-N rank; names already
    # held stay while score > exit_score and rank is inside top (N * keep_rank_mult).
    ok = px.reindex(score.index).notna() & vol.reindex(score.index).gt(0)
    ranked = score[ok].sort_values(ascending=False)
    rank = pd.Series(range(1, len(ranked) + 1), index=ranked.index)
    n = r["max_positions"]
    keep = [s for s in held if s in rank.index and ranked[s] > r.get("exit_score", 0.0) and rank[s] <= n * r.get("keep_rank_mult", 2.0)]
    new = [s for s in ranked.index if ranked[s] > r["min_score"] and s not in keep]
    chosen = [s for s in keep + new if s not in blocked and s not in stopped][:n]
    elig = ranked[ranked > r["min_score"]]
    picks = ranked[chosen]

    diag = {
        "date": str(pd.Timestamp(date).date()),
        "n_scored": int(score.size),
        "n_eligible": int(elig.size),
        "stopped": stopped,
        "top_scores": {k: round(float(v), 3) for k, v in score.sort_values(ascending=False).head(10).items()},
        "bottom_scores": {k: round(float(v), 3) for k, v in score.sort_values().head(5).items()},
    }
    if picks.empty:
        diag.update({"regime": "n/a", "gross": 0.0})
        return {}, diag

    raw = picks / vol[picks.index]
    w = raw / raw.sum()
    secs = pd.Series({s: sectors_map.get(s, "Other") for s in w.index})
    caps = pd.Series({s: (r["max_etf_position_pct"] if secs[s] in ETF_SECTORS else r["max_position_pct"]) for s in w.index})
    # Allow the whole book only if it can be filled under caps; otherwise the rest stays cash.
    w = _cap_weights(w, caps, secs, r["max_sector_pct"])

    # Volatility targeting on ex-ante covariance.
    rets = aux["rets"].loc[:date].tail(r["vol_lookback_days"])[w.index].fillna(0.0)
    cov = rets.cov().values * TRADING_DAYS
    port_vol = float(np.sqrt(max(w.values @ cov @ w.values, 1e-12)))
    scale = min(r["max_gross"] / max(w.sum(), 1e-9), r["target_vol_annual"] / port_vol)

    # Regime filter on the benchmark.
    regime = "risk_on"
    if "bench_sma" in aux:
        sma = aux["bench_sma"].loc[date]
        if pd.notna(px.get(bench)) and pd.notna(sma) and px[bench] < sma:
            regime = "risk_off"
            scale *= r["risk_off_gross_mult"]

    # Drawdown circuit breaker.
    dd = equity_peak_ratio - 1.0
    dd_state = "normal"
    if dd <= r["dd_flat"]:
        scale, dd_state = 0.0, "flat"
    elif dd <= r["dd_halve"]:
        scale *= 0.5
        dd_state = "halved"

    w = (w * scale).clip(lower=0)
    targets = {s: float(v) for s, v in w.items() if v > 1e-4}
    diag.update(
        {
            "regime": regime,
            "drawdown": round(dd, 4),
            "dd_state": dd_state,
            "ex_ante_vol_unscaled": round(port_vol, 4),
            "scale": round(float(scale), 4),
            "gross": round(sum(targets.values()), 4),
            "targets": {k: round(v, 4) for k, v in sorted(targets.items(), key=lambda kv: -kv[1])},
        }
    )
    return targets, diag
