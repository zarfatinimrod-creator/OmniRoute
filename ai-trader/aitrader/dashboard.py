"""Build the dashboard snapshot: one JSON array of rows, each tagged with its table in `t`.

`python3 -m aitrader dashboard` writes .cache/dashboard/snapshot.json, which is uploaded to the Dashboard artifact
(one file -> one upload per refresh). Everything is read from state/ plus live prices for held symbols.

Both books go into one snapshot (spec 8): the stock rows as before, then the crypto rows (tags prefixed "c": ckpi,
cpos, corder, ctrade, ceq, cregime, clesson) read inside journal.use_book("crypto"). Building writes nothing.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import journal
from .data import _chart, load_config
from .strategy import etf_groups

ROOT = Path(__file__).resolve().parent.parent
IL = ZoneInfo("Asia/Jerusalem")
NY = ZoneInfo("America/New_York")


DD_HE = {"normal": "רגיל", "halved": "חצי חשיפה", "flat": "מזומן מלא", "reentry": "חזרה הדרגתית"}
_REGIME_STOCKS = {"risk_on": "מגמה חיובית", "risk_off": "מגמה שלילית (חצי חשיפה)", "risk_off(no-data)": "אין נתון מגמה (חצי חשיפה)",
                  "defensive": "VIX גבוה (75%)", "defensive(no-vix)": "אין נתון VIX - הגנתי"}
REGIME_HE = {"stocks": _REGIME_STOCKS,  # stock risk-off halves exposure; crypto risk-off is cash (risk_off_gross_mult 0)
             "crypto": {**_REGIME_STOCKS, "risk_off": "מגמה שלילית (מזומן)", "risk_off(no-data)": "אין נתון מגמה (מזומן)"}}
STATE_HE = {"on": "מושקע", "off": "מזומן"}  # the crypto hysteresis state (strategy.regime_series)
EDGE_DSR = 0.95  # spec 7: a Deflated Sharpe of 0.95 or more is a proven edge (pre-registered gate, like ruling R13)
CRYPTO_TAG = re.compile(r"^\s*crypto:\s*", re.I)  # a lesson whose observation starts "crypto: ..." (planning decision 16)
REASON_HE = {"entry": "כניסה", "add": "הוספה", "trim": "הקטנה", "exit": "יציאה", "stop": "סטופ"}


def _regime_he(reg: str | None, book: str = "stocks") -> str:
    if not reg:
        return "—"
    parts = REGIME_HE[book]
    return " + ".join(parts.get(x, x) for x in reg.split("+"))


def _clip(s: str | None, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + " …"


def _r(x, n=4):
    return None if x is None else round(float(x), n)


def _il(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(IL).strftime("%d.%m %H:%M")
    except ValueError:
        return ts


def _px(sym: str) -> float | None:
    try:
        px = _chart(sym, "5d", "1d")["meta"].get("regularMarketPrice")
        return float(px) if px else None
    except Exception:  # noqa: BLE001
        return None


def _book_rows(state: dict | None, t: str, sectors: dict, prices: dict) -> tuple[list[dict], float, float]:
    rows, mkt = [], 0.0
    if not state:
        return rows, 0.0, 0.0
    for s, p in state.get("positions", {}).items():
        last = prices.get(s) or p.get("last_price")
        mkt += p["qty"] * last
    eq = state.get("cash", 0.0) + mkt
    for s, p in sorted(state.get("positions", {}).items()):
        last = prices.get(s) or p.get("last_price")
        row = {"t": t, "symbol": s, "sector": sectors.get(s, "—"), "qty": p["qty"], "avg_cost": _r(p["avg_cost"], 2),
               "last": _r(last, 2), "value": _r(p["qty"] * last, 0), "weight": _r(p["qty"] * last / eq if eq else 0),
               "pnl_pct": _r(last / p["avg_cost"] - 1), "since": p.get("entry_date")}
        if t == "npos":
            ne = p.get("news_entry") or {}
            row.update({"stop_price": _r(p.get("stop_price"), 2), "score": ne.get("score"), "why": ne.get("why")})
        rows.append(row)
    return rows, eq, state.get("cash", 0.0)


def _stock_rows() -> list[dict]:
    cfg = load_config()
    sectors = cfg["universe"]
    bench = cfg.get("benchmark", "SPY")
    rows: list[dict] = []
    port = journal.load_json("portfolio.json") or {}
    shadow = journal.load_json("shadow_portfolio.json") or {}
    news = journal.load_json("news_book.json") or {}
    latest = journal.load_json("latest.json") or {}
    pending = journal.load_json("pending.json") or {}

    held = set(port.get("positions", {})) | set(news.get("positions", {})) | set(shadow.get("positions", {}))
    prices = {s: _px(s) for s in sorted(held | {bench, "^VIX"})}
    pos, q_eq, q_cash = _book_rows(port, "pos", sectors, prices)
    npos, n_eq, n_cash = _book_rows(news, "npos", sectors, prices)
    _, s_eq, _ = _book_rows(shadow, "spos", sectors, prices)
    start_cash = cfg["account"]["starting_cash"]
    n_start = cfg.get("news", {}).get("starting_cash", 100000)
    q_eq = q_eq or start_cash
    n_eq = n_eq or n_start
    s_eq = s_eq or start_cash
    sp = port.get("start_prices") or {}
    spy_ret = (prices[bench] / sp[bench] - 1) if prices.get(bench) and sp.get(bench) else None
    q_gross = sum(r["value"] for r in pos) / q_eq if q_eq else 0
    peak = port.get("peak_equity") or start_cash
    now = datetime.now(timezone.utc)
    now_ny = now.astimezone(NY)
    hours = journal.session_hours(now_ny.date())
    mkt_open = hours is not None and hours[0] <= (now_ny.hour, now_ny.minute) < hours[1]
    scores = journal.read("news_scores.jsonl")
    today_il = now.astimezone(IL).date().isoformat()
    scores_today = [s for s in scores if (s.get("logged_at") or "")[:10] == now.date().isoformat()]
    ntrades = journal.read("news_trades.jsonl")
    hb = journal.load_json("news_heartbeat.json") or {}
    hb_age = (now - datetime.fromisoformat(hb["at"])).total_seconds() / 60 if hb.get("at") else None

    rows.append({
        "t": "kpi", "as_of": now.isoformat(timespec="seconds"), "as_of_il": now.astimezone(IL).strftime("%d.%m.%Y %H:%M"),
        "market": "פתוח" if mkt_open else "סגור", "started": port.get("created"),
        "quant_equity": _r(q_eq, 0), "quant_ret": _r(q_eq / start_cash - 1), "spy_ret": _r(spy_ret),
        "alpha_vs_spy": _r((q_eq / start_cash - 1) - spy_ret) if spy_ret is not None else None,
        "shadow_equity": _r(s_eq, 0), "shadow_ret": _r(s_eq / start_cash - 1),
        "claude_effect": _r((q_eq - s_eq) / start_cash),
        "news_equity": _r(n_eq, 0), "news_ret": _r(n_eq / n_start - 1),
        "cash_pct": _r(q_cash / q_eq if q_eq else 1), "gross_pct": _r(q_gross),
        "drawdown": _r(min(0.0, q_eq / max(peak, q_eq) - 1)), "dd_state": DD_HE.get(dd := port.get("dd_state") or latest.get("dd_state") or "normal", dd),
        "regime": _regime_he(port.get("regime") or latest.get("regime")), "vix": _r(prices.get("^VIX"), 2),
        "spy": _r(prices.get(bench), 2), "n_positions": len(pos), "n_news_positions": len(npos),
        "decision_date": pending.get("decision_date"), "pending_status": {"pending": "ממתין לפתיחה", "executed": "בוצע"}.get(pending.get("status"), pending.get("status") or "—"),
        "headlines_today": len(scores_today), "news_trades_total": len(ntrades),
        "news_engine": "פעיל" if hb_age is not None and hb_age < 3 else ("לא פעיל" if hb_age is not None else "—"),
        "today_il": today_il,
    })
    rows += pos + npos

    # next / last orders of the quant book (+ desk overrides)
    ov = {o["symbol"]: o["action"].replace("size x", "הקטנה ×").replace("veto", "וטו") for o in pending.get("overrides", [])}
    fills = {f["symbol"]: f for f in pending.get("fills", [])} if pending.get("status") == "executed" else {}
    for f in (pending.get("preview_at_close") or []):
        x = fills.get(f["symbol"], f)
        rows.append({"t": "order", "symbol": f["symbol"], "side": "קנייה" if f["side"] == "BUY" else "מכירה", "qty": x["qty"],
                     "price": _r(x["price"], 2), "value": _r(x["value"], 0), "desk": ov.get(f["symbol"], ""),
                     "status": "בוצע" if f["symbol"] in fills else "מתוכנן", "decision_date": pending.get("decision_date")})

    # desk calls (latest per symbol)
    desk = {}
    for p in journal.read("predictions.jsonl"):
        if p.get("source") == "desk":
            desk[p["symbol"]] = p
    for s, p in desk.items():
        rows.append({"t": "desk", "symbol": s, "rating": p.get("rating"), "prob": p.get("prob"), "date": p.get("date"),
                     "thesis": _clip(p.get("thesis"), 420), "invalidation": _clip(p.get("invalidation"), 300)})

    # equity curve (percent since start); one point per logged cycle
    for e in journal.read("equity.jsonl")[-400:]:
        b0 = sp.get(bench)
        rows.append({"t": "eq", "ts": e.get("logged_at"), "book": "quant", "ret": _r(e["equity"] / start_cash - 1)})
        if e.get("shadow_equity"):
            rows.append({"t": "eq", "ts": e.get("logged_at"), "book": "shadow", "ret": _r(e["shadow_equity"] / start_cash - 1)})
        if b0 and e.get("bench_price"):
            rows.append({"t": "eq", "ts": e.get("logged_at"), "book": "spy", "ret": _r(e["bench_price"] / b0 - 1)})
    for e in journal.read("news_equity.jsonl")[-400:]:
        rows.append({"t": "eq", "ts": e.get("at"), "book": "news", "ret": _r(e["equity"] / n_start - 1)})
    rows.append({"t": "eq", "ts": now.isoformat(timespec="seconds"), "book": "quant", "ret": _r(q_eq / start_cash - 1)})
    rows.append({"t": "eq", "ts": now.isoformat(timespec="seconds"), "book": "shadow", "ret": _r(s_eq / start_cash - 1)})
    rows.append({"t": "eq", "ts": now.isoformat(timespec="seconds"), "book": "news", "ret": _r(n_eq / n_start - 1)})
    if spy_ret is not None:
        rows.append({"t": "eq", "ts": now.isoformat(timespec="seconds"), "book": "spy", "ret": _r(spy_ret)})

    # trades (both books, newest first)
    tr = [{"book": "כמותי", **x} for x in journal.read("trades.jsonl")] + [{"book": "חדשות", **x} for x in ntrades]
    tr.sort(key=lambda x: x.get("logged_at", ""), reverse=True)
    for i, x in enumerate(tr[:40]):
        rows.append({"t": "trade", "id": i, "time": _il(x.get("logged_at")), "book": x["book"], "side": "קנייה" if x["side"] == "BUY" else "מכירה",
                     "symbol": x["symbol"], "qty": x["qty"], "price": _r(x["price"], 2), "value": _r(x["value"], 0),
                     "pnl": _r(x.get("realized_pnl"), 0), "reason": _clip(x.get("reason"), 160)})

    # live news feed (newest first)
    bought = {(x["symbol"], (x.get("logged_at") or "")[:16]) for x in ntrades if x["side"] == "BUY"}
    for i, s in enumerate(sorted(scores, key=lambda x: x.get("logged_at", ""), reverse=True)[:60]):
        act = "נקנה" if (s["symbol"], (s.get("logged_at") or "")[:16]) in bought else ("ציון קנייה (שוק סגור)" if s["score"] > 8 else "")
        rows.append({"t": "news", "id": i, "time": _il(s.get("logged_at")), "published": _il(s.get("published")), "symbol": s["symbol"],
                     "score": s["score"], "headline": s.get("headline"), "why": s.get("why"), "action": act,
                     "latency_s": s.get("latency_s")})

    # scorecards: quant/desk/claude/overlays + news
    card = journal.scorecard()
    ncard = journal.scorecard(journal.read("news_predictions.jsonl"), "news_grades.jsonl")
    names = {"quant": "אותות כמותיים", "desk": "דסק המסחר", "claude": "תחזיות Claude", "insider_cluster": "קניות בעלי עניין",
             "congress_buy": "קונגרס", "news_claude": "ציוני חדשות"}
    for c, label in ((card, "כמותי"), (ncard, "חדשות")):
        for k, v in c.items():
            if isinstance(v, dict):
                src, h = k.rsplit("_h", 1)
                rows.append({"t": "score", "key": k, "book": label, "source": names.get(src, src), "horizon": int(h), "n": v["n"],
                             "hit_rate": v["hit_rate"], "brier": v.get("brier")})
    rows.append({"t": "score_open", "open_quant": card.get("open", 0), "evaluated_quant": card.get("evaluated", 0),
                 "open_news": ncard.get("open", 0), "evaluated_news": ncard.get("evaluated", 0)})

    # learning: weights + placebo
    w = (journal.load_json("weights.json") or {}).get("weights") or cfg["prior_weights"]
    pl = journal.load_json("placebo.json") or {}
    heb = {"tsmom": "מומנטום סדרתי", "xsmom": "מומנטום יחסי", "trend": "מגמה", "breakout": "פריצה", "high52": "קרבה לשיא שנתי",
           "reversal": "היפוך קצר", "rsi2": "RSI2 משיכה", "lowvol": "תנודתיות נמוכה (מסנן)"}
    for k, v in w.items():
        z, gate = (pl.get("real_z") or {}).get(k), pl.get("gate_z95")
        rows.append({"t": "weight", "signal": k, "label": heb.get(k, k), "weight": v, "z": z, "gate": gate,
                     "passes": "—" if z is None or gate is None else ("כן" if z > gate else "לא")})

    # time machine: last logged sweep
    trials = [t for t in journal.read("trials.jsonl") if t.get("rows")]
    if trials:
        for r in trials[-1]["rows"]:
            if not str(r.get("variant", "")).startswith("DSR"):
                rows.append({"t": "bt", "variant": r.get("variant"), "sharpe": r.get("sharpe_med", r.get("sharpe")),
                             "cagr": r.get("cagr_med", r.get("cagr")), "maxdd": r.get("maxdd_med", r.get("max_drawdown")),
                             "calmar": r.get("calmar_med", r.get("calmar")), "wins": r.get("wins_vs_base")})
            else:
                rows.append({"t": "bt_dsr", "label": r["variant"], "dsr": r.get("psr_med", r.get("psr_vs_0"))})

    # blackout
    for s, when in sorted(((journal.load_json("earnings.json") or {}).get("blackout") or {}).items()):
        if s in sectors and sectors[s] not in etf_groups(cfg):
            rows.append({"t": "block", "symbol": s, "when": when})

    # rules (owner first), schedule, health, lessons
    n = cfg.get("news", {})
    r = cfg["risk"]
    for who, name, val in [
        ("נמרוד", "קנייה מחדשות רק בציון מעל", f"{n.get('buy_min_score', 8)} מתוך 10"),
        ("נמרוד", "מקסימום לעסקה אחת", f"{n.get('max_position_pct', 0.05):.0%} מהחשבון"),
        ("נמרוד", "סטופ-לוס בלי רגשות", f"ירידה של {n.get('stop_loss_pct', 0.03):.0%} מהקנייה"),
        ("נמרוד", "כסף", "נייר בלבד"),
        ("Claude", "מכירה על חדשות רעות", f"ציון {n.get('sell_on_score_at_most', 2)} ומטה על מניה מוחזקת"),
        ("Claude", "יציאה לפי זמן (חדשות)", f"אחרי {n.get('max_hold_days', 5)} ימי מסחר"),
        ("מערכת", "Claude רק מקטין סיכון", "וטו / הקטנה, אף פעם לא הגדלה"),
        ("מערכת", "יעד תנודתיות (כמותי)", f"{r['target_vol_annual']:.0%} בשנה"),
        ("מערכת", "תקרת מניה / סקטור (כמותי)", f"{r['max_position_pct']:.0%} / {r['max_sector_pct']:.0%}"),
        ("מערכת", "מפסק ירידה", f"חצי חשיפה בירידה של {abs(r['dd_halve']):.0%}, מזומן מלא בירידה של {abs(r['dd_flat']):.0%}"),
        ("מערכת", "מסנן משטר", "SPY מתחת לממוצע 200 = חצי חשיפה; VIX גבוה = 75%"),
        ("מערכת", "חסימת דוחות", "לא נכנסים למניה לפני דוח רבעוני"),
    ]:
        rows.append({"t": "rule", "who": who, "name": name, "value": val})
    for name, il, ny, what in [
        ("מנוע חדשות", "15:07–23:05", "08:07–16:05", "כותרות כל 20 שניות, ציון Claude, חוקי קנייה/סטופ"),
        ("פתיחה", "16:52", "09:52", "ביצוע ההחלטה במחיר הפתיחה האמיתי"),
        ("מעקב צהריים", "19:52", "12:52", "מעקב בלבד, התראה על ירידה חדה"),
        ("סגירה", "23:22", "16:22", "דסק מסחר, החלטה למחר, למידה, סיכום"),
        ("סקירה שבועית", "שבת 17:17", "שבת 10:17", "מכונת הזמן + שיפור אחד מה-backlog"),
        ("קריפטו: החלטה", "02:12", "—", "כל לילה, אחרי סגירת הנר היומי. UTC 00:12 קבוע; השעה בישראל זזה עם שעון קיץ (03:12)"),
        ("קריפטו: ביצוע", "03:07", "—", "פתיחת הנר השעתי של 01:00 UTC. UTC 01:07 קבוע; השעה בישראל זזה עם שעון קיץ (04:07)"),
        ("קריפטו: סיכום בוקר", "08:03", "—", "הודעות הלילה שחיכו + בדיקות דחופות. 08:03 שעון ישראל קבוע, כל השנה"),
    ]:
        rows.append({"t": "slot", "name": name, "time_il": il, "time_ny": ny, "what": what})
    ov_state = journal.load_json("overlays.json") or {}
    chains = all(journal.verify_chain(f)[0] for f in journal.CHAINED)
    for comp, status, detail in [
        ("מנוע חדשות", "ok" if hb_age is not None and hb_age < 3 else ("warn" if not mkt_open else "bad"),
         f"דופק לפני {hb_age:.0f} דק'" if hb_age is not None else "לא רץ בסביבה הזו"),
        ("יומן מוגן (שרשרת האש)", "ok" if chains else "bad", "תקין" if chains else "שבור - לבדוק"),
        ("מחירים (Yahoo)", "ok" if prices.get(bench) else "bad", f"SPY {prices.get(bench)}" if prices.get(bench) else "אין נתון"),
        ("SEC / Nasdaq / OpenInsider", "ok", f"{len(ov_state.get('insider_cluster') or [])} קניות בעלי עניין היום"),
        ("Quiver Quant", "bad" if ov_state.get("congress_buy") is None else "ok", "המפתח נדחה - צריך מפתח תקין" if ov_state.get("congress_buy") is None else "מחובר"),
        ("Liquid", "warn", "לא מחובר - מחכה להחלטה שלך"),
    ]:
        rows.append({"t": "health", "component": comp, "status": status, "detail": detail})
    rows += _lesson_rows(_lessons()[0], "lesson")
    return rows


def _lessons() -> tuple[list[str], list[str]]:
    """(stock lines, crypto lines) of lessons.md, each without its "- ". It is one file in the stock state dir:
    journal._BASE while use_book has switched books, else journal.STATE (never ROOT/state, so tests never read the real
    file). A crypto line loses its "crypto:" tag; untagged lines are stocks (planning decision 16)."""
    lp = (journal.STATE if journal._BASE is None else journal._BASE) / "lessons.md"
    stock, crypto = [], []
    for ln in (lp.read_text(encoding="utf-8").splitlines() if lp.exists() else []):
        if not ln.startswith("- 20"):
            continue
        parts = ln[2:].split("|")
        if len(parts) > 1 and CRYPTO_TAG.match(parts[1]):
            parts[1] = CRYPTO_TAG.sub("", parts[1], count=1)
            crypto.append("|".join(parts))
        else:
            stock.append(ln[2:])
    return stock, crypto


def _lesson_rows(les: list[str], t: str) -> list[dict]:
    rows = []
    for i, ln in enumerate(les[-8:][::-1]):
        parts = [p.strip() for p in ln.split("|")]
        rows.append({"t": t, "id": i, "date": parts[0] if parts else "", "text": parts[1] if len(parts) > 1 else ln,
                     "confidence": next((p.split(":", 1)[1].strip() for p in parts if p.startswith(("confidence", "ביטחון"))), parts[3] if len(parts) > 3 else "")})
    return rows


def _crypto_rows() -> list[dict]:
    """The crypto book (spec 8), read inside use_book("crypto"): ckpi, cpos, corder, ctrade, ceq, cregime, clesson.
    Before the first crypto run there is no <state>/crypto, and nothing is read from it (journal._path would create
    the dir): the summary row then shows the starting cash and live=False."""
    cfg = load_config()
    have = journal.STATE.is_dir()
    load = journal.load_json if have else (lambda name, default=None: default)
    read = journal.read if have else (lambda name: [])
    bench = cfg["benchmark"]
    start = cfg["account"]["starting_cash"]
    port, shadow, pending, latest, dsr = (load(n) or {} for n in ("portfolio.json", "shadow_portfolio.json", "pending.json",
                                                                    "latest.json", "dsr.json"))
    held = set(port.get("positions", {})) | set(shadow.get("positions", {}))
    prices = {s: _px(s) for s in sorted(held | {bench})}  # 24/7 market: the live price is the mark
    pos, eq, cash = _book_rows(port, "cpos", cfg["universe"], prices)
    _, s_eq, _ = _book_rows(shadow, "cspos", cfg["universe"], prices)
    eq, s_eq = eq or start, s_eq or start
    sp = port.get("start_prices") or {}
    b0 = sp.get(bench)
    b_live = prices[bench] / b0 - 1 if prices.get(bench) and b0 else None
    b_ret = b_live if b_live is not None else (latest.get("baselines") or {}).get("bench_since_start")  # Task 6 name
    ret = eq / start - 1
    dv = dsr.get("value")
    peak = port.get("peak_equity") or start
    now = datetime.now(timezone.utc)
    st = pending.get("status")
    rows: list[dict] = [{
        "t": "ckpi", "live": bool(port), "started": port.get("created"), "equity": _r(eq, 0), "ret": _r(ret),
        "shadow_equity": _r(s_eq, 0), "shadow_ret": _r(s_eq / start - 1), "claude_effect": _r((eq - s_eq) / start),
        "bench_since_start": _r(b_ret), "vs_bench": _r(ret - b_ret) if b_ret is not None else None, "btc": _r(prices.get(bench), 2),
        "cash_pct": _r(cash / eq if port else 1), "gross_pct": _r(sum(r["value"] for r in pos) / eq), "n_positions": len(pos),
        "drawdown": _r(min(0.0, eq / max(peak, eq) - 1)), "dd_state": DD_HE.get(dd := port.get("dd_state") or latest.get("dd_state") or "normal", dd),
        "regime": _regime_he(port.get("regime") or latest.get("regime"), "crypto"),
        "fees_paid": _r(port.get("fees_paid", 0.0), 2), "fee_pct": cfg["costs"].get("fee_bps", 0) / 1e4,
        "decision_date": pending.get("decision_date"), "pending_status": {"pending": "ממתין לביצוע", "executed": "בוצע"}.get(st, st or "—"),
        "exec_il": _il(pending.get("exec_ts")), "last_run_il": _il(latest.get("as_of_utc")),
        "dsr": _r(dv), "dsr_gate": EDGE_DSR, "proven_edge": isinstance(dv, (int, float)) and dv >= EDGE_DSR,
    }]
    rows += pos

    # orders of the last decision; the fill is the first full hour after it (planning decision 12), all coins or none
    ov = {o["symbol"]: o["action"].replace("size x", "הקטנה ×").replace("veto", "וטו") for o in pending.get("overrides", [])}
    fills = {f["symbol"]: f for f in pending.get("fills", [])} if st == "executed" else {}
    for f in (pending.get("preview_at_close") or []):
        x = fills.get(f["symbol"], f)
        rows.append({"t": "corder", "symbol": f["symbol"], "side": "קנייה" if f["side"] == "BUY" else "מכירה", "qty": x["qty"],
                     "price": _r(x["price"], 2), "value": _r(x["value"], 0), "desk": ov.get(f["symbol"], ""),
                     "status": "בוצע" if f["symbol"] in fills else ("לא בוצע" if st == "executed" else "מתוכנן"),
                     "when": _il(pending.get("fill_ts") if f["symbol"] in fills else pending.get("exec_ts")),
                     "decision_date": pending.get("decision_date")})

    trades = sorted(read("trades.jsonl"), key=lambda x: x.get("logged_at", ""), reverse=True)
    for i, x in enumerate(trades[:40]):
        rows.append({"t": "ctrade", "id": i, "time": _il(x.get("fill_ts") or x.get("logged_at")),
                     "side": "קנייה" if x["side"] == "BUY" else "מכירה", "symbol": x["symbol"], "qty": x["qty"],
                     "price": _r(x["price"], 2), "value": _r(x["value"], 0), "fee": _r(x.get("fee"), 2),
                     "pnl": _r(x.get("realized_pnl"), 0), "source": x.get("fill_source"),
                     "reason": REASON_HE.get(x.get("reason"), _clip(x.get("reason"), 160))})

    # equity curve: one mark per decision bar (market.equity_mark_per_bar), plus the live mark
    for e in read("equity.jsonl")[-400:]:
        rows.append({"t": "ceq", "ts": e.get("logged_at"), "book": "crypto", "ret": _r(e["equity"] / start - 1)})
        if e.get("shadow_equity"):
            rows.append({"t": "ceq", "ts": e.get("logged_at"), "book": "shadow", "ret": _r(e["shadow_equity"] / start - 1)})
        if b0 and e.get("bench_price"):
            rows.append({"t": "ceq", "ts": e.get("logged_at"), "book": "btc", "ret": _r(e["bench_price"] / b0 - 1)})
    if port:
        ts = now.isoformat(timespec="seconds")
        rows += [{"t": "ceq", "ts": ts, "book": "crypto", "ret": _r(ret)}, {"t": "ceq", "ts": ts, "book": "shadow", "ret": _r(s_eq / start - 1)}]
        if b_live is not None:
            rows.append({"t": "ceq", "ts": ts, "book": "btc", "ret": _r(b_live)})

    # regime gauge: the last decision (event rows skipped); off below sma*(1-band), back on only above sma*(1+band)
    dec = next((d for d in reversed(read("decisions.jsonl")) if "event" not in d), None)
    if dec:
        dg, r = dec.get("diag") or {}, cfg["risk"]
        px, sma, band = dg.get("regime_px"), dg.get("regime_sma"), r.get("regime_band_pct", 0.0)
        lo, hi = (sma * (1 - band), sma * (1 + band)) if sma else (None, None)
        rows.append({"t": "cregime", "date": dg.get("date") or dec.get("date"), "px": px, "sma": sma, "band": band,
                     "sma_days": r["regime_sma_days"], "cash_line": _r(lo, 2), "back_line": _r(hi, 2),
                     "dist_cash": _r(px / lo - 1) if px and lo else None, "dist_back": _r(px / hi - 1) if px and hi else None,
                     "state": dg.get("regime_state"), "state_he": STATE_HE.get(dg.get("regime_state"), "—"),
                     "regime": _regime_he(dg.get("regime"), "crypto")})
    rows += _lesson_rows(_lessons()[1], "clesson")
    return rows


def build() -> list[dict]:
    """One snapshot, both books. Each block runs inside its own book, so a build started inside the crypto book (or
    any later book switch) still reads the stock dir for the stock rows."""
    with journal.use_book("stocks"):
        rows = _stock_rows()
    with journal.use_book("crypto"):
        rows += _crypto_rows()
    return rows


def write() -> Path:
    out = ROOT / ".cache" / "dashboard"
    out.mkdir(parents=True, exist_ok=True)
    p = out / "snapshot.json"
    p.write_text(json.dumps(build(), ensure_ascii=False, default=str), encoding="utf-8")
    return p
