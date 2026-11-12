"""`uptime-report` (supervisor spec 4.6, 11.2): the uptime log, state/uptime.jsonl, as each New York day's percent of
market time with its stops checked, with its causes, and the lines the 16:22 close slot sends about the day (spec 4.5,
8: R4c, R9, R11).

Read-only: the parent is the log's one writer (spec 4.1). Standard library only, like the parent it reads after.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from . import ownerlines, supervise
from .supervise import NY, _when

CAUSES = ("restart", "hang", "handover", "gap", "stale_stops")  # a second that fits two counts under the first
OUTAGE = CAUSES[:4]  # the engine not running or not beating; stale stops are a live engine's (R6)
GAP_ENDS = ("end_of_day", "signal", "orphaned")  # a parent that ended or was stopped: until the next one, a parent gap


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _timed(rows: list[dict]) -> list[tuple[datetime, dict]]:
    """(t, row) for every row whose `t` can be read, in time order; the sort is stable: the log's order within a second."""
    return sorted(((t, r) for r in rows if (t := _when(r.get("t"))) is not None), key=lambda x: x[0])


def _stretches(timed: list[tuple[datetime, dict]], sup: dict) -> dict[str, list]:
    """Every stretch that cannot be shown as protected (spec 4.6), by cause, as (from, to); to None: still open.
    - an `exit` to the next `up`: "hang" after a hang kill; "handover" when the parent then handed over; "gap" when it
      then ended for the day or was stopped (signal, orphaned) and no parent ran until the next; else "restart" (a
      crash, a trip, a halt, a held lock);
    - two marks more than mark_gap_max_seconds apart: "gap";
    - two marks when the later one shows `hb` above up_hb_max_seconds: "hang". A null `hb` (no beat of this child:
      spec 4.6) goes on with what the mark before it showed: "hang" after a stale beat (the hang row is written after
      the kill, so a hang's start comes from the marks), else "gap";
    - two marks when the later one shows `n` above 0 and `stop` above stops_stale_seconds, or no stop it can read:
      "stale_stops"."""
    out: dict[str, list] = {c: [] for c in CAUSES}
    up_after, after = None, {}  # the next `up`, and the next start, sup_stop or up, walking back from the end
    for t, r in reversed(timed):
        ev = r.get("ev")
        if ev == "exit":
            then = after.get("why") if after.get("ev") == "sup_stop" else None
            cause = ("hang" if r.get("why") == "hang" else "handover" if then == "handover"
                     else "gap" if then in GAP_ENDS else "restart")
            out[cause].append((t, up_after))
        if ev == "up":
            up_after = t
        if ev in ("start", "sup_stop", "up"):
            after = r

    def beat_stale(m: dict) -> bool:
        return _num(m.get("hb")) and m["hb"] > sup["up_hb_max_seconds"]

    marks = [(t, r) for t, r in timed if r.get("ev") == "mark"]
    for (ta, a), (tb, b) in zip(marks, marks[1:]):
        if (tb - ta).total_seconds() > sup["mark_gap_max_seconds"]:
            out["gap"].append((ta, tb))
        if beat_stale(b) or (not _num(b.get("hb")) and beat_stale(a)):
            out["hang"].append((ta, tb))
        elif not _num(b.get("hb")):
            out["gap"].append((ta, tb))
        if _num(b.get("n")) and b["n"] > 0 and not (_num(b.get("stop")) and b["stop"] <= sup["stops_stale_seconds"]):
            out["stale_stops"].append((ta, tb))
    return out


def _by_second(timed: list[tuple[datetime, dict]], day: date, cfg: dict):
    """The session of `day` second by second: (its open, each second's cause or None when it is protected, whether a
    name was held in it); None on a day with no session. The time before the day's first row and after its last is a
    "gap". Held: a mark's `n` above 0, or an `up` row's `held`; a second between two such readings is held when either
    says so, before the first and after the last when that one does, and with no reading at all (nothing shows that
    nothing was held)."""
    hours = supervise.session_hours(day, cfg["calendar"])
    if hours is None:
        return None
    (oh, om), (ch, cm) = hours
    open_ = datetime(day.year, day.month, day.day, oh, om, tzinfo=NY)
    close = datetime(day.year, day.month, day.day, ch, cm, tzinfo=NY)
    size = int((close - open_).total_seconds())

    # ponytail: one slot a second (23,400 a day) is the simplest exact union; a far longer span would want merged
    # sorted intervals instead
    def fill(seconds: list, spans, value) -> None:
        for a, b in spans:
            lo = max(0, int((a - open_).total_seconds()))
            hi = size if b is None else min(size, int((b - open_).total_seconds()))
            for i in range(lo, hi):
                if seconds[i] is None:
                    seconds[i] = value

    stretches = _stretches(timed, cfg["supervisor"])
    today = [t for t, _ in timed if t.astimezone(NY).date() == day]
    stretches["gap"] += [(open_, today[0]), (today[-1], close)] if today else [(open_, close)]
    cause: list = [None] * size
    for c in CAUSES:
        fill(cause, stretches[c], c)
    known = [(t, r["n"] > 0) for t, r in timed if r.get("ev") == "mark" and _num(r.get("n"))]
    known += [(t, bool(r["held"])) for t, r in timed if r.get("ev") == "up" and isinstance(r.get("held"), dict)]
    known.sort(key=lambda x: x[0])
    spans = [(a, b) for (a, ha), (b, hb) in zip(known, known[1:]) if ha or hb]
    if not known:
        spans = [(open_, close)]
    else:
        spans += [(open_, known[0][0])] if known[0][1] else []
        spans += [(known[-1][0], close)] if known[-1][1] else []
    held: list = [None] * size
    fill(held, spans, True)
    return open_, cause, held


def day_report(rows: list[dict], day: date, cfg: dict, health: list[dict] | None = None) -> dict:
    """One New York day of the uptime log (spec 4.6, 11.2). rows: the log's rows (other days' too: an outage that began
    before the day counts from the open); health: the rows of news_health.jsonl, None when there is no such file.
    uptime = 1 - unprotected_s / session_s, null with no session. A second that fits two causes is counted once, under
    the first of CAUSES. restarts: the parent's own count (a start's `n` is its restarts_today + 1: it rises at a
    counted restart and repeats at a handover or a lock refusal). ntfy_failed: the day's alert rows `sent` false (a line
    whose call failed, or that had no topic). open_at_close: the `held` of the day's last `up` row (ruling P11)."""
    timed = _timed(rows)
    today = [r for t, r in timed if t.astimezone(NY).date() == day]

    def of(ev: str) -> list[dict]:
        return [r for r in today if r.get("ev") == ev]

    sec = _by_second(timed, day, cfg)
    open_, cause, held = sec if sec else (None, [], [])
    minutes = {t.replace(second=0, microsecond=0) for t, r in timed if r.get("ev") == "mark"}
    by_cause = {c: cause.count(c) for c in CAUSES}
    unprotected = sum(by_cause.values())
    starts = [r["n"] for r in of("start") if _num(r.get("n"))]
    ups, deadman = of("up"), [r.get("what") for r in of("deadman")]
    gaps = [h["stop_gap_max_s"] for h in health or [] if _num(h.get("stop_gap_max_s"))
            and (t := _when(h.get("at"))) is not None and t.astimezone(NY).date() == day]
    blinds = [r["blind_s"] for r in ups if _num(r.get("blind_s"))]
    lefts = [r["left"] for r in of("mark") if _num(r.get("left"))]
    last_held = ups[-1].get("held") if ups else None
    return {
        "day": day.isoformat(),
        "session_s": len(cause),
        "unprotected_s": unprotected,
        "uptime": round(1 - unprotected / len(cause), 4) if cause else None,
        "missing_marks": sum(open_ + timedelta(minutes=k) not in minutes for k in range(len(cause) // 60)),
        "by_cause": by_cause,
        "exposed_s": sum(1 for c, h in zip(cause, held) if c and h),
        "restarts": sum(b - a for a, b in zip(starts, starts[1:]) if b > a),
        "trips": len(of("tripped")),
        "handovers": [r["handover_s"] for r in ups if r.get("handover_s") is not None],
        "longest_blind_s": max(blinds, default=None),
        "deadman": {"alarms": deadman.count("new_seq"), "ping_failed": deadman.count("ping_failed"),
                    "cancel_failed": deadman.count("cancel_failed")},
        "ntfy_failed": sum(1 for r in of("alert") if r.get("sent") is False),
        "left_min": min(lefts, default=None),
        "commits": [r.get("commit") for r in of("code")],
        "open_at_close": dict(last_held) if isinstance(last_held, dict) else None,
        "stop_gap_max_s": None if health is None else max(gaps, default=None),
    }


def _line(line_id: str, sup: dict, **fields) -> dict:
    return {"id": line_id, "priority": ownerlines.priority(line_id),
            "text": ownerlines.render(line_id, max_bytes=sup["max_line_bytes"], free_chars=sup["free_text_max_chars"],
                                      **fields)}


def close_lines(report: dict, rows: list[dict], cfg: dict) -> list[dict]:
    """The close slot's lines about the day (spec 4.5, 8), in this order:
    - R4c: the day's last outage (restart, hang, handover or gap, not stale stops) was still open at the close and has
      outage_report_seconds or more inside the session, the size R4 and R4b report; {held} is open_at_close;
    - R9: a `deadman` row cancel_failed carries dm3 false (Task 21);
    - R11: the day had a trip, or more unprotected minutes than its lines reported: the `m` of each R4 and R4b alert
      row whose line reached a channel (a row of its id with `sent` true, counted once), plus this call's R4c
      (ruling P6). A line that never got `sent` true reported nothing."""
    sup, day, timed = cfg["supervisor"], date.fromisoformat(report["day"]), _timed(rows)
    lines, reported = [], {}
    sec = _by_second(timed, day, cfg)
    if sec:
        open_, cause, _ = sec
        run = next((k for k, c in enumerate(reversed(cause)) if c not in OUTAGE), len(cause))
        if run >= sup["outage_report_seconds"]:
            reported["R4c"] = round(run / 60)
            lines.append(_line("R4c", sup, time=ownerlines.hhmm(open_ + timedelta(seconds=len(cause) - run),
                                                                 sup["owner_tz"]),
                               m=reported["R4c"], held=ownerlines.held_text(report["open_at_close"],
                                                                            sup["held_names_in_line"])))
    today = [r for t, r in timed if t.astimezone(NY).date() == day]
    if any(r.get("ev") == "deadman" and r.get("what") == "cancel_failed" and r.get("dm3") is False for r in today):
        lines.append(_line("R9", sup))
    reported.update({r.get("id"): r.get("m") for r in today if r.get("ev") == "alert"
                     and r.get("kind") in ("R4", "R4b") and r.get("sent") is True and _num(r.get("m"))})
    m = round(report["unprotected_s"] / 60)
    if report["trips"] or m > sum(reported.values()):
        lines.append(_line("R11", sup, r=report["restarts"], t=report["trips"], m=m))
    return lines


def _text(v) -> str:
    if isinstance(v, dict):
        return ", ".join(f"{k} {x}" for k, x in v.items()) or "none"
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) or "-"
    return "-" if v is None else str(v)


def render(reports: list[dict], cfg: dict) -> str:
    """The page of spec 11.2, one block per report in the order given: the percent and its parts, so that a number
    lowered by the parent's own stalls (gap, missing marks) can be told from one lowered by the engine (restart, hang,
    handover, stale stops)."""
    blocks = []
    for r in reports:
        if r["uptime"] is None:
            blocks.append(f"{r['day']}  no session")
            continue
        d = r["deadman"]
        blocks.append("\n".join([
            f"{r['day']}  uptime {r['uptime']:.2%} (target {cfg['supervisor']['uptime_target']:.0%})",
            f"  session_s {r['session_s']}, protected_s {r['session_s'] - r['unprotected_s']}, unprotected_s"
            f" {r['unprotected_s']}, missing_marks {r['missing_marks']}",
            "  by cause: " + ", ".join(f"{c} {s}" for c, s in r["by_cause"].items()) + f"; exposed_s {r['exposed_s']}",
            f"  restarts {r['restarts']}, trips {r['trips']}, handovers {_text(r['handovers'])}, longest_blind_s"
            f" {_text(r['longest_blind_s'])}",
            f"  dead-man alarms {d['alarms']}, ping_failed {d['ping_failed']}, cancel_failed {d['cancel_failed']};"
            f" ntfy_failed {r['ntfy_failed']}, left_min {_text(r['left_min'])}",
            f"  commits {_text(r['commits'])}; open_at_close {_text(r['open_at_close'])}; stop_gap_max_s"
            f" {_text(r['stop_gap_max_s'])}",
        ]))
    return "\n\n".join(blocks)
