"""The Time Machine: replay history day by day with the exact live decision code.

Decisions use data up to the close of day t and execute at the open of day t+1, with slippage.
Signal weights are learned walk-forward (only from outcomes matured before each date).
Never trust one run: `sweep()` re-runs under different cost/parameter assumptions; if the
conclusion flips between reasonable assumptions there is no conclusion, only sensitivity.
"""

from __future__ import annotations

import copy
import json

import pandas as pd

from . import journal
from .broker import PaperBroker
from .learn import walk_forward_weights
from .metrics import summary
from .signals import compute_all
from .strategy import build_targets, periods_per_year, precompute_aux


def _px(row: pd.Series) -> dict:
    return {k: float(v) for k, v in row.items() if pd.notna(v) and v > 0}


def run(panel: dict, cfg: dict, start: str, end: str | None = None, weights_mode: str = "learned",
        rebalance_every: int | None = None, signals: dict | None = None, aux: dict | None = None, phase: int = 0) -> dict:
    close = panel["close"]
    dates = close.loc[start:end].index if end else close.loc[start:].index
    if len(dates) < 30:
        raise ValueError("not enough dates in range")
    signals = signals or compute_all(panel, cfg)
    aux = aux or precompute_aux(panel, cfg)
    rebalance_every = rebalance_every or cfg["risk"].get("rebalance_every_days", 5)
    prior = cfg["prior_weights"]
    if weights_mode == "learned" and cfg["learning"].get("enabled", True):
        gate = (journal.load_json("placebo.json", {}) or {}).get("gate_z95")  # noise level, not return direction
        wmap = walk_forward_weights(signals, close, prior, cfg, list(dates), gate=gate)
    else:
        wmap = {d: prior for d in dates}

    r = cfg["risk"]
    broker = PaperBroker(cfg["account"]["starting_cash"], cfg["costs"]["slippage_bps"], cfg["costs"]["commission_per_share"], None,
                         cfg["costs"].get("qty_step", 1), cfg["costs"].get("fee_bps", 0.0))
    pending, pending_stopped = None, []
    equity, turnover, all_fills = {}, {}, []
    prev_regime, prev_dd = None, None
    exits_only_pending = False
    for i, d in enumerate(dates):
        ds = str(d.date())
        cpx = _px(close.loc[d])
        if pending is not None:
            opx = _px(panel["open"].loc[d])
            exec_px = {**cpx, **opx}  # trade at the open; fall back to close if the open is missing
            eq_before = broker.equity(exec_px)
            cool = str(dates[min(i + r.get("stop_cooldown_days", 10), len(dates) - 1)].date())
            fills = broker.rebalance(pending, exec_px, ds, r["rebalance_band_pct"], r["min_trade_value"], pending_stopped, cool, exits_only_pending)
            turnover[d] = sum(f["value"] for f in fills) / max(eq_before, 1e-9)
            all_fills.extend(fills)
            pending = None
        equity[d] = broker.mark(cpx, ds, cfg["account"]["cash_yield_annual"], periods_per_year(cfg))
        blocked = set(broker.state.get("blocked", {}))
        on_cycle = (i + phase) % rebalance_every == 0
        broker.maybe_reset_peak(prev_regime or "", ds, r.get("dd_reentry_days", 20), r["dd_halve"], r["dd_flat"], r.get("dd_reentry_ref"))
        targets, diag = build_targets(d, panel, signals, wmap[d], cfg, broker.peak_ratio(cpx), broker.positions, blocked, aux)
        # same trigger as live: scheduled rebalance, or any regime / drawdown-state change, or a flat breaker
        changed = (prev_regime is not None and diag.get("regime") != prev_regime) or (prev_dd is not None and diag.get("dd_state") != prev_dd)
        broker.state["dd_state"] = diag.get("dd_state")
        prev_regime, prev_dd = diag.get("regime", prev_regime), diag.get("dd_state", prev_dd)
        if on_cycle or changed or diag.get("dd_state") == "flat":
            pending, pending_stopped, exits_only_pending = targets, diag.get("stopped", []), False
        elif diag.get("stopped"):  # off-cycle day: act on stops only (exits-only, like live)
            pending = {s_: 1.0 for s_ in broker.positions if s_ not in diag["stopped"]}
            pending_stopped, exits_only_pending = diag["stopped"], True

    eq = pd.Series(equity)
    to = pd.Series(turnover, dtype=float)
    bench = cfg.get("benchmark", "SPY")
    spy = close[bench].loc[dates] if bench in close else None
    ew = close.loc[dates].pct_change(fill_method=None).mean(axis=1).fillna(0).add(1).cumprod() * cfg["account"]["starting_cash"]
    rf = cfg["account"]["cash_yield_annual"]
    res = {
        "strategy": summary(eq, to, rf, periods_per_year(cfg)),
        "benchmark_spy": summary(spy / spy.iloc[0] * cfg["account"]["starting_cash"], rf_annual=rf, periods_per_year=periods_per_year(cfg)) if spy is not None else {},
        "benchmark_equal_weight_universe": summary(ew, rf_annual=rf, periods_per_year=periods_per_year(cfg)),
        "n_trades": len(all_fills),
        "final_weights": wmap[dates[-1]],
        "final_positions": {k: v["qty"] for k, v in broker.positions.items()},
    }
    res["_equity"] = eq
    res["_fills"] = all_fills
    return res


_G: dict = {}


def _variants(cfg: dict) -> list[tuple]:
    base_every = cfg["risk"].get("rebalance_every_days", 5)
    return [
        ("base", {}, "learned", base_every),
        ("prior weights (no learning)", {}, "prior", base_every),
        ("costs 15bps", {"costs": {"slippage_bps": 15}}, "learned", base_every),
        ("costs 30bps", {"costs": {"slippage_bps": 30}}, "learned", base_every),
        ("daily rebalance", {}, "learned", 1),
        ("monthly rebalance", {}, "learned", 21),
        ("target vol 10%", {"risk": {"target_vol_annual": 0.10}}, "learned", base_every),
        ("target vol 16%", {"risk": {"target_vol_annual": 0.16}}, "learned", base_every),
        ("no regime filter", {"risk": {"risk_off_gross_mult": 1.0}}, "learned", base_every),
        ("no VIX defensive mode", {"risk": {"defensive_gross_mult": 1.0}}, "learned", base_every),
        ("8 positions max", {"risk": {"max_positions": 8}}, "learned", base_every),
        ("ETF-only universe (no survivorship bias)", {"_etf": True}, "learned", base_every),
    ]


def _job(args):
    name, override, mode, every, phase = args
    c = copy.deepcopy(_G["cfg"])
    panel, signals = _G["panel"], _G["signals"]
    if override.get("_etf"):
        etf = [k for k, v in c["universe"].items() if v in ("Index", "SectorETF", "Bonds", "Gold")]
        panel = {k: (v[etf] if isinstance(v, pd.DataFrame) else v) for k, v in panel.items()}
        c["universe"] = {k: c["universe"][k] for k in etf}
        c["risk"]["max_positions"] = 6
        signals = None
    for sec, kv in override.items():
        if not sec.startswith("_"):
            c[sec].update(kv)
    res = run(panel, c, _G["start"], _G["end"], mode, every, signals=signals, aux=precompute_aux(panel, c), phase=phase)
    out = {"variant": name, "phase": phase, "trades": res["n_trades"], **res["strategy"]}
    if name == "base" and phase == 0:
        out["_daily"] = (res["_equity"].pct_change().dropna()).tolist()
        out["_bench"] = {"SPY buy&hold": res["benchmark_spy"], "Equal-weight universe": res["benchmark_equal_weight_universe"]}
    return out


def sweep(panel: dict, cfg: dict, start: str, end: str | None = None, workers: int = 4) -> pd.DataFrame:
    """Every variant x every weekly rebalance phase, compared PAIRED with the base at the same phase.
    Read the median and the win count, never one row: a change is real only if it wins in most phases."""
    from concurrent.futures import ProcessPoolExecutor

    _G.update({"panel": panel, "cfg": cfg, "start": start, "end": end, "signals": compute_all(panel, cfg)})
    base_every = cfg["risk"].get("rebalance_every_days", 5)
    jobs = []
    for name, ov, mode, every in _variants(cfg):
        phases = [0] if every == 1 else list(range(base_every)) if every == base_every else [k * (every // base_every) for k in range(base_every)]
        jobs += [(name, ov, mode, every, k) for k in phases]
    with ProcessPoolExecutor(max_workers=workers) as ex:  # fork: workers share the panel without pickling
        results = list(ex.map(_job, jobs))
    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in results])
    base = df[df.variant == "base"].set_index("phase")
    rows = []
    for name, g in df.groupby("variant", sort=False):
        g = g.set_index("phase")
        paired = [(g.at[k, "sharpe"] - base.at[k % base_every, "sharpe"]) for k in g.index if (k % base_every) in base.index]
        rows.append({
            "variant": name, "phases": len(g), "sharpe_med": round(g.sharpe.median(), 3), "sharpe_min": round(g.sharpe.min(), 3),
            "sharpe_max": round(g.sharpe.max(), 3), "wins_vs_base": f"{sum(x > 0 for x in paired)}/{len(paired)}" if name != "base" else "-",
            "d_sharpe_med": round(float(pd.Series(paired).median()), 3) if name != "base" else 0.0,
            "cagr_med": round(g.cagr.median(), 4), "maxdd_med": round(g.max_drawdown.median(), 4), "calmar_med": round(g.calmar.median(), 3),
            "turnover_med": round(g.turnover_annual.median(), 2), "psr_med": round(g.psr_vs_0.median(), 3)})
    b0 = next(r for r in results if r["variant"] == "base" and r["phase"] == 0)
    for label, bm in b0["_bench"].items():
        rows.append({"variant": label, "sharpe_med": bm.get("sharpe"), "cagr_med": bm.get("cagr"), "maxdd_med": bm.get("max_drawdown"),
                     "calmar_med": bm.get("calmar"), "psr_med": bm.get("psr_vs_0")})
    try:  # Deflated Sharpe of the base: deflated by every configuration ever registered + this sweep
        from .metrics import dsr
        n_prev = sum(len(t.get("rows", [])) for t in journal.read("trials.jsonl") if "rows" in t)
        srs = df.groupby("variant").sharpe.median() / (periods_per_year(cfg) ** 0.5)
        rf_d = (1 + cfg["account"]["cash_yield_annual"]) ** (1 / periods_per_year(cfg)) - 1
        daily = pd.Series(b0["_daily"]) - rf_d
        rows.append({"variant": f"DSR of base (N={n_prev + len(srs)} trials)", "psr_med": round(dsr(daily, n_prev + len(srs), float(srs.std())), 3)})
    except Exception as e:  # noqa: BLE001 - informative only
        rows.append({"variant": f"DSR unavailable: {type(e).__name__}"})
    return pd.DataFrame(rows)


def to_json(res: dict) -> str:
    return json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, indent=2, default=str)
