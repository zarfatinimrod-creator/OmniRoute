"""Backlog 72 step 2: the forward record of the Coinbase cross-check, kept by the code. LOG MODE ONLY.

* close_audits.jsonl (plain JSON lines, outside the hash chains): one row per completed R6 audit, alert or not, with
  the cross-check of that decision and a verdict: caught, false_alarm, miss, clean, no_check.
* diag.close_xcheck.final_5m: on a decision bar built from 1h bars, the decision close against the close of Yahoo's
  5-minute bar that starts at 23:55 UTC. A failed or empty fetch is close_5m None; it never reaches the decision.
* `xcheck-tally`: read-only, one line per cross-checked decision and the totals.
* None of it runs with close_xcheck_mode off, and with it on the decision, the order, the events, the alerts and every
  other state file are the same as with it off, but for diag.close_xcheck.
Network stubbed everywhere (test_crypto_cycle.CryptoBook, data._get_json).
"""

import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_crypto_cycle as tcc  # the modules, not the classes: their tests must not be collected twice
import test_crypto_hourly_rebuild as hr
from aitrader import cycle, data, journal
from aitrader.__main__ import main
from test_crypto_close_xcheck import HELD, strip

I = tcc.I
REAL_5M = cycle.close_5m  # the real helper (golden_util.frozen_env stubs it per run)
AUDITS = "close_audits.jsonl"
VERDICTS = {"caught": (8.0, 10.0), "false_alarm": (8.0, 3.0), "miss": (0.0, 10.0), "clean": (0.0, 3.0)}  # Coinbase bp, history bp


class Book(tcc.CryptoBook):
    def fresh(self, mode) -> None:
        self.setUp()
        self.cfg = copy.deepcopy(self.cfg)
        self.cfg["market"]["close_xcheck_mode"] = mode

    def snap(self, outs: list) -> dict:
        files = {}
        for f in sorted(self.state.iterdir()):
            if f.is_file():
                text = f.read_text()
                files[f.name] = [json.loads(x) for x in text.splitlines() if x.strip()] if f.suffix == ".jsonl" else json.loads(text)
        return {"outs": json.loads(json.dumps(outs, default=str)), "files": files, "sent": list(self.sent), "prios": list(self.prios)}

    def same_but_for_the_record(self, log: dict, off: dict) -> None:
        """Log mode against off: everything equal but diag.close_xcheck and the measurement file."""
        self.assertNotIn(AUDITS, off["files"])
        self.assertNotIn("close_xcheck", json.dumps(off))
        self.assertNotIn("final_5m", json.dumps(off))
        rest = {k: v for k, v in log["files"].items() if k != AUDITS}
        self.assertEqual(sorted(rest), sorted(off["files"]))
        self.assertEqual(strip(rest), strip(off["files"]))
        self.assertEqual(strip(log["outs"]), strip(off["outs"]))
        self.assertEqual((log["sent"], log["prios"]), (off["sent"], off["prios"]))
        self.assertNotIn("close_xcheck", json.dumps(log["files"]["pending.json"]))  # the order file is untouched

    def revised(self, bp: float) -> dict:
        """Yahoo's history with BTC's close of bar I moved by bp."""
        p = {**self.p, "close": self.p["close"].copy()}
        p["close"].iloc[I, p["close"].columns.get_loc("BTC-USD")] *= 1 + bp / 1e4
        return p

    def daily(self, mode, cb_bp: float, hist_bp: float, audit_mode=None) -> dict:
        """Decide bar I on Yahoo's daily row, fill it, then the next night's run audits it (R6) and decides I+1."""
        self.fresh(mode)
        self.cb = lambda sym, day: self.agree(sym, day) / (1 + (cb_bp if sym == "BTC-USD" else 0.0) / 1e4)
        outs = [self.decide(seed=self.seed(HELD, I))]
        self.set_bars(I + 1, 1)
        outs.append(self.at(I + 1, self.ts(I + 1, 1, 7)))
        if audit_mode:
            self.cfg["market"]["close_xcheck_mode"] = audit_mode
        outs.append(self.at(I + 1, self.ts(I + 2, 0, 12), panel=self.panel(I + 1, self.revised(hist_bp))))
        self.assertEqual([o["decided_now"] for o in outs], [True, False, True])
        return self.snap(outs)


class ForwardRecord(Book):
    def test_every_audit_writes_one_row_with_its_verdict(self):
        for verdict, (cb_bp, hist_bp) in VERDICTS.items():
            log = self.daily("log", cb_bp, hist_bp)
            rows = log["files"][AUDITS]
            self.assertEqual(len(rows), 1, verdict)  # bar I is audited; bar I+1 is still the decision bar
            r = rows[0]
            self.assertEqual(set(r), {"logged_at", "decision_date", "source", "decision_close", "history_close", "gaps_bps",
                                      "limit_bps", "alert", "xcheck", "verdict"})  # no hash, no prev_hash: not chained
            self.assertEqual((r["verdict"], r["decision_date"], r["source"], r["limit_bps"]), (verdict, self.day(I), "daily", 5))
            self.assertEqual(r["logged_at"], self.ts(I + 2, 0, 12))
            self.assertEqual(r["alert"], hist_bp > 5)
            self.assertAlmostEqual(r["gaps_bps"]["BTC-USD"], hist_bp, places=6)
            self.assertEqual(r["gaps_bps"]["ETH-USD"], 0.0)
            self.assertAlmostEqual(r["decision_close"]["BTC-USD"], self.dclose(I, "BTC-USD"), places=6)
            self.assertAlmostEqual(r["history_close"]["BTC-USD"] / r["decision_close"]["BTC-USD"], 1 + hist_bp / 1e4, places=9)
            x = r["xcheck"]
            self.assertEqual(set(x), {"would_decline", "gap_bp", "close_missing", "coinbase_missing", "final_5m"})
            self.assertEqual(x["would_decline"], ["BTC-USD"] if cb_bp > 5 else [])
            self.assertAlmostEqual(x["gap_bp"]["BTC-USD"], cb_bp, places=1)
            self.assertEqual((x["close_missing"], x["coinbase_missing"], x["final_5m"]), ([], [], None))  # a daily-row close
            # what R6 already did is as before: pending.json close_audit, and the revised_close row only on an alert
            pend_audit = [r_ for r_ in log["files"]["decisions.jsonl"] if r_.get("event") == "revised_close"]
            self.assertEqual(len(pend_audit), int(hist_bp > 5), verdict)
            self.same_but_for_the_record(log, self.daily("off", cb_bp, hist_bp))

    def test_no_check_when_the_decision_had_no_cross_check(self):
        log = self.daily("off", 8.0, 10.0, audit_mode="log")  # decided before the check was on, audited after
        r = log["files"][AUDITS][0]
        self.assertEqual((r["verdict"], r["xcheck"], r["alert"]), ("no_check", None, True))

    def test_off_writes_no_file_and_an_audit_runs_once(self):
        off = self.daily("off", 8.0, 10.0)
        self.assertNotIn(AUDITS, off["files"])
        self.daily("log", 8.0, 10.0)
        self.at(I + 1, self.ts(I + 2, 1, 7), panel=self.panel(I + 1, self.revised(10.0)))  # a later run of the same night
        self.assertEqual(len(tcc.read_jsonl(self.state, AUDITS)), 1)

    def test_the_file_is_outside_the_hash_chains(self):
        self.assertNotIn(AUDITS, journal.CHAINED)
        self.daily("log", 8.0, 10.0)
        (self.state / AUDITS).write_text("not json\n")  # a damaged measurement file is no broken chain
        with mock.patch.object(journal, "STATE", self.state):
            self.assertEqual(journal.broken_chains(journal.MAIN_CHAINED), [])

    def test_a_failing_write_changes_nothing(self):
        real = journal.append

        def append(name, record):
            if name == AUDITS:
                raise OSError("disk full")
            real(name, record)

        buf = io.StringIO()
        with mock.patch.object(journal, "append", append), contextlib.redirect_stdout(buf):
            log = self.daily("log", 8.0, 10.0)
        self.assertNotIn(AUDITS, log["files"])
        self.assertIn("close_audits.jsonl not written (OSError", buf.getvalue())
        self.assertTrue(log["files"]["pending.json"])
        self.assertEqual(len([r for r in log["files"]["decisions.jsonl"] if r.get("event") == "revised_close"]), 1)
        self.assertTrue(any("BTC-USD" in e and "bp" in e for e in log["outs"][2]["events"]))
        self.same_but_for_the_record(log, self.daily("off", 8.0, 10.0))
        with mock.patch.object(cycle, "_log_close_audit", mock.Mock(side_effect=ValueError("x"))), contextlib.redirect_stdout(buf):
            self.same_but_for_the_record(self.daily("log", 8.0, 10.0), self.daily("off", 8.0, 10.0))  # any failure of the record
        self.assertIn("close_audits.jsonl not written (ValueError", buf.getvalue())

    def test_tally_reads_the_cycles_own_files(self):
        self.daily("log", 8.0, 10.0)
        before = sorted((f.name, f.read_bytes()) for f in self.state.iterdir())
        with mock.patch.object(journal, "STATE", self.state):
            lines = cycle.xcheck_tally()
        self.assertEqual(sorted((f.name, f.read_bytes()) for f in self.state.iterdir()), before)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith(f"{self.day(I)} daily | close BTC-USD="))
        self.assertIn("| coinbase bp BTC-USD=+8.0 ETH-USD=+0.0 | would_decline BTC-USD | history bp BTC-USD=+10.0 ETH-USD=+0.0 | caught", lines[0])
        self.assertTrue(lines[1].startswith(f"{self.day(I + 1)} daily"))
        self.assertTrue(lines[1].endswith("| awaiting"))
        self.assertEqual(lines[2], "rows 2 flags 2 caught 1 false_alarm 0 miss 0 clean 0 awaiting 1 | misses with final_5m 0, without 0")


class Final5m(Book):
    """The decision bar I is missing from Yahoo's daily reply and is built from its 1h bars (backlog 70)."""
    gap, row, replies = hr.Rebuild.gap, hr.Rebuild.row, hr.Rebuild.replies

    def end(self, i: int) -> int:
        return hr.t0_of(self.day(i)) + 24 * hr.HOUR

    def five(self, i: int, sym: str, mult: float = 1.0, stamp_off: int = -300) -> dict:
        """Yahoo's 5m reply: one bar stamped 23:55 UTC of day i (plus stamp_off + 300) closing at mult x the day's close."""
        c = None if mult is None else self.row(i, sym)["close"] * mult
        return hr.chart([self.end(i) + stamp_off], [(c, c, c, c, 0)])

    def rebuilt(self, mode, fives, patches=None, fresh=True) -> tuple[dict, list]:
        """The 00:12 run of day I+1 with row I missing: rebuild, decide. fives: {sym: 5m reply or exception} or a callable."""
        if fresh:
            self.fresh(mode)
        hours, calls = self.replies(I), []

        def get(url, params=None, **k):
            sym = next(s for s in hours if url == data.CHART_URL.format(sym=s))
            calls.append((sym, dict(params)))
            got = hours[sym] if params["interval"] == "1h" else fives[sym]
            if isinstance(got, BaseException):
                raise got
            return got

        with mock.patch.object(data, "_get_json", get):
            out = self.at(I + 1, self.ts(I + 1, 0, 12), panel=self.gap(I + 1, I), seed=self.seed(HELD, I),
                          patches={"hourly_day_bars": hr.REAL_HOURLY, "close_5m": REAL_5M, **(patches or {})})
        self.assertTrue(out["decided_now"])
        return self.snap([out]), calls

    def xc(self, run: dict) -> dict:
        rows = [r for r in run["files"]["decisions.jsonl"] if r.get("date") == self.day(I) and "diag" in r]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["diag"]["hourly_rebuild"]["source"], "yahoo_1h")
        return rows[0]["diag"]["close_xcheck"]

    def test_the_5m_close_is_logged_on_a_rebuilt_bar_and_changes_nothing(self):
        fives = {"BTC-USD": self.five(I, "BTC-USD", 1 / 1.0004), "ETH-USD": self.five(I, "ETH-USD", 1 / 0.9998)}
        log, calls = self.rebuilt("log", fives)
        f5 = self.xc(log)["final_5m"]
        self.assertEqual(sorted(f5), self.coins)
        self.assertEqual(set(f5["BTC-USD"]), {"close_5m", "gap_5m_bp"})  # no error key
        self.assertAlmostEqual(f5["BTC-USD"]["close_5m"], self.row(I, "BTC-USD")["close"] / 1.0004, places=6)
        self.assertAlmostEqual(f5["BTC-USD"]["gap_5m_bp"], 4.0, places=2)
        self.assertAlmostEqual(f5["ETH-USD"]["gap_5m_bp"], -2.0, places=2)
        self.assertEqual(f5["BTC-USD"]["gap_5m_bp"], round(f5["BTC-USD"]["gap_5m_bp"], 3))
        asked = [(s, p) for s, p in calls if p["interval"] == "5m"]
        self.assertEqual(sorted(s for s, _ in asked), self.coins)  # once per universe symbol
        for _, p in asked:  # the bar that starts at 23:55 UTC of the decision day, by period
            self.assertEqual(p, {"period1": self.end(I) - 300, "period2": self.end(I), "interval": "5m"})
        off, off_calls = self.rebuilt("off", fives)
        self.assertEqual([p["interval"] for _, p in off_calls], ["1h"] * len(self.coins))  # off: no 5m fetch
        self.same_but_for_the_record(log, off)

    def test_a_failing_or_empty_5m_fetch_is_none_and_changes_nothing(self):
        btc = self.five(I, "BTC-USD")
        off, _ = self.rebuilt("off", {})
        cases = {"down": (RuntimeError("GET failed"), "RuntimeError"), "unreachable": (data.Unreachable("x"), "Unreachable"),
                 "shape": ({"chart": {"result": None}}, "TypeError"), "no_quote": ({"chart": {"result": [{"timestamp": [1]}]}}, "KeyError"),
                 "other_bar": (self.five(I, "ETH-USD", stamp_off=-600), None), "null": (self.five(I, "ETH-USD", None), None),
                 "nan": (self.five(I, "ETH-USD", float("nan")), None), "empty": (hr.chart([], []), None)}
        for name, (reply, err) in cases.items():
            log, _ = self.rebuilt("log", {"BTC-USD": btc, "ETH-USD": reply})
            f5 = self.xc(log)["final_5m"]
            self.assertEqual(f5["ETH-USD"], {"close_5m": None, "gap_5m_bp": None, **({"error": err} if err else {})}, name)
            self.assertEqual(f5["BTC-USD"]["gap_5m_bp"], 0.0, name)  # one symbol's failure does not cost the other
            json.dumps(log["files"], allow_nan=False)
            self.same_but_for_the_record(log, off)

    def test_a_slow_5m_reply_moves_no_order(self):
        """The clock is real in production: a decision that starts at 00:59:58 and waits 32 s for Yahoo's 5m reply still
        executes at 01:00, as with the check off. The fetch runs after exec_ts and pending.json are fixed."""
        fives = {s: self.five(I, s) for s in self.coins}

        class Slow(dict):  # asking for the 5m reply moves the clock past the hour
            def __getitem__(_, sym):
                journal.now_utc = lambda: self.ts(I + 1, 1, 0, 30)
                return fives[sym]

        def late(mode, replies):
            with mock.patch.object(Book, "at", lambda b, upto, clock, **k: tcc.CryptoBook.at(b, upto, self.ts(I + 1, 0, 59, 58), **k)):
                return self.rebuilt(mode, replies)

        log, calls = late("log", Slow())
        off, _ = late("off", fives)
        self.assertEqual(sum(p["interval"] == "5m" for _, p in calls), len(self.coins))
        self.assertEqual(self.xc(log)["final_5m"]["BTC-USD"]["gap_5m_bp"], 0.0)
        self.assertEqual(log["files"]["pending.json"]["exec_ts"], self.ts(I + 1, 1, 0))
        for part in ("pending.json", "decisions.jsonl"):  # the order and the decision row (its logged_at too) are as with
            self.assertEqual(strip(log["files"][part]), strip(off["files"][part]), part)  # the check off; rows written
        self.assertEqual(log["outs"][0]["events"], off["outs"][0]["events"])  # after the fetch carry the later clock
        self.assertTrue(any(self.ts(I + 1, 1, 0) in e for e in log["outs"][0]["events"]))  # "scheduled for 01:00"
        self.assertEqual((log["sent"], log["prios"]), (off["sent"], off["prios"]))

    def test_a_kill_during_the_5m_fetch_leaves_a_clean_retry(self):
        """Ctrl-C (or a session timeout) while Yahoo's 5m reply is awaited: nothing of the decision is written yet, so the
        rerun decides it in full. A fetch after pending.json would leave an order with no decision row."""
        fives = {s: self.five(I, s) for s in self.coins}
        clean, _ = self.rebuilt("log", fives)
        self.fresh("log")
        with self.assertRaises(KeyboardInterrupt):
            self.rebuilt("log", {s: KeyboardInterrupt() for s in self.coins}, fresh=False)
        killed = self.snap([])["files"]
        self.assertNotEqual(killed.get("pending.json", {}).get("decision_date"), self.day(I))
        self.assertFalse([r for r in killed.get("decisions.jsonl", []) if r.get("date") == self.day(I)])
        rerun, _ = self.rebuilt("log", fives, fresh=False)  # asserts decided_now
        self.assertEqual(rerun, clean)

    def test_no_5m_fetch_on_a_daily_row_or_in_a_proposal(self):
        calls = []
        spy = lambda sym, day: calls.append(sym)  # noqa: E731
        self.fresh("log")
        self.assertTrue(self.decide(seed=self.seed(HELD, I), patches={"close_5m": spy})["decided_now"])
        dec = [r for r in tcc.read_jsonl(self.state, "decisions.jsonl") if "diag" in r][-1]
        self.assertIn("close_xcheck", dec["diag"])
        self.assertNotIn("final_5m", dec["diag"]["close_xcheck"])
        self.fresh("log")  # a proposal of a rebuilt bar is no decision: nothing is fetched for the record
        with mock.patch.object(data, "_get_json", lambda url, params=None, **k: self.replies(I)[url.rsplit("/", 1)[1]]):
            out = self.at(I + 1, self.ts(I + 1, 0, 12), panel=self.gap(I + 1, I), propose=True, seed=self.seed(HELD, I),
                          patches={"hourly_day_bars": hr.REAL_HOURLY, "close_5m": spy})
        self.assertIn("hourly_rebuild", out["diag"])
        self.assertNotIn("final_5m", out["diag"]["close_xcheck"])
        self.assertEqual(calls, [])

    def test_the_audit_of_a_rebuilt_decision_carries_the_source_and_the_5m_field(self):
        fives = {s: self.five(I, s, 1 / 1.0003) for s in self.coins}
        log, _ = self.rebuilt("log", fives)
        hourly = log["files"]["pending.json"]["decision_close"]
        self.set_bars(I + 1, 1)
        late = {**self.p, "close": self.p["close"].copy()}  # Yahoo's daily row I arrives 19 bp above the hourly close
        late["close"].iloc[I, late["close"].columns.get_loc("BTC-USD")] = hourly["BTC-USD"] * 1.0019
        late["close"].iloc[I, late["close"].columns.get_loc("ETH-USD")] = hourly["ETH-USD"]
        self.at(I + 1, self.ts(I + 1, 1, 7), panel=self.panel(I + 1, late))
        self.assertFalse((self.state / AUDITS).exists())  # still the decision bar
        self.assertTrue(self.at(I + 2, self.ts(I + 2, 0, 12), panel=self.panel(I + 2, late))["decided_now"])
        rows = tcc.read_jsonl(self.state, AUDITS)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["source"], r["verdict"], r["alert"], r["decision_close"]), ("yahoo_1h", "miss", True, hourly))
        self.assertAlmostEqual(r["gaps_bps"]["BTC-USD"], 19.0, places=6)
        self.assertEqual(r["xcheck"]["final_5m"], self.xc(log)["final_5m"])
        self.assertAlmostEqual(r["xcheck"]["final_5m"]["BTC-USD"]["gap_5m_bp"], 3.0, places=2)
        with mock.patch.object(journal, "STATE", self.state):
            lines = cycle.xcheck_tally()
        self.assertTrue(lines[0].startswith(f"{self.day(I)} yahoo_1h | close "))
        self.assertIn("| 5m bp BTC-USD=+3.0 ETH-USD=+3.0 | history bp BTC-USD=+19.0 ETH-USD=+0.0 | miss", lines[0])
        self.assertTrue(lines[-1].endswith("miss 1 clean 0 awaiting 1 | misses with final_5m 1, without 0"))


class Helper(unittest.TestCase):
    def test_close_5m_reads_only_the_2355_bar(self):
        end = hr.t0_of("2026-11-13")
        seen = []

        def get(url, params=None, **k):
            seen.append((url, params))
            return hr.chart([end - 600, end - 300, end], [(1, 1, 1, 10.0, 0), (2, 2, 2, 20.5, 0), (3, 3, 3, 30.0, 0)])

        with mock.patch.object(data, "_get_json", get):
            self.assertEqual(REAL_5M("BTC-USD", "2026-11-12"), 20.5)
        self.assertEqual(seen, [(data.CHART_URL.format(sym="BTC-USD"), {"period1": end - 300, "period2": end, "interval": "5m"})])


def xrow(date, decline, audit=None, f5=None, rebuilt=False) -> tuple[dict, dict | None]:
    """A decision row with a cross-check and (audit = (history bp, verdict)) its close_audits row."""
    x = {"mode": "log", "bp": 5, "symbols": {"BTC-USD": {"close": 70000.5, "coinbase": 70000.0, "gap_bp": 7.2 if decline else 0.071}},
         "would_decline": ["BTC-USD"] if decline else [], "unreachable": ["ETH-USD"], "close_missing": [], "coinbase_missing": ["ETH-USD"],
         **({"final_5m": f5} if f5 else {})}
    dec = {"date": date, "diag": {"close_xcheck": x, **({"hourly_rebuild": {"source": "yahoo_1h"}} if rebuilt else {})}}
    aud = audit and {"decision_date": date, "gaps_bps": {"BTC-USD": audit[0], "ETH-USD": 0.0}, "verdict": audit[1]}
    return dec, aud


class Cli(unittest.TestCase):
    def tally(self, base: Path) -> tuple[int, list[str]]:
        buf = io.StringIO()
        with mock.patch.object(journal, "STATE", base), contextlib.redirect_stdout(buf):
            code = main(["--book", "crypto", "xcheck-tally"])
        return code, buf.getvalue().splitlines()

    def test_tally_on_a_small_fixture(self):
        f5 = {"BTC-USD": {"close_5m": 69990.0, "gap_5m_bp": 1.5}, "ETH-USD": {"close_5m": None, "gap_5m_bp": None, "error": "RuntimeError"}}
        pairs = [xrow("2026-11-20", True, (9.0, "caught")), xrow("2026-11-21", True, (1.0, "false_alarm")),
                 xrow("2026-11-22", False, (-12.25, "miss"), f5, rebuilt=True), xrow("2026-11-23", False, (6.0, "miss")),
                 xrow("2026-11-24", False, (0.5, "clean")), xrow("2026-11-25", False)]
        decisions = [{"date": "2026-11-19", "diag": {"regime": "risk_on"}}, *(d for d, _ in pairs),
                     {"event": "revised_close", "date": "2026-11-20"}]
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / data.load_config("crypto")["market"]["state_subdir"]
            state.mkdir()
            (state / "decisions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in decisions))
            (state / AUDITS).write_text("".join(json.dumps(a) + "\n" for _, a in pairs if a) + '{"torn')
            before = sorted((f.name, f.read_bytes()) for f in state.iterdir())
            code, lines = self.tally(Path(tmp))
            self.assertEqual(sorted((f.name, f.read_bytes()) for f in state.iterdir()), before)  # it writes nothing
            self.assertEqual(sorted(f.name for f in Path(tmp).iterdir()), [state.name])
        self.assertEqual(code, 0)
        self.assertEqual(lines, [
            "2026-11-20 daily | close BTC-USD=70000.5 | coinbase bp BTC-USD=+7.2 | would_decline BTC-USD | history bp BTC-USD=+9.0 ETH-USD=+0.0 | caught",
            "2026-11-21 daily | close BTC-USD=70000.5 | coinbase bp BTC-USD=+7.2 | would_decline BTC-USD | history bp BTC-USD=+1.0 ETH-USD=+0.0 | false_alarm",
            "2026-11-22 yahoo_1h | close BTC-USD=70000.5 | coinbase bp BTC-USD=+0.1 | would_decline - | 5m bp BTC-USD=+1.5 ETH-USD=?"
            " | history bp BTC-USD=-12.2 ETH-USD=+0.0 | miss",
            "2026-11-23 daily | close BTC-USD=70000.5 | coinbase bp BTC-USD=+0.1 | would_decline - | history bp BTC-USD=+6.0 ETH-USD=+0.0 | miss",
            "2026-11-24 daily | close BTC-USD=70000.5 | coinbase bp BTC-USD=+0.1 | would_decline - | history bp BTC-USD=+0.5 ETH-USD=+0.0 | clean",
            "2026-11-25 daily | close BTC-USD=70000.5 | coinbase bp BTC-USD=+0.1 | would_decline - | awaiting",
            "rows 6 flags 2 caught 1 false_alarm 1 miss 2 clean 1 awaiting 1 | misses with final_5m 1, without 1",
        ])

    def test_tally_with_no_files_prints_zeros_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, lines = self.tally(Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual((code, lines), (0, ["rows 0 flags 0 caught 0 false_alarm 0 miss 0 clean 0 awaiting 0 | misses with final_5m 0, without 0"]))


if __name__ == "__main__":
    unittest.main()
