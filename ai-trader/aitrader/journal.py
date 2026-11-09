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


CHAINED = {"decisions.jsonl", "trades.jsonl", "learning.jsonl", "predictions.jsonl", "grades.jsonl"}


def pred_key(p: dict) -> str:
    return f"{p['date']}|{p['symbol']}|{p['horizon']}|{p.get('source', 'quant')}|{p.get('logged_at', '')}"


def graded() -> dict:
    return {g["key"]: g for g in read("grades.jsonl")}


def open_predictions() -> list[dict]:
    g = graded()
    return [p for p in read("predictions.jsonl") if pred_key(p) not in g and p.get("status") != "no_price"]


def _last_hash(p: Path) -> str:
    if not p.exists() or p.stat().st_size == 0:
        return "genesis"
    with p.open("rb") as f:
        f.seek(max(0, p.stat().st_size - 1_000_000))
        tail = f.read().decode("utf-8", "replace").strip().splitlines()
    try:
        return json.loads(tail[-1]).get("hash", "genesis")
    except (ValueError, IndexError):
        return "genesis"


def append(name: str, record: dict) -> None:
    """Append one JSON line. Decision/trade/learning logs are SHA-256 chained (tamper-evident)."""
    p = _path(name)
    if name in CHAINED:
        prev = _last_hash(p)
        body = json.dumps(json.loads(json.dumps(record, default=str)), sort_keys=True, default=str)
        record = {**record, "prev_hash": prev, "hash": hashlib.sha256((prev + body).encode()).hexdigest()}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")


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


def evaluate_predictions(close: pd.DataFrame, bench: str) -> dict:
    """Grade predictions whose horizon has passed (trading days). Predictions are never edited:
    each grade is a new, hash-chained record in grades.jsonl."""
    idx = close.index
    for p in open_predictions():
        d = pd.Timestamp(p["date"])
        pos = idx.searchsorted(d)
        if pos >= len(idx) or pos + p["horizon"] >= len(idx) or p.get("price") in (None, 0):
            continue
        end = idx[pos + p["horizon"]]
        # quant calls are made on the decision bar's close; Claude/desk/overlay calls are made later at a live
        # price, so they are graded from the price actually logged (no credit for moves already seen)
        start = idx[pos] if idx[pos] == d and p.get("source", "quant") == "quant" else None
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
        append("grades.jsonl", {
            "key": pred_key(p), "graded_at": now_utc(), "eval_date": str(end.date()), "ret": round(ret, 4),
            "bench_ret": round(bret, 4), "excess": round(excess, 4), "hit": bool((excess > 0) == (p["direction"] == "up")),
        })
    return scorecard()


def scorecard(preds: list[dict] | None = None) -> dict:
    preds = preds if preds is not None else read("predictions.jsonl")
    g = graded()
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
