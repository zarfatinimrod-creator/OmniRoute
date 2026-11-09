"""Live paper-trading cycle with the same timing as the time machine.

  * DECIDE after the close of session D (final bar): mark, learn, grade, build targets, apply Claude's
    veto/shrink overrides, store them as pending orders (like market-on-open orders placed overnight).
  * EXECUTE the pending orders at the OPEN price of the next session D+1, whenever the next run happens
    (morning, midday or even the next evening - the fill is always the official open, never later info).
  * MONITOR intraday: mark-to-market and alert on big moves; never trade intraday.

A shadow book executes the quant targets WITHOUT Claude's overrides, so the report shows whether the
LLM layer adds or removes value. Every step is idempotent: re-running the same day changes nothing.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from . import journal, notify
from .broker import PaperBroker
from .data import corporate_actions, earnings_on, fetch_panel, load_config, load_market, market_status, official_opens
from .learn import ic_table, signal_stats, update_weights, walk_forward_weights
from .signals import compute_all
from .strategy import build_targets, combine, precompute_aux

ROOT = Path(__file__).resolve().parent.parent
NY = ZoneInfo("America/New_York")


def _px(row: pd.Series) -> dict:
    return {k: float(v) for k, v in row.items() if pd.notna(v) and v > 0}


def _learn(signals, close, cfg, ds: str) -> dict:
    """Load weights; update at most once per decision date. Bootstraps walk-forward from history on first run."""
    prior = cfg["prior_weights"]
    ws = journal.load_json("weights.json")
    L = cfg["learning"]
    if ws is None:
        dates = list(close.index[300:])
        wmap = walk_forward_weights(signals, close, prior, cfg, dates, gate=(journal.load_json("placebo.json", {}) or {}).get("gate_z95"))
        w = wmap[dates[-1]]
        ws = {"asof": ds, "weights": w, "bootstrapped_from": str(dates[0].date())}
        journal.append("learning.jsonl", {"date": ds, "event": "bootstrap", "weights": w, "logged_at": journal.now_utc()})
    elif ws["asof"] != ds and _trading_days_between(close, ws["asof"], ds) >= L.get("update_every_days", 21):
        h = L["primary_horizon_days"]
        ic = ic_table(signals, close, h)
        st = signal_stats(ic, len(ic) - 1, h, L["ic_half_life_days"])
        gate = (journal.load_json("placebo.json", {}) or {}).get("gate_z95")
        new, why = update_weights(ws["weights"], prior, st, cfg, gate)
        journal.append("learning.jsonl", {"date": ds, "event": "update", "old": ws["weights"], "new": new, "why": why, "logged_at": journal.now_utc()})
        ws = {**ws, "asof": ds, "weights": new}
    journal.save_json("weights.json", ws)
    return ws["weights"]


def _trading_days_between(close: pd.DataFrame, a: str, b: str) -> int:
    idx = close.index
    return int(idx.searchsorted(pd.Timestamp(b)) - idx.searchsorted(pd.Timestamp(a)))


def _open_cutoff_utc(day) -> str:
    """09:30 New York on `day`, as a UTC ISO string (overrides logged after it must not touch that open)."""
    d = pd.Timestamp(day).date()
    return datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY).astimezone(ZoneInfo("UTC")).replace(microsecond=0).isoformat()


def _check_reduce_only(raw: dict, final: dict) -> None:
    """Hard invariant (fail loud): Claude can only remove names or shrink weights, never add or enlarge."""
    extra = set(final) - set(raw)
    bigger = {s: (raw[s], final[s]) for s in final if s in raw and final[s] > raw[s] + 1e-12}
    if extra or bigger:
        raise RuntimeError(f"override invariant violated: added={sorted(extra)} enlarged={bigger}")


def _apply_overrides(targets: dict, held: dict, ds: str, cutoff_utc: str | None = None) -> tuple[dict, list]:
    """Claude's review may veto new entries or shrink sizes - never add names or increase risk.
    Entries logged after `cutoff_utc` (the open they would affect) are ignored: no look-ahead."""
    ov = journal.load_json("overrides.json", {}) or {}
    if ov.get("date") != ds:
        return dict(targets), []

    def ok(ts):
        return cutoff_utc is None or not ts or ts <= cutoff_utc

    applied = []
    t = dict(targets)
    for sym, v in (ov.get("vetoes") or {}).items():
        reason, ts = (v.get("reason"), v.get("logged_at")) if isinstance(v, dict) else (v, None)
        if sym in t and sym not in held and ok(ts):  # only new entries; exits and holds are the code's call
            t.pop(sym)
            applied.append({"symbol": sym, "action": "veto", "reason": reason, "logged_at": ts})
    for sym, v in (ov.get("size_mult") or {}).items():
        mult, reason = v[0], v[1]
        ts = v[2] if len(v) > 2 else None
        if sym in t and ok(ts):
            m = max(0.0, min(1.0, float(mult)))
            t[sym] *= m
            applied.append({"symbol": sym, "action": f"size x{m}", "reason": reason, "logged_at": ts})
    _check_reduce_only(targets, t)
    return t, applied


def _eval_close(close: pd.DataFrame) -> pd.DataFrame:
    """Universe closes plus any symbol an open prediction refers to (overlay names outside the universe)."""
    need = {p["symbol"] for p in journal.open_predictions()} - set(close.columns)
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


def _earnings_blackout(ds: str, days: int) -> dict[str, str]:
    """Symbols reporting from the decision day through the next `days` calendar days, plus the day before
    (no entries from ~2 sessions before earnings to 1 session after). Cached per decision date."""
    cache = journal.load_json("earnings.json", {}) or {}
    if cache.get("date") == ds:
        return cache["blackout"]
    d0 = datetime.strptime(ds, "%Y-%m-%d").date()
    out: dict[str, str] = {}
    unknown = []
    for k in range(-1, days + 1):
        day = (d0 + timedelta(days=k)).isoformat()
        got = earnings_on(day)
        if got is None:
            unknown.append(day)
            continue
        for sym, when in got.items():
            out.setdefault(sym, f"{day} {when}")
    if unknown:  # never cache a partial calendar; the next run retries. Fail closed for NEW entries.
        print(f"[earnings] calendar unavailable for {unknown}; new stock entries blocked this decision")
        out["*"] = "calendar unavailable: " + ",".join(unknown)
    else:
        journal.save_json("earnings.json", {"date": ds, "blackout": out})
    return out


def _bar_is_final(d: pd.Timestamp) -> bool:
    now = datetime.now(NY)
    return d.date() < now.date() or (d.date() == now.date() and (now.hour, now.minute) >= (16, 5))


def _brokers(cfg: dict, prices: dict, ds: str) -> tuple[PaperBroker, PaperBroker]:
    c = cfg["costs"]
    main_state = journal.load_json("portfolio.json")
    main = PaperBroker(cfg["account"]["starting_cash"], c["slippage_bps"], c["commission_per_share"], main_state)
    if main_state is None:  # first run: remember the starting line for the baselines
        main.state.update({"created": ds, "last_mark": None, "start_prices": prices})
    shadow = PaperBroker(cfg["account"]["starting_cash"], c["slippage_bps"], c["commission_per_share"], journal.load_json("shadow_portfolio.json"))
    return main, shadow


def _market_opened(d: pd.Timestamp) -> bool:
    now = datetime.now(NY)
    return d.date() < now.date() or (d.date() == now.date() and (now.hour, now.minute) >= (9, 31))


def _execute_pending(panel, cfg, main, shadow, events) -> list[dict]:
    """Fill pending targets at the official open of the first session after the decision date."""
    r = cfg["risk"]
    close = panel["close"]
    pending = journal.load_json("pending.json")
    if not pending or pending.get("status") != "pending":
        return []
    later = close.index[close.index > pd.Timestamp(pending["decision_date"])]
    if not len(later) or not _market_opened(later[0]):
        return []
    d_exec = later[0]
    # Overrides logged before THIS open count (reduce-only); recomputed from the raw targets so a shrink is
    # never applied twice. Anything logged after 09:30 on the fill day is ignored (it saw the open).
    if not pending.get("exits_only"):
        pending["targets"], pending["overrides"] = _apply_overrides(pending["targets_raw"], main.positions, pending["decision_date"], _open_cutoff_utc(d_exec))
    names = set(pending["targets"]) | set(pending["targets_raw"]) | set(main.positions) | set(shadow.positions)
    real = official_opens(sorted(names), d_exec)  # 09:30 1-minute bar: the true opening trade
    opx = {**_px(close.loc[d_exec]), **_px(panel["open"].loc[d_exec]), **real}  # 1m open > daily open > close
    pending["open_source"] = {"one_minute": sorted(real), "daily_fallback": sorted(n for n in names if n not in real)}
    ds_exec = str(d_exec.date())
    cool = str((d_exec + pd.offsets.BDay(r.get("stop_cooldown_days", 10))).date())
    xo = pending.get("exits_only", False)
    forced = {o["symbol"] for o in pending.get("overrides", []) if o["action"].startswith("size")}
    fills = main.rebalance(pending["targets"], opx, ds_exec, r["rebalance_band_pct"], r["min_trade_value"], pending.get("stopped", []), cool, xo, forced)
    stp = set(pending.get("stopped_shadow", pending.get("stopped", [])))
    sh_targets = pending["targets_raw"] if not xo else {s_: w for s_, w in pending.get("shadow_hold", {}).items() if s_ not in stp}
    shadow.rebalance(sh_targets, opx, ds_exec, r["rebalance_band_pct"], r["min_trade_value"], list(stp), cool, xo)
    if pending.get("rebalance"):
        main.state["last_rebalance"] = shadow.state["last_rebalance"] = pending["decision_date"]
    # crash safety: books first, then the trade log, then mark the decision executed
    journal.save_json("portfolio.json", main.state)
    journal.save_json("shadow_portfolio.json", shadow.state)
    for f in fills:
        journal.append("trades.jsonl", {**f, "decision_date": pending["decision_date"], "fill": "open", "logged_at": journal.now_utc()})
    pending.update({"status": "executed", "executed_on": ds_exec, "fills": fills})
    journal.save_json("pending.json", pending)
    if fills:
        events.append(f"בוצע בפתיחה {ds_exec}: " + ", ".join(f"{f['side']} {f['qty']} {f['symbol']} @ {f['price']}" for f in fills))
    return fills


def _decide(panel, cfg, main, shadow, dec: pd.Timestamp, force_rebalance: bool, persist: bool, events) -> dict:
    """Targets for decision bar `dec` (data up to its close only). persist=False = proposal, no state change."""
    r = cfg["risk"]
    bench = cfg.get("benchmark", "SPY")
    panel = {k: (v.loc[:dec] if hasattr(v, "loc") else v) for k, v in panel.items()}  # nothing after the decision bar's close
    close = panel["close"]
    ds = str(dec.date())
    px = _px(close.loc[dec])
    signals = compute_all(panel, cfg)
    aux = precompute_aux(panel, cfg)
    if persist:
        weights = _learn(signals, close, cfg, ds)
    else:
        weights = (journal.load_json("weights.json") or {}).get("weights") or cfg["prior_weights"]
    m = main if persist else copy.deepcopy(main)
    prev_regime, prev_dd = m.state.get("regime"), m.state.get("dd_state")
    y = cfg["account"]["cash_yield_annual"]
    m.maybe_reset_peak(prev_regime or "", ds, r.get("dd_reentry_days", 20), r["dd_halve"], r["dd_flat"])  # m is a copy when proposing
    if persist:
        m.mark(px, ds, y if m.state.get("last_mark") not in (None, ds) else 0.0)
        shadow.mark(px, ds, y if shadow.state.get("last_mark") not in (None, ds) else 0.0)
    blocked = set(m.state.get("blocked", {}))
    targets_raw, diag = build_targets(dec, panel, signals, weights, cfg, m.peak_ratio(px), m.positions, blocked, aux)
    last_reb = m.state.get("last_rebalance")
    days_since = (close.index.get_loc(dec) - close.index.get_loc(pd.Timestamp(last_reb))) if last_reb and pd.Timestamp(last_reb) in close.index else 10**6
    risk_changed = (prev_regime is not None and prev_regime != diag.get("regime")) or (prev_dd is not None and prev_dd != diag.get("dd_state"))
    due = force_rebalance or days_since >= r.get("rebalance_every_days", 5) or risk_changed or diag.get("dd_state") == "flat"
    stopped = diag.get("stopped", [])
    exits_only = not due
    if exits_only:  # off-cycle: hold the book, act only on stops (exits), never re-trade overnight gaps
        targets_raw = {s: w for s, w in m.weights(px).items() if s not in stopped}
    bo = _earnings_blackout(ds, r.get("earnings_blackout_days", 4))
    from .strategy import ETF_SECTORS
    skipped = {s: bo.get(s, bo.get("*")) for s in list(targets_raw)
               if s not in m.positions and (s in bo or ("*" in bo and cfg["universe"].get(s) not in ETF_SECTORS))}
    for s in skipped:
        targets_raw.pop(s)
    cap = r.get("earnings_max_position_pct", 1.0)
    for s in list(targets_raw):  # held through a report: cap the size (ATR stops cannot protect an earnings gap)
        if s in bo and s in m.positions and cfg["universe"].get(s) not in ETF_SECTORS and targets_raw[s] > cap:
            targets_raw[s] = cap
    _, sdiag = build_targets(dec, panel, signals, weights, cfg, shadow.peak_ratio(px), shadow.positions, set(shadow.state.get("blocked", {})), aux)
    targets, applied = _apply_overrides(targets_raw, m.positions, ds, _open_cutoff_utc(dec + pd.offsets.BDay(1)))
    preview = copy.deepcopy(m).rebalance(targets, px, ds, r["rebalance_band_pct"], r["min_trade_value"], stopped, None, exits_only)
    new_entries = [f["symbol"] for f in preview if f["side"] == "BUY" and f["symbol"] not in m.positions]
    decision = {"decision_date": ds, "status": "pending", "rebalance": due, "exits_only": exits_only, "targets": targets, "targets_raw": targets_raw,
                "stopped_shadow": sdiag.get("stopped", []), "shadow_hold": shadow.weights(px),
                "stopped": stopped, "overrides": applied, "earnings_blackout": skipped, "preview_at_close": preview,
                "new_entries": new_entries, "diag": diag, "weights": weights, "logged_at": journal.now_utc()}
    if not persist:
        journal.save_json("proposal.json", decision)
        return decision
    journal.save_json("pending.json", {k: v for k, v in decision.items() if k not in ("diag", "weights")})
    m.state["regime"], m.state["dd_state"] = diag.get("regime"), diag.get("dd_state")
    journal.append("decisions.jsonl", {"date": ds, "logged_at": journal.now_utc(), "due_rebalance": due, "weights": weights, "diag": diag,
                                       "overrides": applied, "earnings_blackout": skipped, "preview": preview})
    score = combine(signals, weights, dec)
    journal.record_predictions(ds, score, {k: v.loc[dec] for k, v in signals.items()}, px, px.get(bench),
                               cfg["learning"]["horizons_days"], list(m.positions))
    _overlays_once_per_day(cfg, ds, bench)
    if preview:
        events.append("מתוכנן לפתיחה הבאה: " + ", ".join(f"{f['side']} {f['qty']} {f['symbol']}" for f in preview))
    if stopped:
        events.append("סטופ-לוס (יבוצע בפתיחה): " + ", ".join(stopped))
    if prev_regime and prev_regime != diag.get("regime"):
        events.append(f"שינוי משטר שוק: {prev_regime} -> {diag.get('regime')}")
    if prev_dd and prev_dd != diag.get("dd_state"):
        events.append(f"מצב ירידה מהשיא: {prev_dd} -> {diag.get('dd_state')}")
    return decision


def run_cycle(execute: bool = True, force_rebalance: bool = False, max_age_hours: float = 0.1, propose: bool = False) -> dict:
    cfg = load_config()
    bench = cfg.get("benchmark", "SPY")
    panel = load_market(cfg, "10y", max_age_hours)
    close = panel["close"]
    last = close.index[-1]
    dec_bar = last if _bar_is_final(last) else (close.index[-2] if len(close) > 1 else last)
    try:
        mkt = market_status(bench)
    except Exception as e:  # noqa: BLE001
        mkt = {"is_open": False, "error": type(e).__name__}
    events: list[str] = []
    prices_last = _px(close.loc[last])
    main, shadow = _brokers(cfg, _px(close.loc[dec_bar]), str(dec_bar.date()))
    # Splits/dividends through the latest bar are applied BEFORE any fill: the feed is already adjusted, so a
    # fill on a split day must see the post-split share count. Idempotent (tracked per position).
    acts = {sym: corporate_actions(sym) for sym in set(main.positions) | set(shadow.positions)}
    w_hold = cfg["account"].get("dividend_withholding", 0.25)
    ca_notes = main.apply_corporate_actions(acts, str(last.date()), w_hold)
    shadow.apply_corporate_actions(acts, str(last.date()), w_hold)
    if propose:  # what the next decision would be, for the trading desk; changes no state
        return _decide(panel, cfg, main, shadow, dec_bar, force_rebalance, False, events)

    executed: list[dict] = []
    diag: dict = {}
    decided_now = False
    events.extend(ca_notes)
    if execute:
        executed += _execute_pending(panel, cfg, main, shadow, events)
        if (journal.load_json("pending.json") or {}).get("decision_date") != str(dec_bar.date()):
            diag = _decide(panel, cfg, main, shadow, dec_bar, force_rebalance, True, events).get("diag", {})
            decided_now = True
            executed += _execute_pending(panel, cfg, main, shadow, events)  # a missed morning: fill at that open now
    weights = (journal.load_json("weights.json") or {}).get("weights", cfg["prior_weights"])
    ds = str(last.date())

    journal.save_json("portfolio.json", main.state)
    journal.save_json("shadow_portfolio.json", shadow.state)
    card = journal.evaluate_predictions(_eval_close(close.loc[:dec_bar]), bench)  # final bars only

    equity = main.equity(prices_last)
    sh_eq = shadow.equity(prices_last)
    gross = sum(p["qty"] * prices_last.get(s, p["last_price"]) for s, p in main.positions.items()) / equity if equity else 0
    journal.append("equity.jsonl", {"date": ds, "logged_at": journal.now_utc(), "equity": round(equity, 2), "shadow_equity": round(sh_eq, 2),
                                    "cash": round(main.cash, 2), "gross": round(gross, 4), "bench_price": prices_last.get(bench),
                                    "market_open": mkt.get("is_open"), "decided": decided_now})
    sp = main.state.get("start_prices") or {}
    common = [k for k in sp if k in prices_last]
    pend = journal.load_json("pending.json") or {}
    summary = {
        "date": ds, "as_of_utc": journal.now_utc(), "market": mkt, "equity": round(equity, 2), "cash": round(main.cash, 2),
        "gross": round(gross, 4), "return_since_start": round(equity / cfg["account"]["starting_cash"] - 1, 4),
        "shadow_return_since_start": round(sh_eq / cfg["account"]["starting_cash"] - 1, 4),
        "baselines": {
            "spy_since_start": round(prices_last[bench] / sp[bench] - 1, 4) if bench in sp and bench in prices_last else None,
            "equal_weight_since_start": round(sum(prices_last[k] / sp[k] for k in common) / len(common) - 1, 4) if common else None,
        },
        "started": main.state.get("created"), "regime": main.state.get("regime"), "dd_state": main.state.get("dd_state"),
        "drawdown": round(main.peak_ratio(prices_last) - 1, 4), "decided_now": decided_now, "weights": weights,
        "pending": {k: pend.get(k) for k in ("decision_date", "status", "rebalance", "targets", "overrides", "earnings_blackout", "preview_at_close")},
        "executed": executed, "top_scores": diag.get("top_scores"), "bottom_scores": diag.get("bottom_scores"),
        "stopped": diag.get("stopped", []), "scorecard": card,
        "overlays": {k: (journal.load_json("overlays.json", {}) or {}).get(k) for k in ("insider_cluster", "congress_buy", "logged")},
        "positions": {s: {"qty": p["qty"], "avg_cost": round(p["avg_cost"], 2), "last": round(prices_last.get(s, p["last_price"]), 2),
                          "pnl_pct": round(prices_last.get(s, p["last_price"]) / p["avg_cost"] - 1, 4), "since": p["entry_date"]}
                      for s, p in main.positions.items()},
    }
    # intraday watch: alert on a big adverse move in a holding (no trading)
    if mkt.get("is_open"):
        movers = {s: v["pnl_pct"] for s, v in summary["positions"].items()}
        prev_close = _px(close.iloc[-2]) if len(close) > 1 else {}
        day_moves = {s: prices_last[s] / prev_close[s] - 1 for s in main.positions if s in prices_last and s in prev_close}
        big = {s: m for s, m in day_moves.items() if m <= -0.06}
        if big:
            events.append("ירידה חדה היום: " + ", ".join(f"{s} {m:+.1%}" for s, m in big.items()) + " (הסטופ ייבדק בסגירה)")
        summary["day_moves"] = {s: round(m, 4) for s, m in day_moves.items()}
        del movers
    journal.save_json("latest.json", summary)
    from .report import write_daily_report  # local import keeps the module graph flat

    write_daily_report(summary)
    if events:
        body = "\n".join(events) + f"\nשווי תיק (נייר): ${equity:,.0f} ({summary['return_since_start']:+.2%}) | בלי Claude: {summary['shadow_return_since_start']:+.2%}"
        summary["alert_channels"] = notify.send("AI Trader - תיק נייר", body, cfg, "high" if executed or diag.get("stopped") else "default")
    summary["events"] = events
    journal.save_json("latest.json", summary)
    return summary
