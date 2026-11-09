"""Trading journal: every prediction, decision, fill and lesson, as append-only JSONL in state/.

Four memory layers (taken from the Age of Blood agent setup):
  working    - state/portfolio.json, state/weights.json (what is true now)
  episodic   - predictions/decisions/trades JSONL (what happened, when, why)
  semantic   - state/lessons.md (what we learned; each lesson cites evidence)
  procedural - config.json + skills/trader/SKILL.md (how we act; changed only with evidence)
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
BOOK = "stocks"  # the active book (use_book); data.load_config() with no argument follows it
_BASE: Path | None = None  # the stock state dir while use_book has switched books; None: STATE is the stock dir


def _path(name: str) -> Path:
    STATE.mkdir(parents=True, exist_ok=True)
    return STATE / name


@contextlib.contextmanager
def use_book(book: str):
    """Make `book` the active book for the block: STATE and BOOK switch, and both come back on exit (also on an
    exception). The stock state dir is whatever STATE is on entry (tests point it at a temp dir), so every book
    stays inside it: stocks -> that dir, crypto -> that dir / market.state_subdir. Entering the active book again
    is a no-op."""
    global STATE, BOOK, _BASE
    if book not in ("stocks", "crypto"):
        raise ValueError(f"unknown book {book!r} (stocks | crypto)")
    if book == BOOK:
        yield
        return
    from .data import load_config

    saved = STATE, BOOK, _BASE
    base = STATE if _BASE is None else _BASE
    STATE, BOOK, _BASE = base / load_config(book)["market"]["state_subdir"], book, base
    try:
        yield
    finally:
        STATE, BOOK, _BASE = saved


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


def calendar_covers(day) -> bool:
    """True when config.json's calendar lists the holidays and early closes for this date's year."""
    return pd.Timestamp(day).year in set(_calendar().get("years", []))


def session_hours(day) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """NYSE regular session (open, close) in New York (hour, minute) for a date, or None when closed
    (weekend / holiday in config.json calendar). Early-close days end at 13:00. A year the calendar does not
    cover counts as closed (fail closed: unknown holidays must not look like sessions)."""
    d = pd.Timestamp(day).date()
    cal = _calendar()
    if d.weekday() >= 5 or not calendar_covers(d) or d.isoformat() in set(cal.get("holidays", [])):
        return None
    return (9, 30), ((13, 0) if d.isoformat() in set(cal.get("early_close", [])) else (16, 0))


def pred_key(p: dict) -> str:
    """Unique per call. News calls scored in the same second share date/symbol/logged_at, so they also carry
    their headline id (or, for rows written before ids, a hash of headline + direction + score)."""
    base = f"{p['date']}|{p['symbol']}|{p['horizon']}|{p.get('source', 'quant')}|{p.get('logged_at', '')}"
    uid = p.get("id") or (hashlib.sha256(f"{p['headline']}|{p.get('direction')}|{p.get('score')}".encode()).hexdigest()[:12]
                          if p.get("headline") else "")
    return f"{base}|{uid}" if uid else base


def graded(grades_name: str = "grades.jsonl") -> dict:
    return {g["key"]: g for g in read(grades_name)}


def open_predictions(preds_name: str = "predictions.jsonl", grades_name: str = "grades.jsonl") -> list[dict]:
    g = graded(grades_name)
    return [p for p in read(preds_name) if pred_key(p) not in g]


def _frag_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _tail_fragment(p: Path) -> str | None:
    """The unterminated last line a crash mid-append leaves behind (None when the file ends with a newline)."""
    if not p.exists() or p.stat().st_size == 0:
        return None
    with p.open("rb") as f:
        f.seek(-1, 2)
        if f.read(1) == b"\n":
            return None
        f.seek(max(0, p.stat().st_size - 1_000_000))
        data = f.read()
    return data[data.rfind(b"\n") + 1:].decode("utf-8", "replace")


def _last_hash(p: Path, frag: str | None) -> str:
    """Hash of the last complete record. Only an unterminated final fragment (a crash mid-append) is skipped;
    a complete line that does not parse returns 'genesis', so the chain breaks and tampering stays visible."""
    if not p.exists() or p.stat().st_size == 0:
        return "genesis"
    with p.open("rb") as f:
        f.seek(max(0, p.stat().st_size - 1_000_000))
        lines = f.read().decode("utf-8", "replace").split("\n")
    if frag is not None:
        lines = lines[:-1]
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            return json.loads(line).get("hash", "genesis")
        except ValueError:
            return "genesis"
    return "genesis"


def append(name: str, record: dict) -> None:
    """Append one JSON line. Decision/trade/learning logs are SHA-256 chained (tamper-evident). After a crash
    mid-append the torn fragment is closed off with a newline and named in the next record (after_torn), so
    the chain continues and verify_chain can tell a crash fragment from an edited record."""
    p = _path(name)
    frag = _tail_fragment(p)
    whole = None
    if frag is not None:  # a complete record that only lost its newline is a record, not a fragment
        try:
            whole = json.loads(frag)
        except ValueError:
            whole = None
    if name in CHAINED:
        if isinstance(whole, dict):
            prev = whole.get("hash", "genesis")
        else:
            prev = _last_hash(p, frag)
            if frag is not None:
                record = {**record, "after_torn": _frag_hash(frag)}
        body = json.dumps(json.loads(json.dumps(record, default=str)), sort_keys=True, default=str)
        record = {**record, "prev_hash": prev, "hash": hashlib.sha256((prev + body).encode()).hexdigest()}
    with p.open("a", encoding="utf-8") as f:
        f.write(("\n" if frag is not None else "") + json.dumps(record, default=str, ensure_ascii=False) + "\n")


def verify_chain(name: str) -> tuple[bool, int]:
    """Re-compute the chain. Returns (ok, records_checked). An unreadable line passes only as a crash
    fragment: the record right after it names it (after_torn), or it is the unterminated last line."""
    p = _path(name)
    if not p.exists():
        return True, 0
    lines = p.read_bytes().decode("utf-8", "replace").split("\n")
    prev, n, pending = "genesis", 0, None
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            if pending is not None or i < len(lines) - 1 and not _names_next(lines, i):
                return False, n
            pending = _frag_hash(line)
            continue
        if pending is not None and r.get("after_torn") != pending:
            return False, n
        pending = None
        h = r.pop("hash", None)
        pv = r.pop("prev_hash", None)
        body = json.dumps(r, sort_keys=True, default=str)
        if pv != prev or h != hashlib.sha256((prev + body).encode()).hexdigest():
            return False, n
        prev, n = h, n + 1
    return True, n


def _names_next(lines: list[str], i: int) -> bool:
    """Is the unreadable line i followed by a record that names it as a crash fragment?"""
    for nxt in lines[i + 1:]:
        if nxt.strip():
            try:
                return json.loads(nxt).get("after_torn") == _frag_hash(lines[i])
            except ValueError:
                return False
    return False


def read(name: str) -> list[dict]:
    p = _path(name)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").split("\n"):  # same split as verify_chain
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


def _entry_bar(p: dict, idx: pd.DatetimeIndex, market: dict | None = None) -> tuple[pd.Timestamp | None, int | None]:
    """Entry for a Claude / desk / overlay / news call: the first price knowable when it was LOGGED, whatever
    date it carries (a desk or overlay call can carry the earlier decision date). Returns (start bar or None
    for "use the logged price", bar position the horizon counts from).
    - live price observed during that day's regular session -> that price; horizon counted from that day
      (the price time is `price_at` when the writer recorded it, else `logged_at`; early closes end at 13:00)
    - logged before that day's close without a live price    -> that session's close (no credit for the gap;
      covers pre-open calls, stale quotes and price None)
    - after the close (13:00 on early-close days), on a closed day or an uncovered calendar year, or with no
      usable time                                           -> the next session's close
    market with calendar "utc_daily" (crypto): every day is a session, 00:00-24:00 UTC, weekends included. A call
    with a price uses it (horizon from the log day); with price None it takes that day's close (None until that
    bar exists, so nothing is graded from a bar that has not closed)."""
    if (market or {}).get("calendar") == "utc_daily":
        ts = _ny_time(p.get("logged_at"))
        if ts is not None:
            day = pd.Timestamp(ts.tz_convert("UTC").date())
            if day in idx and p.get("price") is not None:
                return None, idx.get_loc(day)
            return _next_bar(idx, day, inclusive=True)
    ny = _ny_time(p.get("logged_at"))
    if ny is None:  # no time of day: the session after the later of the call's date and its log date
        anchor = pd.Timestamp(p["date"])
        try:
            logged = pd.Timestamp(str(p.get("logged_at"))[:10])
            anchor = max(anchor, logged) if logged is not pd.NaT else anchor
        except (ValueError, TypeError):
            pass
        return _next_bar(idx, anchor, inclusive=False)
    day, hm = pd.Timestamp(ny.date()), (ny.hour, ny.minute)
    hours = session_hours(day)
    if hours is not None and day in idx and p.get("price") is not None:
        seen = _ny_time(p.get("price_at")) or ny
        seen_hm = (seen.hour, seen.minute) if seen.date() == ny.date() else (0, 0)
        if hours[0] <= seen_hm and hm < hours[1]:
            return None, idx.get_loc(day)
    if hours is not None and hm < hours[1]:  # that session's close is still ahead of the call
        return _next_bar(idx, day, inclusive=True)
    return _next_bar(idx, day, inclusive=False)


def broken_chains(names=None) -> list[str]:
    """Names of hash-chained logs (all, or the given set) whose chain does not verify (empty = all good)."""
    return sorted(n for n in (CHAINED if names is None else names) if not verify_chain(n)[0])


def evaluate_predictions(close: pd.DataFrame, bench: str, preds_name: str = "predictions.jsonl", grades_name: str = "grades.jsonl",
                         market: dict | None = None) -> dict:
    """Grade predictions whose horizon has passed (trading days). Predictions are never edited:
    each grade is a new, hash-chained record in grades.jsonl. market["grading"] == "absolute" (crypto) grades
    against cash (benchmark return 0), so excess is the coin's own return; None / stock grades against `bench`."""
    absolute = (market or {}).get("grading") == "absolute"
    idx = close.index
    done: set[str] = set()
    for p in open_predictions(preds_name, grades_name):
        if pred_key(p) in done:  # one grade per key, even if a duplicate row slipped in
            continue
        if p.get("source", "quant") == "quant":
            # quant calls are made on the decision bar's close and graded from it
            d = pd.Timestamp(p["date"])
            pos = idx.searchsorted(d)
            if pos >= len(idx):
                continue
            start = idx[pos] if idx[pos] == d else None
        else:
            start, pos = _entry_bar(p, idx, market)
            if pos is None:
                continue
        if pos + p["horizon"] >= len(idx):
            continue
        end = idx[pos + p["horizon"]]
        sym = p["symbol"]
        if sym not in close or (not absolute and bench not in close):
            continue
        # Prefer the split/dividend-adjusted series at both ends (immune to later splits); fall back to the
        # logged price only when the prediction date is not a bar in the series (e.g. logged on a holiday).
        p0 = close.at[start, sym] if start is not None else p.get("price")
        if absolute:
            if any(v is None or pd.isna(v) or v == 0 for v in (p0, close.at[end, sym])):
                continue
            ret, bret = close.at[end, sym] / p0 - 1, 0.0
        else:
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
        done.add(pred_key(p))
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
    """What we said and learned about a ticker before (TradingAgents-style memory injection). Calls and trades
    come from the active book; lessons.md is one file for every book, in the stock state dir (crypto lines are
    tagged 'crypto: ...')."""
    sym = symbol.upper()
    preds = [p for p in read("predictions.jsonl") if p["symbol"] == sym]
    trades = [t for t in read("trades.jsonl") if t["symbol"] == sym]
    lessons_path = (STATE if _BASE is None else _BASE) / "lessons.md"
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
