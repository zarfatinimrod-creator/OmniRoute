"""One live paper-trading cycle: data -> learn -> decide -> (Claude overrides) -> execute -> journal -> report -> alert."""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

from . import journal, notify
from .broker import PaperBroker
from .data import fetch_panel, load_config, market_status
from .learn import ic_table, signal_stats, update_weights, walk_forward_weights
from .signals import compute_all
from .strategy import build_targets, combine, precompute_aux

ROOT = Path(__file__).resolve().parent.parent


def _px(row: pd.Series) -> dict:
    return {k: float(v) for k, v in row.items() if pd.notna(v) and v > 0}


def _learn(signals, close, cfg, ds: str) -> dict:
    """Load weights; update at most once per trading day. Bootstraps walk-forward from history on first run."""
    prior = cfg["prior_weights"]
    ws = journal.load_json("weights.json")
    L = cfg["learning"]
    if ws is None:
        dates = list(close.index[300:])
        wmap = walk_forward_weights(signals, close, prior, cfg, dates)
        w = wmap[dates[-1]]
        ws = {"asof": ds, "weights": w, "bootstrapped_from": str(dates[0].date())}
        journal.append("learning.jsonl", {"date": ds, "event": "bootstrap", "weights": w, "logged_at": journal.now_utc()})
    elif ws["asof"] != ds:
        h = L["primary_horizon_days"]
        ic = ic_table({k: v.tail(400) for k, v in signals.items()}, close.tail(400), h)
        st = signal_stats(ic, len(ic) - 1, h, L["ic_half_life_days"])
        new, why = update_weights(ws["weights"], prior, st, cfg)
        journal.append("learning.jsonl", {"date": ds, "event": "update", "old": ws["weights"], "new": new, "why": why, "logged_at": journal.now_utc()})
        ws = {**ws, "asof": ds, "weights": new}
    journal.save_json("weights.json", ws)
    return ws["weights"]


def _apply_overrides(targets: dict, held: dict, ds: str) -> tuple[dict, list]:
    """Claude's review may veto entries/adds or shrink sizes - never add names or increase risk."""
    ov = journal.load_json("overrides.json", {}) or {}
    if ov.get("date") != ds:
        return targets, []
    applied = []
    t = dict(targets)
    for sym, reason in (ov.get("vetoes") or {}).items():
        if sym in t and sym not in held:  # cannot veto an exit or a hold; only new entries
            t.pop(sym)
            applied.append({"symbol": sym, "action": "veto", "reason": reason})
    for sym, (mult, reason) in (ov.get("size_mult") or {}).items():
        if sym in t:
            m = max(0.0, min(1.0, float(mult)))
            t[sym] *= m
            applied.append({"symbol": sym, "action": f"size x{m}", "reason": reason})
    return t, applied


def _eval_close(close: pd.DataFrame) -> pd.DataFrame:
    """Universe closes plus any symbol an open prediction refers to (overlay names outside the universe)."""
    need = {p["symbol"] for p in journal.read("predictions.jsonl") if p["status"] == "open"} - set(close.columns)
    if not need:
        return close
    extra = fetch_panel(sorted(need), "1y", 6.0)["close"]
    return close.join(extra, how="left")


def _overlays_once_per_day(cfg: dict, ds: str, bench: str) -> dict:
    """Insider cluster buys + Quiver congress buys, logged as forward-graded predictions (no capital yet)."""
    prev = journal.load_json("overlays.json", {}) or {}
    if prev.get("date") == ds:
        return prev
    from . import alt
    from .data import live_prices

    out = {"date": ds, "insider_cluster": [], "congress_buy": None, "logged": 0}
    try:
        out["insider_cluster"] = alt.openinsider_cluster_buys()[:25]
    except Exception as e:  # noqa: BLE001 - optional source
        out["insider_error"] = type(e).__name__
    try:
        cb = alt.quiver_congress_buys()
        out["congress_buy"] = None if cb is None else [r for r in cb if r["net"] > 0][:25]
    except Exception as e:  # noqa: BLE001
        out["congress_error"] = type(e).__name__
    names = {r["ticker"] for r in out["insider_cluster"]} | {r["ticker"] for r in (out["congress_buy"] or [])}
    px = live_prices(sorted(names | {bench})) if names else {}
    out["logged"] += alt.log_overlay_predictions(out["insider_cluster"], "insider_cluster", px, px.get(bench), ds)
    out["logged"] += alt.log_overlay_predictions(out["congress_buy"] or [], "congress_buy", px, px.get(bench), ds)
    journal.save_json("overlays.json", out)
    return out


def run_cycle(execute: bool = True, force_rebalance: bool = False, max_age_hours: float = 0.2) -> dict:
    cfg = load_config()
    r = cfg["risk"]
    bench = cfg.get("benchmark", "SPY")
    panel = fetch_panel(list(cfg["universe"]), "10y", max_age_hours)
    close = panel["close"]
    date = close.index[-1]
    ds = str(date.date())
    try:
        mkt = market_status(bench)
    except Exception as e:  # noqa: BLE001
        mkt = {"is_open": False, "error": type(e).__name__}

    signals = compute_all(panel, cfg)
    aux = precompute_aux(panel, cfg)
    weights = _learn(signals, close, cfg, ds)

    prices = _px(close.loc[date])
    state = journal.load_json("portfolio.json")
    broker = PaperBroker(cfg["account"]["starting_cash"], cfg["costs"]["slippage_bps"], cfg["costs"]["commission_per_share"], state)
    if state is None:  # first run: remember the starting line for the shadow baselines
        broker.state.update({"created": ds, "last_mark": None, "start_prices": prices})
    prev_regime = broker.state.get("regime")
    prev_dd_state = broker.state.get("dd_state")
    yield_today = cfg["account"]["cash_yield_annual"] if broker.state.get("last_mark") not in (None, ds) else 0.0
    equity = broker.mark(prices, ds, yield_today)

    blocked = set(broker.state.get("blocked", {}))
    targets, diag = build_targets(date, panel, signals, weights, cfg, broker.peak_ratio(prices), broker.positions, blocked, aux)

    last_reb = broker.state.get("last_rebalance")
    pos_of = {d: i for i, d in enumerate(close.index)}
    days_since = (pos_of[date] - pos_of.get(pd.Timestamp(last_reb), -10**6)) if last_reb else 10**6
    due = force_rebalance or days_since >= r.get("rebalance_every_days", 5)
    stopped = diag.get("stopped", [])
    if not due:  # off-cycle: hold current book, only act on stops
        cur = broker.weights(prices)
        targets = {s: w for s, w in cur.items() if s not in stopped}
    targets, applied = _apply_overrides(targets, broker.positions, ds)

    cool_pos = min(pos_of[date] + r.get("stop_cooldown_days", 10), len(close.index) - 1)
    cooldown_until = str((date + pd.tseries.offsets.BDay(r.get("stop_cooldown_days", 10))).date()) if cool_pos == pos_of[date] else str(close.index[cool_pos].date())
    preview = copy.deepcopy(broker).rebalance(targets, prices, ds, r["rebalance_band_pct"], r["min_trade_value"], stopped, cooldown_until)

    executed = []
    if execute and mkt.get("is_open") and preview:
        executed = broker.rebalance(targets, prices, ds, r["rebalance_band_pct"], r["min_trade_value"], stopped, cooldown_until)
        if due:
            broker.state["last_rebalance"] = ds
        for f in executed:
            journal.append("trades.jsonl", {**f, "logged_at": journal.now_utc()})
    elif execute and due and not preview and mkt.get("is_open"):
        broker.state["last_rebalance"] = ds  # nothing to trade, but the rebalance happened

    broker.state["regime"] = diag.get("regime")
    broker.state["dd_state"] = diag.get("dd_state")
    equity = broker.equity(prices)
    journal.save_json("portfolio.json", broker.state)

    score = combine(signals, weights, date)
    n_pred = journal.record_predictions(ds, score, {k: v.loc[date] for k, v in signals.items()}, prices,
                                        prices.get(bench), cfg["learning"]["horizons_days"], list(broker.positions))
    overlays = _overlays_once_per_day(cfg, ds, bench)
    card = journal.evaluate_predictions(_eval_close(close), bench)

    gross = sum(p["qty"] * prices.get(s, p["last_price"]) for s, p in broker.positions.items()) / equity if equity else 0
    journal.append("equity.jsonl", {"date": ds, "logged_at": journal.now_utc(), "equity": round(equity, 2), "cash": round(broker.cash, 2),
                                    "gross": round(gross, 4), "bench_price": prices.get(bench), "market_open": mkt.get("is_open")})
    decision = {"date": ds, "logged_at": journal.now_utc(), "market": mkt, "due_rebalance": due, "weights": weights, "diag": diag,
                "overrides": applied, "preview": preview, "executed": executed, "predictions_logged": n_pred}
    journal.append("decisions.jsonl", decision)

    sp = broker.state.get("start_prices") or {}
    common = [k for k in sp if k in prices]
    baselines = {
        "spy_since_start": round(prices[bench] / sp[bench] - 1, 4) if bench in sp and bench in prices else None,
        "equal_weight_since_start": round(sum(prices[k] / sp[k] for k in common) / len(common) - 1, 4) if common else None,
    }
    summary = {
        "date": ds, "market": mkt, "equity": round(equity, 2), "cash": round(broker.cash, 2), "gross": round(gross, 4),
        "return_since_start": round(equity / cfg["account"]["starting_cash"] - 1, 4), "baselines": baselines,
        "started": broker.state.get("created"), "regime": diag.get("regime"),
        "dd_state": diag.get("dd_state"), "drawdown": diag.get("drawdown"), "due_rebalance": due, "weights": weights,
        "targets": diag.get("targets", {}), "top_scores": diag.get("top_scores"), "bottom_scores": diag.get("bottom_scores"),
        "stopped": stopped, "preview_orders": preview, "overlays": {k: overlays.get(k) for k in ("insider_cluster", "congress_buy", "logged")}, "executed": executed, "overrides": applied, "scorecard": card,
        "positions": {s: {"qty": p["qty"], "avg_cost": round(p["avg_cost"], 2), "last": round(prices.get(s, p["last_price"]), 2),
                          "pnl_pct": round(prices.get(s, p["last_price"]) / p["avg_cost"] - 1, 4), "since": p["entry_date"]}
                      for s, p in broker.positions.items()},
    }
    journal.save_json("latest.json", summary)
    from .report import write_daily_report  # local import keeps module graph flat

    write_daily_report(summary)

    events = []
    if executed:
        events.append("בוצעו פקודות: " + ", ".join(f"{f['side']} {f['qty']} {f['symbol']} @ {f['price']}" for f in executed))
    elif preview and not mkt.get("is_open"):
        events.append("פקודות ממתינות לפתיחת השוק: " + ", ".join(f"{f['side']} {f['qty']} {f['symbol']}" for f in preview))
    if stopped:
        events.append("סטופ-לוס הופעל: " + ", ".join(stopped))
    if prev_regime and prev_regime != diag.get("regime"):
        events.append(f"שינוי משטר שוק: {prev_regime} -> {diag.get('regime')}")
    if prev_dd_state and prev_dd_state != diag.get("dd_state"):
        events.append(f"מצב ירידה מהשיא: {prev_dd_state} -> {diag.get('dd_state')}")
    if events:
        body = "\n".join(events) + f"\nשווי תיק (נייר): ${equity:,.0f} ({summary['return_since_start']:+.2%})"
        summary["alert_channels"] = notify.send("AI Trader - פעולה בתיק הנייר", body, cfg, "high" if executed or stopped else "default")
    summary["events"] = events
    return summary
