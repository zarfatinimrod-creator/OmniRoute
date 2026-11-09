"""Task 8: crypto quiet hours (alerts queue, DST-correct), the morning summary command, delivery exit codes, ack.

The network never runs: notify's requests.post is stubbed in every test, the clock is journal.now_utc.
"""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
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
            journal.append("decisions.jsonl", {"decision_date": decision, "logged_at": as_of})
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

    def test_calendar_helper_used(self):
        self.assertEqual(str(UtcDailyCalendar.last_final_bar(datetime.fromisoformat(NOW))), "2026-11-09")


if __name__ == "__main__":
    unittest.main()
