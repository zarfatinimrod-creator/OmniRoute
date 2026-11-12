"""uptime-report (supervisor spec 4.6, 8, 11.2): the uptime log as the day's percent of market time with its stops
checked, its causes, and the close slot's lines (R4c, R9, R11). The rows are built here as the parent writes them;
nothing here starts a process, and the command runs against a temporary state directory."""

from helpers import no_phone  # noqa: F401  (first: a test run must never reach the owner's phone)

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from aitrader import __main__ as cli
from aitrader import journal, supervise, uptime

CFG = supervise.load_cfg()  # the spec's defaults: mark_gap_max_seconds 150, up_hb_max_seconds 60, stops_stale 120


def row(t: str, ev: str, **fields) -> dict:
    """One row of the uptime log, as supervise.append_row writes it."""
    return {"t": t, "ev": ev, "sup": 4242, **fields}


def marks(day: str, first: str, last: str, outage: tuple[str, str] | None = None, skip: tuple = (),
          **fields) -> list[dict]:
    """One mark a minute from first to last (UTC), hb 5; inside the outage [start, end) hb is the seconds since its
    start, the exit. skip: the minutes ("HH:MM") that have no mark. fields: the other values of every mark."""
    t, end = (datetime.fromisoformat(f"{day}T{x}+00:00") for x in (first, last))
    lo, hi = (datetime.fromisoformat(f"{day}T{x}+00:00") for x in outage) if outage else (None, None)
    out = []
    while t <= end:
        if t.strftime("%H:%M") not in skip:
            hb = (t - lo).total_seconds() if lo and lo <= t < hi else 5
            out.append(row(t.isoformat(), "mark", **{"hb": hb, "stop": None, "n": 0, "open": True, "blind": [],
                                                      "dm": None, "left": None, **fields}))
        t += timedelta(minutes=1)
    return out


def edit(rows: list[dict], t: str, **fields) -> None:
    """Changes the mark at t (UTC, ISO-8601) in place."""
    next(r for r in rows if r["ev"] == "mark" and r["t"] == t).update(fields)


def out_of(*args: str) -> str:
    """The command's stdout, run against journal.STATE (the test's temporary directory)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.main(["uptime-report", *args])
    assert code == 0, code
    return out.getvalue()


class Report(unittest.TestCase):
    def state(self, rows: list[dict]) -> Path:
        """A temporary state directory holding rows as state/uptime.jsonl; journal.STATE points at it."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "uptime.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                          encoding="utf-8")
        self.enterContext(mock.patch.object(journal, "STATE", tmp))
        return tmp

    def test_one_known_gap_gives_exactly_99_percent(self):
        rows = marks("2026-11-12", "14:30:00", "21:00:00", outage=("16:00:00", "16:03:54"))
        rows += [row("2026-11-12T16:00:00+00:00", "exit", rc=1, why="exit"), row("2026-11-12T16:03:54+00:00", "up", down_s=234, blind_s=0, handover_s=None)]
        r = uptime.day_report(sorted(rows, key=lambda x: x["t"]), date(2026, 11, 12), CFG)
        self.assertEqual((r["session_s"], r["unprotected_s"], r["uptime"], r["missing_marks"], r["by_cause"]["restart"]), (23400, 234, 0.99, 0, 234))
        self.assertIn("99.00%", uptime.render([r], CFG))

    def test_five_minutes_without_marks_are_a_gap_of_300_s_and_4_missing_marks(self):  # no marks from 15:01 to 15:04
        rows = marks("2026-11-12", "14:30:00", "21:00:00", skip=("15:01", "15:02", "15:03", "15:04"))
        r = uptime.day_report(rows, date(2026, 11, 12), CFG)
        self.assertEqual((r["unprotected_s"], r["missing_marks"], r["by_cause"]["gap"]), (300, 4, 300))

    def test_an_early_close_day_has_12600_session_seconds(self):  # Review Focus 3: 2026-11-27, a full day of marks
        rows = marks("2026-11-27", "14:30:00", "18:00:00")  # 09:30 to 13:00 New York
        r = uptime.day_report(rows, date(2026, 11, 27), CFG)
        self.assertEqual((r["session_s"], r["unprotected_s"], r["uptime"]), (12600, 0, 1.0))

    def test_close_lines_and_only_the_notify_form_prints_them(self):  # an exit at 20:50 UTC with no up; a tripped row; no alert rows
        rows = [row("2026-11-12T13:07:00+00:00", "start", child=2, n=1, backoff_s=0),
                row("2026-11-12T13:08:00+00:00", "up", down_s=None, blind_s=0, handover_s=None, held={"MU": 708.97})]
        rows += marks("2026-11-12", "14:30:00", "20:50:00", n=1, stop=30)
        loop = datetime.fromisoformat("2026-11-12T20:48:58+00:00")
        for n in range(2, 7):  # a crash loop: five restarts (a start's n is restarts_today + 1); the sixth fall trips
            t = loop + timedelta(seconds=12 * (n - 2))
            rows += [row(t.isoformat(), "exit", child=n, rc=1, signal=None, ran_s=10.0, why="exit"),
                     row((t + timedelta(seconds=2)).isoformat(), "start", child=n + 1, n=n, backoff_s=2)]
        rows += [row("2026-11-12T20:50:00+00:00", "exit", child=7, rc=1, signal=None, ran_s=12.0, why="exit"),
                 row("2026-11-12T20:50:00+00:00", "tripped", restarts=5, window_s=600, trips_today=1),
                 row("2026-11-12T20:50:00+00:00", "sup_stop", why="crash_loop", rc=75)]
        r = uptime.day_report(rows, date(2026, 11, 12), CFG)
        self.assertEqual([l["id"] for l in uptime.close_lines(r, rows, CFG)], ["R4c", "R11"])
        self.assertTrue(all(l["text"].endswith("כסף נייר") for l in uptime.close_lines(r, rows, CFG)))
        self.assertIn("המנוע נפל 6 פעמים,", uptime.close_lines(r, rows, CFG)[-1]["text"])  # falls: as R3 said, 5 + 1
        tmp = self.state(rows)
        self.assertEqual(("\"notify\"" in out_of("--day", "2026-11-12"), "\"notify\"" in out_of("--day", "2026-11-12", "--notify")), (False, True))
        self.assertEqual([p.name for p in tmp.iterdir()], ["uptime.jsonl"])  # read-only: nothing written beside it

    def test_an_empty_log_is_a_day_with_no_protected_second(self):
        self.assertEqual(uptime.day_report([], date(2026, 11, 12), CFG)["uptime"], 0.0)

    def test_each_cause_is_counted_once_under_the_first_that_fits(self):
        """Restart, hang, handover, gap, stale stops (the brief's order). A hang with the switch off: hb above
        up_hb_max_seconds in the marks, with stale stops inside it (hang wins). A hang kill: the hang row is written
        after the kill, so the hang's start comes from the marks, and the mark with no beat right after the kill
        goes on with the hang. A handover: the planned exit to the next parent's up. Marks 300 s apart whose later
        one shows an old beat are a gap only: a VM pause freezes the parent and the engine together, so the beat is as
        old as the pause (spec 4.6 names the mark gap the VM pause, the dead machine, the stalled parent). Marks a
        minute apart with an old beat (15:01-15:03, 16:01-16:02) are still a hang."""
        held = {"MU": 708.97}
        rows = [row("2026-11-12T13:07:00+00:00", "start", child=7, n=1, backoff_s=0),
                row("2026-11-12T13:08:00+00:00", "up", down_s=None, blind_s=0, handover_s=None, held=held)]
        rows += marks("2026-11-12", "14:30:00", "21:00:00", skip=("19:01", "19:02", "19:03", "19:04"), n=1, stop=30)
        for t, hb, stop in (("15:01", 65, 95), ("15:02", 125, 155), ("15:03", 185, 215), ("15:04", 5, 200),
                            ("16:01", 65, 30), ("16:02", 125, 30), ("19:05", 290, 30)):
            edit(rows, f"2026-11-12T{t}:00+00:00", hb=hb, stop=stop)
        edit(rows, "2026-11-12T16:03:00+00:00", hb=None, stop=None, n=None)
        edit(rows, "2026-11-12T17:19:00+00:00", hb=None, stop=None, n=None)
        rows += [row("2026-11-12T16:02:30+00:00", "hang", child=7, hb=185.0, phase="score", killed_with="TERM"),
                 row("2026-11-12T16:02:30+00:00", "exit", child=7, rc=None, signal=15, ran_s=900.0, why="hang"),
                 row("2026-11-12T16:02:31+00:00", "start", child=8, n=2, backoff_s=0),
                 row("2026-11-12T16:03:20+00:00", "up", child=8, down_s=50, blind_s=200, handover_s=None, held=held),
                 row("2026-11-12T17:18:00+00:00", "exit", child=8, rc=143, signal=None, ran_s=4000.0, why="planned"),
                 row("2026-11-12T17:18:01+00:00", "sup_stop", why="handover", rc=76),
                 row("2026-11-12T17:18:30+00:00", "sup_start", until="16:05", handover=True),
                 row("2026-11-12T17:18:30+00:00", "start", child=9, n=2, backoff_s=0),
                 row("2026-11-12T17:19:10+00:00", "up", child=9, down_s=None, blind_s=70, handover_s=70.0, held=held)]
        r = uptime.day_report(rows, date(2026, 11, 12), CFG)
        self.assertEqual(r["by_cause"], {"restart": 0, "hang": 380, "handover": 70, "gap": 300, "stale_stops": 60})
        self.assertEqual((r["unprotected_s"], r["exposed_s"], r["missing_marks"], r["handovers"], r["restarts"],
                          r["longest_blind_s"]), (810, 810, 4, [70.0], 1, 200))

    def test_r11_counts_only_the_r4_and_r4b_lines_that_reached_a_channel(self):
        """Ruling P6 and the controller's addition: a line counts as reported when one of its rows says sent true
        (counted once, by its id); a line that never did reports nothing, and its minutes count toward R11."""
        rows = marks("2026-11-12", "14:30:00", "21:00:00", skip=tuple(f"15:{m:02d}" for m in range(1, 15)))
        r4 = {"id": "R4-1", "kind": "R4", "text": "...", "m": 10}  # 15 unprotected minutes, 15:00 to 15:15
        r4b = {"id": "R4b-2", "kind": "R4b", "text": "...", "m": 5}
        rows += [row("2026-11-12T15:15:05+00:00", "alert", **r4, sent=False),
                 row("2026-11-12T15:15:06+00:00", "alert", **r4b, sent=False),
                 row("2026-11-12T15:16:05+00:00", "alert", **r4, sent=True),
                 row("2026-11-12T15:17:05+00:00", "alert", **r4, sent=True)]  # a second true row of R4-1: once
        r = uptime.day_report(rows, date(2026, 11, 12), CFG)
        lines = uptime.close_lines(r, rows, CFG)
        self.assertEqual([l["id"] for l in lines], ["R11"])
        self.assertIn(" 15 דקות ", lines[0]["text"])
        rows.append(row("2026-11-12T15:18:05+00:00", "alert", **r4b, sent=True))
        self.assertEqual(uptime.close_lines(uptime.day_report(rows, date(2026, 11, 12), CFG), rows, CFG), [])

    def test_open_at_close_and_r4cs_held_are_the_held_of_the_days_last_up(self):  # ruling P11
        rows = [row("2026-11-12T13:08:00+00:00", "up", down_s=None, blind_s=0, handover_s=None,
                    held={"MU": 708.97, "AAA": 10.0})]
        rows += marks("2026-11-12", "14:30:00", "20:30:00", n=1, stop=30)
        rows += [row("2026-11-12T17:59:15+00:00", "exit", child=7, rc=1, signal=None, ran_s=900.0, why="exit"),
                 row("2026-11-12T18:00:00+00:00", "up", child=8, down_s=45, blind_s=45, handover_s=None,
                     held={"MU": 708.97}),  # AAA was sold
                 row("2026-11-12T20:30:00+00:00", "exit", child=8, rc=1, signal=None, ran_s=9000.0, why="exit")]
        r = uptime.day_report(sorted(rows, key=lambda x: x["t"]), date(2026, 11, 12), CFG)
        self.assertEqual(r["open_at_close"], {"MU": 708.97})
        r4c = uptime.close_lines(r, rows, CFG)[0]
        self.assertEqual((r4c["id"], r4c["priority"]), ("R4c", "high"))
        self.assertIn("מ-22:30 עד סוף המסחר: 30 דקות בלי בדיקת סטופים. פתוח: MU (סטופ 708.97).",
                      r4c["text"])  # 20:30 UTC on the owner's clock; AAA, sold, is not in it

    def test_r4c_needs_an_engine_outage_as_long_as_r4_reports_and_r11_takes_what_it_leaves(self):
        """Stale stops at the close are a live engine's (R6), not "the engine did not run"; an outage shorter than
        outage_report_seconds (180) gets no line of its own, as for R4 and R4b. Both minutes go to R11."""
        stale = marks("2026-11-12", "14:30:00", "21:00:00", n=1, stop=30)
        for m in range(51, 61):
            edit(stale, (datetime.fromisoformat("2026-11-12T20:00:00+00:00") + timedelta(minutes=m)).isoformat(),
                 stop=200)
        short = marks("2026-11-12", "14:30:00", "20:59:00")
        short.append(row("2026-11-12T20:58:30+00:00", "exit", child=7, rc=1, signal=None, ran_s=9000.0, why="exit"))
        for rows, cause, s in ((stale, "stale_stops", 600), (sorted(short, key=lambda x: x["t"]), "restart", 90)):
            r = uptime.day_report(rows, date(2026, 11, 12), CFG)
            self.assertEqual((r["by_cause"][cause], r["unprotected_s"]), (s, s))
            self.assertEqual([l["id"] for l in uptime.close_lines(r, rows, CFG)], ["R11"])

    def test_a_dead_man_alarm_is_true_when_the_engine_was_down_and_false_when_only_ntfy_was(self):
        """Spec 11.2: dead-man alarms, true and false. A `new_seq` row comes at the first ping after the old message
        was due, so the delay_seconds - seq_margin_seconds before it lie in the silence the alarm came from. True: the
        engine was down then (an exit at 15:00, back at 15:08). False: the marks show a fresh beat all through and the
        pings failed (17:00:30 to 17:05:30). False too: the next morning's new seq after a cancel that failed after the
        close (what went out was DM3, or the DM1 that R9 calls false), although the night before it is a gap."""
        rows = marks("2026-11-12", "14:30:00", "21:05:00", outage=("15:00:00", "15:08:00"))
        rows += [row("2026-11-12T15:00:00+00:00", "exit", child=7, rc=1, signal=None, ran_s=900.0, why="exit"),
                 row("2026-11-12T15:00:01+00:00", "start", child=8, n=2, backoff_s=1),
                 row("2026-11-12T15:08:00+00:00", "up", child=8, down_s=480, blind_s=480, handover_s=None, held={}),
                 row("2026-11-12T15:08:00+00:00", "deadman", what="new_seq")]
        failed = datetime.fromisoformat("2026-11-12T17:00:00+00:00")
        rows += [row((failed + timedelta(seconds=30 * k)).isoformat(), "deadman", what="ping_failed", status="URLError")
                 for k in range(1, 12)]
        rows += [row("2026-11-12T17:06:00+00:00", "deadman", what="new_seq"),
                 row("2026-11-12T17:06:00+00:00", "deadman", what="recovered"),
                 row("2026-11-12T21:03:00+00:00", "deadman", what="cancel_failed", dm3=True),
                 row("2026-11-12T21:03:01+00:00", "deadman", what="disarmed")]
        rows += marks("2026-11-13", "13:08:00", "13:12:00")
        rows.append(row("2026-11-13T13:10:00+00:00", "deadman", what="new_seq"))
        rows.sort(key=lambda x: x["t"])
        r = uptime.day_report(rows, date(2026, 11, 12), CFG)
        self.assertEqual(r["deadman"],
                         {"alarms": 2, "alarms_true": 1, "alarms_false": 1, "ping_failed": 11, "cancel_failed": 1})
        self.assertIn("dead-man alarms 2 (true 1, false 1)", uptime.render([r], CFG))
        self.assertEqual(uptime.day_report(rows, date(2026, 11, 13), CFG)["deadman"],
                         {"alarms": 1, "alarms_true": 0, "alarms_false": 1, "ping_failed": 0, "cancel_failed": 0})

    def test_the_days_counts_and_r9(self):
        """restarts (the parent's own count: n rises at a counted restart, a handover's start repeats it), commits,
        failed ntfy lines, the lowest `left`, the dead-man's rows, the largest stop gap of the day; R9 when the close
        cancel failed and DM3 could not be placed."""
        rows = marks("2026-11-12", "14:30:00", "21:00:00", left=250)
        edit(rows, "2026-11-12T20:00:00+00:00", left=240)
        rows += [row("2026-11-12T13:07:00+00:00", "start", child=7, n=1, backoff_s=0),
                 row("2026-11-12T13:07:05+00:00", "code", child=7, commit="abc1234", dirty=False, code_changed=False),
                 row("2026-11-12T15:00:00+00:00", "exit", child=7, rc=1, signal=None, ran_s=6000.0, why="exit"),
                 row("2026-11-12T15:00:01+00:00", "start", child=8, n=2, backoff_s=0),
                 row("2026-11-12T15:00:40+00:00", "up", child=8, down_s=40, blind_s=40, handover_s=None, held={}),
                 row("2026-11-12T15:00:41+00:00", "code", child=8, commit="abc1234", dirty=False, code_changed=False),
                 row("2026-11-12T17:18:30+00:00", "start", child=9, n=2, backoff_s=0),
                 row("2026-11-12T16:00:00+00:00", "alert", id="R6-1", kind="R6", text="...", sent=False),
                 row("2026-11-12T16:30:00+00:00", "deadman", what="new_seq"),
                 row("2026-11-12T16:31:00+00:00", "deadman", what="ping_failed", status=429),
                 row("2026-11-12T16:32:00+00:00", "deadman", what="ping_failed", status="URLError"),
                 row("2026-11-12T21:01:00+00:00", "deadman", what="cancel_failed", dm3=False)]
        health = [{"at": "2026-11-11T20:00:00+00:00", "stop_gap_max_s": 99.0},
                  {"at": "2026-11-12T15:00:00+00:00", "stop_gap_max_s": 18.6},
                  {"at": "2026-11-12T20:00:00+00:00", "stop_gap_max_s": 31.2},
                  {"at": "2026-11-12T20:05:00+00:00", "stop_gap_max_s": None}]
        r = uptime.day_report(sorted(rows, key=lambda x: x["t"]), date(2026, 11, 12), CFG, health)
        self.assertEqual((r["restarts"], r["trips"], r["commits"], r["ntfy_failed"], r["left_min"], r["deadman"],
                          r["stop_gap_max_s"]),
                         (1, 0, ["abc1234", "abc1234"], 1, 240,
                          {"alarms": 1, "alarms_true": 0, "alarms_false": 1, "ping_failed": 2, "cancel_failed": 1},
                          31.2))
        self.assertIsNone(uptime.day_report(rows, date(2026, 11, 12), CFG)["stop_gap_max_s"])  # no file: null
        self.assertEqual([l["id"] for l in uptime.close_lines(r, rows, CFG)], ["R9", "R11"])  # 40 s: one minute untold
        rows[-1]["dm3"] = True
        self.assertEqual([l["id"] for l in uptime.close_lines(r, rows, CFG)], ["R11"])


if __name__ == "__main__":
    unittest.main()
