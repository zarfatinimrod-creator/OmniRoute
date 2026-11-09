"""Trading journal: every prediction, decision, fill and lesson, as append-only JSONL in state/.

Four memory layers (taken from the Age of Blood agent setup):
  working    - state/portfolio.json, state/weights.json (what is true now)
  episodic   - predictions/decisions/trades JSONL (what happened, when, why)
  semantic   - state/lessons.md (what we learned; each lesson cites evidence)
  procedural - config.json + skills/trader/SKILL.md (how we act; changed only with evidence)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"


def _path(name: str) -> Path:
    STATE.mkdir(exist_ok=True)
    return STATE / name


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


CHAINED = {"decisions.jsonl", "trades.jsonl", "learning.jsonl", "predictions.jsonl", "grades.jsonl",
           "news_trades.jsonl", "news_scores.jsonl", "news_predictions.jsonl", "news_grades.jsonl"}
NEWS_CHAINED = {n for n in CHAINED if n.startswith("news_")}  # owned by the news engine
MAIN_CHAINED = CHAINED - NEWS_CHAINED  # owned by the quant cycle


def _calendar() -> dict:
    try:
        return json.loads((ROOT / "config.json").read_text(encoding="utf-8")).get("calendar", {})
    except (OSError, ValueError):
        return {}


def session_hours(day) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """NYSE regular session (open, close) in New York (hour, minute) for a date, or None when closed
    (weekend / holiday in config.json calendar). Early-close days end at 13:00."""
    d = pd.Timestamp(day).date()
    cal = _calendar()
    if d.weekday() >= 5 or d.isoformat() in set(cal.get("holidays", [])):
        return None
    return (9, 30), ((13, 0) if d.isoformat() in set(cal.get("early_close", [])) else (16, 0))


def pred_key(p: dict) -> str:
    return f"{p['date']}|{p['symbol']}|{p['horizon']}|{p.get('source', 'quant')}|{p.get('logged_at', '')}"


def graded(grades_name: str = "grades.jsonl") -> dict:
    return {g["key"]: g for g in read(grades_name)}


def open_predictions(preds_name: str = "predictions.jsonl", grades_name: str = "grades.jsonl") -> list[dict]:
    g = graded(grades_name)
    return [p for p in read(preds_name) if pred_key(p) not in g]


def _last_hash(p: Path) -> str:
    """Hash of the last READABLE record: a torn line left by a crash is skipped (read() skips it too), so one
    bad write never breaks the chain for every later record."""
    if not p.exists() or p.stat().st_size == 0:
        return "genesis"
    with p.open("rb") as f:
        f.seek(max(0, p.stat().st_size - 1_000_000))
        tail = f.read().decode("utf-8", "replace").strip().splitlines()
    for line in reversed(tail):
        try:
            return json.loads(line).get("hash", "genesis")
        except ValueError:
            continue
    return "genesis"


def append(name: str, record: dict) -> None:
    """Append one JSON line. Decision/trade/learning logs are SHA-256 chained (tamper-evident)."""
    p = _path(name)
    if name in CHAINED:
        prev = _last_hash(p)
        body = json.dumps(json.loads(json.dumps(record, default=str)), sort_keys=True, default=str)
        record = {**record, "prev_hash": prev, "hash": hashlib.sha256((prev + body).encode()).hexdigest()}
    torn = p.exists() and p.stat().st_size > 0 and p.read_bytes()[-1:] != b"\n"
    with p.open("a", encoding="utf-8") as f:  # a torn last line (no newline) must not swallow this record
        f.write(("\n" if torn else "") + json.dumps(record, default=str, ensure_ascii=False) + "\n")


def verify_chain(name: str) -> tuple[bool, int]:
    """Re-compute the chain. Returns (ok, records_checked)."""
    prev = "genesis"
    rows = read(name)
    for i, r in enumerate(rows):
        h = r.pop("hash", None)
        pv = r.pop("prev_hash", None)
        body = json.dumps(r, sort_keys=True, default=str)
        if pv != prev or h != hashlib.sha256((prev + body).encode()).hexdigest():
            return False, i
        prev = h
    return True, len(rows)


def read(name: str) -> list[dict]:
    p = _path(name)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:  # a torn last line from a crash must not brick every later cycle
            print(f"[journal] skipped unreadable line in {name}")
    return out


def write_all(name: str, records: list[dict]) -> None:
    p = _path(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, default=str, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    tmp.replace(p)


def load_json(name: str, default=None):
    p = _path(name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_json(name: str, obj) -> None:
    p = _path(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


def record_predictions(date: str, score: pd.Series, components: dict[str, pd.Series], prices: dict,
                       bench_px: float, horizons: list[int], held: list[str], top_n: int = 10, source: str = "quant") -> int:
    """Log the day's calls once per date: top/bottom names plus everything held."""
    existing = {(p["date"], p["symbol"], p["horizon"], p.get("source", "quant")) for p in read("predictions.jsonl")}
    s = score.dropna().sort_values(ascending=False)
    names = list(dict.fromkeys(list(s.head(top_n).index) + list(s.tail(top_n // 2).index) + [h for h in held if h in s.index]))
    n = 0
    for sym in names:
        if sym not in prices:
            continue
        for h in horizons:
            key = (date, sym, h, source)
            if key in existing:
                continue
            append("predictions.jsonl", {
                "date": date, "logged_at": now_utc(), "symbol": sym, "horizon": h, "source": source,
                "score": round(float(s[sym]), 4),
                "direction": "up" if s[sym] > 0 else "down",
                "components": {k: (round(float(v.get(sym)), 4) if pd.notna(v.get(sym)) else None) for k, v in components.items()},
                "price": prices[sym], "bench_price": bench_px, "status": "open",
            })
            n += 1
    return n


def _ny_time(stamp) -> pd.Timestamp | None:
    """A logged UTC stamp in New York time (naive stamps are UTC: every writer uses now_utc())."""
    try:
        ts = pd.Timestamp(str(stamp))
    except (ValueError, TypeError):
        return None
    if ts is pd.NaT or len(str(stamp)) < 16:  # a bare date has no time of day
        return None
    return (ts.tz_localize("UTC") if ts.tzinfo is None else ts).tz_convert("America/New_York")


def _next_bar(idx: pd.DatetimeIndex, after: pd.Timestamp, inclusive: bool) -> tuple[pd.Timestamp | None, int | None]:
    nxt = idx[idx >= after] if inclusive else idx[idx > after]
    return (nxt[0], idx.get_loc(nxt[0])) if len(nxt) else (None, None)


def _entry_bar(p: dict, idx: pd.DatetimeIndex) -> tuple[pd.Timestamp | None, int | None]:
    """Entry for a Claude / desk / overlay / news call: the first price knowable when it was LOGGED, whatever
    date it carries (a desk or overlay call can carry the earlier decision date). Returns (start bar or None
    for "use the logged price", bar position the horizon counts from).
    - live price observed during that day's regular session -> that price; horizon counted from that day
      (the price time is `price_at` when the writer recorded it, else `logged_at`; early closes end at 13:00)
    - logged before the open                                -> that session's close (no credit for the gap)
    - anything else (after the close, closed day, price None = writer saw the market closed, no usable time)
                                                            -> the next session's close"""
    ny = _ny_time(p.get("logged_at"))
    if ny is None:  # no time of day: the conservative entry is the session after the call's date
        return _next_bar(idx, pd.Timestamp(p["date"]), inclusive=False)
    day, hm = pd.Timestamp(ny.date()), (ny.hour, ny.minute)
    hours = session_hours(day)
    if hours is not None and day in idx and p.get("price") is not None:
        seen = _ny_time(p.get("price_at")) or ny
        seen_hm = (seen.hour, seen.minute) if seen.date() == ny.date() else (0, 0)
        if hours[0] <= seen_hm and hm < hours[1]:
            return None, idx.get_loc(day)
    if hours is not None and hm < hours[0]:
        return _next_bar(idx, day, inclusive=True)
    return _next_bar(idx, day, inclusive=False)


def broken_chains(names=None) -> list[str]:
    """Names of hash-chained logs (all, or the given set) whose chain does not verify (empty = all good)."""
    return sorted(n for n in (CHAINED if names is None else names) if not verify_chain(n)[0])


def evaluate_predictions(close: pd.DataFrame, bench: str, preds_name: str = "predictions.jsonl", grades_name: str = "grades.jsonl") -> dict:
    """Grade predictions whose horizon has passed (trading days). Predictions are never edited:
    each grade is a new, hash-chained record in grades.jsonl."""
    idx = close.index
    for p in open_predictions(preds_name, grades_name):
        if p.get("source", "quant") == "quant":
            # quant calls are made on the decision bar's close and graded from it
            d = pd.Timestamp(p["date"])
            pos = idx.searchsorted(d)
            if pos >= len(idx):
                continue
            start = idx[pos] if idx[pos] == d else None
        else:
            start, pos = _entry_bar(p, idx)
            if pos is None:
                continue
        if pos + p["horizon"] >= len(idx):
            continue
        end = idx[pos + p["horizon"]]
        sym = p["symbol"]
        if sym not in close or bench not in close:
            continue
        # Prefer the split/dividend-adjusted series at both ends (immune to later splits); fall back to the
        # logged price only when the prediction date is not a bar in the series (e.g. logged on a holiday).
        p0 = close.at[start, sym] if start is not None else p.get("price")
        b0 = close.at[start, bench] if start is not None else p.get("bench_price")
        px_end, b_end = close.at[end, sym], close.at[end, bench]
        if any(v is None or pd.isna(v) or v == 0 for v in (p0, b0, px_end, b_end)):
            continue
        ret = px_end / p0 - 1
        bret = b_end / b0 - 1
        excess = ret - bret
        append(grades_name, {
            "key": pred_key(p), "graded_at": now_utc(), "eval_date": str(end.date()), "ret": round(ret, 4),
            "bench_ret": round(bret, 4), "excess": round(excess, 4), "hit": bool((excess > 0) == (p["direction"] == "up")),
        })
    return scorecard(read(preds_name), grades_name)


def scorecard(preds: list[dict] | None = None, grades_name: str = "grades.jsonl") -> dict:
    preds = preds if preds is not None else read("predictions.jsonl")
    g = graded(grades_name)
    ev = [{**p, **g[pred_key(p)]} for p in preds if pred_key(p) in g]
    out = {"open": len(preds) - len(ev), "evaluated": len(ev)}
    for src in sorted({p.get("source", "quant") for p in ev}):
        for h in sorted({p["horizon"] for p in ev}):
            sub = [p for p in ev if p["horizon"] == h and p.get("source", "quant") == src]
            if not sub:
                continue
            ups = [p for p in sub if p["direction"] == "up"]
            row = {
                "n": len(sub),
                "hit_rate": round(sum(p["hit"] for p in sub) / len(sub), 3),
                "avg_excess_up_calls": round(sum(p["excess"] for p in ups) / len(ups), 4) if ups else None,
            }
            probs = [p for p in sub if p.get("prob") is not None]
            if probs:  # Brier: prob that the stock beats SPY over the horizon; 0.25 = coin flip
                row["brier"] = round(sum((p["prob"] - (1.0 if p["excess"] > 0 else 0.0)) ** 2 for p in probs) / len(probs), 4)
                row["n_prob"] = len(probs)
            out[f"{src}_h{h}"] = row
    return out


def context(symbol: str, n: int = 5) -> dict:
    """What we said and learned about a ticker before (TradingAgents-style memory injection)."""
    sym = symbol.upper()
    preds = [p for p in read("predictions.jsonl") if p["symbol"] == sym]
    trades = [t for t in read("trades.jsonl") if t["symbol"] == sym]
    lessons_path = _path("lessons.md")
    lessons = [ln for ln in lessons_path.read_text().splitlines() if sym in ln] if lessons_path.exists() else []
    g = graded()
    evaluated = [{**p, **g[pred_key(p)]} for p in preds if pred_key(p) in g]
    return {
        "symbol": sym,
        "recent_predictions": preds[-n:],
        "graded": {"n": len(evaluated), "hit_rate": round(sum(p["hit"] for p in evaluated) / len(evaluated), 3) if evaluated else None},
        "recent_trades": trades[-n:],
        "lessons": lessons[-n:],
        "recent_lessons_any": (lessons_path.read_text().strip().splitlines()[-3:] if lessons_path.exists() else []),
    }
