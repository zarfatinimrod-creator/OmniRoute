"""Task 8: crypto quiet hours (alerts queue, DST-correct), the morning summary command, delivery exit codes, ack.

The network never runs: notify's requests.post is stubbed in every test, the clock is journal.now_utc.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from aitrader import __main__ as cli
from aitrader import data, journal, notify
from aitrader.market import UtcDailyCalendar

IL = ZoneInfo("Asia/Jerusalem")
NOW = "2026-11-10T06:30:00+00:00"  # 08:30 Israel (winter); last final bar = 2026-11-09


def utc_of(y, mo, d, hh, mm) -> str:
    return datetime(y, mo, d, hh, mm, tzinfo=IL).astimezone(timezone.utc).isoformat()


class Env(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        self.posts: list = []

        class R:
            ok = True

        def post(url, **kw):
            self.posts.append((url, kw.get("json")))
            return R()

        p = mock.patch.object(notify.requests, "post", post)
        p.start()
        self.addCleanup(p.stop)
        env = mock.patch.dict("os.environ", {"AITRADER_NTFY_TOPIC": "test-topic"})
        env.start()
        self.addCleanup(env.stop)
        s = mock.patch.object(journal, "STATE", self.root)
        s.start()
        self.addCleanup(s.stop)
        self.clock = NOW
        c = mock.patch.object(journal, "now_utc", lambda: self.clock)
        c.start()
        self.addCleanup(c.stop)
        self.crypto = data.load_config("crypto")
        self.stock = data.load_config("stocks")

    def send_crypto(self, title="t", body="b", **kw):
        with journal.use_book("crypto"), contextlib.redirect_stdout(io.StringIO()):
            return notify.send(title, body, self.crypto, **kw)

    def queue(self):
        with journal.use_book("crypto"):
            return journal.load_json("alert_queue.json", []) or []


class QuietHours(Env):
    def test_crypto_queues_at_night_both_dst_dates(self):
        for y, mo, d in ((2026, 10, 25), (2027, 3, 26)):  # the Israel DST switch days
            for hh, mm, queued in ((2, 0, True), (7, 59, True), (8, 0, False)):
                with self.subTest(date=(y, mo, d), at=f"{hh:02d}:{mm:02d}"):
                    self.clock = utc_of(y, mo, d, hh, mm)
                    self.posts.clear()
                    ch = self.send_crypto()
                    if queued:
                        self.assertEqual(ch, ["queued"])
                        self.assertEqual(self.posts, [])
                        self.assertEqual(self.queue()[-1]["queued_at"], self.clock)
                    else:
                        self.assertEqual(ch, ["ntfy"])
                        self.assertEqual(len(self.posts), 1)

    def test_queue_entry_shape_and_force(self):
        self.clock = utc_of(2026, 11, 10, 1, 0)
        self.send_crypto("T", "B", priority="urgent")
        self.assertEqual(self.queue(), [{"queued_at": self.clock, "title": "T", "body": "B", "priority": "urgent"}])
        self.assertEqual(self.send_crypto(force=True), ["ntfy"])  # force bypasses the queue
        self.assertEqual(len(self.queue()), 1)

    def test_stock_sends_at_2322(self):
        self.clock = utc_of(2026, 11, 10, 23, 22)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(notify.send("t", "b", self.stock), ["ntfy"])
        self.assertEqual(len(self.posts), 1)
        self.assertFalse((self.root / "alert_queue.json").exists())


class Summary(Env):
    """summary --book crypto, run through the CLI with a crypto state dir under self.root."""

    def run_cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["summary", "--book", "crypto", *args])
        text = out.getvalue()
        return code, json.loads(text[text.index("{"):text.rindex("}") + 1]) if "{" in text else None

    def cdir(self) -> Path:
        d = self.root / self.crypto["market"]["state_subdir"]
        d.mkdir(parents=True, exist_ok=True)
        return d

    def healthy(self, decision="2026-11-09", as_of="2026-11-10T00:15:00+00:00"):
        d = self.cdir()
        with journal.use_book("crypto"):
            journal.append("decisions.jsonl", {"event": "revised_close", "x": 1})
            journal.append("decisions.jsonl", {"date": decision, "logged_at": as_of, "due_rebalance": False, "weights": {},
                                               "diag": {}, "overrides": {}, "earnings_blackout": {}, "preview": []})  # cycle.py's row
        (d / "latest.json").write_text(json.dumps({"date": decision, "as_of_utc": as_of}))

    def test_summary_exit_codes(self):
        self.healthy()
        code, out = self.run_cli()
        self.assertEqual((code, out["urgent"]), (0, []))
        code, out = self.run_cli("--send")  # delivered, nothing urgent
        self.assertEqual((code, out["channels"]), (0, ["ntfy"]))
        self.assertEqual(len(self.posts), 1)
        # urgent item: a stale decision
        self.clock = "2026-11-12T06:30:00+00:00"
        code, out = self.run_cli()
        self.assertEqual(code, 2)
        self.assertTrue(out["urgent"])
        self.assertTrue(out["text"].startswith("URGENT"))
        code, out = self.run_cli("--send")
        self.assertEqual(code, 2)
        # not delivered: no ntfy, no telegram
        with mock.patch.dict("os.environ", {}, clear=True):
            code, out = self.run_cli("--send")
        self.assertEqual((code, out["channels"]), (3, []))

    def test_ack_only_up_to_newest(self):
        self.healthy()
        self.cdir()
        q = [{"queued_at": f"2026-11-10T0{h}:00:00+00:00", "title": f"t{h}", "body": "b", "priority": "default"} for h in (1, 2, 3)]
        (self.cdir() / "alert_queue.json").write_text(json.dumps(q))
        code, out = self.run_cli("--ack", "2026-11-10T02:00:00+00:00")
        self.assertEqual([x["title"] for x in self.queue()], ["t3"])
        # --send auto-acks up to newest and only after a delivery
        (self.cdir() / "alert_queue.json").write_text(json.dumps(q))
        code, out = self.run_cli()
        self.assertEqual(out["newest"], q[-1]["queued_at"])
        self.assertEqual(len(self.queue()), 3)  # no --send: untouched
        with mock.patch.dict("os.environ", {}, clear=True):
            self.run_cli("--send")
        self.assertEqual(len(self.queue()), 3)  # not delivered: kept
        self.run_cli("--send")
        self.assertEqual(self.queue(), [])
        # an item queued after the summary was built survives an ack of the older newest
        (self.cdir() / "alert_queue.json").write_text(json.dumps(q))
        self.run_cli("--ack", q[0]["queued_at"])
        self.assertEqual(len(self.queue()), 2)

    def test_summary_flags_missing_decision_and_broken_chain_as_urgent(self):
        self.healthy(decision="2026-11-07")  # expected 2026-11-09
        with journal.use_book("crypto"):
            (journal.STATE / "decisions.jsonl").write_text(
                (journal.STATE / "decisions.jsonl").read_text().replace("2026-11-07", "2026-11-06"))
        code, out = self.run_cli()
        self.assertEqual(code, 2)
        joined = "\n".join(out["urgent"])
        self.assertIn("decisions.jsonl", joined)  # broken chain
        self.assertIn("2026-11-09", joined)  # the missing expected decision date

    def test_decision_row_alone_satisfies_expected_decision(self):
        self.healthy()  # no pending.json; only the real-shaped decisions row for 2026-11-09
        self.assertFalse((self.cdir() / "pending.json").exists())
        code, out = self.run_cli()
        self.assertEqual((code, out["urgent"]), (0, []))

    def test_bare_ack_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["summary", "--book", "crypto", "--ack"])

    def test_stale_latest_and_repeated_skips_urgent(self):
        self.healthy(as_of="2026-11-09T00:15:00+00:00")  # 30 h before NOW > 26
        code, out = self.run_cli()
        self.assertTrue(any("latest.json" in u for u in out["urgent"]))
        self.healthy(as_of="2026-11-10T00:15:00+00:00")
        d = self.cdir()
        (d / "skips.jsonl").write_text(json.dumps({"logged_at": "2026-11-10T00:12:00+00:00", "reason": "stale"}) + "\n")
        self.assertEqual(self.run_cli()[0], 0)  # one skip is not urgent
        with (d / "skips.jsonl").open("a") as f:
            f.write(json.dumps({"logged_at": "2026-11-10T01:07:00+00:00", "reason": "stale"}) + "\n")
        code, out = self.run_cli()
        self.assertEqual(code, 2)
        self.assertTrue(any("skip" in u for u in out["urgent"]))

    def test_queued_urgent_item_leads_and_counts(self):
        self.healthy()
        q = [{"queued_at": "2026-11-10T02:00:00+00:00", "title": "Hack", "body": "x", "priority": "urgent"}]
        (self.cdir() / "alert_queue.json").write_text(json.dumps(q))
        code, out = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("Hack", out["urgent"][0])

    # ---- final review items 2b, 5, 7, 8 ------------------------------------------------------------------------
    def pending(self, **kw):
        (self.cdir() / "pending.json").write_text(json.dumps({"decision_date": "2026-11-09", **kw}))

    def test_unapplied_sweep_config_change_is_urgent(self):
        """Item 2b: the sweep shipped the candidate only after an ablation (dsr.json config_change_needed) and
        books.crypto does not carry the overrides yet: urgent. Applied, not needed, or crypto_base shipped: not urgent.
        Trading the candidate while the sweep shipped crypto_base is urgent too."""
        self.healthy()
        d = self.cdir()

        def dsr(**kw):
            (d / "dsr.json").write_text(json.dumps({"profile": "crypto", "value": 0.4, "n": 160, **kw}))
            return self.run_cli()

        code, out = dsr(config_change_needed=True, overrides={"risk.atr_stop_mult": 0.0})
        self.assertEqual(code, 2)
        self.assertTrue(any("risk.atr_stop_mult" in u and "not applied" in u for u in out["urgent"]), out["urgent"])
        code, out = dsr(config_change_needed=True, overrides={"universe": ["BTC-USD"], "risk.dd_reentry_ref": "unset"})
        self.assertTrue(any("universe" in u and "risk.dd_reentry_ref" not in u for u in out["urgent"]), out["urgent"])
        for kw in ({"config_change_needed": True, "overrides": {"risk.atr_stop_mult": 3.0, "risk.dd_reentry_ref": "unset",
                                                                "universe": ["ETH-USD", "BTC-USD"]}},  # already applied
                   {"config_change_needed": False, "overrides": {}}):
            with self.subTest(kw=kw):
                code, out = dsr(**kw)
                self.assertEqual((code, out["urgent"]), (0, []))
        (d / "dsr.json").write_text(json.dumps({"profile": "crypto_base", "value": 0.4, "n": 160, "config_change_needed": True,
                                                "overrides": {"risk.atr_stop_mult": 0.0}}))
        code, out = self.run_cli()  # books.crypto.ship_profile is "crypto": trading a profile the sweep did not ship
        self.assertEqual(code, 2)
        self.assertTrue(any("crypto_base" in u for u in out["urgent"]), out["urgent"])
        self.assertFalse(any("risk.atr_stop_mult" in u for u in out["urgent"]))  # the candidate's change is moot

    def test_last_fill_source_listed_and_waiting_fill_urgent(self):
        """Item 5: the summary lists the last fill's source; an order still pending more than
        market.fill_urgent_after_hours after exec_ts is urgent ("fill waiting since <exec_ts>")."""
        self.healthy()
        self.pending(status="executed", exec_ts="2026-11-10T01:00:00+00:00", fill_ts="2026-11-10T02:00:00+00:00",
                     fill_source="BTC-USD:1h,ETH-USD:1m")
        code, out = self.run_cli()
        self.assertEqual((code, out["urgent"]), (0, []))
        self.assertIn("BTC-USD:1h,ETH-USD:1m", out["text"])
        self.assertIn("04:00", out["text"])  # fill_ts 02:00 UTC in Israel time
        lim = self.crypto["market"]["fill_urgent_after_hours"]
        for late, urgent in ((lim + 0.5, True), (lim - 0.5, False)):
            exec_ts = (datetime.fromisoformat(NOW) - timedelta(hours=late)).isoformat()
            self.pending(status="pending", exec_ts=exec_ts)
            code, out = self.run_cli()
            self.assertEqual(any(f"fill waiting since {exec_ts}" in u for u in out["urgent"]), urgent, late)
            self.assertEqual(code, 2 if urgent else 0)
        # the 08:03 Israel summary flags a 01:00 UTC order still unfilled, in winter and in summer
        for day, clock in (("2026-11-10", utc_of(2026, 11, 10, 8, 3)), ("2026-07-10", utc_of(2026, 7, 10, 8, 3))):
            self.clock = clock
            self.healthy(decision=str(UtcDailyCalendar.last_final_bar(datetime.fromisoformat(clock))), as_of=clock)
            self.pending(status="pending", exec_ts=f"{day}T01:00:00+00:00")
            self.assertTrue(any("fill waiting since" in u for u in self.run_cli()[1]["urgent"]), day)

    def test_queued_times_in_israel_time(self):
        """Item 7: queued alerts show their time in Israel time (DST-aware), not UTC."""
        self.healthy()
        q = [{"queued_at": "2026-11-10T01:00:00+00:00", "title": "winter", "body": "b", "priority": "default"},
             {"queued_at": "2026-07-10T01:00:00+00:00", "title": "summer", "body": "b", "priority": "default"}]
        (self.cdir() / "alert_queue.json").write_text(json.dumps(q))
        text = self.run_cli()[1]["text"]
        self.assertIn("03:00 IST winter", text)
        self.assertIn("04:00 IDT summer", text)
        self.assertNotIn("01:00Z", text)

    def test_summary_refuses_the_stock_book(self):
        """Item 8: the expected-date check is UTC-calendar only, so summary refuses --book stocks (exit 1, a message)."""
        err = io.StringIO()
        for argv in (["summary"], ["--book", "stocks", "summary"], ["summary", "--book", "stocks", "--send"]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(argv), 1)
                self.assertEqual(out.getvalue(), "")
        self.assertIn("crypto", err.getvalue())
        self.assertEqual(self.posts, [])

    def test_calendar_helper_used(self):
        self.assertEqual(str(UtcDailyCalendar.last_final_bar(datetime.fromisoformat(NOW))), "2026-11-09")


if __name__ == "__main__":
    unittest.main()
