"""CLI: python -m aitrader <command>

  cycle [--dry-run] [--force-rebalance]   one live paper cycle (execute only when the market is open)
  status                                  print the latest summary
  backtest [--start 2018-01-01] [--sweep] the time machine (historical replay)
  predict SYMBOL up|down [--horizon N] [--note TEXT]   log Claude's own call for later grading
  veto SYMBOL --reason TEXT               veto today's new entry in SYMBOL (Claude review)
  shrink SYMBOL MULT --reason TEXT        shrink today's target for SYMBOL (0..1)
  news SYMBOL                             recent headlines
  context SYMBOL                          past calls, trades and lessons for a ticker (read before deciding)
  verify                                  check the tamper-evident hash chains
  news-live [--until 16:05] [--minutes N]  live news trader (separate paper book): headlines -> Claude score 1-10 -> rules
  news-score [--n 8]                      score recent headlines without trading (scorer check)
  news-status                             news book, last trades, news scorecard
  dashboard                               build .cache/dashboard/snapshot.json for the Dashboard artifact
  placebo [--k 100]                       noise gate the learner must beat (signals shuffled across stocks)
  brief SYMBOL                            analyst packet for the trading desk (the only facts agents may cite)
  desk SYMBOL RATING --prob P --thesis T --invalidation I   record the desk's final call (Sell/Underweight=veto, Hold=shrink 0.5)
  scorecard                               grade matured predictions

  --book stocks|crypto (before or after the command; default stocks) picks the paper book. crypto runs in
  state/crypto/ and is accepted by cycle, status, scorecard, backtest, verify, predict, context, veto, shrink;
  every other command is stock-only in v1 and refuses it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import journal

BOOK_CMDS = {"cycle", "status", "scorecard", "backtest", "verify", "predict", "context", "veto", "shrink"}  # take --book crypto


def _today_market_date() -> str:
    """The decision date overrides/desk calls apply to: the open proposal, else the latest decision."""
    for name, key in (("proposal.json", "decision_date"), ("pending.json", "decision_date"), ("latest.json", "date")):
        v = (journal.load_json(name, {}) or {}).get(key)
        if v:
            return v
    return datetime.now(timezone.utc).date().isoformat()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="aitrader")
    ap.add_argument("--book", choices=["stocks", "crypto"], default="stocks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cycle")
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--force-rebalance", action="store_true")
    c.add_argument("--propose", action="store_true", help="show the next decision (for the trading desk) without changing state")
    sub.add_parser("status")
    sub.add_parser("scorecard")
    b = sub.add_parser("backtest")
    b.add_argument("--start", default="2018-01-01")
    b.add_argument("--end", default=None)
    b.add_argument("--sweep", action="store_true")
    p = sub.add_parser("predict")
    p.add_argument("symbol")
    p.add_argument("direction", choices=["up", "down"])
    p.add_argument("--horizon", type=int, default=None, help="trading days (default: learning.default_horizon)")
    p.add_argument("--note", default="")
    p.add_argument("--prob", type=float, default=None, help="probability (0-1) that SYMBOL beats the benchmark (stocks) or rises (crypto)")
    cx = sub.add_parser("context")
    cx.add_argument("symbol")
    sub.add_parser("verify")
    nl = sub.add_parser("news-live")
    nl.add_argument("--until", default="16:05", help="New York time to stop")
    nl.add_argument("--minutes", type=float, default=None)
    ns = sub.add_parser("news-score")
    ns.add_argument("--n", type=int, default=8)
    ns.add_argument("--minutes", type=int, default=120)
    sub.add_parser("news-status")
    sub.add_parser("dashboard")
    pl = sub.add_parser("placebo")
    pl.add_argument("--k", type=int, default=100)
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
    for sp in sub.choices.values():  # --book also after the command; SUPPRESS keeps the top-level value when absent
        sp.add_argument("--book", choices=["stocks", "crypto"], default=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.book != "stocks" and a.cmd not in BOOK_CMDS:
        print(f"{a.cmd} is stock-only in v1: it does not take --book {a.book}", file=sys.stderr)
        return 2
    with journal.use_book(a.book):
        return _run(a)


def _run(a: argparse.Namespace) -> int:
    if a.cmd == "cycle":
        from .cycle import run_cycle

        out = run_cycle(execute=not a.dry_run, force_rebalance=a.force_rebalance, propose=a.propose)
        if out.get("halted"):
            print(json.dumps({"halted": out["halted"]}, ensure_ascii=False))
            sys.exit(1)
        if out.get("skipped"):  # crypto: stale or absent data, nothing decided or filled; a later run retries
            print(json.dumps({"skipped": out["skipped"]}, ensure_ascii=False))
            return 0
        if a.propose:
            print(json.dumps({k: out.get(k) for k in ("decision_date", "rebalance", "new_entries", "preview_at_close", "earnings_blackout", "stopped", "overrides")}
                             | {"regime": out["diag"].get("regime"), "top_scores": out["diag"].get("top_scores")}, indent=1, default=str))
        else:
            print(json.dumps({k: out[k] for k in ("date", "market", "equity", "return_since_start", "shadow_return_since_start", "regime", "dd_state", "decided_now", "executed", "pending", "events") if k in out}, indent=1, default=str))
    elif a.cmd == "status":
        print(json.dumps(journal.load_json("latest.json", {}), indent=1, default=str))
    elif a.cmd == "scorecard":
        print(json.dumps(journal.scorecard(), indent=1))
    elif a.cmd == "backtest":
        from . import backtest
        from .data import load_config, load_market

        cfg = load_config()
        panel = load_market(cfg, "10y")
        if a.sweep:
            df = backtest.sweep(panel, cfg, a.start, a.end)
            print(df.to_string(index=False))
            journal.append("trials.jsonl", {"logged_at": journal.now_utc(), "start": a.start, "rows": df.to_dict("records")})
        else:
            print(backtest.to_json(backtest.run(panel, cfg, a.start, a.end)))
    elif a.cmd == "predict":
        from .data import live_prices, load_config, market_status

        cfg = load_config()
        horizon = a.horizon if a.horizon is not None else cfg["learning"]["default_horizon"]
        bench = cfg.get("benchmark", "SPY")
        px = live_prices([a.symbol.upper(), bench])
        if a.symbol.upper() not in px:
            print("no price for symbol", file=sys.stderr)
            return 1
        try:
            is_open = market_status(bench).get("is_open", False)
        except Exception:  # noqa: BLE001
            is_open = False
        journal.append("predictions.jsonl", {
            "date": _today_market_date(), "logged_at": journal.now_utc(), "symbol": a.symbol.upper(), "horizon": horizon,
            "source": "claude", "score": 1.0 if a.direction == "up" else -1.0, "direction": a.direction, "note": a.note,
            "prob": None if a.prob is None else max(0.0, min(1.0, a.prob)), "model_note": "graded forward only (post knowledge cutoff)",
            "components": {}, "price": px[a.symbol.upper()] if is_open else None, "bench_price": px.get(bench) if is_open else None,
            "entry": "live" if is_open else "next_session_close", "status": "open"})
        print(f"logged claude call: {a.symbol.upper()} {a.direction} h={horizon} @ {px[a.symbol.upper()]}")
    elif a.cmd in ("veto", "shrink"):
        ds = _today_market_date()
        ov = journal.load_json("overrides.json", {}) or {}
        if ov.get("date") != ds:
            ov = {"date": ds, "vetoes": {}, "size_mult": {}}
        if a.cmd == "veto":
            ov["vetoes"][a.symbol.upper()] = {"reason": a.reason, "logged_at": journal.now_utc()}
        else:
            ov["size_mult"][a.symbol.upper()] = [max(0.0, min(1.0, a.mult)), a.reason, journal.now_utc()]
        journal.save_json("overrides.json", ov)
        print(json.dumps(ov, indent=1))
    elif a.cmd == "context":
        print(json.dumps(journal.context(a.symbol), indent=1, default=str))
    elif a.cmd == "verify":
        bad = []
        for name in sorted(journal.CHAINED if journal.BOOK == "stocks" else journal.MAIN_CHAINED):  # news: stock-only
            ok, n = journal.verify_chain(name)
            print(f"{name}: {'OK' if ok else 'BROKEN at record ' + str(n)} ({n} records)")
            bad += [] if ok else [name]
        print("ALL CHAINS OK" if not bad else "BROKEN: " + ", ".join(bad) + " - stop and report")
        if bad:
            sys.exit(1)
    elif a.cmd == "news-live":
        from .news_live import run

        run(a.until, a.minutes)
    elif a.cmd == "news-score":  # score recent headlines without trading (a check of the scorer)
        from datetime import datetime, timedelta, timezone

        from .data import load_config
        from .news_live import NewsTrader, live_price, ncfg, score_batch

        cfg = load_config()
        nt = NewsTrader(cfg)
        from concurrent.futures import ThreadPoolExecutor
        from .news_live import fetch_headlines

        with ThreadPoolExecutor(max_workers=8) as ex:
            items = [x for b in ex.map(lambda s_: fetch_headlines(s_, nt.session), nt.universe) for x in b]
        after = datetime.now(timezone.utc) - timedelta(minutes=a.minutes)
        items = sorted([x for x in items if datetime.fromisoformat(x["published"]) >= after], key=lambda x: x["published"], reverse=True)[: a.n]
        for x in items:
            x["price"], x["day_move_pct"] = live_price(x["symbol"])
        sc = score_batch(items, ncfg(cfg)["model"])
        for x in items:
            s_ = sc.get(x["key"], {})
            print(f"{s_.get('score', '?'):>2} | {x['symbol']:<5} | {x['published'][11:16]}Z | move {x['day_move_pct']} | {x['title'][:90]} | {s_.get('why', '')}")
    elif a.cmd == "dashboard":
        from .dashboard import write

        print(write())
    elif a.cmd == "news-status":
        b = journal.load_json("news_book.json", {}) or {}
        print(json.dumps({"cash": round(b.get("cash", 0), 2), "positions": b.get("positions", {}),
                          "trades": journal.read("news_trades.jsonl")[-10:],
                          "scorecard": journal.scorecard(journal.read("news_predictions.jsonl"), "news_grades.jsonl")}, indent=1, default=str, ensure_ascii=False))
    elif a.cmd == "placebo":
        from .data import load_config, load_market
        from .learn import placebo_gate
        from .signals import compute_all

        cfg = load_config()
        panel = load_market(cfg, "10y")
        res = placebo_gate(compute_all(panel, cfg), panel["close"], cfg, a.k)
        res["computed_at"] = journal.now_utc()
        journal.save_json("placebo.json", res)
        journal.append("learning.jsonl", {"event": "placebo_gate", **res, "logged_at": journal.now_utc()})
        print(json.dumps(res, indent=1))
    elif a.cmd == "brief":
        from .desk import brief

        print(json.dumps(brief(a.symbol), indent=1, default=str))
    elif a.cmd == "desk":
        from .data import live_prices, load_config, market_status
        from .desk import RATING_TO_ACTION

        cfg = load_config()
        sym = a.symbol.upper()
        bench = cfg.get("benchmark", "SPY")
        px = live_prices([sym, bench])
        ds = _today_market_date()
        prob = max(0.0, min(1.0, a.prob))
        try:
            is_open = market_status(bench).get("is_open", False)
        except Exception:  # noqa: BLE001
            is_open = False
        journal.append("predictions.jsonl", {
            "date": ds, "logged_at": journal.now_utc(), "symbol": sym, "horizon": a.horizon, "source": "desk",
            "rating": a.rating, "prob": prob, "score": round(2 * prob - 1, 3), "direction": "up" if prob >= 0.5 else "down",
            "thesis": a.thesis, "invalidation": a.invalidation, "components": {},
            "price": px.get(sym) if is_open else None, "bench_price": px.get(bench) if is_open else None,
            "entry": "live" if is_open else "next_session_close", "status": "open"})
        action = RATING_TO_ACTION[a.rating]
        if action:
            ov = journal.load_json("overrides.json", {}) or {}
            if ov.get("date") != ds:
                ov = {"date": ds, "vetoes": {}, "size_mult": {}}
            reason = f"desk {a.rating} p={prob:.2f}: {a.thesis[:160]}"
            if action[0] == "veto":
                ov["vetoes"][sym] = {"reason": reason, "logged_at": journal.now_utc()}
            else:
                ov["size_mult"][sym] = [action[1], reason, journal.now_utc()]
            journal.save_json("overrides.json", ov)
        print(f"desk logged: {sym} {a.rating} p={prob:.2f} -> {action or 'no override (code decides size)'}")
    elif a.cmd == "news":
        from .data import news_headlines

        for h in news_headlines(a.symbol.upper()):
            print(f"- {h['date']} | {h['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
