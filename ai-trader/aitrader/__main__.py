"""CLI: python -m aitrader <command>

  cycle [--dry-run] [--force-rebalance]   one live paper cycle (execute only when the market is open)
  status                                  print the latest summary
  backtest [--start 2018-01-01] [--sweep] the time machine (historical replay)
  predict SYMBOL up|down [--horizon 20] [--note TEXT]   log Claude's own call for later grading
  veto SYMBOL --reason TEXT               veto today's new entry in SYMBOL (Claude review)
  shrink SYMBOL MULT --reason TEXT        shrink today's target for SYMBOL (0..1)
  news SYMBOL                             recent headlines
  context SYMBOL                          past calls, trades and lessons for a ticker (read before deciding)
  verify                                  check the tamper-evident hash chains
  brief SYMBOL                            analyst packet for the trading desk (the only facts agents may cite)
  desk SYMBOL RATING --prob P --thesis T --invalidation I   record the desk's final call (Sell/Underweight=veto, Hold=shrink 0.5)
  scorecard                               grade matured predictions
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import journal


def _today_market_date() -> str:
    s = journal.load_json("latest.json", {}) or {}
    return s.get("date") or datetime.now(timezone.utc).date().isoformat()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="aitrader")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cycle")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--force-rebalance", action="store_true")
    sub.add_parser("status")
    sub.add_parser("scorecard")
    b = sub.add_parser("backtest")
    b.add_argument("--start", default="2018-01-01")
    b.add_argument("--end", default=None)
    b.add_argument("--sweep", action="store_true")
    p = sub.add_parser("predict")
    p.add_argument("symbol")
    p.add_argument("direction", choices=["up", "down"])
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--note", default="")
    p.add_argument("--prob", type=float, default=None, help="probability (0-1) that SYMBOL beats SPY over the horizon")
    cx = sub.add_parser("context")
    cx.add_argument("symbol")
    sub.add_parser("verify")
    br = sub.add_parser("brief")
    br.add_argument("symbol")
    dk = sub.add_parser("desk")
    dk.add_argument("symbol")
    dk.add_argument("rating", choices=["Buy", "Overweight", "Hold", "Underweight", "Sell"])
    dk.add_argument("--prob", type=float, required=True, help="P(SYMBOL beats SPY over horizon)")
    dk.add_argument("--horizon", type=int, default=20)
    dk.add_argument("--thesis", required=True)
    dk.add_argument("--invalidation", required=True)
    v = sub.add_parser("veto")
    v.add_argument("symbol")
    v.add_argument("--reason", required=True)
    s = sub.add_parser("shrink")
    s.add_argument("symbol")
    s.add_argument("mult", type=float)
    s.add_argument("--reason", required=True)
    n = sub.add_parser("news")
    n.add_argument("symbol")
    a = ap.parse_args(argv)

    if a.cmd == "cycle":
        from .cycle import run_cycle

        out = run_cycle(execute=not a.dry_run, force_rebalance=a.force_rebalance)
        print(json.dumps({k: out[k] for k in ("date", "market", "equity", "return_since_start", "regime", "dd_state", "due_rebalance", "executed", "preview_orders", "events") if k in out}, indent=1, default=str))
    elif a.cmd == "status":
        print(json.dumps(journal.load_json("latest.json", {}), indent=1, default=str))
    elif a.cmd == "scorecard":
        print(json.dumps(journal.scorecard(), indent=1))
    elif a.cmd == "backtest":
        from . import backtest
        from .data import fetch_panel, load_config

        cfg = load_config()
        panel = fetch_panel(list(cfg["universe"]), "10y")
        if a.sweep:
            df = backtest.sweep(panel, cfg, a.start, a.end)
            print(df.to_string(index=False))
            journal.append("trials.jsonl", {"logged_at": journal.now_utc(), "start": a.start, "rows": df.to_dict("records")})
        else:
            print(backtest.to_json(backtest.run(panel, cfg, a.start, a.end)))
    elif a.cmd == "predict":
        from .data import live_prices, load_config

        cfg = load_config()
        bench = cfg.get("benchmark", "SPY")
        px = live_prices([a.symbol.upper(), bench])
        if a.symbol.upper() not in px:
            print("no price for symbol", file=sys.stderr)
            return 1
        journal.append("predictions.jsonl", {
            "date": _today_market_date(), "logged_at": journal.now_utc(), "symbol": a.symbol.upper(), "horizon": a.horizon,
            "source": "claude", "score": 1.0 if a.direction == "up" else -1.0, "direction": a.direction, "note": a.note,
            "prob": None if a.prob is None else max(0.0, min(1.0, a.prob)), "model_note": "graded forward only (post knowledge cutoff)",
            "components": {}, "price": px[a.symbol.upper()], "bench_price": px.get(bench), "status": "open"})
        print(f"logged claude call: {a.symbol.upper()} {a.direction} h={a.horizon} @ {px[a.symbol.upper()]}")
    elif a.cmd in ("veto", "shrink"):
        ds = _today_market_date()
        ov = journal.load_json("overrides.json", {}) or {}
        if ov.get("date") != ds:
            ov = {"date": ds, "vetoes": {}, "size_mult": {}}
        if a.cmd == "veto":
            ov["vetoes"][a.symbol.upper()] = a.reason
        else:
            ov["size_mult"][a.symbol.upper()] = [max(0.0, min(1.0, a.mult)), a.reason]
        journal.save_json("overrides.json", ov)
        print(json.dumps(ov, indent=1))
    elif a.cmd == "context":
        print(json.dumps(journal.context(a.symbol), indent=1, default=str))
    elif a.cmd == "verify":
        for name in sorted(journal.CHAINED):
            ok, n = journal.verify_chain(name)
            print(f"{name}: {'OK' if ok else 'BROKEN at record ' + str(n)} ({n} records)")
    elif a.cmd == "brief":
        from .desk import brief

        print(json.dumps(brief(a.symbol), indent=1, default=str))
    elif a.cmd == "desk":
        from .data import live_prices, load_config
        from .desk import RATING_TO_ACTION

        cfg = load_config()
        sym = a.symbol.upper()
        bench = cfg.get("benchmark", "SPY")
        px = live_prices([sym, bench])
        ds = _today_market_date()
        prob = max(0.0, min(1.0, a.prob))
        journal.append("predictions.jsonl", {
            "date": ds, "logged_at": journal.now_utc(), "symbol": sym, "horizon": a.horizon, "source": "desk",
            "rating": a.rating, "prob": prob, "score": round(2 * prob - 1, 3), "direction": "up" if prob >= 0.5 else "down",
            "thesis": a.thesis, "invalidation": a.invalidation, "components": {},
            "price": px.get(sym), "bench_price": px.get(bench), "status": "open" if sym in px else "no_price"})
        action = RATING_TO_ACTION[a.rating]
        if action:
            ov = journal.load_json("overrides.json", {}) or {}
            if ov.get("date") != ds:
                ov = {"date": ds, "vetoes": {}, "size_mult": {}}
            reason = f"desk {a.rating} p={prob:.2f}: {a.thesis[:160]}"
            if action[0] == "veto":
                ov["vetoes"][sym] = reason
            else:
                ov["size_mult"][sym] = [action[1], reason]
            journal.save_json("overrides.json", ov)
        print(f"desk logged: {sym} {a.rating} p={prob:.2f} -> {action or 'no override (code decides size)'}")
    elif a.cmd == "news":
        from .data import news_headlines

        for h in news_headlines(a.symbol.upper()):
            print(f"- {h['date']} | {h['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
