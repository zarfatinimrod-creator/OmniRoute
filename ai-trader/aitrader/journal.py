"""Trading journal: every prediction, decision, fill and lesson, as append-only JSONL in state/.

Four memory layers (taken from the Age of Blood agent setup):
  working    - state/portfolio.json, state/weights.json (what is true now)
  episodic   - predictions/decisions/trades JSONL (what happened, when, why)
  semantic   - state/lessons.md (what we learned; each lesson cites evidence)
  procedural - config.json + skills/trader/SKILL.md (how we act; changed only with evidence)
"""

from __future__ import annotations

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


def append(name: str, record: dict) -> None:
    with _path(name).open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def read(name: str) -> list[dict]:
    p = _path(name)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def write_all(name: str, records: list[dict]) -> None:
    p = _path(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, default=str) + "\n" for r in records))
    tmp.replace(p)


def load_json(name: str, default=None):
    p = _path(name)
    return json.loads(p.read_text()) if p.exists() else default


def save_json(name: str, obj) -> None:
    p = _path(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str) + "\n")
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
    """Grade open predictions whose horizon has passed (in trading days). Returns a scorecard."""
    preds = read("predictions.jsonl")
    idx = close.index
    changed = 0
    for p in preds:
        if p["status"] != "open":
            continue
        d = pd.Timestamp(p["date"])
        pos = idx.searchsorted(d)
        if pos >= len(idx) or pos + p["horizon"] >= len(idx):
            continue
        end = idx[pos + p["horizon"]]
        px_end = close.at[end, p["symbol"]] if p["symbol"] in close else None
        b_end = close.at[end, bench] if bench in close else None
        if px_end is None or pd.isna(px_end) or b_end is None or pd.isna(b_end):
            continue
        ret = px_end / p["price"] - 1
        bret = b_end / p["bench_price"] - 1
        excess = ret - bret
        p.update({
            "status": "evaluated", "eval_date": str(end.date()), "ret": round(ret, 4), "bench_ret": round(bret, 4),
            "excess": round(excess, 4), "hit": bool((excess > 0) == (p["direction"] == "up")),
        })
        changed += 1
    if changed:
        write_all("predictions.jsonl", preds)
    return scorecard(preds)


def scorecard(preds: list[dict] | None = None) -> dict:
    preds = preds if preds is not None else read("predictions.jsonl")
    ev = [p for p in preds if p["status"] == "evaluated"]
    out = {"open": sum(p["status"] == "open" for p in preds), "evaluated": len(ev)}
    for src in sorted({p.get("source", "quant") for p in ev}):
        for h in sorted({p["horizon"] for p in ev}):
            sub = [p for p in ev if p["horizon"] == h and p.get("source", "quant") == src]
            if not sub:
                continue
            ups = [p for p in sub if p["direction"] == "up"]
            out[f"{src}_h{h}"] = {
                "n": len(sub),
                "hit_rate": round(sum(p["hit"] for p in sub) / len(sub), 3),
                "avg_excess_up_calls": round(sum(p["excess"] for p in ups) / len(ups), 4) if ups else None,
            }
    return out
