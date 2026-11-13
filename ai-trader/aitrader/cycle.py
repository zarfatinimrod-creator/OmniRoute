"""Live paper-trading cycle with the same timing as the time machine.

  * DECIDE after the close of session D (final bar): mark, learn, grade, build targets, apply Claude's
    veto/shrink overrides, store them as pending orders (like market-on-open orders placed overnight).
  * EXECUTE the pending orders at the OPEN price of the next session D+1, whenever the next run happens
    (morning, midday or even the next evening - the fill is always the official open, never later info).
  * MONITOR intraday: mark-to-market and alert on big moves; never trade intraday.
  * CRYPTO (market.calendar "utc_daily", market.UtcDailyCalendar): decide after the 00:00 UTC close, execute at exec_ts
    (the first full hour after the decision is logged, never before D+1 01:00 UTC) at the 1h/1m bar open, all coins
    or none; one equity mark per decision bar. The NYSE functions below serve the stock book only.

A shadow book executes the quant targets WITHOUT Claude's overrides, so the report shows whether the
LLM layer adds or removes value. Every step is idempotent: re-running the same day changes nothing.
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from . import data, journal, notify
from .broker import PaperBroker
from .data import (Unreachable, apply_close_source, coinbase_close, corporate_actions, earnings_on, fetch_panel, load_config,
                   load_market, market_status, official_opens, stale_symbols)
from .learn import ic_table, signal_stats, update_weights, walk_forward_weights
from .market import UtcDailyCalendar
from .signals import compute_all
from .strategy import build_targets, combine, etf_groups, periods_per_year, precompute_aux

ROOT = Path(__file__).resolve().parent.parent
NY = ZoneInfo("America/New_York")


def _px(row: pd.Series) -> dict:
    return {k: float(v) for k, v in row.items() if pd.notna(v) and v > 0}


def _learn(signals, close, cfg, ds: str) -> dict:
    """Load weights; update at most once per decision date. Bootstraps walk-forward from history on first run."""
    prior = cfg["prior_weights"]
    L = cfg["learning"]
    if not L.get("enabled", True):
        return dict(prior)
    ws = journal.load_json("weights.json")
    if ws is None:
        dates = list(close.index[300:])
        wmap = walk_forward_weights(signals, close, prior, cfg, dates, gate=(journal.load_json("placebo.json", {}) or {}).get("gate_z95"))
        w = wmap[dates[-1]]
        ws = {"asof": ds, "weights": w, "bootstrapped_from": str(dates[0].date())}
        journal.append("learning.jsonl", {"date": ds, "event": "bootstrap", "weights": w, "logged_at": journal.now_utc()})
    elif ws["asof"] != ds and _trading_days_between(close, ws["asof"], ds) >= L.get("update_every_days", 21):
        h = L["primary_horizon_days"]
        ic = ic_table(signals, close, h, L.get("ic_min_names", 10))
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


def _eval_close(close: pd.DataFrame, preds_name: str = "predictions.jsonl", grades_name: str = "grades.jsonl") -> pd.DataFrame:
    """Universe closes plus any symbol an open prediction refers to (overlay names outside the universe)."""
    need = {p["symbol"] for p in journal.open_predictions(preds_name, grades_name)} - set(close.columns)
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
    """The clock half of the bar-final rule (16:05 New York); the fetch-time half is data.stale_symbols."""
    now = datetime.now(NY)
    return d.date() < now.date() or (d.date() == now.date() and (now.hour, now.minute) >= (16, 5))


def _bar_end_utc(d, cfg: dict) -> datetime:
    """When bar d counts as final if fetched after it: stocks 16:00 New York + 5 min, also on early-close days (the
    clock of _bar_is_final); a utc_daily bar at the next 00:00 UTC + 5 min."""
    d = pd.Timestamp(d)
    if cfg.get("market", {}).get("calendar") == "utc_daily":
        return UtcDailyCalendar.bar_end(d) + UtcDailyCalendar.FINAL_AFTER
    return datetime(d.year, d.month, d.day, 16, 5, tzinfo=NY).astimezone(timezone.utc)


def _utc_now() -> datetime:
    """The crypto clock is journal.now_utc(): logged_at, exec_ts, bar-final and fills all read one clock, so a frozen
    journal clock freezes the whole UTC path. The stock path keeps datetime.now in _bar_is_final/_market_opened."""
    return datetime.fromisoformat(journal.now_utc())


def _hold_frozen(targets: dict, cur: dict, frozen: set, max_gross: float) -> dict:
    """Planning decision 10: a frozen (stale or absent) held name keeps its current weight; the other targets shrink
    pro rata only if the book would pass max_gross."""
    hold = {s: cur[s] for s in sorted(frozen) if s in cur}
    if not hold:
        return targets
    rest = {s: w for s, w in targets.items() if s not in frozen}
    room, tot = max(0.0, max_gross - sum(hold.values())), sum(rest.values())
    k = min(1.0, room / tot) if tot > 0 else 1.0
    return {**{s: w * k for s, w in rest.items()}, **hold}


def _frozen_runs(held_frozen: set, ds: str) -> dict[str, int]:
    """Consecutive decisions on which each held symbol was frozen (final review item 4), in frozen_runs.json. A decision
    without one resets it. Written only when something is counted or a count was just cleared, so a book that never
    freezes never writes the file; a second call for the same decision date counts nothing."""
    prev = journal.load_json("frozen_runs.json", {}) or {}
    old = prev.get("runs", {})
    if prev.get("date") == ds:
        return old
    runs = {s: old.get(s, 0) + 1 for s in sorted(held_frozen)}
    if runs or old:
        journal.save_json("frozen_runs.json", {"date": ds, "runs": runs})
    return runs


def _coinbase_guard(close: pd.DataFrame, dec: pd.Timestamp, cfg: dict) -> dict | None:
    """Planning decision 11: the decision close of each universe symbol against Coinbase's public daily candle.
    None when market.coinbase_guard_pct is 0 (stocks). status: breach (a gap above the limit) > unreachable > ok."""
    pct = cfg.get("market", {}).get("coinbase_guard_pct", 0)
    if not pct:
        return None
    gaps, down = {}, []
    for s in sorted(cfg["universe"]):
        cb = coinbase_close(s, dec)
        if cb is None:
            down.append(s)
        else:
            gaps[s] = float(close.at[dec, s]) / cb - 1
    breach = sorted(s for s, g in gaps.items() if abs(g) > pct)
    return {"status": "breach" if breach else "unreachable" if down else "ok", "pct": pct, "gaps": gaps,
            "breach": breach, "unreachable": down}


def _brokers(cfg: dict, prices: dict, ds: str) -> tuple[PaperBroker, PaperBroker]:
    c = cfg["costs"]
    main_state = journal.load_json("portfolio.json")
    main = PaperBroker(cfg["account"]["starting_cash"], c["slippage_bps"], c["commission_per_share"], main_state, c.get("qty_step", 1), c.get("fee_bps", 0.0))
    if main_state is None:  # first run: remember the starting line for the baselines
        main.state.update({"created": ds, "last_mark": None, "start_prices": prices})
    shadow = PaperBroker(cfg["account"]["starting_cash"], c["slippage_bps"], c["commission_per_share"], journal.load_json("shadow_portfolio.json"), c.get("qty_step", 1), c.get("fee_bps", 0.0))
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
    fills = _fill_books(pending, opx, ds_exec, cool, cfg, main, shadow)
    if fills:
        events.append(f"בוצע בפתיחה {ds_exec}: " + ", ".join(f"{f['side']} {f['qty']} {f['symbol']} @ {f['price']}" for f in fills))
    return fills


def _fill_books(pending: dict, opx: dict, ds_exec: str, cool: str, cfg: dict, main, shadow, extra: dict | None = None) -> list[dict]:
    """Fill a pending decision at prices opx in the main and the shadow book and persist it. extra: keys added to each
    trade record and to pending (crypto: fill_source, fill_ts). A Coinbase breach (ruling R9a) fills the main book
    exits-only; the shadow book keeps the quant targets."""
    r = cfg["risk"]
    xo = pending.get("exits_only", False)
    forced = {o["symbol"] for o in pending.get("overrides", []) if o["action"].startswith("size")}
    frz = set(pending.get("frozen", []))  # decided on stale data: never traded by this decision
    fills = main.rebalance(pending["targets"], opx, ds_exec, r["rebalance_band_pct"], r["min_trade_value"], pending.get("stopped", []), cool,
                           xo or pending.get("coinbase_breach", False), forced, frz)
    stp = set(pending.get("stopped_shadow", pending.get("stopped", [])))
    sh_targets = pending["targets_raw"] if not xo else {s_: w for s_, w in pending.get("shadow_hold", {}).items() if s_ not in stp}
    shadow.rebalance(sh_targets, opx, ds_exec, r["rebalance_band_pct"], r["min_trade_value"], list(stp), cool, xo, frozen=frz)
    if pending.get("rebalance"):
        main.state["last_rebalance"] = shadow.state["last_rebalance"] = pending["decision_date"]
    # crash safety: books first, then the trade log, then mark the decision executed
    journal.save_json("portfolio.json", main.state)
    journal.save_json("shadow_portfolio.json", shadow.state)
    for f in fills:
        journal.append("trades.jsonl", {**f, "decision_date": pending["decision_date"], "fill": "open", **(extra or {}), "logged_at": journal.now_utc()})
    pending.update({"status": "executed", "executed_on": ds_exec, "fills": fills, **(extra or {})})
    journal.save_json("pending.json", pending)
    return fills


def _execute_pending_utc(cfg: dict, main, shadow, events, now: datetime) -> list[dict]:
    """Crypto fill (planning decision 12): all coins or none, at the open of the first hour from exec_ts on (up to now,
    and less than market.fill_max_wait_hours after exec_ts) where every coin has its 1h bar, else its 1m bar
    (UtcDailyCalendar.fill_prices). Nothing priced: the order stays pending and a later run retries; past the cap it
    waits for the next decision to expire it (its stops are then carried, see _decide). An unreachable Yahoo ends the
    walk (never skip ahead over hours that were not answered). Never the daily open (the price the signal saw).
    Overrides count only up to exec_ts, also when the fill slips to a later hour. The panel is not read, so a dropped
    decision bar (next_open without a D+1 row) cannot break a fill (ruling R9c)."""
    pending = journal.load_json("pending.json")
    if not pending or pending.get("status") != "pending":
        return []
    exec_ts = pending["exec_ts"]
    hour = datetime.fromisoformat(exec_ts)
    if now < hour:
        return []
    if not pending.get("exits_only"):
        pending["targets"], pending["overrides"] = _apply_overrides(pending["targets_raw"], main.positions, pending["decision_date"], exec_ts)
    names = set(pending["targets"]) | set(pending["targets_raw"]) | set(main.positions) | set(shadow.positions)
    max_h = cfg["market"]["fill_max_wait_hours"]
    cap = datetime.fromisoformat(exec_ts) + timedelta(hours=max_h)
    got = None
    try:  # ponytail: a fill_prices probe per started hour from exec_ts, at most max_h (each asks 1h then 1m per coin)
        while got is None and hour <= now and hour < cap:
            got = UtcDailyCalendar.fill_prices(names, hour.isoformat())
            hour = hour if got else hour + timedelta(hours=1)
    except Unreachable:
        events.append(f"Yahoo לא זמין (1h/1m) ב-{hour.isoformat()}: הזמנות {pending['decision_date']} ממתינות - ריצה מאוחרת תנסה שוב")
        return []
    if got is None:
        late = f" - עבר חלון ההמתנה ({max_h} שעות): לא יבוצעו, ההחלטה הבאה תחליף אותן" if now >= cap else " - ריצה מאוחרת תנסה שוב"
        events.append(f"הזמנות {pending['decision_date']} ממתינות: אין מחיר פתיחה (1h/1m) לכל המטבעות מאז {exec_ts}{late}")
        return []
    opx, src = got
    ds_exec = str(hour.date())
    cool = UtcDailyCalendar.cooldown_until(ds_exec, cfg["risk"].get("stop_cooldown_days", 10))
    fills = _fill_books(pending, opx, ds_exec, cool, cfg, main, shadow, {"fill_source": src, "fill_ts": hour.isoformat()})
    if fills:
        events.append(f"בוצע ב-{hour.isoformat()} ({src}): " + ", ".join(f"{f['side']} {f['qty']} {f['symbol']} @ {f['price']}" for f in fills))
    return fills


OHLCV = ("open", "high", "low", "close", "volume")


def _price(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0


def _day_hours(day) -> range:
    """Start stamps (epoch seconds) of the 1h bars of the UTC day `day`: 24 by definition, not a setting."""
    start, end = UtcDailyCalendar.session_window(day)
    return range(int(start.timestamp()), int(end.timestamp()), data.INTRADAY_SECONDS["1h"])


def hourly_day_bars(sym: str, day) -> dict | None:
    """Backlog 70: the UTC day `day` of `sym` folded from Yahoo's 1h bars into one daily row: first open, highest high,
    lowest low, last close, summed volume (a null volume counts 0). One chart call, period1 = day 00:00 UTC, period2 =
    the next 00:00 UTC (as data.intraday_open asks). Only the rows stamped inside the day count (Yahoo also sends the
    next day's 00:00 row, all null, seen 2026-11-13), and they must be exactly the hours 00:00..23:00, each with a
    finite, positive open/high/low/close. Anything else - a missing, null, extra or misaligned hour, a failed fetch
    (RuntimeError, data.Unreachable) or a reply of another shape - is None: no rebuild."""
    want = _day_hours(day)
    t0, t1 = want.start, want.stop
    try:
        got = data._get_json(data.CHART_URL.format(sym=sym), {"period1": t0, "period2": t1, "interval": "1h"})
        res = got["chart"]["result"][0]
        q = res["indicators"]["quote"][0]
        rows: dict[int, list] = {}
        for i, t in enumerate(res.get("timestamp") or []):
            if t0 <= t < t1:
                if t != int(t) or int(t) in rows:  # a fractional or repeated stamp
                    return None
                rows[int(t)] = [q[f][i] for f in OHLCV]
    except Exception:  # noqa: BLE001 - any failure is "no rebuild"; the backlog 68 rule then makes no decision
        return None
    if sorted(rows) != list(want):
        return None
    hours = [rows[t] for t in sorted(rows)]
    if not all(_price(v) for h in hours for v in h[:4]):
        return None
    return {"open": float(hours[0][0]), "high": float(max(h[1] for h in hours)), "low": float(min(h[2] for h in hours)),
            "close": float(hours[-1][3]),
            "volume": float(sum(h[4] for h in hours if isinstance(h[4], (int, float)) and math.isfinite(h[4])))}


def _rebuild_from_hourly(panel: dict, day, symbols, events: list) -> dict:
    """Backlog 70 (utc_daily only): Yahoo's daily reply can lack the row of the UTC day that just closed for hours (its
    prices null, dropped by data._bars_from_chart; 2026-11-12 and 2026-11-13). When the final bar `day` has no prices at
    all for some of `symbols` (universe + benchmark) and the daily reply was fetched after that bar ended, each such
    symbol's day is built from Yahoo's 1h bars (hourly_day_bars). All or none: one symbol without 24 complete hours
    leaves the panel as fetched, and the backlog 68 rule makes no decision. A coin absent from the reply, a daily row
    with some prices but no close, or a reply fetched before the bar ended is never rebuilt (the stale rule handles
    them), so a bar never mixes daily and hourly values and a Yahoo value is never overwritten. Frames are copied, never
    changed in place; out["_hourly_rebuild"] logs the rows (the decision record and pending.json carry it; R6 compares
    the decision close with Yahoo's daily close once that row arrives)."""
    close = panel["close"]
    d = pd.Timestamp(day)
    need = sorted(s for s in symbols if d not in close.index or s not in close.columns or pd.isna(close.at[d, s]))
    if not need or any(s not in close.columns for s in need):
        return panel
    if any(d in panel[f].index and pd.notna(panel[f].at[d, s]) for f in OHLCV[:4] for s in need):
        return panel
    fetched, end = panel.get("_fetched_at") or {}, UtcDailyCalendar.bar_end(d) + UtcDailyCalendar.FINAL_AFTER
    if any(fetched.get(s) is not None and fetched[s] < end for s in need):
        return panel
    rows = {}
    for s in need:
        rows[s] = hourly_day_bars(s, d)
        if rows[s] is None:
            return panel
    out = dict(panel)
    for f in OHLCV:
        ix = panel[f].index
        fr = panel[f].copy() if d in ix else panel[f].reindex(ix.append(pd.DatetimeIndex([d])).sort_values())
        for s in need:
            if pd.isna(fr.at[d, s]):
                fr.at[d, s] = rows[s][f]
        out[f] = fr
    n = len(_day_hours(d))
    out["_hourly_rebuild"] = {"bar": str(d.date()), "source": "yahoo_1h", "hours": n, "inserted": d not in close.index,
                              "symbols": rows}
    events.append(f"השורה היומית של {d.date()} ב-Yahoo ריקה - היום נבנה מ-{n} נרות שעתיים של Yahoo (close "
                  + ", ".join(f"{s} {rows[s]['close']:,.2f}" for s in need) + ")")
    return out


def _without_rebuild(close: pd.DataFrame, log: dict | None) -> pd.DataFrame:
    """The closes as Yahoo's daily reply had them: a forecast is graded only on Yahoo's daily close, never on a row
    built from hourly bars (grades are permanent, and the R6 audit does not reach them). It waits for the daily row."""
    if not log or pd.Timestamp(log["bar"]) not in close.index:
        return close
    d = pd.Timestamp(log["bar"])
    if log["inserted"]:
        return close.drop(index=d)
    c = close.copy()
    c.loc[d, sorted(log["symbols"])] = float("nan")
    return c


def _audit_revised_close(panel: dict, dec_bar: pd.Timestamp, cfg: dict, events: list) -> None:
    """Ruling R6 (spec 4): the closes the last decision used against the history values of that bar, once it is no
    longer the decision bar (Yahoo rewrites the latest completed close). A gap above market.revised_close_alert_bps
    writes a revised_close record to decisions.jsonl and an event (alerted through notify). Audited once per decision;
    a history without that bar is retried by a later run."""
    limit = cfg.get("market", {}).get("revised_close_alert_bps")
    pend = journal.load_json("pending.json") or {}
    used = pend.get("decision_close")
    if not limit or not used or "close_audit" in pend or pd.Timestamp(pend["decision_date"]) >= dec_bar:
        return
    d, close = pd.Timestamp(pend["decision_date"]), panel["close"]
    hist = {s: float(close.at[d, s]) for s in used if s in close.columns and d in close.index and pd.notna(close.at[d, s])}
    if set(hist) != set(used):
        return
    gaps = {s: round((hist[s] / used[s] - 1) * 1e4, 6) for s in sorted(used)}
    big = {s: g for s, g in gaps.items() if abs(g) > limit}
    src = {"decision_close_source": pend["hourly_rebuild"]["source"]} if pend.get("hourly_rebuild") else {}  # backlog 70
    pend["close_audit"] = {"gaps_bps": gaps, "alert": bool(big), **src, "logged_at": journal.now_utc()}
    journal.save_json("pending.json", pend)
    if big:
        journal.append("decisions.jsonl", {"event": "revised_close", "date": pend["decision_date"], "decision_close": used,
                                           "history_close": hist, "gaps_bps": gaps, "limit_bps": limit, **src, "logged_at": journal.now_utc()})
        events.append(f"סגירה מתוקנת: ההחלטה של {pend['decision_date']} השתמשה בסגירה שההיסטוריה שינתה - "
                      + ", ".join(f"{s} {g:+.1f}bp" for s, g in big.items()) + f" (סף {limit}bp). לבדוק את market.close_source"
                      + (" (סגירת ההחלטה נבנתה מנרות שעתיים, backlog 70)" if src else ""))


def _decide(panel, cfg, main, shadow, dec: pd.Timestamp, force_rebalance: bool, persist: bool, events, frozen: set | None = None) -> dict:
    """Targets for decision bar `dec` (data up to its close only). persist=False = proposal, no state change.
    frozen: symbols with a stale or absent bar - neither bought nor sold, a held one keeps its current weight."""
    frozen = set(frozen or ())
    r = cfg["risk"]
    bench = cfg.get("benchmark", "SPY")
    mk = cfg.get("market", {})
    utc = mk.get("calendar") == "utc_daily"
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
    m.maybe_reset_peak(prev_regime or "", ds, r.get("dd_reentry_days", 20), r["dd_halve"], r["dd_flat"], r.get("dd_reentry_ref"))  # m is a copy when proposing
    if persist:
        m.mark(px, ds, y if m.state.get("last_mark") not in (None, ds) else 0.0, periods_per_year(cfg))
        shadow.mark(px, ds, y if shadow.state.get("last_mark") not in (None, ds) else 0.0, periods_per_year(cfg))
    blocked = set(m.state.get("blocked", {}))
    targets_raw, diag = build_targets(dec, panel, signals, weights, cfg, m.peak_ratio(px), m.positions, blocked, aux, frozen)
    last_reb = m.state.get("last_rebalance")
    days_since = (close.index.get_loc(dec) - close.index.get_loc(pd.Timestamp(last_reb))) if last_reb and pd.Timestamp(last_reb) in close.index else 10**6
    risk_changed = (prev_regime is not None and prev_regime != diag.get("regime")) or (prev_dd is not None and prev_dd != diag.get("dd_state"))
    old = (journal.load_json("pending.json") or {}) if utc else {}
    expiring = old.get("status") == "pending" and old.get("decision_date") != ds  # decision 12: unfilled, replaced now
    # An expiring order never traded, but the regime and drawdown state it acted on were saved when it was decided,
    # so risk_changed cannot see them again: the decision that replaces it is a full one, never exits-only (which
    # would hold a book that a regime-off order had to sell). A proposal for an already decided date repeats it.
    redo = expiring or (old.get("decision_date") == ds and bool(old.get("rebalance")))
    due = force_rebalance or days_since >= r.get("rebalance_every_days", 5) or risk_changed or diag.get("dd_state") == "flat" or redo
    stopped = diag.get("stopped", [])
    carried = sh_carried = []
    if expiring:  # basic law, never wait out a stop: what the expiring order had to sell is sold at the next fill
        sells = set(old.get("stopped") or [])
        if old.get("exits_only"):  # an exits-only order sold exactly the held names it left out of its targets
            sells |= {s for s in m.positions if not (old.get("targets") or {}).get(s)}
        carried = sorted(sells & set(m.positions))
        sh_carried = sorted(set(old.get("stopped_shadow", old.get("stopped")) or []) & set(shadow.positions))
    elif old.get("decision_date") == ds:  # a proposal for an already decided date repeats what that decision carried
        carried = sorted(set(old.get("carried_stops") or []) & set(m.positions))
    if carried:
        stopped = sorted(set(stopped) | set(carried))
        targets_raw = {s: w for s, w in targets_raw.items() if s not in carried}
        diag["carried_stops"] = carried
    exits_only = not due
    if exits_only:  # off-cycle: hold the book, act only on stops (exits), never re-trade overnight gaps
        targets_raw = {s: w for s, w in m.weights(px).items() if s not in stopped}
    targets_raw = _hold_frozen(targets_raw, m.weights(px), frozen, r["max_gross"])
    bo = _earnings_blackout(ds, r.get("earnings_blackout_days", 4)) if mk.get("earnings_blackout", True) else {}
    etf = etf_groups(cfg)
    skipped = {s: bo.get(s, bo.get("*")) for s in list(targets_raw)
               if s not in m.positions and (s in bo or ("*" in bo and cfg["universe"].get(s) not in etf))}
    for s in skipped:
        targets_raw.pop(s)
    cap = r.get("earnings_max_position_pct", 1.0)
    for s in list(targets_raw):  # held through a report: cap the size (ATR stops cannot protect an earnings gap)
        if s in bo and s in m.positions and cfg["universe"].get(s) not in etf and targets_raw[s] > cap:
            targets_raw[s] = cap
    guard = _coinbase_guard(close, dec, cfg)
    if guard:
        diag["coinbase_guard"] = guard
        if guard["status"] == "breach":  # exits only: nothing grows, no new names; stops and regime-off still sell
            cur = m.weights(px)
            targets_raw = {s: min(w, cur[s]) for s, w in targets_raw.items() if s in cur}
            events.append(f"בדיקת Coinbase: פער מעל {guard['pct']:.0%} ב-{', '.join(guard['breach'])} - יציאות בלבד בהחלטה הזו")
        if guard["unreachable"]:
            events.append(f"אזהרה: Coinbase לא זמין ({', '.join(guard['unreachable'])}) - ממשיכים בלי בדיקת המחיר")
    if panel.get("_close_source"):  # next_open: both closes of the decision bar, for the revised-close check
        diag["close_source"] = panel["_close_source"]
    rebuilt = panel.get("_hourly_rebuild") if (panel.get("_hourly_rebuild") or {}).get("bar") == ds else None
    if rebuilt:  # backlog 70: this decision bar was built from Yahoo's 1h bars
        diag["hourly_rebuild"] = rebuilt
    _, sdiag = build_targets(dec, panel, signals, weights, cfg, shadow.peak_ratio(px), shadow.positions, set(shadow.state.get("blocked", {})), aux, frozen)
    if utc:  # planning decision 12: execute on the first full hour after the decision is logged; overrides count until then
        logged_at = journal.now_utc()
        exec_ts = UtcDailyCalendar.exec_time(dec, logged_at)
        cutoff = exec_ts
    else:
        cutoff = _open_cutoff_utc(dec + pd.offsets.BDay(1))
    targets, applied = _apply_overrides(targets_raw, m.positions, ds, cutoff)
    preview = copy.deepcopy(m).rebalance(targets, px, ds, r["rebalance_band_pct"], r["min_trade_value"], stopped, None, exits_only, frozen=frozen)
    new_entries = [f["symbol"] for f in preview if f["side"] == "BUY" and f["symbol"] not in m.positions]
    decision = {"decision_date": ds, "status": "pending", "rebalance": due, "exits_only": exits_only, "targets": targets, "targets_raw": targets_raw,
                "stopped_shadow": sorted(set(sdiag.get("stopped", [])) | set(sh_carried)) if sh_carried else sdiag.get("stopped", []),
                "shadow_hold": shadow.weights(px),
                "stopped": stopped, "overrides": applied, "earnings_blackout": skipped, "preview_at_close": preview,
                "new_entries": new_entries, "diag": diag, "weights": weights, "logged_at": logged_at if utc else journal.now_utc(),
                **({"frozen": sorted(frozen)} if frozen else {}),
                **({"carried_stops": carried} if carried else {}),
                **({"exec_ts": exec_ts, "decision_close": px} if utc else {}),  # decision_close: the revised-close audit (R6)
                **({"hourly_rebuild": rebuilt} if rebuilt else {}),
                **({"coinbase_breach": True} if guard and guard["status"] == "breach" else {})}  # R9a: the fill is exits-only
    if not persist:
        journal.save_json("proposal.json", decision)
        return decision
    if expiring:  # decision 12: an unfilled order is recorded before a new decision overwrites it
        journal.append("decisions.jsonl", {"event": "expired_unfilled", "date": old.get("decision_date"), "exec_ts": old.get("exec_ts"),
                                           "targets": old.get("targets"), **({"carried_stops": carried} if carried else {}),
                                           "logged_at": journal.now_utc()})
        events.append(f"הזמנות {old.get('decision_date')} לא בוצעו עד ההחלטה הבאה ופג תוקפן (expired_unfilled)")
        if carried:
            msg = (f"stop could not fill on {(old.get('exec_ts') or '?')[:10]}: {', '.join(carried)} - forced exit at the next fill"
                   f" ({exec_ts})")
            events.append(msg)
            notify.send("AI Trader - סטופ לא בוצע", msg + " (כסף נייר)", cfg, "urgent")
    journal.save_json("pending.json", {k: v for k, v in decision.items() if k not in ("diag", "weights")})
    if mk.get("delete_proposal_on_decision"):  # spec 3.3: a stale proposal must not date a later veto
        (journal.STATE / "proposal.json").unlink(missing_ok=True)
    m.state["regime"], m.state["dd_state"] = diag.get("regime"), diag.get("dd_state")
    journal.append("decisions.jsonl", {"date": ds, "logged_at": journal.now_utc(), "due_rebalance": due, "weights": weights, "diag": diag,
                                       "overrides": applied, "earnings_blackout": skipped, "preview": preview})
    score = combine(signals, weights, dec)
    journal.record_predictions(ds, score, {k: v.loc[dec] for k, v in signals.items()}, px, px.get(bench),
                               cfg["learning"]["horizons_days"], list(m.positions))
    if mk.get("overlays", True):
        _overlays_once_per_day(cfg, ds, bench)
    if preview:
        events.append((f"מתוכנן ל-{exec_ts}: " if utc else "מתוכנן לפתיחה הבאה: ") + ", ".join(f"{f['side']} {f['qty']} {f['symbol']}" for f in preview))
    if stopped:
        events.append("סטופ-לוס (יבוצע בפתיחה): " + ", ".join(stopped))
    if frozen & set(m.positions):
        events.append("נתונים ישנים/חסרים - מוקפא, לא נקנה ולא נמכר והסטופ לא נבדק: " + ", ".join(sorted(frozen & set(m.positions))))
    long_frozen = {s_: k for s_, k in _frozen_runs(frozen & set(m.positions), ds).items() if k >= mk["frozen_alert_runs"]}
    if long_frozen:  # escalate: a stale held name is a stop nobody checks
        notify.send("AI Trader - תקלה", "\n".join(f"{s_} no data for {k} runs - stop not checked" for s_, k in long_frozen.items())
                    + " (כסף נייר)", cfg, "urgent")
    if prev_regime and prev_regime != diag.get("regime"):
        events.append(f"שינוי משטר שוק: {prev_regime} -> {diag.get('regime')}")
    if prev_dd and prev_dd != diag.get("dd_state"):
        events.append(f"מצב ירידה מהשיא: {prev_dd} -> {diag.get('dd_state')}")
    return decision


def run_cycle(execute: bool = True, force_rebalance: bool = False, max_age_hours: float = 0.1, propose: bool = False) -> dict:
    cfg = load_config()
    bad = journal.broken_chains(journal.MAIN_CHAINED)  # the news engine checks its own chains
    if bad:  # fail closed: never decide or trade on top of a tampered / corrupted journal
        msg = ("hash chain broken: " + ", ".join(bad) + " - cycle halted, nothing traded; positions are frozen"
               " and stops are NOT being checked until the chain is repaired")
        notify.send("AI Trader - תקלה", msg + " (כסף נייר)", cfg, "urgent")
        return {"halted": msg, "executed": [], "decided_now": False, "events": [msg]}
    bench = cfg.get("benchmark", "SPY")
    mk = cfg.get("market", {})
    utc = mk.get("calendar") == "utc_daily"  # the crypto branch (planning decision 5)
    panel = load_market(cfg, mk.get("history", "10y"), max_age_hours)
    close = panel["close"]
    last = close.index[-1]
    prev = close.index[-2] if len(close) > 1 else last
    events: list[str] = []
    now = _utc_now() if utc else None
    clock_final = (lambda d: UtcDailyCalendar.bar_is_final(d, now)) if utc else _bar_is_final
    no_decision = None
    # Bar-final rule (planning decision 10): the clock says the session ended AND the data was fetched after it.
    if mk.get("stale_skips_run"):  # crypto: any stale or absent coin (or benchmark) skips the run before any decision or fill
        want = UtcDailyCalendar.last_final_bar(now) if utc else None
        if want:  # backlog 70: a final day missing from Yahoo's daily reply is built from its 24 hourly bars, if complete
            try:
                panel = _rebuild_from_hourly(panel, want, set(cfg["universe"]) | {bench}, events)
            except Exception as e:  # noqa: BLE001 - never stops the cycle; the panel stays as fetched (backlog 68 rule)
                print(f"[cycle] backlog 70: no rebuild of {want} ({type(e).__name__})")
            close = panel["close"]
            last = close.index[-1]
            prev = close.index[-2] if len(close) > 1 else last
        dec_bar = last if clock_final(last) else prev
        stale = stale_symbols(panel, dec_bar, _bar_end_utc(dec_bar, cfg), set(cfg["universe"]) | {bench})
        if stale:
            msg = f"stale or absent data for {', '.join(sorted(stale))} on {dec_bar.date()}: run skipped, a later run retries"
            if not propose:  # plain JSON-lines (not chained); ruling R7: the morning summary counts repeats
                journal.append("skips.jsonl", {"logged_at": journal.now_utc(), "reason": msg})
            return {"skipped": msg, "executed": [], "decided_now": False, "events": [msg]}
        frozen = set()
        if want and dec_bar.date() != want:  # backlog 68: a daily row missing from the reply; never decide on an older close
            no_decision = (f"אין שורה יומית של {want} בנתונים (הנר האחרון הסופי הוא {dec_bar.date()}) - אין החלטה בריצה הזו,"
                           " הזמנה ממתינה עדיין מתמלאת, ריצה מאוחרת תנסה שוב")
    else:  # stocks: a stale benchmark makes the newest bar not final; a stale or absent symbol is frozen
        final = clock_final(last) and bench not in stale_symbols(panel, last, _bar_end_utc(last, cfg), [bench])
        dec_bar = last if final else prev
        frozen = stale_symbols(panel, dec_bar, _bar_end_utc(dec_bar, cfg), cfg["universe"])
        if bench in stale_symbols(panel, dec_bar, _bar_end_utc(dec_bar, cfg), [bench]):  # ruling R9b: stale on prev too
            no_decision = f"נתוני {bench} ישנים או חסרים גם ב-{dec_bar.date()} - אין החלטה בריצה הזו, ריצה מאוחרת תנסה שוב"
    if utc and not propose:
        _audit_revised_close(panel, dec_bar, cfg, events)
    if mk.get("close_source", "yahoo") != "yahoo":  # next_open: close[D] = open[D+1]; no D+1 row, no decision on D
        panel = apply_close_source(panel, mk["close_source"], dec_bar)
        close = panel["close"]
        if dec_bar not in close.index:
            events.append(f"אין עדיין שורת {(dec_bar + pd.Timedelta(days=1)).date()} - אין החלטה על {dec_bar.date()}, ריצה מאוחרת תנסה שוב")
            dec_bar = close.index[close.index < dec_bar][-1]
            last = close.index[-1]
    if no_decision:
        if propose:
            return {"skipped": no_decision, "executed": [], "decided_now": False, "events": [no_decision]}
        events.append(no_decision)
    try:
        mkt = market_status(bench)
    except Exception as e:  # noqa: BLE001
        mkt = {"is_open": False, "error": type(e).__name__}
    prices_last = _px(close.loc[last])
    main, shadow = _brokers(cfg, _px(close.loc[dec_bar]), str(dec_bar.date()))
    ca_notes: list[str] = []
    if mk.get("corporate_actions", True):
        # Splits/dividends through the latest bar are applied BEFORE any fill: the feed is already adjusted, so a
        # fill on a split day must see the post-split share count. Idempotent (tracked per position).
        acts = {sym: corporate_actions(sym) for sym in set(main.positions) | set(shadow.positions)}
        w_hold = cfg["account"].get("dividend_withholding", 0.25)
        ca_notes = main.apply_corporate_actions(acts, str(last.date()), w_hold)
        shadow.apply_corporate_actions(acts, str(last.date()), w_hold)
    if propose:  # what the next decision would be, for the trading desk; changes no state
        return _decide(panel, cfg, main, shadow, dec_bar, force_rebalance, False, events, frozen)

    executed: list[dict] = []
    diag: dict = {}
    decided_now = False
    events.extend(ca_notes)

    def fill() -> list[dict]:
        if utc:
            return _execute_pending_utc(cfg, main, shadow, events, now)
        return _execute_pending(panel, cfg, main, shadow, events)

    if execute:
        executed += fill()
        if not no_decision and (journal.load_json("pending.json") or {}).get("decision_date") != str(dec_bar.date()):
            diag = _decide(panel, cfg, main, shadow, dec_bar, force_rebalance, True, events, frozen).get("diag", {})
            decided_now = True
            executed += fill()  # stocks: a missed morning fills at that open now; crypto: exec_ts is still ahead
    weights = (journal.load_json("weights.json") or {}).get("weights", cfg["prior_weights"])
    ds = str(last.date())

    journal.save_json("portfolio.json", main.state)
    journal.save_json("shadow_portfolio.json", shadow.state)
    graded = _without_rebuild(close, panel.get("_hourly_rebuild")).loc[:dec_bar]  # final bars, Yahoo's daily closes only
    card = journal.evaluate_predictions(_eval_close(graded), bench, market=cfg.get("market"))
    try:  # the news book's calls; a failure here must not cost the quant book its records and alerts
        nfiles = ("news_predictions.jsonl", "news_grades.jsonl")
        journal.evaluate_predictions(_eval_close(graded, *nfiles), bench, *nfiles)
    except Exception as e:  # noqa: BLE001 - logged, not hidden
        events.append(f"news grading failed: {type(e).__name__}: {str(e)[:120]}")

    equity = main.equity(prices_last)
    sh_eq = shadow.equity(prices_last)
    gross = sum(p["qty"] * prices_last.get(s, p["last_price"]) for s, p in main.positions.items()) / equity if equity else 0
    if not mk.get("equity_mark_per_bar"):
        journal.append("equity.jsonl", {"date": ds, "logged_at": journal.now_utc(), "equity": round(equity, 2), "shadow_equity": round(sh_eq, 2),
                                        "cash": round(main.cash, 2), "gross": round(gross, 4), "bench_price": prices_last.get(bench),
                                        "market_open": mkt.get("is_open"), "decided": decided_now})
    elif decided_now:  # crypto (spec 3.3): one mark per decision bar, at its decision close; runs that do nothing write nothing
        px_d = _px(close.loc[dec_bar])
        eq_d = main.equity(px_d)
        gross_d = sum(p["qty"] * px_d.get(s, p["last_price"]) for s, p in main.positions.items()) / eq_d if eq_d else 0
        journal.append("equity.jsonl", {"date": str(dec_bar.date()), "logged_at": journal.now_utc(), "equity": round(eq_d, 2),
                                        "shadow_equity": round(shadow.equity(px_d), 2), "cash": round(main.cash, 2),
                                        "gross": round(gross_d, 4), "bench_price": px_d.get(bench), "market_open": mkt.get("is_open"),
                                        "decided": True})
    sp = main.state.get("start_prices") or {}
    common = [k for k in sp if k in prices_last]
    pend = journal.load_json("pending.json") or {}
    summary = {
        "date": ds, "as_of_utc": journal.now_utc(), "market": mkt, "equity": round(equity, 2), "cash": round(main.cash, 2),
        "gross": round(gross, 4), "return_since_start": round(equity / cfg["account"]["starting_cash"] - 1, 4),
        "shadow_return_since_start": round(sh_eq / cfg["account"]["starting_cash"] - 1, 4),
        "baselines": {
            ("bench_since_start" if utc else "spy_since_start"): round(prices_last[bench] / sp[bench] - 1, 4) if bench in sp and bench in prices_last else None,
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
        big = {s: m for s, m in day_moves.items() if m <= -cfg.get("market", {}).get("intraday_alert_pct", 0.06)}
        if big:
            events.append("ירידה חדה היום: " + ", ".join(f"{s} {m:+.1%}" for s, m in big.items()) + " (הסטופ ייבדק בסגירה)")
        summary["day_moves"] = {s: round(m, 4) for s, m in day_moves.items()}
        del movers
    journal.save_json("latest.json", summary)
    from .report import write_daily_report  # local import keeps the module graph flat

    write_daily_report(summary, cfg)
    if events:
        body = "\n".join(events) + f"\nשווי תיק (נייר): ${equity:,.0f} ({summary['return_since_start']:+.2%}) | בלי Claude: {summary['shadow_return_since_start']:+.2%}"
        summary["alert_channels"] = notify.send("AI Trader - תיק נייר", body, cfg, "high" if executed or diag.get("stopped") else "default")
    summary["events"] = events
    journal.save_json("latest.json", summary)
    return summary
