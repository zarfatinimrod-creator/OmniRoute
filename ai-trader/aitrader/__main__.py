"""CLI: python -m aitrader <command>

  cycle [--dry-run] [--force-rebalance]   one live paper cycle (execute only when the market is open)
  status                                  print the latest summary
  backtest [--start 2018-01-01] [--sweep] the time machine (historical replay); --book crypto: the crypto sweep (spec 7)
           [--compare RUN_A RUN_B]        two saved sweep records row by row (read-only)
           [--drift]                      paper versus time machine: every live fill against the official open (read-only)
  predict SYMBOL up|down [--horizon N] [--note TEXT]   log Claude's own call for later grading
  veto SYMBOL --reason TEXT               veto today's new entry in SYMBOL (Claude review)
  shrink SYMBOL MULT --reason TEXT        shrink today's target for SYMBOL (0..1)
  news SYMBOL                             recent headlines
  context SYMBOL                          past calls, trades and lessons for a ticker (read before deciding)
  summary --book crypto [--send] [--ack TS]  crypto morning summary: urgent first; --send delivers (exit 0 ok, 2 ok+urgent,
                                          3 not delivered); without --book crypto it refuses (exit 1)
  verify                                  check the tamper-evident hash chains
  news-live [--until 16:05] [--minutes N]  live news trader (separate paper book): headlines -> Claude score 1-10 -> rules
  news-live --supervised PARENT_PID       the same engine under a parent process: it dies with that parent and exits 143
                                          when its parent is another pid; SIGTERM is a planned stop (exit 143) either way
  news-live --check                       the checks of an engine start and the news hash chains, read-only (no lock, nothing
                                          written or sent): exit 0, or 5 calendar, 7 git merge in progress, 6 book, 4 chains
  news-score [--n 8]                      score recent headlines without trading (scorer check)
  news-status                             news book, last trades, news scorecard
  news-exit SYMBOL --reason TEXT          ask the news engine to sell a held name at its next live quote (never buys);
                                          a waiting request, or an exit sold today, also keeps the engine from buying it
  news-exit SYMBOL --cancel --said TEXT   take a waiting request back, only on the owner's word (TEXT: his words, written
                                          to state/news_exit_cancels.jsonl); exit 1 when there is none: it may have been acted on
  dashboard                               build .cache/dashboard/snapshot.json for the Dashboard artifact
  placebo [--k 100]                       noise gate the learner must beat (signals shuffled across stocks)
  brief SYMBOL                            analyst packet for the trading desk (the only facts agents may cite)
  desk SYMBOL RATING --prob P --thesis T --invalidation I   record the desk's final call (Sell/Underweight=veto, Hold=shrink 0.5)
  scorecard                               grade matured predictions
  postmortem                              realized losses with no review yet (Basic law, item 3), all books; with --record
                                          --keys K[,K] --inside-rules yes|no --data-ok yes|no --verdict V --causes T[,T]
                                          --what TEXT --lesson TEXT --fix TEXT [--fix-ref REF] it writes the review
  news-hold --reason TEXT                 the news engine opens no new position until the hold is lifted (stops and sales
                                          go on); `news-hold --release --reason TEXT` lifts it, on the owner's word
  uptime-report [--day [YYYY-MM-DD] [--notify]] [--days N]   the supervisor's uptime log, read-only: each New York day's
                                          percent of market time with its stops checked, and its causes (default the
                                          last supervisor.report_days days; --day: one day, today when bare); --notify
                                          (the close slot only) adds the day's R4c, R9 and R11 as one line {"notify": [...]}

  --book stocks|crypto (before or after the command; default stocks) picks the paper book. crypto runs in
  state/crypto/ and is accepted by cycle, status, scorecard, backtest, verify, predict, context, veto, shrink, summary;
  every other command is stock-only in v1 and refuses it.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import journal

BOOK_CMDS = {"cycle", "status", "scorecard", "backtest", "verify", "predict", "context", "veto", "shrink", "summary"}  # take --book crypto


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
    b.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"),
                   help="two run records (ids under state/trial_runs), row by row; read-only")
    b.add_argument("--drift", action="store_true",
                   help="every live fill next to the official open the time machine fills at; read-only")
    p = sub.add_parser("predict")
    p.add_argument("symbol")
    p.add_argument("direction", choices=["up", "down"])
    p.add_argument("--horizon", type=int, default=None, help="trading days (default: learning.default_horizon)")
    p.add_argument("--note", default="")
    p.add_argument("--prob", type=float, default=None, help="probability (0-1) that SYMBOL beats the benchmark (stocks) or rises (crypto)")
    cx = sub.add_parser("context")
    cx.add_argument("symbol")
    sub.add_parser("verify")
    sm = sub.add_parser("summary")
    sm.add_argument("--send", action="store_true", help="deliver through notify (bypasses quiet hours); auto-acks up to newest")
    sm.add_argument("--ack", default=None, metavar="TS", help="drop queued alerts with queued_at <= TS (TS required: the printed 'newest')")
    nl = sub.add_parser("news-live")
    nl.add_argument("--until", default="16:05", help="New York time to stop")
    nl.add_argument("--minutes", type=float, default=None)
    nl.add_argument("--check", action="store_true", help="run the start checks and the chain check and exit with their code;"
                                                         " takes no lock, starts no engine, writes and sends nothing")
    nl.add_argument("--supervised", type=int, default=None, metavar="PARENT_PID",
                    help="the engine of a parent process: it dies with that parent, and does not start under another")
    ns = sub.add_parser("news-score")
    ns.add_argument("--n", type=int, default=8)
    ns.add_argument("--minutes", type=int, default=120)
    sub.add_parser("news-status")
    nx = sub.add_parser("news-exit")
    nx.add_argument("symbol")
    how = nx.add_mutually_exclusive_group(required=True)
    how.add_argument("--reason")
    how.add_argument("--cancel", action="store_true", help="take a waiting request back (only with --said)")
    nx.add_argument("--said", help="with --cancel: the owner's own words that take the request back (written down)")
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
    nh = sub.add_parser("news-hold")
    nh.add_argument("--reason", required=True, help="why the hold is set, or (with --release) the owner's word that lifts it")
    nh.add_argument("--release", action="store_true")
    pm = sub.add_parser("postmortem")
    pm.add_argument("--record", action="store_true", help="write a review for the fills named by --keys")
    pm.add_argument("--keys", default="", help="comma-separated fill keys as the list prints them (book:hash; 8 or more characters of the hash); one book per review")
    pm.add_argument("--inside-rules", choices=["yes", "no"], default=None)
    pm.add_argument("--data-ok", choices=["yes", "no"], default=None)
    pm.add_argument("--verdict", default=None, help="bad_data | bad_rule | rule_broken | ops_defect | planned_loss")
    pm.add_argument("--causes", default="", help="comma-separated cause tags (reused across reviews to catch repeats)")
    pm.add_argument("--what", default="")
    pm.add_argument("--lesson", default="")
    pm.add_argument("--fix", default="")
    pm.add_argument("--fix-ref", default="", help="commit, backlog item or lesson that carries the fix")
    ur = sub.add_parser("uptime-report")
    one = ur.add_mutually_exclusive_group()
    one.add_argument("--day", nargs="?", const="", default=None, metavar="YYYY-MM-DD",
                     help="one New York day (today when bare)")
    one.add_argument("--days", type=int, default=None, help="the last N days (default supervisor.report_days)")
    ur.add_argument("--notify", action="store_true",
                    help="with --day: add the close slot's lines as one JSON line; only the close slot pushes them")
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
    elif a.cmd == "backtest" and a.compare:  # read-only: did a re-run reproduce a registered run (the active book's records)
        from . import backtest

        ra, rb = (backtest.load_record(journal.STATE / "trial_runs" / f"{x}.json.gz") for x in a.compare)
        diff = backtest.diff_records(ra, rb)
        print(json.dumps({"a": ra["run_id"], "b": rb["run_id"], "identical": not diff, "differences": diff}, indent=1, default=str))
    elif a.cmd == "backtest" and a.drift:  # read-only: the gap between the price the bot got and the one a replay assumes
        from . import backtest, report
        from .data import load_config

        cfg = load_config()
        print(report.drift_report(backtest.drift(journal.read("trades.jsonl"), cfg), cfg))
    elif a.cmd == "backtest" and a.book == "crypto":  # spec 7: the paired-phase sweep decides crypto_base vs candidate
        from . import crypto_sweep
        from .data import fetch_panel, load_config
        from .market import UtcDailyCalendar

        panel = fetch_panel(list(crypto_sweep.SYMBOLS), load_config()["market"]["history"])
        fetched = panel.get("_fetched_at") or {}  # the last bar that was final when the data was fetched
        end = a.end or str(UtcDailyCalendar.last_final_bar(min(fetched.values()) if fetched else journal.now_utc()))
        res = crypto_sweep.run_sweep(panel, a.start, crypto_sweep.SPLIT, end)
        print(json.dumps({"ship": res["ship"], "final_candidate": res["final_candidate"], "pass_rule": res["pass_rule"],
                          "dsr": res["dsr"], "report": res["report"],
                          "runs": {k: {"sharpe_med": round(r["sharpe_med"], 3), "d_sharpe_med": r.get("d_sharpe_med"), "wins": r.get("wins")}
                                   for k, r in res["runs"].items()}}, indent=1, default=str))
    elif a.cmd == "backtest":
        from . import backtest
        from .data import load_config, load_market

        cfg = load_config()
        panel = load_market(cfg, "10y")
        if a.sweep:
            from . import report

            detail: dict = {}
            df = backtest.sweep(panel, cfg, a.start, a.end, detail=detail)
            print(df.to_string(index=False))
            rec = backtest.register(df, detail, panel, cfg, a.start, a.end)  # the trials.jsonl line + the run record
            print("\n" + report.sweep_report(df, detail, rec, cfg))
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
    elif a.cmd == "summary":
        from . import notify
        from .data import load_config

        if a.book != "crypto":  # the expected-decision check runs on the UTC daily calendar only
            print("summary is crypto-only in v1: run it with --book crypto", file=sys.stderr)
            return 1
        cfg = load_config()
        if a.ack is not None and not a.send:
            n = notify.ack(a.ack)
            print(json.dumps({"acked": n}))
            return 0
        s = notify.build_summary(cfg)
        channels: list[str] = []
        if a.send:
            channels = notify.send("AI Trader - crypto morning summary", s["text"], cfg, "urgent" if s["urgent"] else "default", force=True)
        delivered = any(c in ("ntfy", "telegram") for c in channels)
        if delivered:
            notify.ack(a.ack or s["newest"])
        print(json.dumps({"channels": channels, **s}, indent=1, ensure_ascii=False))
        if a.send and not delivered:
            return 3
        return 2 if s["urgent"] else 0
    elif a.cmd == "verify":
        bad = []
        for name in sorted(journal.CHAINED if journal.BOOK == "stocks" else journal.MAIN_CHAINED):  # news: stock-only
            ok, n = journal.verify_chain(name)
            print(f"{name}: {'OK' if ok else 'BROKEN at record ' + str(n)} ({n} records)")
            bad += [] if ok else [name]
        print("ALL CHAINS OK" if not bad else "BROKEN: " + ", ".join(bad) + " - stop and report")
        try:  # Basic law, item 3: a realized loss with no review is shown at every session start (never fatal here)
            from . import postmortem

            waiting = postmortem.pending()
            if waiting:
                print(f"LOSSES AWAITING REVIEW: {len(waiting)} (-${abs(sum(x['loss'] for x in waiting)):,.2f})"
                      " - after this slot's own steps run `python3 -m aitrader postmortem` and follow"
                      " skills/trader/SKILL.md section 3א")
            again = postmortem.repeated()
            if again:
                print("REPEATED CAUSES: " + ", ".join(f"{t} ({n} losses)" for t, n in again.items())
                      + " - the same cause in two losing sales: if it is a second event, top of state/backlog.md as a"
                        " defect and tell the owner once (skills/trader/SKILL.md section 0)")
        except Exception as e:  # noqa: BLE001
            print(f"postmortem check failed: {type(e).__name__}")
        if journal.BOOK == "stocks":
            try:
                from .news_live import buy_hold

                hold = buy_hold()
                if hold:
                    print(f"NEWS BUYS ON HOLD since {hold.get('since')}: {hold['reason']}")
            except Exception as e:  # noqa: BLE001
                print(f"news hold check failed: {type(e).__name__}")
        if bad:
            sys.exit(1)
    elif a.cmd == "news-live":
        from .news_live import run

        return run(a.until, a.minutes, check=a.check, supervised=a.supervised) or 0  # the code says why it ended (news_live.run): 3 = the book is held
    elif a.cmd == "news-score":  # score recent headlines without trading (a check of the scorer)
        from datetime import datetime, timedelta, timezone

        from .data import load_config
        from .news_live import NewsTrader, live_price, market_open_now, ncfg, score_batch

        cfg = load_config()
        nt = NewsTrader(cfg)
        from concurrent.futures import ThreadPoolExecutor
        from .news_live import fetch_headlines

        with ThreadPoolExecutor(max_workers=8) as ex:
            items = [x for b in ex.map(lambda s_: fetch_headlines(s_, nt.session), nt.universe) for x in b]
        after = datetime.now(timezone.utc) - timedelta(minutes=a.minutes)
        items = sorted([x for x in items if datetime.fromisoformat(x["published"]) >= after], key=lambda x: x["published"], reverse=True)[: a.n]
        is_open = market_open_now()
        for x in items:
            x["price"], move = live_price(x["symbol"])
            x["day_move_pct"] = move if is_open else None  # as the engine: outside the session it is not "so far today"
        sc = score_batch(items, ncfg(cfg)["model"])
        # a check costs what an engine call costs: on record with the others, and named so it is not taken for one
        nt.scorer_called(sc.facts and {**sc.facts, "source": "news-score"})
        for x in items:
            s_ = sc.get(x["key"], {})
            print(f"{s_.get('score', '?'):>2} | {x['symbol']:<5} | {x['published'][11:16]}Z | move {x['day_move_pct']} | {x['title'][:90]} | {s_.get('why', '')}")
    elif a.cmd == "dashboard":
        from .dashboard import write

        print(write())
    elif a.cmd == "news-status":
        from . import postmortem
        from .news_live import buy_hold

        b = journal.load_json("news_book.json", {}) or {}
        try:  # a blocked book must not look like a quiet one
            waiting = postmortem.pending("news")
        except Exception as e:  # noqa: BLE001
            waiting = f"unreadable ({type(e).__name__}): buys are blocked"
        print(json.dumps({"cash": round(b.get("cash", 0), 2), "positions": b.get("positions", {}),
                          "trades": journal.read("news_trades.jsonl")[-10:],
                          "losses_awaiting_review": waiting, "buy_hold": buy_hold(),
                          "scorecard": journal.scorecard(journal.read("news_predictions.jsonl"), "news_grades.jsonl")}, indent=1, default=str, ensure_ascii=False))
    elif a.cmd == "news-hold":  # the news book's kind of veto: only ever stops buys; sales and stops never pass through it
        from .news_live import set_hold

        from .news_live import buy_hold

        try:
            h = set_hold(a.reason, release=a.release)
        except ValueError as e:
            print(f"news-hold: {e}", file=sys.stderr)
            return 2
        except OSError as e:  # the two files are written one after the other: say which state the hold is in now
            now = buy_hold()
            print(f"news-hold: {type(e).__name__}: {str(e)[:200]}. The hold is now "
                  + (f"SET ({now['reason']})" if now else "NOT set") + "; check state/news_hold.json and"
                  " state/news_holds.jsonl", file=sys.stderr)
            return 1
        print(json.dumps({"hold": h or None, "released": a.reason.strip() if a.release else None}, indent=1, ensure_ascii=False))
        print("commit and push state/news_hold.json and state/news_holds.jsonl now: a hold that is not pushed is lost"
              " with the container", file=sys.stderr)
    elif a.cmd == "news-exit":  # only a request: the book lives in the engine's session, which sells and clears it
        from .data import load_config
        from .news_live import SYMBOL, _clean, ncfg, update_exits

        sym = a.symbol.upper()
        if not SYMBOL.fullmatch(sym):  # the name becomes a key in the requests file and a line in the owner's alerts
            print(f"news-exit: {_clean(a.symbol, 20)!r} is not a ticker symbol", file=sys.stderr)
            return 2
        if a.said is not None and not a.cancel:
            print("--said belongs to --cancel", file=sys.stderr)
            return 2
        reason = _clean(a.reason or "", 120)
        if not a.cancel and not reason:  # the engine takes only an entry with a reason as a request
            print("news-exit needs a reason with text in it", file=sys.stderr)
            return 2
        said = _clean(a.said or "", 120)
        if a.cancel and not said:  # a cancel keeps a position open: more risk, so only on the owner's word (backlog 63)
            print("news-exit --cancel needs --said with the owner's words: a waiting exit is taken back only on his word",
                  file=sys.stderr)
            return 2
        n = ncfg(load_config())
        lock = {"wait": n["exits_lock_wait_seconds"], "retry": n["exits_lock_retry_seconds"]}  # config.json's, as the engine's
        try:
            if a.cancel:
                ex, was = update_exits(drop=[sym], **lock)
            else:
                ex, was = update_exits(put={sym: {"reason": reason, "requested_at": journal.now_utc()}}, **lock)
        except TimeoutError as e:  # another writer hangs with the lock
            print(f"{e}: nothing was changed, run the command again", file=sys.stderr)
            return 1
        if a.cancel and sym not in (was or {}):
            print(("news_exits.json cannot be read" if was is None else f"no exit request for {sym} is waiting (the engine may"
                   " already have acted on it: see news-status)") + ": nothing was cancelled", file=sys.stderr)
            return 1
        if a.cancel:  # on record with his words; not hash-chained (the engine never reads it, so it can never stop it)
            try:
                journal.append("news_exit_cancels.jsonl", {"at": journal.now_utc(), "symbol": sym, "said": said,
                                                           "request": was[sym]})
            except Exception:  # noqa: BLE001 - the request is already gone, whatever stopped the row: the owner is told
                print(f"the request for {sym} was cancelled but the cancel could not be written down: tell the owner",
                      file=sys.stderr)
                return 1
        if was is None:
            print("news_exits.json could not be read and was replaced: any request that was in it is gone", file=sys.stderr)
        print(json.dumps(ex, indent=1, ensure_ascii=False))
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
    elif a.cmd == "postmortem":
        from . import postmortem

        if not a.record and any((a.keys, a.inside_rules, a.data_ok, a.verdict, a.causes, a.what, a.lesson, a.fix, a.fix_ref)):
            print("postmortem: the answers of a review need --record; nothing was written", file=sys.stderr)
            return 2
        if a.record:
            if a.inside_rules is None or a.data_ok is None or a.verdict is None:
                print("postmortem --record needs --inside-rules, --data-ok and --verdict", file=sys.stderr)
                return 2
            try:
                rec = postmortem.record([k for k in a.keys.split(",") if k.strip()], a.inside_rules == "yes", a.data_ok == "yes",
                                        a.verdict, a.causes.split(","), a.what, a.lesson, a.fix, a.fix_ref)
            except ValueError as e:
                print(f"postmortem: {e}", file=sys.stderr)
                return 2
            except Exception as e:  # noqa: BLE001 - a ledger or journal that cannot be used: say which, no traceback
                print(f"postmortem: the review was NOT written ({type(e).__name__}: {str(e)[:200]}); check"
                      f" state/{postmortem.LEDGER} and the trade journals", file=sys.stderr)
                return 1
            print(json.dumps(rec, indent=1, ensure_ascii=False))
        try:
            print(json.dumps(postmortem.summary(), indent=1, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001 - say which file, do not die with a traceback
            print(f"postmortem: the list could not be built ({type(e).__name__}: {str(e)[:200]}); check state/{postmortem.LEDGER}"
                  " and the trade journals. Until it can be read the news engine opens no position.", file=sys.stderr)
            return 1
    elif a.cmd == "uptime-report":  # read-only: the supervisor's uptime log (spec 4.6, 11.2)
        from datetime import date, datetime, timedelta  # local, as news-score's: that import makes the names local here

        from . import supervise, uptime

        if a.notify and a.day is None:
            print("uptime-report: --notify belongs to --day (the close slot's one reading of its day)", file=sys.stderr)
            return 2
        if a.days is not None and a.days < 1:
            print(f"uptime-report: --days takes 1 or more, not {a.days}", file=sys.stderr)
            return 2
        today = datetime.now(supervise.NY).date()
        try:
            one = date.fromisoformat(a.day) if a.day else today
        except ValueError:
            print(f"uptime-report: --day takes YYYY-MM-DD, not {a.day[:20]!r}", file=sys.stderr)
            return 2
        cfg = supervise.load_cfg()
        n = a.days or cfg["supervisor"]["report_days"]
        days = [one] if a.day is not None else [today - timedelta(days=k) for k in range(n - 1, -1, -1)]
        rows = supervise.read_rows(journal.STATE / "uptime.jsonl")
        health_file = journal.STATE / "news_health.jsonl"  # read, never created: journal.path would make the folder
        health = supervise.read_rows(health_file) if health_file.exists() else None
        reports = [uptime.day_report(rows, d, cfg, health) for d in days]
        print(uptime.render(reports, cfg))
        if a.notify:
            print(json.dumps({"notify": uptime.close_lines(reports[0], rows, cfg)}, ensure_ascii=False))
    elif a.cmd == "news":
        from .data import news_headlines

        for h in news_headlines(a.symbol.upper()):
            print(f"- {h['date']} | {h['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
