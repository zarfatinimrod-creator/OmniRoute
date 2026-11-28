"""Backlog 70: a final UTC day missing from Yahoo's daily reply is built from Yahoo's 24 hourly bars of that day.

Yahoo sent the row of the UTC day that just closed with open/high/low/close null for 6+ hours, two nights running
(bar 2026-11-11 on 11-12, bar 2026-11-12 on 11-13; logs/2026-11-13-crypto-night.md). data._bars_from_chart drops it,
so the backlog 68 rule made no decision and the crypto_base regime exit was missed. On the utc_daily calendar only,
cycle.hourly_day_bars folds the 24 complete hours (00:00..23:00 UTC) into the missing row: first open, highest high,
lowest low, last close, summed volume. Anything less than 24 complete hours keeps the backlog 68 skip unchanged.
Network stubbed everywhere (data._get_json or cycle.hourly_day_bars).
"""

import contextlib
import io
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import pandas as pd

from aitrader import cycle, data, journal
from aitrader.strategy import precompute_aux
from golden_util import FIRST_BAR, frozen_env, load_panel
from test_core import cfg_for
from test_crypto_cycle import I, CryptoBook, load, read_jsonl

UTC = timezone.utc
REAL_HOURLY = getattr(cycle, "hourly_day_bars", None)  # the real helper (the at() harness stubs it per run)
HOUR = 3600

# Yahoo's 1h chart of BTC-USD for 2026-11-12, fetched 2026-11-13 06:13 UTC with period1 = 11-12 00:00 UTC, period2 =
# 11-13 00:00 UTC: 24 rows 00:00..23:00 (open, high, low, close, volume), then a 25th row stamped 11-13 00:00 with
# every field null. The last close equals Coinbase's daily close of 11-12 (71,369.90, logs/2026-11-13-crypto-night.md).
REAL_DAY = "2026-11-12"
REAL_HOURS = [
    (73922.75, 74118.96875, 73758.09375, 73993.9765625, 0), (73988.078125, 73991.6875, 73512.1796875, 73622.3984375, 331233280),
    (73612.171875, 73991.53125, 73494.0703125, 73711.78125, 0), (73703.40625, 73788.2734375, 73615.9765625, 73709.953125, 88989696),
    (73712.1796875, 73770.4375, 73543.1875, 73640.90625, 0), (73640.5390625, 73640.5390625, 73436.5, 73493.9609375, 0),
    (73498.2890625, 73637.328125, 73325.1796875, 73425.0390625, 0), (73440.21875, 73570.171875, 73336.1015625, 73557.6484375, 0),
    (73553.34375, 73593.75, 73415.7890625, 73502.0625, 0), (73495.78125, 73495.78125, 73166.6171875, 73405.4609375, 0),
    (73403.1171875, 73536.34375, 73282.5078125, 73370.71875, 0), (73370.71875, 73388.5, 72684.953125, 72857.5625, 473956352),
    (72815.9609375, 73049.21875, 72682.0234375, 72810.359375, 686802944), (72810.3671875, 72847.5234375, 72192.59375, 72414.8828125, 1921923072),
    (72418.9375, 72484.7890625, 71219.1875, 71548.3125, 2637703168), (71535.546875, 71636.6484375, 71174.2265625, 71610.0, 1344796672),
    (71594.3984375, 72112.7734375, 71430.1328125, 71681.09375, 839546880), (71692.0703125, 71983.4921875, 71581.6328125, 71826.421875, 137140224),
    (71825.5, 71997.1875, 71505.578125, 71678.9921875, 258537472), (71686.4765625, 71691.390625, 71346.15625, 71597.7578125, 0),
    (71596.203125, 71596.203125, 71308.03125, 71346.0234375, 224194560), (71360.2109375, 71550.9921875, 71288.6015625, 71461.8203125, 0),
    (71429.7578125, 71445.4921875, 71228.40625, 71325.7421875, 0), (71325.7421875, 71446.5703125, 71050.40625, 71369.8984375, 0),
]


def t0_of(day) -> int:
    d = pd.Timestamp(day)
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def chart(stamps: list, rows: list) -> dict:
    """A Yahoo chart reply: stamps (epoch seconds) and rows (open, high, low, close, volume)."""
    cols = list(zip(*rows)) if rows else [[]] * 5
    quote = {k: list(c) for k, c in zip(("open", "high", "low", "close", "volume"), cols)}
    return {"chart": {"result": [{"meta": {"dataGranularity": "1h"}, "timestamp": stamps, "indicators": {"quote": [quote]}}],
                      "error": None}}


def day_chart(day, rows: list, boundary: bool = True) -> dict:
    """24 hourly rows of `day` stamped 00:00..23:00 UTC, plus (as Yahoo sends it) the next 00:00 row with nulls."""
    t0 = t0_of(day)
    stamps = [t0 + HOUR * k for k in range(len(rows))]
    if boundary:
        return chart(stamps + [t0 + 24 * HOUR], list(rows) + [(None,) * 5])
    return chart(stamps, list(rows))


def hours_for(o: float, h: float, low: float, c: float, v: float) -> list:
    """24 complete hours whose fold is exactly (o, h, low, c, v): first open o, one high h, one low `low`, last close c,
    the whole volume in the first hour (null volumes elsewhere count as 0)."""
    mid = (h + low) / 2
    out = []
    for k in range(24):
        ok, ck = (o if k == 0 else mid), (c if k == 23 else mid)
        hk = h if k == 5 else max(ok, ck, mid)
        lk = low if k == 17 else min(ok, ck, mid)
        out.append((ok, hk, lk, ck, v if k == 0 else (None if k % 2 else 0)))
    return out


class HourlyDayBars(unittest.TestCase):
    """The helper alone: one Yahoo 1h chart call per symbol and UTC day, 24 complete hours or None."""

    def fold(self, reply, sym="BTC-USD", day=REAL_DAY):
        seen = []

        def get(url, params=None, **k):
            seen.append((url, params))
            if isinstance(reply, Exception):
                raise reply
            return reply

        with mock.patch.object(data, "_get_json", get):
            out = cycle.hourly_day_bars(sym, pd.Timestamp(day))
        return out, seen

    def test_folds_the_real_reply_of_2026_11_12(self):
        out, seen = self.fold(day_chart(REAL_DAY, REAL_HOURS))
        t0 = t0_of(REAL_DAY)
        self.assertEqual(seen, [(data.CHART_URL.format(sym="BTC-USD"), {"period1": t0, "period2": t0 + 86400, "interval": "1h"})])
        self.assertEqual(out, {"open": 73922.75, "high": max(r[1] for r in REAL_HOURS), "low": min(r[2] for r in REAL_HOURS),
                               "close": 71369.8984375, "volume": float(sum(r[4] for r in REAL_HOURS))})
        self.assertEqual((out["high"], out["low"]), (74118.96875, 71050.40625))
        self.assertEqual(self.fold(day_chart(REAL_DAY, REAL_HOURS, boundary=False))[0], out)  # without the null 25th row

    def test_null_volumes_count_as_zero(self):
        rows = [r[:4] + (None,) for r in REAL_HOURS]
        rows[3] = REAL_HOURS[3]
        self.assertEqual(self.fold(day_chart(REAL_DAY, rows))[0]["volume"], 88989696.0)

    def test_an_incomplete_day_is_none(self):
        t0 = t0_of(REAL_DAY)
        stamps = [t0 + HOUR * k for k in range(24)]

        def with_value(k: int, field: int, v):
            rows = [list(r) for r in REAL_HOURS]
            rows[k][field] = v
            return day_chart(REAL_DAY, [tuple(r) for r in rows])

        cases = {
            "23 hours": day_chart(REAL_DAY, REAL_HOURS[:23]),
            "23 hours, last missing, boundary row only": chart(stamps[:23] + [t0 + 24 * HOUR], REAL_HOURS[:23] + [(None,) * 5]),
            "first hour missing": chart(stamps[1:], REAL_HOURS[1:]),
            "null close": with_value(10, 3, None),
            "null open": with_value(0, 0, None),
            "null high": with_value(23, 1, None),
            "null low": with_value(7, 2, None),
            "nan close": with_value(4, 3, float("nan")),
            "inf high": with_value(4, 1, float("inf")),
            "zero low": with_value(4, 2, 0.0),
            "negative open": with_value(4, 0, -1.0),
            "text close": with_value(4, 3, "71369.9"),
            "misaligned stamp": chart(stamps[:5] + [stamps[5] + 1800] + stamps[6:], REAL_HOURS),
            "fractional stamp": chart(stamps[:5] + [stamps[5] + 0.5] + stamps[6:], REAL_HOURS),
            "extra in-day stamp (a live row)": chart(stamps + [t0 + 23 * HOUR + 600], REAL_HOURS + [REAL_HOURS[-1]]),
            "duplicate stamp": chart(stamps + [stamps[-1]], REAL_HOURS + [REAL_HOURS[-1]]),
            "the day shifted by an hour": chart([s + HOUR for s in stamps], REAL_HOURS),
            "column shorter than the stamps": {"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [
                {"open": [r[0] for r in REAL_HOURS], "high": [r[1] for r in REAL_HOURS], "low": [r[2] for r in REAL_HOURS],
                 "close": [r[3] for r in REAL_HOURS][:23], "volume": [r[4] for r in REAL_HOURS]}]}}]}},
            "no close column": {"chart": {"result": [{"timestamp": stamps, "indicators": {"quote": [
                {"open": [r[0] for r in REAL_HOURS], "high": [r[1] for r in REAL_HOURS], "low": [r[2] for r in REAL_HOURS]}]}}]}},
            "no rows": chart([], []),
            "no result": {"chart": {"result": None, "error": {"code": "Not Found"}}},
            "no chart": {},
            "a list": [],
        }
        for name, reply in cases.items():
            with self.subTest(name):
                self.assertIsNone(self.fold(reply)[0])

    def test_a_failed_fetch_is_none(self):
        for err in (RuntimeError("GET failed"), data.Unreachable("Yahoo down"), ValueError("bad JSON")):
            with self.subTest(type(err).__name__):
                out, seen = self.fold(err)
                self.assertIsNone(out)
                self.assertEqual(len(seen), 1)


class Rebuild(CryptoBook):
    """Through run_cycle: the 00:12 UTC run of day I+1 finds row I missing from Yahoo's daily reply."""

    def gap(self, upto: int, missing: int, base: dict | None = None) -> dict:
        return {k: v.drop(index=self.idx[missing]) for k, v in self.panel(upto, base).items()}

    def row(self, i: int, sym: str) -> dict:
        return {f: float(self.p[f].iloc[i][sym]) for f in ("open", "high", "low", "close", "volume")}

    def replies(self, i: int, close_mult: float = 1.0, broken: dict | None = None) -> dict:
        """Yahoo 1h replies per symbol for day i: hours whose fold is row i (the close times close_mult)."""
        out = {}
        for s in self.coins:
            r = self.row(i, s)
            c = r["close"] * close_mult
            out[s] = day_chart(self.day(i), hours_for(r["open"], max(r["high"], c), min(r["low"], c), c, r["volume"]))
        return {**out, **(broken or {})}

    def run_real(self, upto: int, clock: str, replies: dict, **kw) -> tuple[dict, list]:
        """One run with the real helper on stubbed Yahoo replies {symbol: reply or exception}."""
        calls = []

        def get(url, params=None, **k):
            sym = next(s for s in replies if url == data.CHART_URL.format(sym=s))
            calls.append((sym, params))
            if isinstance(replies[sym], Exception):
                raise replies[sym]
            return replies[sym]

        with mock.patch.object(data, "_get_json", get):
            out = self.at(upto, clock, patches={"hourly_day_bars": REAL_HOURLY, **kw.pop("patches", {})}, **kw)
        return out, calls

    def backlog68(self, i: int = I) -> str:
        return (f"אין שורה יומית של {self.day(i)} בנתונים (הנר האחרון הסופי הוא {self.day(i - 1)}) - אין החלטה בריצה הזו,"
                " הזמנה ממתינה עדיין מתמלאת, ריצה מאוחרת תנסה שוב")

    def use_profile(self, profile: str) -> None:
        self.cfg, self.state = data.load_config("crypto", profile), self.mkdtemp()
        self.coins = sorted(self.cfg["universe"])

    # ---- (1) a missing row with 24 complete hours is rebuilt and decided ----------------------------------------
    def test_missing_row_is_built_from_24_hours_and_decided(self):
        for profile in ("crypto_base", "crypto"):
            with self.subTest(profile=profile):
                self.use_profile(profile)
                pn = self.gap(I + 1, I)
                before = {k: v.copy() for k, v in pn.items()}
                out, calls = self.run_real(I + 1, self.ts(I + 1, 0, 12), self.replies(I, 1.0007), panel=pn)
                t0 = t0_of(self.day(I))
                self.assertEqual(sorted(calls), [(s, {"period1": t0, "period2": t0 + 86400, "interval": "1h"}) for s in self.coins])
                self.assertTrue(out["decided_now"])
                pend = self.pending()
                self.assertEqual(pend["decision_date"], self.day(I))
                hourly = {s: self.row(I, s)["close"] * 1.0007 for s in self.coins}
                self.assertEqual(pend["decision_close"], hourly)  # the last hourly close
                self.assertNotIn(self.backlog68(), out["events"])
                line = [e for e in out["events"] if "נרות שעתיים" in e]
                self.assertEqual(len(line), 1)
                self.assertIn(self.day(I), line[0])
                self.assertIn("24", line[0])
                for s in self.coins:
                    self.assertIn(f"{s} {hourly[s]:,.2f}", line[0])
                self.assertTrue(any(line[0] in body for body in self.sent))
                log = read_jsonl(self.state, "decisions.jsonl")[-1]["diag"]["hourly_rebuild"]
                self.assertEqual((log["bar"], log["source"], log["hours"], log["inserted"]), (self.day(I), "yahoo_1h", 24, True))
                self.assertEqual(set(log["symbols"]), set(self.coins))
                self.assertEqual(log["symbols"][self.coins[0]]["close"], hourly[self.coins[0]])
                self.assertEqual(pend["hourly_rebuild"], log)
                for k, v in before.items():  # the panel it was given is not changed in place
                    pd.testing.assert_frame_equal(pn[k], v)

    def test_rebuilt_row_decides_like_the_full_daily_row(self):
        """Hours whose fold equals Yahoo's own row I give the same decision as the reply that has row I."""
        control = self.decide()
        ctrl = self.pending()
        self.setUp()
        out, _ = self.run_real(I + 1, self.ts(I + 1, 0, 12), self.replies(I), panel=self.gap(I + 1, I))
        pend = self.pending()
        self.assertTrue(control["decided_now"] and out["decided_now"])
        for k in ("decision_date", "targets", "targets_raw", "stopped", "exec_ts", "decision_close", "preview_at_close"):
            self.assertEqual(pend[k], ctrl[k], k)
        self.assertNotIn("hourly_rebuild", ctrl)

    def test_rebuilt_row_without_a_newer_row_is_the_decision_bar(self):
        """No D+1 row in the reply at all: the rebuilt row is the newest row and the decision bar."""
        out, _ = self.run_real(I, self.ts(I + 1, 0, 12), self.replies(I), panel=self.gap(I, I))
        self.assertTrue(out["decided_now"])
        self.assertEqual(self.pending()["decision_date"], self.day(I))
        self.assertEqual(out["date"], self.day(I))

    # ---- (2) and (3) anything short of 24 complete hours keeps the backlog 68 skip -------------------------------
    def control_skip(self) -> tuple[dict, dict]:
        """The run and the desk's view as they are without any rebuild (the harness stub)."""
        self.state = self.mkdtemp()
        prop = self.at(I + 1, self.ts(I + 1, 0, 12), propose=True, panel=self.gap(I + 1, I))
        out = self.at(I + 1, self.ts(I + 1, 0, 12), panel=self.gap(I + 1, I))
        self.assertIn(self.backlog68(), out["events"])
        return prop, out

    def assert_unchanged_skip(self, run, name: str) -> None:
        prop0, out0 = self.control_skip()
        self.state, self.sent = self.mkdtemp(), []
        prop = run(propose=True)
        out = run()
        self.assertEqual(prop["skipped"], prop0["skipped"], name)
        self.assertEqual((out["decided_now"], out["executed"], out["events"]), (False, [], out0["events"]), name)
        self.assertIsNone(self.pending(), name)
        self.assertEqual(read_jsonl(self.state, "decisions.jsonl"), [], name)

    def test_incomplete_hours_keep_the_backlog_68_skip(self):
        t0 = t0_of(self.day(I))
        good = self.replies(I)
        btc = hours_for(1.0, 2.0, 0.5, 1.5, 1.0)
        null_close = [list(r) for r in btc]
        null_close[12][3] = None
        cases = {
            "23 hours": {"BTC-USD": day_chart(self.day(I), btc[:23])},
            "one null close": {"BTC-USD": day_chart(self.day(I), [tuple(r) for r in null_close])},
            "misaligned stamp": {"BTC-USD": chart([t0 + HOUR * k + (900 if k == 9 else 0) for k in range(24)], btc)},
            "one coin complete, the other not": {"ETH-USD": day_chart(self.day(I), btc[:23])},
        }
        for name, broken in cases.items():
            for profile in (("crypto",) if "coin" in name else ("crypto_base", "crypto")):
                with self.subTest(name, profile=profile):
                    self.use_profile(profile)
                    rep = {s: good[s] for s in self.coins} | {s: v for s, v in broken.items() if s in self.coins}

                    def run(propose=False, rep=rep):
                        return self.run_real(I + 1, self.ts(I + 1, 0, 12), rep, panel=self.gap(I + 1, I), propose=propose)[0]

                    self.assert_unchanged_skip(run, name)

    def test_failed_hourly_fetch_keeps_the_skip_and_never_raises(self):
        for err in (RuntimeError("GET failed: connection refused"), data.Unreachable("Yahoo 1h down")):
            with self.subTest(type(err).__name__):
                def run(propose=False, err=err):
                    return self.run_real(I + 1, self.ts(I + 1, 0, 12), {"BTC-USD": err, "ETH-USD": err},
                                         panel=self.gap(I + 1, I), propose=propose)[0]

                self.assert_unchanged_skip(run, type(err).__name__)

        def boom(sym, day):  # the helper itself raising (a bug in it) must not stop the cycle either
            raise ValueError("unexpected")

        with self.subTest("helper raises"), contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assert_unchanged_skip(lambda propose=False: self.at(I + 1, self.ts(I + 1, 0, 12), panel=self.gap(I + 1, I),
                                                                     propose=propose, patches={"hourly_day_bars": boom}),
                                       "helper raises")
        self.assertIn(f"backlog 70: no rebuild of {self.day(I)} (ValueError)", buf.getvalue())  # said, not swallowed

    def test_daily_reply_fetched_before_the_bar_ended_is_not_rebuilt(self):
        """A daily reply older than the bar end (a cache read in an outage) is not made to look final by a rebuild."""
        calls = []
        pn = self.gap(I + 1, I)
        end = cycle._bar_end_utc(self.idx[I], self.cfg)
        pn["_fetched_at"] = {s: end - timedelta(minutes=20) for s in self.coins}
        out = self.at(I + 1, self.ts(I + 1, 0, 12), panel=pn, patches={"hourly_day_bars": lambda s, d: calls.append(s)})
        self.assertEqual(calls, [])
        self.assertFalse(out["decided_now"])
        self.assertIn(self.backlog68(), out["events"])

        pn["_fetched_at"] = {s: end + timedelta(minutes=2) for s in self.coins}  # fetched after the bar end: rebuilt
        out, _ = self.run_real(I + 1, self.ts(I + 1, 0, 12), self.replies(I), panel=pn)
        self.assertTrue(out["decided_now"])

    # ---- (4) a present daily row: the helper is never called -----------------------------------------------------
    def spy(self):
        calls = []
        return calls, (lambda sym, day: calls.append((sym, day)) or None)

    def test_present_daily_row_never_calls_the_helper(self):
        calls, spy = self.spy()
        out = self.decide(patches={"hourly_day_bars": spy})
        self.assertTrue(out["decided_now"])
        self.assertEqual(calls, [])
        pend = self.pending()
        self.assertEqual(pend["decision_close"], {s: float(self.p["close"].iloc[I][s]) for s in self.coins})
        self.assertNotIn("hourly_rebuild", pend)
        self.assertNotIn("hourly_rebuild", read_jsonl(self.state, "decisions.jsonl")[-1]["diag"])
        self.assertFalse([e for e in out["events"] if "נרות שעתיים" in e])

    def test_only_the_missing_coin_is_fetched_and_daily_values_are_kept(self):
        """Row I present for BTC, absent for ETH: only ETH is built, BTC keeps Yahoo's daily values."""
        pn = self.panel(I + 1)
        pn = {**pn, **{f: pn[f].copy() for f in ("open", "high", "low", "close", "volume")}}
        for f in ("open", "high", "low", "close", "volume"):
            pn[f].iloc[I, pn[f].columns.get_loc("ETH-USD")] = float("nan")
        out, calls = self.run_real(I + 1, self.ts(I + 1, 0, 12), self.replies(I, 1.0007), panel=pn)
        self.assertEqual([c[0] for c in calls], ["ETH-USD"])
        self.assertTrue(out["decided_now"])
        pend = self.pending()
        self.assertEqual(pend["decision_close"], {"BTC-USD": float(self.p["close"].iloc[I]["BTC-USD"]),
                                                  "ETH-USD": self.row(I, "ETH-USD")["close"] * 1.0007})
        self.assertEqual((set(pend["hourly_rebuild"]["symbols"]), pend["hourly_rebuild"]["inserted"]), ({"ETH-USD"}, False))

    def test_a_partial_daily_row_is_never_mixed_with_hourly_values(self):
        """ETH's row I has an open but no close (not a shape fetch_panel produces): no rebuild, the stale rule skips."""
        calls, spy = self.spy()
        pn = self.panel(I + 1)
        pn = {**pn, "close": pn["close"].copy()}
        pn["close"].iloc[I, pn["close"].columns.get_loc("ETH-USD")] = float("nan")
        out = self.at(I + 1, self.ts(I + 1, 0, 12), panel=pn, patches={"hourly_day_bars": spy})
        self.assertEqual(calls, [])
        self.assertIn("ETH-USD", out["skipped"])

    # ---- (5) the stock calendar never calls the helper ----------------------------------------------------------
    def test_stock_calendar_never_calls_the_helper(self):
        full = load_panel()
        cfg = cfg_for(full)
        cfg["risk"]["min_score"] = -1.0
        idx = full["close"].index
        calls, spy = self.spy()
        outs = []
        with frozen_env(self.mkdtemp(), None), mock.patch.object(cycle, "hourly_day_bars", spy):
            cycle.load_config = lambda: cfg
            for n in (FIRST_BAR, FIRST_BAR + 2):  # the second run: yesterday's row missing from the reply
                pn = {k: v.iloc[:n] for k, v in full.items()}
                if n > FIRST_BAR:
                    pn = {k: v.drop(index=idx[n - 2]) for k, v in pn.items()}
                cycle.load_market = lambda c, rng="10y", age=0.1, pn=pn: pn
                outs.append(cycle.run_cycle())
        self.assertEqual(calls, [])
        self.assertTrue(all(o["decided_now"] for o in outs))

    # ---- (6) the rebuilt close drives the crypto_base regime exit ------------------------------------------------
    def test_rebuilt_close_under_the_band_exits_on_crypto_base(self):
        self.use_profile("crypto_base")
        self.p = {k: v[self.coins] if isinstance(v, pd.DataFrame) else v for k, v in self.p.items()}
        reg = precompute_aux(self.p, self.cfg)["regime"]
        j = next(k for k in range(250, len(reg) - 3) if reg.iloc[k - 1] == "risk_on" and reg.iloc[k] == "risk_off")
        seed = {**self.seed({"BTC-USD": 0.8}, j - 1), "regime": "risk_on", "dd_state": "normal", "last_rebalance": self.day(j - 1)}

        missed = self.at(j + 1, self.ts(j + 1, 0, 12), panel=self.gap(j + 1, j), seed=seed)  # today: no decision
        self.assertFalse(missed["decided_now"])
        self.assertIsNone(self.pending())

        self.state = self.mkdtemp()
        out, _ = self.run_real(j + 1, self.ts(j + 1, 0, 12), self.replies(j), panel=self.gap(j + 1, j), seed=seed)
        self.assertTrue(out["decided_now"])
        pend = self.pending()
        dec = read_jsonl(self.state, "decisions.jsonl")[-1]
        self.assertEqual(dec["diag"]["regime"], "risk_off")
        self.assertEqual((pend["targets"], pend["exits_only"]), ({}, False))
        self.assertEqual([(f["side"], f["symbol"], f["reason"]) for f in pend["preview_at_close"]], [("SELL", "BTC-USD", "exit")])
        self.assertTrue(any("risk_on -> risk_off" in e for e in out["events"]))

        self.set_bars(j + 1, 1)
        out = self.at(j + 1, self.ts(j + 1, 1, 7))
        self.assertEqual([(f["side"], f["symbol"]) for f in out["executed"]], [("SELL", "BTC-USD")])
        self.assertNotIn("BTC-USD", load(self.state, "portfolio.json")["positions"])

    # ---- R6 and grading -----------------------------------------------------------------------------------------
    def test_r6_compares_the_rebuilt_close_with_yahoos_daily_row_when_it_arrives(self):
        out, _ = self.run_real(I + 1, self.ts(I + 1, 0, 12), self.replies(I), panel=self.gap(I + 1, I))
        self.assertTrue(out["decided_now"])
        hourly = self.pending()["decision_close"]
        self.set_bars(I + 1, 1)
        out, calls = self.run_real(I + 1, self.ts(I + 1, 1, 7), self.replies(I), panel=self.gap(I + 1, I))  # still null
        self.assertTrue(out["executed"])
        self.assertFalse(out["decided_now"])
        self.assertEqual(len(calls), len(self.coins))  # rebuilt again, decided once
        self.assertNotIn("close_audit", self.pending())  # the decision bar itself is never audited

        late = {**self.p, "close": self.p["close"].copy()}  # Yahoo's daily row I arrives, 19 bp above the hourly close
        late["close"].iloc[I, late["close"].columns.get_loc("BTC-USD")] = hourly["BTC-USD"] * 1.0019
        late["close"].iloc[I, late["close"].columns.get_loc("ETH-USD")] = hourly["ETH-USD"]
        out = self.at(I + 1, self.ts(I + 1, 9, 3), panel=self.panel(I + 1, late))
        self.assertNotIn("close_audit", self.pending())  # still the decision bar
        self.assertFalse([e for e in out["events"] if "bp" in e])

        calls, spy = self.spy()
        out = self.at(I + 2, self.ts(I + 2, 0, 12), panel=self.panel(I + 2, late), patches={"hourly_day_bars": spy})
        self.assertEqual(calls, [])
        self.assertTrue(out["decided_now"])
        rec = [r for r in read_jsonl(self.state, "decisions.jsonl") if r.get("event") == "revised_close"]
        self.assertEqual(len(rec), 1)
        self.assertEqual((rec[0]["date"], rec[0]["decision_close"]), (self.day(I), hourly))
        self.assertAlmostEqual(rec[0]["gaps_bps"]["BTC-USD"], 19.0, places=6)
        self.assertEqual(rec[0]["gaps_bps"]["ETH-USD"], 0.0)
        self.assertEqual(rec[0]["decision_close_source"], "yahoo_1h")
        alert = [e for e in out["events"] if "BTC-USD" in e and "bp" in e]
        self.assertEqual(len(alert), 1)
        self.assertIn("נרות שעתיים", alert[0])

    def test_forecasts_are_not_graded_on_a_rebuilt_close(self):
        seen = []
        real = journal.evaluate_predictions

        def spy(close, *a, **k):
            seen.append(close.index)
            return real(close, *a, **k)

        with mock.patch.object(journal, "evaluate_predictions", spy):
            out, _ = self.run_real(I + 1, self.ts(I + 1, 0, 12), self.replies(I), panel=self.gap(I + 1, I))
        self.assertTrue(out["decided_now"])
        self.assertTrue(seen)
        for ix in seen:  # the rebuilt row I is left out until Yahoo's daily row arrives
            self.assertEqual(ix[-1], self.idx[I - 1])
        seen.clear()
        self.state = self.mkdtemp()
        with mock.patch.object(journal, "evaluate_predictions", spy):
            self.decide()
        self.assertTrue(seen and all(ix[-1] == self.idx[I] for ix in seen))  # control: a daily row I is graded on


if __name__ == "__main__":
    unittest.main()
