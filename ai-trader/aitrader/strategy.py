"""Turn signal scores into risk-managed target weights. Same code path for live and the time machine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .signals import TRADING_DAYS, atr, realized_vol, returns

ETF_SECTORS = {"Index", "SectorETF", "Bonds", "Gold"}  # stock default; the live value is market.etf_groups


def etf_groups(cfg: dict) -> set[str]:
    return set(cfg.get("market", {}).get("etf_groups", ETF_SECTORS))


def periods_per_year(cfg: dict) -> int:
    return cfg.get("market", {}).get("periods_per_year", TRADING_DAYS)


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


def regime_series(px: pd.Series, sma: pd.Series, band: float, mode: str) -> tuple[pd.Series, pd.Series]:
    """Causal regime per bar from the benchmark close and its SMA: ("risk_on" | "risk_off" | "risk_off(no-data)",
    carried state "on" | "off" | None). A NaN close or SMA is no-data that day (fails closed).
    offset: risk-off while px < sma*(1-band), bar by bar.
    hysteresis: the first valid bar starts the state like offset; then off below sma*(1-band) and back on only above
    sma*(1+band). A no-data bar leaves the carried state unchanged. Nothing is persisted: the value at t depends only
    on bars up to t and on where the history starts."""
    if mode not in ("offset", "hysteresis"):
        raise ValueError(f"unknown risk.regime_band_mode {mode!r} (offset | hysteresis)")
    p, lo, hi = px.to_numpy(float), (sma * (1 - band)).to_numpy(float), (sma * (1 + band)).to_numpy(float)
    valid = (px.notna() & sma.notna()).to_numpy()
    regime, state, on = [], [], None
    for i in range(len(p)):
        if not valid[i]:
            regime.append("risk_off(no-data)")
        else:
            on = bool(p[i] > hi[i]) if (mode == "hysteresis" and on is False) else not p[i] < lo[i]
            regime.append("risk_on" if on else "risk_off")
        state.append(None if on is None else "on" if on else "off")
    return pd.Series(regime, index=px.index, dtype=object), pd.Series(state, index=px.index, dtype=object)


def precompute_aux(panel: dict, cfg: dict) -> dict:
    """Panels reused every day (vol, ATR, benchmark SMA, regime). Backward-looking only."""
    r = cfg["risk"]
    close = panel["close"]
    bench = cfg.get("benchmark", "SPY")
    aux = {
        "vol": realized_vol(close, r["vol_lookback_days"]),
        "vol_long": realized_vol(close, r.get("lowvol_exclude_lookback", 252)),
        "atr": atr(panel["high"], panel["low"], close, r["atr_days"]),
        "rets": returns(close),
    }
    if bench in close:
        aux["bench_sma"] = close[bench].rolling(r["regime_sma_days"], min_periods=r["regime_sma_days"]).mean()
        bpx, sma = close[bench], aux["bench_sma"]
    else:  # no benchmark column: every day is no-data (fails closed)
        bpx = sma = pd.Series(np.nan, index=close.index)
    aux["regime"], aux["regime_state"] = regime_series(bpx, sma, r.get("regime_band_pct", 0.0), r.get("regime_band_mode", "offset"))
    return aux


def _dd_state(dd: float, r: dict) -> str:
    return "flat" if dd <= r["dd_flat"] else "halved" if dd <= r["dd_halve"] else "normal"


def _regime_detail(aux: dict, date, bpx) -> dict:
    """The inputs behind the regime on `date`, for books that report them (market.fill_regime_on_no_picks)."""
    sma = aux["bench_sma"].loc[date] if "bench_sma" in aux else np.nan
    return {"regime_px": round(float(bpx), 4) if pd.notna(bpx) else None,
            "regime_sma": round(float(sma), 4) if pd.notna(sma) else None,
            "regime_state": aux["regime_state"].loc[date]}


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
        if r["atr_stop_mult"] > 0 and sym in px and pd.notna(px[sym]) and pd.notna(a.get(sym)):
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
    # low-vol anomaly as a filter: no NEW entries in the most volatile names of the day
    too_hot = set()
    if r.get("lowvol_exclude_top_pct") and "vol_long" in aux:
        vl = aux["vol_long"].loc[date].dropna()
        if len(vl) >= r.get("lowvol_exclude_min_names", 10):
            too_hot = set(vl[vl >= vl.quantile(1 - r["lowvol_exclude_top_pct"])].index)
    new = [s for s in ranked.index if ranked[s] > r["min_score"] and s not in keep and s not in too_hot]
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
    # Regime filter on the benchmark (aux["regime"], causal). Fails CLOSED: missing data counts as risk-off.
    regime = aux["regime"].loc[date]
    fill = cfg.get("market", {}).get("fill_regime_on_no_picks", False)
    detail = _regime_detail(aux, date, px.get(bench, np.nan)) if fill else {}
    if picks.empty:
        if not fill:  # stocks: as before, no regime and no drawdown state on a day with no picks
            diag.update({"regime": "n/a", "gross": 0.0})
            return {}, diag
        # crypto: the regime and the drawdown state every day, or a flat book's re-entry streak breaks (decision 8)
        dd = equity_peak_ratio - 1.0
        diag.update({"regime": regime, **detail, "drawdown": round(dd, 4), "dd_state": _dd_state(dd, r), "gross": 0.0})
        return {}, diag

    raw = picks / vol[picks.index]
    w = raw / raw.sum()
    secs = pd.Series({s: sectors_map.get(s, "Other") for s in w.index})
    etf = etf_groups(cfg)
    by_sym = r.get("max_position_pct_by_symbol", {})
    caps = pd.Series({s: by_sym.get(s, r["max_etf_position_pct"] if secs[s] in etf else r["max_position_pct"]) for s in w.index})
    # Allow the whole book only if it can be filled under caps; otherwise the rest stays cash.
    w = _cap_weights(w, caps, secs, r["max_sector_pct"])

    # Volatility targeting on ex-ante covariance.
    rets = aux["rets"].loc[:date].tail(r["vol_lookback_days"])[w.index].fillna(0.0)
    cov = rets.cov().values * periods_per_year(cfg)
    port_vol = float(np.sqrt(max(w.values @ cov @ w.values, 1e-12)))
    scale = min(r["max_gross"] / max(w.sum(), 1e-9), r["target_vol_annual"] / port_vol)

    if regime != "risk_on":
        scale *= r["risk_off_gross_mult"]

    # Defensive mode: VIX in the top of its own trailing-year range (percentile, not a fixed level).
    vix = panel.get("vix")
    if r.get("defensive_vix_pct") and (vix is not None or panel.get("_require_vix")):
        hist = vix.loc[:date].tail(252).dropna() if vix is not None else pd.Series(dtype=float)
        missing = vix is None or pd.isna(vix.get(date, np.nan)) or len(hist) <= 60  # fail closed when VIX is missing
        if missing or (hist <= hist.iloc[-1]).mean() >= r["defensive_vix_pct"]:
            regime = regime + ("+defensive(no-vix)" if missing else "+defensive")
            scale *= r.get("defensive_gross_mult", 0.75)

    # Drawdown circuit breaker.
    dd = equity_peak_ratio - 1.0
    dd_state = _dd_state(dd, r)
    if dd_state == "flat":
        scale = 0.0
    elif dd_state == "halved":
        scale *= 0.5

    # Scale, then re-apply per-name and sector caps WITHOUT redistribution (scaling up must never breach caps).
    w = np.minimum((w * scale).clip(lower=0), caps)
    for sec, tot in w.groupby(secs).sum().items():
        if tot > r["max_sector_pct"]:
            w[secs == sec] *= r["max_sector_pct"] / tot
    targets = {s: float(v) for s, v in w.items() if v > 1e-4}
    diag.update(
        {
            "regime": regime,
            **detail,
            "drawdown": round(dd, 4),
            "dd_state": dd_state,
            "ex_ante_vol_unscaled": round(port_vol, 4),
            "scale": round(float(scale), 4),
            "gross": round(sum(targets.values()), 4),
            "targets": {k: round(v, 4) for k, v in sorted(targets.items(), key=lambda kv: -kv[1])},
        }
    )
    return targets, diag
