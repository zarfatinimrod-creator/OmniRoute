"""A stand-in for the news engine under the supervisor's parent (supervisor spec 11.1): it writes the engine's
heartbeat, then exits, hangs or crashes as a script says. Standard library only, so it starts in a moment; it reaches
nothing outside this machine.

    dummy_child.py --heartbeat FILE --script FILE [--until HH:MM] [--supervised PID]

The script is a JSON list of runs. Start n plays run n and the last run repeats; the number of starts so far is kept
in <script>.n. A run, every key optional (RUN holds the defaults):
  beats         heartbeats to write before `then`; -1: beat for ever
  every_s       seconds between two beats
  first_after_s seconds before the first beat
  then          "exit" (with `code`), "hang" (no more beats, sleep), "crash" (os._exit(code or 1))
  code          the exit code
  ignore_term   SIGTERM changes nothing (else it ends the child with 143, as a planned stop ends the engine)
  held          {symbol: stop}, the names the book holds
  stop_age_s    how old each name's stop look is at a beat: a number, or [[age, beats], ...] played in order, the
                last age repeating
  open          the beat's market_open
  blind         the beat's blind list
  commit        the beat's code.commit
--until is taken and never acted on (ruling P1): the dummy ends only as its script says. --supervised PID is honoured
as the engine honours it (news_live.run): the child asks to die with its parent, does not start under another parent,
and leaves with 143 when its parent is no longer PID.
"""

from __future__ import annotations

import argparse
import ctypes
import itertools
import json
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = {"beats": -1, "every_s": 0.1, "first_after_s": 0, "then": "exit", "code": 0, "ignore_term": False, "held": {},
       "stop_age_s": 0, "open": True, "blind": [], "commit": "abc1234"}


def _utc(t: datetime) -> str:
    return t.replace(microsecond=0).isoformat()


def _ages(stop_age_s):
    """The stop age of each beat in turn."""
    if not isinstance(stop_age_s, list):
        return itertools.repeat(stop_age_s)
    return itertools.chain(*(itertools.repeat(age, n) for age, n in stop_age_s), itertools.repeat(stop_age_s[-1][0]))


def _beat(path: Path, run: dict, step: int, age: float, started: str, supervised: bool) -> None:
    """The engine's heartbeat (Task 4's fields) at the end of a step: phase "idle", every held name looked at `age`
    seconds ago. Written whole: a tmp file, then a rename, as the engine writes it."""
    now = datetime.now(timezone.utc)
    checked = _utc(now - timedelta(seconds=age))
    hb = {"at": _utc(now), "headlines_seen": 0, "positions": len(run["held"]), "queue": 0, "stops_checked_at": checked,
          "buys_blocked": None, "code": {"commit": run["commit"], "dirty": False, "started": started}, "lock": True,
          "pid": os.getpid(), "step": step, "phase": "idle", "market_open": run["open"],
          "held": {sym: {"stop": stop, "checked_at": checked} for sym, stop in run["held"].items()},
          "blind": run["blind"], "blind_since": {sym: checked for sym in run["blind"]}, "blind_told": [],
          "told_through": None, "mismatch_told": None, "supervised": supervised}
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(hb))
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heartbeat", required=True, type=Path)
    ap.add_argument("--script", required=True, type=Path)
    ap.add_argument("--until")  # taken and never acted on
    ap.add_argument("--supervised", type=int)
    a = ap.parse_args(argv)
    runs = json.loads(a.script.read_text())
    count = Path(f"{a.script}.n")
    n = int(count.read_text()) + 1 if count.exists() else 1
    count.write_text(f"{n}\n")
    run = {**RUN, **runs[min(n, len(runs)) - 1]}
    unknown = sorted(set(run) - set(RUN)) + ([] if run["then"] in ("exit", "hang", "crash") else [run["then"]])
    if unknown:  # a misspelt key would quietly play the default and the test would pass for the wrong reason
        print(f"dummy_child: unknown in run {n}: {unknown}", file=sys.stderr)
        return 2
    signal.signal(signal.SIGTERM, signal.SIG_IGN if run["ignore_term"] else lambda *_: sys.exit(143))
    if a.supervised is not None:  # as news_live.run: die with the parent, and never start under another one
        if sys.platform == "linux":
            ctypes.CDLL(None).prctl(1, signal.SIGKILL)  # 1 = PR_SET_PDEATHSIG (linux/prctl.h)
        if os.getppid() != a.supervised:
            return 143
    started = _utc(datetime.now(timezone.utc))
    ages = _ages(run["stop_age_s"])
    time.sleep(run["first_after_s"])
    step = 0
    while run["beats"] < 0 or step < run["beats"]:
        if step:
            time.sleep(run["every_s"])
        if a.supervised is not None and os.getppid() != a.supervised:  # the parent is gone: a planned stop
            return 143
        step += 1
        _beat(a.heartbeat, run, step, next(ages), started, a.supervised is not None)
    if run["then"] == "hang":
        while True:
            time.sleep(3600)
    if run["then"] == "crash":
        os._exit(run["code"] or 1)
    return run["code"]


if __name__ == "__main__":
    sys.exit(main())
