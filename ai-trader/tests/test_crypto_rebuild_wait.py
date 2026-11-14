"""Backlog 71 (b, d): the crypto decide run waits briefly for Yahoo's last 1h bar and says why a rebuild was declined.

On 2026-11-14 the 00:12 UTC run (started about 00:13:20) declined the hourly rebuild of 2026-11-13 and logged no reason;
hourly_day_bars returned all 24 bars at 00:13:47 and a rerun at 00:14:14 rebuilt and decided
(logs/2026-11-14-crypto-night.md). So:
* (d) when the decision bar's daily row is missing and hourly_day_bars declines, the run tries the rebuild again every
  market.rebuild_poll_seconds until it succeeds or market.rebuild_wait_seconds have passed since the first try, then
  falls back to the backlog 68 skip exactly as before. Either key absent (or 0): one try, as before. A run that cannot
  decide that bar anyway (propose, dry run, a decision already recorded) never waits, nor does the stock calendar.
* (b) a declined rebuild has a reason tag (fetch_error:<Type>, hours:<n>, null_value, misaligned_stamp, ...); a run that
  ends in the backlog 68 skip writes one plain row to skips.jsonl (bar, symbols, reason, tries, seconds) and prints a
  "[cycle] backlog 71: ..." line; the backlog 68 event text is unchanged.
The wait runs on cycle._monotonic and cycle._sleep; every test here puts both on one fake clock, so nothing sleeps.
Network stubbed everywhere (data._get_json).
"""

import contextlib
import io
import unittest
from datetime import timedelta
from unittest import mock

import pandas as pd

import test_crypto_hourly_rebuild as hr
from aitrader import cycle, data
from golden_util import FIRST_BAR, frozen_env, load_panel
from test_core import cfg_for
from test_crypto_cycle import I, CryptoBook, read_jsonl

WAIT, POLL = 240, 30
KEYS = ("rebuild_wait_seconds", "rebuild_poll_seconds")


class FakeClock:
    """cycle._monotonic and cycle._sleep on one clock: a sleep moves it, and a stubbed fetch may move it too."""

    def __init__(self):
        self.t = 1000.0
        self.sleeps: list = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s

    @contextlib.contextmanager
    def on(self):
        with mock.patch.object(cycle, "_sleep", self.sleep), mock.patch.object(cycle, "_monotonic", self.monotonic):
            yield self


# test_crypto_cycle.CryptoBook.at (also the harness of test_crypto_hourly_rebuild) stubs hourly_day_bars but not the new
# wait, and that file is not edited here. A book whose config sets both keys would really sleep there on every declined
# rebuild, so every run through it gets a fake clock unless the test runs its own.
_REAL_SLEEP = getattr(cycle, "_sleep", None)
_harness_at = CryptoBook.at


def _at_on_a_fake_clock(self, *a, **kw):
    if getattr(cycle, "_sleep", None) is not _REAL_SLEEP:  # the test set its own clock
        return _harness_at(self, *a, **kw)
    with FakeClock().on():
        return _harness_at(self, *a, **kw)


CryptoBook.at = _at_on_a_fake_clock


class Wait(CryptoBook):
    """The 00:12 UTC run of day I+1; row I missing from Yahoo's daily reply. Helpers borrowed from the backlog 70 tests
    (functions, not the class, so its tests are not collected twice)."""

    gap, row, backlog68, use_profile = hr.Rebuild.gap, hr.Rebuild.row, hr.Rebuild.backlog68, hr.Rebuild.use_profile

    def setUp(self):
        super().setUp()
        self.clock = FakeClock()

    def keys(self, wait=WAIT, poll=POLL) -> None:
        self.cfg["market"].update({"rebuild_wait_seconds": wait, "rebuild_poll_seconds": poll})

    def hours(self, i: int, sym: str, close_mult: float = 1.0) -> list:
        """24 complete hours whose fold is row i of sym (as hr.Rebuild.replies)."""
        r = self.row(i, sym)
        c = r["close"] * close_mult
        return hr.hours_for(r["open"], max(r["high"], c), min(r["low"], c), c, r["volume"])

    def full(self, sym: str, i: int = I) -> dict:
        return hr.day_chart(self.day(i), self.hours(i, sym))

    def short(self, sym: str, i: int = I) -> dict:
        return hr.day_chart(self.day(i), self.hours(i, sym)[:23])

    def run_seq(self, seq: dict, upto: int = I + 1, clock: str | None = None, fetch_s: float = 0.0, **kw):
        """One run with the real helper. seq: {symbol: [reply or exception per call]} (the last one repeats). Each call
        moves the fake clock by fetch_s. Returns (out, [(symbol, clock at the call)], stdout)."""
        left = {s: list(v) for s, v in seq.items()}
        calls = []

        def get(url, params=None, **k):
            sym = next(s for s in left if url == data.CHART_URL.format(sym=s))
            calls.append((sym, self.clock.t))
            self.clock.t += fetch_s
            r = left[sym].pop(0) if len(left[sym]) > 1 else left[sym][0]
            if isinstance(r, Exception):
                raise r
            return r

        buf = io.StringIO()
        kw.setdefault("panel", self.gap(upto, I))
        with mock.patch.object(data, "_get_json", get), self.clock.on(), contextlib.redirect_stdout(buf):
            out = self.at(upto, clock or self.ts(I + 1, 0, 12), patches={"hourly_day_bars": hr.REAL_HOURLY,
                                                                          **kw.pop("patches", {})}, **kw)
        return out, calls, buf.getvalue()

    def skips(self) -> list:
        return read_jsonl(self.state, "skips.jsonl")

    def b71(self, stdout: str) -> list:
        return [x for x in stdout.splitlines() if x.startswith("[cycle] backlog 71:")]

    # ---- (1) declined once, complete after one poll: rebuilt and decided in the same run -------------------------
    def test_second_try_after_one_poll_rebuilds_and_decides(self):
        for profile in ("crypto_base", "crypto"):
            with self.subTest(profile=profile):
                self.use_profile(profile)
                self.clock = FakeClock()
                self.keys()
                seq = {s: [self.short(s), self.full(s)] if s == "BTC-USD" else [self.full(s)] for s in self.coins}
                out, calls, stdout = self.run_seq(seq)
                self.assertEqual(self.clock.sleeps, [POLL])
                self.assertEqual(calls, [("BTC-USD", 1000.0)] + [(s, 1000.0 + POLL) for s in self.coins])  # all or none
                self.assertTrue(out["decided_now"])
                pend = self.pending()
                self.assertEqual((pend["decision_date"], pend["hourly_rebuild"]["bar"]), (self.day(I), self.day(I)))
                self.assertEqual(pend["decision_close"], {s: self.row(I, s)["close"] for s in self.coins})
                self.assertNotIn(self.backlog68(), out["events"])
                self.assertEqual(len([e for e in out["events"] if "נרות שעתיים" in e]), 1)
                self.assertEqual(self.skips(), [])
                self.assertEqual(self.b71(stdout), [])
                # the same decision as a run whose first try already had the 24 hours
                ctrl_state, self.state = self.state, self.mkdtemp()
                self.clock = FakeClock()
                ctrl, _, _ = self.run_seq({s: [self.full(s)] for s in self.coins})
                self.assertEqual(self.clock.sleeps, [])
                ctrl_pend, self.state = self.pending(), ctrl_state
                for k in ("decision_date", "targets", "targets_raw", "stopped", "exec_ts", "decision_close",
                          "preview_at_close", "hourly_rebuild"):
                    self.assertEqual(pend[k], ctrl_pend[k], k)

    # ---- (2) never complete: the old skip, inside the budget, and a skips.jsonl row ------------------------------
    def test_never_complete_ends_in_the_backlog_68_skip_within_the_budget(self):
        for wait, poll, sleeps in ((WAIT, POLL, [POLL] * 8), (100, 30, [30, 30, 30, 10])):
            with self.subTest(wait=wait, poll=poll):
                self.cfg, self.state, self.clock = data.load_config("crypto", "crypto"), self.mkdtemp(), FakeClock()
                ctrl, _, _ = self.run_seq({s: [self.short(s)] for s in self.coins})  # the keys absent: as before
                self.assertIn(self.backlog68(), ctrl["events"])
                self.state, self.clock = self.mkdtemp(), FakeClock()
                self.keys(wait, poll)
                out, calls, stdout = self.run_seq({s: [self.short(s)] for s in self.coins})
                self.assertEqual(self.clock.sleeps, sleeps)
                self.assertLessEqual(sum(self.clock.sleeps), wait)
                starts = [t for s, t in calls]
                self.assertEqual([s for s, _ in calls], ["BTC-USD"] * len(sleeps + [0]))
                self.assertEqual(starts[-1], 1000.0 + wait)  # the last try at the end of the budget, none after
                self.assertEqual((out["decided_now"], out["executed"], out["events"]), (False, [], ctrl["events"]))
                self.assertIsNone(self.pending())
                self.assertEqual(read_jsonl(self.state, "decisions.jsonl"), [])
                self.assertEqual(self.skips(), [{"logged_at": self.ts(I + 1, 0, 12), "event": "rebuild_declined",
                                                 "bar": self.day(I), "symbols": self.coins, "symbol": "BTC-USD",
                                                 "reason": "hours:23", "tries": len(calls), "waited_s": float(wait)}])
                line = self.b71(stdout)
                self.assertEqual(len(line), 1)
                for part in (self.day(I), "BTC-USD", "hours:23", f"{len(calls)} tries", f"{wait:g} s"):
                    self.assertIn(part, line[0])

    def test_propose_never_waits_and_writes_no_row(self):
        self.keys()
        out, calls, stdout = self.run_seq({s: [self.short(s)] for s in self.coins}, propose=True)
        self.assertEqual(out["skipped"], self.backlog68())
        self.assertEqual((self.clock.sleeps, len(calls)), ([], 1))
        self.assertEqual(self.skips(), [])
        self.assertIn("hours:23", self.b71(stdout)[0])  # said on stdout; a proposal writes no state

    # ---- (3) a fetch that keeps failing ends within the budget ---------------------------------------------------
    def test_failing_fetch_ends_within_the_budget(self):
        for err, fetch_s, sleeps, tries in ((RuntimeError("GET failed: connection refused"), 0.0, [POLL] * 8, 9),
                                            (data.Unreachable("Yahoo 1h down"), 50.0, [POLL] * 3, 4),
                                            (data.Unreachable("Yahoo 1h hangs"), 300.0, [], 1)):
            with self.subTest(type(err).__name__, fetch_s=fetch_s):
                self.state, self.clock = self.mkdtemp(), FakeClock()
                self.keys()
                out, calls, stdout = self.run_seq({s: [err] for s in self.coins}, fetch_s=fetch_s)
                self.assertEqual(self.clock.sleeps, sleeps)
                self.assertEqual(len(calls), tries)
                self.assertTrue(all(t <= 1000.0 + WAIT for _, t in calls))  # no try starts after the budget
                self.assertEqual(self.clock.t, calls[-1][1] + fetch_s)  # the run ends with the last try
                self.assertFalse(out["decided_now"])
                self.assertIn(self.backlog68(), out["events"])
                row = self.skips()[-1]
                self.assertEqual((row["reason"], row["tries"], row["waited_s"]),
                                 (f"fetch_error:{type(err).__name__}", tries, self.clock.t - 1000.0))
                self.assertEqual(len(self.b71(stdout)), 1)

    def test_a_helper_that_raises_is_not_tried_again(self):
        self.keys()

        def boom(sym, day):
            raise ValueError("unexpected")

        buf = io.StringIO()
        with self.clock.on(), contextlib.redirect_stdout(buf):
            out = self.at(I + 1, self.ts(I + 1, 0, 12), panel=self.gap(I + 1, I), patches={"hourly_day_bars": boom})
        self.assertEqual(self.clock.sleeps, [])
        self.assertIn(f"backlog 70: no rebuild of {self.day(I)} (ValueError)", buf.getvalue())  # unchanged
        self.assertIn(self.backlog68(), out["events"])
        self.assertEqual((self.skips()[0]["reason"], self.skips()[0]["tries"]), ("error:ValueError", 1))

    # ---- (4) the keys absent (or 0): one try, as before -----------------------------------------------------------
    def test_keys_absent_or_zero_mean_no_wait(self):
        variants = {"absent": {}, "wait only": {"rebuild_wait_seconds": WAIT}, "poll only": {"rebuild_poll_seconds": POLL},
                    "wait 0": {"rebuild_wait_seconds": 0, "rebuild_poll_seconds": POLL},
                    "poll 0": {"rebuild_wait_seconds": WAIT, "rebuild_poll_seconds": 0}}
        for name, extra in variants.items():
            with self.subTest(name):
                self.cfg, self.state, self.clock = data.load_config("crypto", "crypto"), self.mkdtemp(), FakeClock()
                for k in KEYS:
                    self.cfg["market"].pop(k, None)
                self.cfg["market"].update(extra)
                out, calls, _ = self.run_seq({s: [self.short(s), self.full(s)] for s in self.coins})
                self.assertEqual((self.clock.sleeps, calls), ([], [("BTC-USD", 1000.0)]))
                self.assertFalse(out["decided_now"])
                self.assertIn(self.backlog68(), out["events"])
                self.assertEqual([(r["reason"], r["tries"], r["waited_s"]) for r in self.skips()], [("hours:23", 1, 0.0)])

    # ---- (5) the stock calendar never waits and never calls the helper -------------------------------------------
    def test_stock_calendar_never_waits(self):
        full = load_panel()
        cfg = cfg_for(full)
        cfg["risk"]["min_score"] = -1.0
        cfg["market"].update({"rebuild_wait_seconds": WAIT, "rebuild_poll_seconds": POLL})
        idx = full["close"].index
        calls, outs, tmp = [], [], self.mkdtemp()
        with frozen_env(tmp, None), self.clock.on(), mock.patch.object(cycle, "hourly_day_bars", lambda s, d: calls.append(s)):
            cycle.load_config = lambda: cfg
            for n in (FIRST_BAR, FIRST_BAR + 2):  # the second run: yesterday's row missing from the reply
                pn = {k: v.iloc[:n] for k, v in full.items()}
                if n > FIRST_BAR:
                    pn = {k: v.drop(index=idx[n - 2]) for k, v in pn.items()}
                cycle.load_market = lambda c, rng="10y", age=0.1, pn=pn: pn
                outs.append(cycle.run_cycle())
        self.assertEqual((calls, self.clock.sleeps), ([], []))
        self.assertTrue(all(o["decided_now"] for o in outs))
        self.assertFalse((tmp / "skips.jsonl").exists())

    # ---- (6) a present daily row: no wait, no helper call --------------------------------------------------------
    def test_present_daily_row_never_waits(self):
        self.keys()
        calls = []
        with self.clock.on():
            out = self.decide(patches={"hourly_day_bars": lambda s, d: calls.append(s)})
        self.assertTrue(out["decided_now"])
        self.assertEqual((calls, self.clock.sleeps, self.skips()), ([], [], []))

    # ---- a run that cannot decide the bar anyway never waits -----------------------------------------------------
    def test_no_wait_when_the_bar_is_already_decided_or_on_a_dry_run(self):
        self.keys()
        out, _, _ = self.run_seq({s: [self.full(s)] for s in self.coins})  # 00:12: rebuilt and decided
        self.assertTrue(out["decided_now"])
        self.set_bars(I + 1, 1)
        out, calls, stdout = self.run_seq({s: [self.short(s)] for s in self.coins}, clock=self.ts(I + 1, 1, 7))
        self.assertTrue(out["executed"])  # the fill run: the rebuild declines now, the decision stands
        self.assertEqual((self.clock.sleeps, len(calls), self.skips()), ([], 1, []))
        self.assertIn("hours:23", self.b71(stdout)[0])

        self.state, self.clock = self.mkdtemp(), FakeClock()
        out, calls, _ = self.run_seq({s: [self.short(s)] for s in self.coins}, execute=False)
        self.assertEqual((out["decided_now"], self.clock.sleeps, len(calls), self.skips()), (False, [], 1, []))

    def test_declines_decided_by_the_daily_reply_are_not_retried(self):
        """A partial daily row or a daily reply fetched before the bar ended cannot change by waiting: one look, no
        helper call. The partial row is skipped by the stale rule, whose own skips.jsonl row stays the only one."""
        self.keys()
        pn = self.gap(I + 1, I)
        pn["_fetched_at"] = {s: cycle._bar_end_utc(self.idx[I], self.cfg) - timedelta(minutes=20) for s in self.coins}
        out, calls, stdout = self.run_seq({s: [self.full(s)] for s in self.coins}, panel=pn)
        self.assertEqual((calls, self.clock.sleeps), ([], []))
        self.assertIn(self.backlog68(), out["events"])
        self.assertEqual([(r["reason"], r["symbol"], r["tries"]) for r in self.skips()], [("stale_daily_fetch", "BTC-USD", 1)])
        self.assertIn("stale_daily_fetch", self.b71(stdout)[0])

        self.state = self.mkdtemp()
        pn = self.panel(I + 1)
        pn = {**pn, "close": pn["close"].copy()}
        pn["close"].iloc[I, pn["close"].columns.get_loc("ETH-USD")] = float("nan")  # an open, no close
        out, calls, stdout = self.run_seq({s: [self.full(s)] for s in self.coins}, panel=pn)
        self.assertEqual((calls, self.clock.sleeps), ([], []))
        self.assertIn("ETH-USD", out["skipped"])
        self.assertEqual([r["reason"] for r in self.skips()], [out["skipped"]])  # the stale rule's row, as before
        self.assertIn("ETH-USD partial_daily_row", self.b71(stdout)[0])

    # ---- (7) reason tags -----------------------------------------------------------------------------------------
    def test_reason_tags_through_the_run(self):
        btc = self.hours(I, "BTC-USD")
        null_close = [list(r) for r in btc]
        null_close[12][3] = None
        t0 = hr.t0_of(self.day(I))
        cases = {"hours:23": hr.day_chart(self.day(I), btc[:23]),
                 "null_value": hr.day_chart(self.day(I), [tuple(r) for r in null_close]),
                 "misaligned_stamp": hr.chart([t0 + hr.HOUR * k + (900 if k == 9 else 0) for k in range(24)], btc)}
        for tag, reply in cases.items():
            with self.subTest(tag):
                self.state, self.clock = self.mkdtemp(), FakeClock()
                out, _, stdout = self.run_seq({"BTC-USD": [reply], "ETH-USD": [self.full("ETH-USD")]})
                self.assertFalse(out["decided_now"])
                self.assertEqual([(r["reason"], r["symbol"]) for r in self.skips()], [(tag, "BTC-USD")])
                self.assertIn(f"BTC-USD {tag}", self.b71(stdout)[0])


class Tags(unittest.TestCase):
    """cycle.hourly_day_fold: hourly_day_bars' work with the reason of a None; hourly_day_bars keeps its return."""

    def fold(self, reply, fn=None):
        def get(url, params=None, **k):
            if isinstance(reply, Exception):
                raise reply
            return reply

        with mock.patch.object(data, "_get_json", get):
            return (fn or cycle.hourly_day_fold)("BTC-USD", pd.Timestamp(hr.REAL_DAY))

    def test_each_decline_has_its_tag(self):
        day = hr.REAL_DAY
        t0 = hr.t0_of(day)
        stamps = [t0 + hr.HOUR * k for k in range(24)]
        rows = hr.REAL_HOURS

        def with_value(k: int, field: int, v):
            r = [list(x) for x in rows]
            r[k][field] = v
            return hr.day_chart(day, [tuple(x) for x in r])

        cases = {
            "23 hours": (hr.day_chart(day, rows[:23]), "hours:23"),
            "first hour missing": (hr.chart(stamps[1:], rows[1:]), "hours:23"),
            "the day shifted by an hour": (hr.chart([s + hr.HOUR for s in stamps], rows), "hours:23"),
            "no rows": (hr.chart([], []), "hours:0"),
            "null close": (with_value(10, 3, None), "null_value"),
            "null open": (with_value(0, 0, None), "null_value"),
            "nan close": (with_value(4, 3, float("nan")), "bad_value"),
            "zero low": (with_value(4, 2, 0.0), "bad_value"),
            "text close": (with_value(4, 3, "71369.9"), "bad_value"),
            "misaligned stamp": (hr.chart(stamps[:5] + [stamps[5] + 1800] + stamps[6:], rows), "misaligned_stamp"),
            "fractional stamp": (hr.chart(stamps[:5] + [stamps[5] + 0.5] + stamps[6:], rows), "misaligned_stamp"),
            "extra in-day stamp": (hr.chart(stamps + [t0 + 23 * hr.HOUR + 600], rows + [rows[-1]]), "misaligned_stamp"),
            "duplicate stamp": (hr.chart(stamps + [stamps[-1]], rows + [rows[-1]]), "duplicate_stamp"),
            "no close column": ({"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [
                {"open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows]}]}}]}},
                "bad_reply:KeyError"),
            "no result": ({"chart": {"result": None, "error": {"code": "Not Found"}}}, "bad_reply:TypeError"),
            "a list": ([], "bad_reply:TypeError"),
            "fetch RuntimeError": (RuntimeError("GET failed"), "fetch_error:RuntimeError"),
            "fetch Unreachable": (data.Unreachable("Yahoo down"), "fetch_error:Unreachable"),
        }
        for name, (reply, tag) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.fold(reply), (None, tag))
                cycle._HOURLY_WHY.clear()
                self.assertIsNone(self.fold(reply, cycle.hourly_day_bars))  # the return shape is unchanged
                self.assertEqual(cycle._HOURLY_WHY, {"BTC-USD": tag})

    def test_a_complete_day_has_no_tag(self):
        row, why = self.fold(hr.day_chart(hr.REAL_DAY, hr.REAL_HOURS))
        self.assertIsNone(why)
        self.assertEqual(row, self.fold(hr.day_chart(hr.REAL_DAY, hr.REAL_HOURS), cycle.hourly_day_bars))
        self.assertEqual(row["close"], 71369.8984375)


if __name__ == "__main__":
    unittest.main()
