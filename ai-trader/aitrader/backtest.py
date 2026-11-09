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
from .strategy import build_targets, precompute_aux


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
    if weights_mode == "learned":
        gate = (journal.load_json("placebo.json", {}) or {}).get("gate_z95")  # noise level, not return direction
        wmap = walk_forward_weights(signals, close, prior, cfg, list(dates), gate=gate)
    else:
        wmap = {d: prior for d in dates}

    r = cfg["risk"]
    broker = PaperBroker(cfg["account"]["starting_cash"], cfg["costs"]["slippage_bps"], cfg["costs"]["commission_per_share"])
    pending, pending_stopped = None, []
    equity, turnover, all_fills = {}, {}, []
    for i, d in enumerate(dates):
        ds = str(d.date())
        cpx = _px(close.loc[d])
        if pending is not None:
            opx = _px(panel["open"].loc[d])
            exec_px = {**cpx, **opx}  # trade at the open; fall back to close if the open is missing
            eq_before = broker.equity(exec_px)
            cool = str(dates[min(i + r.get("stop_cooldown_days", 10), len(dates) - 1)].date())
            fills = broker.rebalance(pending, exec_px, ds, r["rebalance_band_pct"], r["min_trade_value"], pending_stopped, cool)
            turnover[d] = sum(f["value"] for f in fills) / max(eq_before, 1e-9)
            all_fills.extend(fills)
            pending = None
        equity[d] = broker.mark(cpx, ds, cfg["account"]["cash_yield_annual"])
        blocked = set(broker.state.get("blocked", {}))
        on_cycle = (i + phase) % rebalance_every == 0
        if on_cycle or broker.positions:
            targets, diag = build_targets(d, panel, signals, wmap[d], cfg, broker.peak_ratio(cpx), broker.positions, blocked, aux)
            if on_cycle or diag.get("dd_state") == "flat":
                pending, pending_stopped = targets, diag.get("stopped", [])
            elif diag.get("stopped"):  # off-cycle day: only act on stops
                keep = {s: broker.weights(cpx).get(s, 0.0) for s in broker.positions if s not in diag["stopped"]}
                pending, pending_stopped = keep, diag["stopped"]

    eq = pd.Series(equity)
    to = pd.Series(turnover, dtype=float)
    bench = cfg.get("benchmark", "SPY")
    spy = close[bench].loc[dates] if bench in close else None
    ew = close.loc[dates].pct_change(fill_method=None).mean(axis=1).fillna(0).add(1).cumprod() * cfg["account"]["starting_cash"]
    rf = cfg["account"]["cash_yield_annual"]
    res = {
        "strategy": summary(eq, to, rf),
        "benchmark_spy": summary(spy / spy.iloc[0] * cfg["account"]["starting_cash"], rf_annual=rf) if spy is not None else {},
        "benchmark_equal_weight_universe": summary(ew, rf_annual=rf),
        "n_trades": len(all_fills),
        "final_weights": wmap[dates[-1]],
        "final_positions": {k: v["qty"] for k, v in broker.positions.items()},
    }
    res["_equity"] = eq
    res["_fills"] = all_fills
    return res


def sweep(panel: dict, cfg: dict, start: str, end: str | None = None) -> pd.DataFrame:
    """Re-run under several assumptions. Read the spread, not the best row."""
    signals = compute_all(panel, cfg)
    base_every = cfg["risk"].get("rebalance_every_days", 5)
    variants = [
        ("base (learned weights)", {}, "learned", base_every),
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
    ]
    rows = []
    for name, override, mode, every in variants:
        c = copy.deepcopy(cfg)
        for sec, kv in override.items():
            c[sec].update(kv)
        res = run(panel, c, start, end, mode, every, signals=signals, aux=precompute_aux(panel, c))
        s = res["strategy"]
        rows.append({"variant": name, **{k: s.get(k) for k in ("cagr", "vol", "sharpe", "max_drawdown", "calmar", "turnover_annual", "psr_vs_0")}, "trades": res["n_trades"]})
    # survivorship-free check: ETFs only (no stock picked with hindsight)
    etf = [k for k, v in cfg["universe"].items() if v in ("Index", "SectorETF", "Bonds", "Gold")]
    pe = {k: (v[etf] if isinstance(v, pd.DataFrame) else v) for k, v in panel.items()}
    ce = copy.deepcopy(cfg)
    ce["universe"] = {k: cfg["universe"][k] for k in etf}
    ce["risk"]["max_positions"] = 6
    ree = run(pe, ce, start, end, "learned", base_every)
    s = ree["strategy"]
    rows.append({"variant": "ETF-only universe (no survivorship bias)", **{k: s.get(k) for k in ("cagr", "vol", "sharpe", "max_drawdown", "calmar", "turnover_annual", "psr_vs_0")}, "trades": ree["n_trades"]})
    b = ree["benchmark_equal_weight_universe"]
    rows.append({"variant": "Equal-weight ETFs", **{k: b.get(k) for k in ("cagr", "vol", "sharpe", "max_drawdown", "calmar", "psr_vs_0")}})
    base = run(panel, cfg, start, end, "learned", base_every, signals=signals)
    # The weekly rebalance day is arbitrary: re-run the base on every phase and report the spread.
    ph = [run(panel, cfg, start, end, "learned", base_every, signals=signals, phase=k)["strategy"] for k in range(1, base_every)]
    ph.append(base["strategy"])
    shp = pd.Series([x["sharpe"] for x in ph])
    rows.append({"variant": f"base over {len(ph)} rebalance phases (mean; sd={shp.std():.3f}, min={shp.min():.3f})",
                 **{k: round(float(pd.Series([x[k] for x in ph]).mean()), 4) for k in ("cagr", "vol", "sharpe", "max_drawdown", "calmar", "turnover_annual", "psr_vs_0")}})
    # Deflated Sharpe: deflate the base by every configuration ever tried (trials.jsonl + this sweep).
    try:
        from .metrics import dsr
        n_prev = sum(len(t.get("rows", [])) for t in journal.read("trials.jsonl"))
        srs = pd.Series([r_["sharpe"] for r_ in rows if r_.get("trades")]) / (252 ** 0.5)
        daily = base["_equity"].pct_change().dropna() - ((1 + cfg["account"]["cash_yield_annual"]) ** (1 / 252) - 1)
        rows.append({"variant": f"DSR of base (N={n_prev + len(srs)} trials)", "psr_vs_0": round(dsr(daily, n_prev + len(srs), float(srs.std())), 3)})
    except Exception as e:  # noqa: BLE001 - informative only
        rows.append({"variant": f"DSR unavailable: {type(e).__name__}"})
    for label, key in (("SPY buy&hold", "benchmark_spy"), ("Equal-weight universe", "benchmark_equal_weight_universe")):
        b = base[key]
        rows.append({"variant": label, **{k: b.get(k) for k in ("cagr", "vol", "sharpe", "max_drawdown", "calmar", "psr_vs_0")}})
    return pd.DataFrame(rows)


def to_json(res: dict) -> str:
    return json.dumps({k: v for k, v in res.items() if not k.startswith("_")}, indent=2, default=str)
