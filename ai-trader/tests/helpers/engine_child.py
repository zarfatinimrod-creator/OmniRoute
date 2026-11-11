"""The real news engine in a process of its own, for tests and drills (supervisor spec 11.1).

    python3 tests/helpers/engine_child.py --state-dir DIR --scenario FILE --sent FILE [news-live options]

journal.STATE is pointed at DIR, every call of the engine that leaves the process (the network, a subprocess, the
model) is replaced by a stand-in that answers from the scenario file, the tripwire is installed, and then
`python3 -m aitrader news-live` runs with the options and its exit code is this process's. Never on the live state.

Scenario keys, all optional (SCENARIO holds the defaults):
  session          "open": market_open_now() is true and a quote the stand-in stamped counts as live. Else closed.
  calendar_covers  what journal.calendar_covers answers.
  universe, news   cfg["universe"]; keys merged over cfg["news"].
  prices           live_price. A number for every name, or {symbol: list}: one value per call, the last repeats; a
                   name the table does not hold costs PRICE. null = no quote. Every call stamps QUOTE_TIME.
  quote_delay_s    a sleep inside every live_price.
  polls            the feed. Poll n is a list of {key, symbol, title}, published = now; after the list, nothing.
  opens            official_opens, {symbol: price}. A name not in it has no 09:30 bar: the queue takes the live quote.
  scores           score_batch, {key: score}; 5 for a key it does not hold.
  score_delay_s    a sleep inside every score_batch; "never" = for good.
  score_orphan     true: the first score_batch starts `sleep 60`, writes its pid to <sent file>.orphan and leaves it.
  send_ok          notify.send appends {at, title, body, priority} to the sent file and returns ["ntfy"]; false: [].
  bars             bars_since, rows of [start (UTC ISO), low, close].
  commit           the commit code_stamp names.

A start must take a second, so one thing is set that no scenario key names: the loop waits QUICK["poll_seconds"]
between steps unless the scenario's news.poll_seconds says otherwise (config.json's own wait would hold every exit
back by that long). The options go to news-live as they came. With no --until the engine ends at its own default,
16:05 New York, by the real clock: a start made after that ends before its first step. Whoever needs a start at any
hour names the end (the tests do: Procs.start_engine in tests/test_supervise.py).
The session is what the scenario says; the calendar behind catch_up_stops and the 5-day exit stays the real one.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # the ai-trader folder, also when PYTHONPATH does not name it
from aitrader import __main__ as cli  # noqa: E402
from aitrader import journal, news_live  # noqa: E402

PRICE = 100.0
SCENARIO = {"session": "closed", "calendar_covers": True, "universe": {"AAA": "Tech", "BBB": "Tech", "SPY": "Index"},
            "news": {}, "prices": PRICE, "quote_delay_s": 0, "polls": [], "opens": {}, "scores": {}, "score_delay_s": 0,
            "score_orphan": False, "send_ok": True, "bars": [], "commit": "abc1234"}
QUICK = {"poll_seconds": 1}  # the loop sleeps at least 1 s whatever this says (news_live._run)


def install(sc: dict, sent: str) -> None:
    """Puts a stand-in that answers from the scenario `sc` in the place of every call of the engine that leaves the
    process: the feed, the quote, the minute bars, the official open, the scorer, the two checker seams, the phone and
    git. With them the session, the calendar's cover and the config, so that a scenario plays the same on any day."""
    is_open = sc["session"] == "open"
    asked = Counter()  # (stand-in, symbol) -> how many times it was asked

    news_live.market_open_now = lambda: is_open
    news_live.NewsTrader._quote_is_live = lambda self, price_at, published=None, now=None: is_open and bool(price_at)
    journal.calendar_covers = lambda day: sc["calendar_covers"]

    real_config = news_live.load_config

    def load_config(*a, **k):
        cfg = real_config(*a, **k)
        return {**cfg, "universe": sc["universe"], "news": {**cfg["news"], **QUICK, **sc["news"]}}

    def live_price(sym):
        time.sleep(sc["quote_delay_s"])
        table = sc["prices"]
        seq = table.get(sym, PRICE) if isinstance(table, dict) else table
        seq = seq if isinstance(seq, list) else [seq]
        px = seq[min(asked["price", sym], len(seq) - 1)]
        asked["price", sym] += 1
        news_live.QUOTE_TIME[sym] = journal.now_utc()
        return (None, None) if px is None else (px, 0.0)

    def feed(sym, session=None):
        n = asked["poll", sym]  # the poll asks once per name of the universe
        asked["poll", sym] += 1
        now = datetime.now(timezone.utc).isoformat()
        return [{"key": x["key"], "symbol": sym, "title": x["title"], "link": "", "published": now, "description": ""}
                for x in (sc["polls"][n] if n < len(sc["polls"]) else []) if x["symbol"] == sym]

    def score_batch(items, model, timeout=90):
        out = news_live.Scores()  # with its facts, as the real call: the engine journals the call from them
        if not items:
            return out
        t0 = time.monotonic()
        if sc["score_orphan"] and not asked["orphan"]:  # what a scorer child of a dead engine would be: left running
            asked["orphan"] += 1
            child = subprocess.Popen(["sleep", "60"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
            Path(sent + ".orphan").write_text(str(child.pid))
        while sc["score_delay_s"] == "never":
            time.sleep(3600)
        time.sleep(sc["score_delay_s"])
        out.update({x["key"]: {"score": sc["scores"].get(x["key"], 5), "why": "stub"} for x in items})
        out.facts.update(model=model, prompt=news_live.PROMPT_ID, sent=len(items), answered=len(out),
                         wall_s=round(time.monotonic() - t0, 3))
        return out

    def send(title, body, cfg, priority="default", force=False):
        row = {"at": datetime.now(timezone.utc).isoformat(), "title": title, "body": body, "priority": priority}
        with open(sent, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return ["ntfy"] if sc["send_ok"] else []

    news_live.load_config = load_config
    news_live.live_price = live_price
    news_live._feed = news_live.fetch_headlines = feed
    news_live.score_batch = score_batch
    news_live.notify.send = send
    news_live.official_opens = lambda symbols, day: {s: sc["opens"][s] for s in symbols if s in sc["opens"]}
    news_live.bars_since = lambda sym, since, now: [(datetime.fromisoformat(t), lo, c) for t, lo, c in sc["bars"]]
    news_live.code_stamp = lambda: {"commit": sc["commit"], "dirty": False, "started": journal.now_utc()}
    # the checker seams answer as tests/test_core.py sets them: a confirmed company announcement, scored 10 again
    news_live.verify_headline = lambda item, model, timeout=60: {"kind": "company_announcement", "confirmed": True, "why": "test"}
    news_live.rescore_headline = lambda item, model, timeout=None: 10


def install_tripwire(path: str) -> None:
    """Whatever a stand-in missed stops here, before it leaves the machine: an HTTP call or a connection to a host
    other than 127.0.0.1, or a `claude` or `git` process, writes the call's name to `path` and ends the process with
    97. It does not raise: the engine's loop catches every Exception and would go on."""

    def guard(owner, attr: str, name: str, stays_here) -> None:
        real = getattr(owner, attr)

        def call(*a, **k):
            try:
                ok = stays_here(*a, **k)
            except Exception:  # noqa: BLE001 - a call that cannot be read is not known to stay here
                ok = False
            if not ok:
                try:
                    with open(path, "a") as f:
                        f.write(name + "\n")
                finally:
                    os._exit(97)
            return real(*a, **k)
        setattr(owner, attr, call)

    def local(url) -> bool:
        return urlsplit(url).hostname == "127.0.0.1"

    def program(args) -> str:  # what a Popen starts: the first word of a shell line, else the first item
        return os.path.basename(os.fsdecode(args.split()[0] if isinstance(args, str) else args[0]))

    guard(requests.sessions.Session, "request", "requests.sessions.Session.request", lambda self, method, url, *a, **k: local(url))
    guard(urllib.request, "urlopen", "urllib.request.urlopen", lambda url, *a, **k: local(getattr(url, "full_url", url)))
    guard(socket, "create_connection", "socket.create_connection", lambda address, *a, **k: address[0] == "127.0.0.1")
    guard(subprocess.Popen, "__init__", "subprocess.Popen", lambda self, args, *a, **k: program(args) not in ("claude", "git"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    for name in ("--state-dir", "--scenario", "--sent"):
        ap.add_argument(name, required=True)
    args, options = ap.parse_known_args(argv)
    given = json.loads(Path(args.scenario).read_text())
    unknown = sorted(set(given) - set(SCENARIO))
    if unknown:  # a misspelt key would leave its default in place and the test would pass for the wrong reason
        ap.error("unknown scenario keys: " + ", ".join(unknown))
    journal.STATE = Path(args.state_dir)
    install({**SCENARIO, **given}, args.sent)
    install_tripwire(args.sent + ".tripwire")
    return cli.main(["news-live", *options])


if __name__ == "__main__":
    sys.exit(main())
