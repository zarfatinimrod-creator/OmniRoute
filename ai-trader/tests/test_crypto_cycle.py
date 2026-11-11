"""The crypto cycle path (plan 2026-11-09-crypto-book-v1, Task 6; planning decision 12, spec 3.2, 3.3, 6.1).

* UtcDailyCalendar: bars end at 00:00 UTC, 7 days a week; final 5 minutes later.
* Decide at 00:12 UTC; exec_ts = the first full hour strictly after logged_at, never before D+1 01:00 UTC. The
  override cutoff is exec_ts.
* Fill all coins or none at the open of the 1h bar at exec_ts, else the 1m bar, else keep the order pending (a later
  run takes the first hour from exec_ts on that has every coin). Never the daily open. fill_source is logged.
* An unfilled pending overwritten by a new decision is first recorded as expired_unfilled.
* One equity mark per decision bar; proposal.json deleted on a decision; VIX, earnings, overlays and corporate
  actions off; reports under market.report_dir; latest.json bench_since_start.
* Rulings: R6 revised-close audit, R9a Coinbase breach fills the main book exits-only, R9b stale benchmark, R9c a
  dropped decision bar.
Network stubbed everywhere: Yahoo daily (load_market), Yahoo 1h/1m (data.intraday_open), Coinbase.
"""

import json
import re
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import requests

from aitrader import cycle, data, journal
from aitrader import report as rep
from aitrader.market import UtcDailyCalendar
from aitrader.strategy import precompute_aux
from golden_util import FIRST_BAR, frozen_env, load_panel
from test_core import cfg_for
from test_regime import crypto_panel

UTC = timezone.utc
REAL_INTRADAY_OPEN = data.intraday_open  # the real function (frozen_env patches it per test)
I = 213  # a risk-on day on the synthetic panel with both coins picked (test_data_rules.CryptoRun)
STAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")  # journal.now_utc()


def settled_panel() -> dict:
    """crypto_panel with open[t+1] == close[t], as on Yahoo's settled history (spec 4: older closes equal the next
    open exactly), so the next_open rule does not move the decision close."""
    p = crypto_panel()
    close = p["close"]
    opn = close.shift(1).fillna(close.iloc[0])
    return {**p, "open": opn, "high": np.maximum(p["high"], opn), "low": np.minimum(p["low"], opn)}


def read_jsonl(state: Path, name: str) -> list[dict]:
    path = state / name
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def load(state: Path, name: str):
    path = state / name
    return json.loads(path.read_text()) if path.exists() else None


class CryptoBook(unittest.TestCase):
    """A crypto book in a temp state dir. Frozen clock (journal.now_utc), stubbed intraday bars and Coinbase."""

    def setUp(self):
        self.p = settled_panel()
        self.idx = self.p["close"].index
        self.cfg = data.load_config("crypto")
        self.coins = sorted(self.cfg["universe"])
        self.state = self.mkdtemp()
        self.reports = self.mkdtemp()
        self.bars: dict = {}  # (sym, ts, interval) -> open; anything else is a missing bar
        self.bar_calls: list = []
        self.sent: list = []
        self.prios: list = []  # notify priority per sent message
        self.cb = self.agree

    def mkdtemp(self) -> Path:
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        return d

    # ---- clock and stubs -------------------------------------------------------------------------
    def ts(self, i: int, hh: int, mm: int = 0, ss: int = 0) -> str:
        d = self.idx[i]
        return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=UTC).isoformat()

    def day(self, i: int) -> str:
        return str(self.idx[i].date())

    def dclose(self, i: int, sym: str) -> float:
        """The decision close of bar i (next_open: the open of row i+1; equal to close[i] on this panel)."""
        return float(self.p["open"].iloc[i + 1][sym])

    def agree(self, sym, day):
        return self.dclose(self.idx.get_loc(pd.Timestamp(day)), sym)

    def bar(self, sym, ts, interval):
        self.bar_calls.append((sym, ts, interval))
        return self.bars.get((sym, ts, interval))

    def set_bars(self, i: int, hh: int, interval: str = "1h", syms=None, mult: float = 1.01):
        """Intraday opens at day i hh:00 UTC: mult x the decision close of bar i-1 (never the daily open)."""
        for s in syms or self.coins:
            self.bars[(s, self.ts(i, hh), interval)] = round(self.dclose(i - 1, s) * mult, 2)

    def panel(self, upto: int, base: dict | None = None) -> dict:
        return {k: v.iloc[:upto + 1] for k, v in (base or self.p).items()}

    def at(self, upto: int, clock: str, propose: bool = False, execute: bool = True, seed: dict | None = None,
            panel: dict | None = None, patches: dict | None = None) -> dict:
        """One run_cycle with rows 0..upto visible at `clock` (UTC, journal.now_utc format)."""
        pn = panel if panel is not None else self.panel(upto)
        with frozen_env(self.state, None):
            journal.now_utc = lambda: clock
            rep.ROOT = self.reports
            cycle.load_config = lambda: self.cfg
            cycle.load_market = lambda c, rng="10y", age=0.1: pn
            cycle.coinbase_close = self.cb
            cycle.notify.send = lambda title, body, cfg, prio="default", **k: self.sent.append(body) or self.prios.append(prio) or []
            data.intraday_open = self.bar
            for k, v in (patches or {}).items():
                setattr(cycle, k, v)
            if seed is not None and not (self.state / "portfolio.json").exists():
                journal.save_json("portfolio.json", seed)
            return cycle.run_cycle(execute=execute, propose=propose)

    def seed(self, weights: dict, i: int) -> dict:
        """A book worth 100,000 holding `weights` at the decision close of bar i."""
        px = {s: self.dclose(i, s) for s in weights}
        pos = {s: {"qty": round(w * 100000.0 / px[s], 6), "avg_cost": px[s], "entry_date": "2024-06-01",
                   "peak_close": px[s], "last_price": px[s]} for s, w in weights.items()}
        return {"cash": 100000.0 - sum(q["qty"] * px[s] for s, q in pos.items()), "peak_equity": 100000.0,
                "blocked": {}, "positions": pos}

    def decide(self, i: int = I, **kw) -> dict:
        """The 00:12 UTC run on day i+1: decides bar i."""
        return self.at(i + 1, self.ts(i + 1, 0, 12), **kw)

    def pending(self) -> dict:
        return load(self.state, "pending.json")

    def trades(self) -> list[dict]:
        return read_jsonl(self.state, "trades.jsonl")


class Calendar(unittest.TestCase):
    def test_exec_ts_rules(self):
        """Decision 12: the first full hour strictly after logged_at, never earlier than D+1 01:00 UTC, formatted
        like journal.now_utc() (override cutoffs are compared as strings)."""
        d = pd.Timestamp("2026-11-09")
        ex = UtcDailyCalendar.exec_time
        self.assertEqual(ex(d, "2026-11-10T00:12:00+00:00"), "2026-11-10T01:00:00+00:00")
        self.assertEqual(ex(d, "2026-11-10T01:00:00+00:00"), "2026-11-10T02:00:00+00:00")
        self.assertEqual(ex(d, "2026-11-10T00:59:59+00:00"), "2026-11-10T01:00:00+00:00")
        self.assertEqual(ex(d, "2026-11-09T22:30:00+00:00"), "2026-11-10T01:00:00+00:00")  # never before D+1 01:00
        self.assertEqual(ex(d, "2026-11-11T05:40:12+00:00"), "2026-11-11T06:00:00+00:00")  # a late catch-up run
        self.assertTrue(STAMP.match(ex(d, "2026-11-10T00:12:00+00:00")))
        self.assertTrue(STAMP.match(journal.now_utc()))

    def test_calendar_basics(self):
        U, d = UtcDailyCalendar, pd.Timestamp("2026-11-09")
        self.assertEqual(U.periods_per_year, 365)
        self.assertEqual(U.bar_end(d), datetime(2026, 11, 10, tzinfo=UTC))
        self.assertEqual(U.session_window(d), (datetime(2026, 11, 9, tzinfo=UTC), datetime(2026, 11, 10, tzinfo=UTC)))
        at = datetime(2026, 11, 10, 0, 5, tzinfo=UTC)
        self.assertFalse(U.bar_is_final(d, at - timedelta(seconds=1), None))
        self.assertTrue(U.bar_is_final(d, at, None))
        self.assertTrue(U.bar_is_final(d, at + timedelta(hours=1), at))
        self.assertFalse(U.bar_is_final(d, at + timedelta(hours=1), at - timedelta(minutes=1)))  # fetched too early
        self.assertEqual(U.last_final_bar(datetime(2026, 11, 10, 0, 12, tzinfo=UTC)), d.date())
        self.assertEqual(U.last_final_bar(datetime(2026, 11, 10, 0, 4, tzinfo=UTC)), (d - pd.Timedelta(days=1)).date())
        self.assertEqual(U.cooldown_until("2026-11-10", 14), "2026-11-24")  # calendar days, not business days

    def test_fill_prices_chain_and_intraday_open(self):
        """fill_prices: 1h open -> 1m open -> None, all coins or none. intraday_open: missing = no row at ts, a null
        open or Yahoo's 404/422 "no data"; volume is ignored; an unreachable Yahoo raises data.Unreachable."""
        ts = "2026-11-10T01:00:00+00:00"
        t0 = int(datetime.fromisoformat(ts).timestamp())
        opens = {("BTC-USD", "1h"): 74000.0, ("ETH-USD", "1m"): 2100.0}
        with mock.patch.object(data, "intraday_open", lambda s, t, iv: opens.get((s, iv)) if t == ts else None):
            self.assertEqual(UtcDailyCalendar.fill_prices(["ETH-USD", "BTC-USD"], ts),
                             ({"BTC-USD": 74000.0, "ETH-USD": 2100.0}, "BTC-USD:1h,ETH-USD:1m"))
            self.assertEqual(UtcDailyCalendar.fill_prices(["BTC-USD"], ts), ({"BTC-USD": 74000.0}, "1h"))
            self.assertIsNone(UtcDailyCalendar.fill_prices(["BTC-USD", "XRP-USD"], ts))  # one coin missing: nothing

        def chart(rows, opens_):
            return {"chart": {"result": [{"meta": {}, "timestamp": rows,
                                          "indicators": {"quote": [{"open": opens_, "volume": [0] * len(rows)}]}}]}}

        seen = []
        answers = {"1h": chart([t0, t0 + 3600], [74000.5, None]), "1m": chart([t0 + 60], [1.0])}

        def get(url, params=None, **k):
            seen.append((url, params))
            return answers[params["interval"]]

        with mock.patch.object(data, "_get_json", get):
            self.assertEqual(data.intraday_open("BTC-USD", ts, "1h"), 74000.5)  # volume 0 still counts
            self.assertIsNone(data.intraday_open("BTC-USD", ts, "1m"))  # no row at ts
        self.assertEqual(seen[0][1], {"period1": t0, "period2": t0 + 3600, "interval": "1h"})
        self.assertIn("BTC-USD", seen[0][0])
        with mock.patch.object(data, "_get_json", lambda *a, **k: chart([t0], [None])):
            self.assertIsNone(data.intraday_open("BTC-USD", ts, "1h"))  # null open
        # final review item 6: an unreachable Yahoo is not a missing bar. A transport failure raises data.Unreachable;
        # Yahoo's own "no data" answer (HTTP 404 / 422) is a missing bar (None)
        with mock.patch.object(data, "_get_json", mock.Mock(side_effect=RuntimeError("GET failed"))):
            with self.assertRaises(data.Unreachable):
                data.intraday_open("BTC-USD", ts, "1h")

        class Resp:
            def __init__(self, code):
                self.status_code = code

            def raise_for_status(self):
                raise requests.HTTPError(f"{self.status_code}", response=self)

        with mock.patch.object(data.time, "sleep", lambda s: None):
            with mock.patch.object(data._session, "get", mock.Mock(side_effect=requests.ConnectionError("down"))):
                with self.assertRaises(data.Unreachable):
                    data.intraday_open("BTC-USD", ts, "1h")
            with mock.patch.object(data._session, "get", lambda *a, **k: Resp(503)):
                with self.assertRaises(data.Unreachable):
                    data.intraday_open("BTC-USD", ts, "1h")
            for code in (404, 422):  # Yahoo's "no data" / "range not available": a missing bar
                with mock.patch.object(data._session, "get", lambda *a, code=code, **k: Resp(code)):
                    self.assertIsNone(data.intraday_open("BTC-USD", ts, "1h"), code)


class DecideAndFill(CryptoBook):
    def test_decide_then_fill_at_0100_hour_open(self):
        out = self.decide()
        self.assertTrue(out["decided_now"])
        self.assertEqual(out["executed"], [])
        pend = self.pending()
        self.assertEqual((pend["decision_date"], pend["exec_ts"]), (self.day(I), self.ts(I + 1, 1)))
        self.assertEqual(pend["decision_close"], {s: self.dclose(I, s) for s in self.coins})
        self.assertEqual(self.bar_calls, [])  # nothing is priced before exec_ts

        self.set_bars(I + 1, 1, "1h")
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        slip = self.cfg["costs"]["slippage_bps"] / 1e4
        self.assertEqual({(f["side"], f["symbol"]) for f in out["executed"]}, {("BUY", s) for s in self.coins})
        for f in out["executed"]:
            self.assertEqual(f["date"], self.day(I + 1))
            bar = self.bars[(f["symbol"], self.ts(I + 1, 1), "1h")]
            self.assertEqual(f["price"], round(bar * (1 + slip), 4))
            self.assertNotAlmostEqual(f["price"], float(self.p["open"].iloc[I + 1][f["symbol"]]) * (1 + slip), places=2)
        self.assertEqual([(t["fill_source"], t["fill_ts"]) for t in self.trades()], [("1h", self.ts(I + 1, 1))] * 2)
        pend = self.pending()
        self.assertEqual((pend["status"], pend["fill_source"], pend["fill_ts"]), ("executed", "1h", self.ts(I + 1, 1)))

    def test_fill_falls_back_to_minute_then_waits(self):
        self.decide()
        self.set_bars(I + 1, 1, "1h", ["BTC-USD"])
        self.set_bars(I + 1, 1, "1m", ["ETH-USD"], mult=1.02)  # ETH's 1h bar is missing; its 1m bar is there
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertEqual(len(out["executed"]), 2)
        eth = next(f for f in out["executed"] if f["symbol"] == "ETH-USD")
        slip = self.cfg["costs"]["slippage_bps"] / 1e4
        self.assertEqual(eth["price"], round(self.bars[("ETH-USD", self.ts(I + 1, 1), "1m")] * (1 + slip), 4))
        self.assertEqual({t["fill_source"] for t in self.trades()}, {"BTC-USD:1h,ETH-USD:1m"})

        self.setUp()  # a fresh book: ETH has neither bar at 01:00 -> wait; 02:00 has both coins -> fill there
        self.decide()
        self.set_bars(I + 1, 1, "1h", ["BTC-USD"])
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertEqual(out["executed"], [])
        self.assertIn(("ETH-USD", self.ts(I + 1, 1), "1m"), self.bar_calls)  # the minute fallback was tried
        self.assertEqual(self.pending()["status"], "pending")
        self.assertTrue(any(self.ts(I + 1, 1) in e for e in out["events"]))
        self.set_bars(I + 1, 2, "1h", mult=0.99)
        out = self.at(I + 1, self.ts(I + 1, 2, 5))
        self.assertEqual(len(out["executed"]), 2)
        self.assertEqual({t["fill_ts"] for t in self.trades()}, {self.ts(I + 1, 2)})
        self.assertEqual(self.pending()["exec_ts"], self.ts(I + 1, 1))  # the order's exec_ts is not rewritten

    def test_all_or_nothing_fill(self):
        """Review Focus 3: the 01:00 bar is missing for one coin: nothing fills, the orders stay pending; the next run
        fills them once the bar is there."""
        self.decide()
        before = (self.state / "portfolio.json").read_bytes()
        self.set_bars(I + 1, 1, "1h", ["BTC-USD"])
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertEqual(out["executed"], [])
        self.assertEqual(self.trades(), [])
        self.assertEqual(json.loads(before)["positions"], load(self.state, "portfolio.json")["positions"])
        self.assertEqual(self.pending()["status"], "pending")
        self.set_bars(I + 1, 1, "1h", ["ETH-USD"])  # Yahoo published ETH's 01:00 bar late
        out = self.at(I + 1, self.ts(I + 1, 1, 40))
        self.assertEqual({f["symbol"] for f in out["executed"]}, set(self.coins))
        self.assertEqual({t["fill_ts"] for t in self.trades()}, {self.ts(I + 1, 1)})

    def test_expired_unfilled_record(self):
        self.decide()
        self.at(I + 1, self.ts(I + 1, 1, 7))  # no bars at all: stays pending
        old = self.pending()
        out = self.decide(I + 1)  # the next decision overwrites it
        self.assertTrue(out["decided_now"])
        recs = read_jsonl(self.state, "decisions.jsonl")
        self.assertEqual([r.get("event") for r in recs], [None, "expired_unfilled", None])
        exp = recs[1]
        self.assertEqual((exp["date"], exp["exec_ts"], exp["targets"]), (self.day(I), self.ts(I + 1, 1), old["targets"]))
        self.assertEqual(recs[2]["date"], self.day(I + 1))
        with mock.patch.object(journal, "STATE", self.state):
            self.assertTrue(journal.verify_chain("decisions.jsonl")[0])
        self.assertEqual((self.pending()["decision_date"], self.pending()["exec_ts"]), (self.day(I + 1), self.ts(I + 2, 1)))
        self.assertTrue(any("expired_unfilled" in e for e in out["events"]))

        self.setUp()  # a filled pending is not an expired one
        self.decide()
        self.set_bars(I + 1, 1)
        self.at(I + 1, self.ts(I + 1, 1, 7))
        self.decide(I + 1)
        self.assertNotIn("expired_unfilled", [r.get("event") for r in read_jsonl(self.state, "decisions.jsonl")])

    def test_exec_ts_through_run_cycle(self):
        self.at(I + 1, self.ts(I + 1, 1, 0, 0))  # a decision logged at 01:00:00 executes at 02:00
        self.assertEqual(self.pending()["exec_ts"], self.ts(I + 1, 2))

    def test_override_cutoff_is_exec_ts(self):
        self.decide()
        ov = {"date": self.day(I), "vetoes": {"ETH-USD": {"reason": "before", "logged_at": self.ts(I + 1, 0, 59, 59)}},
              "size_mult": {"BTC-USD": [0.5, "after", self.ts(I + 1, 1, 0, 1)]}}
        (self.state / "overrides.json").write_text(json.dumps(ov))
        self.set_bars(I + 1, 1)
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        pend = self.pending()
        self.assertEqual([(o["symbol"], o["action"]) for o in pend["overrides"]], [("ETH-USD", "veto")])
        self.assertNotIn("ETH-USD", pend["targets"])
        self.assertEqual(pend["targets"]["BTC-USD"], pend["targets_raw"]["BTC-USD"])  # logged after exec_ts: ignored
        self.assertEqual([f["symbol"] for f in out["executed"]], ["BTC-USD"])

        self.setUp()  # the cutoff stays exec_ts when the fill slips to a later hour
        self.decide()
        ov["size_mult"]["BTC-USD"][2] = self.ts(I + 1, 1, 30)
        (self.state / "overrides.json").write_text(json.dumps(ov))
        self.set_bars(I + 1, 2)
        self.at(I + 1, self.ts(I + 1, 2, 5))
        pend = self.pending()
        self.assertEqual((pend["status"], pend["fill_ts"]), ("executed", self.ts(I + 1, 2)))
        self.assertEqual([o["symbol"] for o in pend["overrides"]], ["ETH-USD"])

    def test_idempotent_rerun_no_double_fill(self):
        self.decide()
        self.set_bars(I + 1, 1)
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertTrue(out["executed"])
        trades, book = self.trades(), (self.state / "portfolio.json").read_bytes()
        n_dec = len(read_jsonl(self.state, "decisions.jsonl"))
        self.set_bars(I + 1, 2)
        for clock in (self.ts(I + 1, 1, 30), self.ts(I + 1, 8, 3)):
            out = self.at(I + 1, clock)
            self.assertEqual((out["executed"], out["decided_now"]), ([], False))
        self.assertEqual(self.trades(), trades)
        self.assertEqual(json.loads((self.state / "portfolio.json").read_bytes())["positions"], json.loads(book)["positions"])
        self.assertEqual(len(read_jsonl(self.state, "decisions.jsonl")), n_dec)
        with mock.patch.object(journal, "STATE", self.state):
            self.assertTrue(journal.verify_chain("trades.jsonl")[0])


class BookKeeping(CryptoBook):
    def test_one_equity_mark_per_bar(self):
        self.decide()
        rows = read_jsonl(self.state, "equity.jsonl")
        self.assertEqual([(r["date"], r["decided"]) for r in rows], [(self.day(I), True)])
        self.assertEqual(rows[0]["bench_price"], self.dclose(I, "BTC-USD"))  # marked at the decision close
        self.at(I + 1, self.ts(I + 1, 0, 30))
        self.set_bars(I + 1, 1)
        self.at(I + 1, self.ts(I + 1, 1, 7))  # the fill run
        self.at(I + 1, self.ts(I + 1, 8, 3), execute=False)
        self.assertEqual(len(read_jsonl(self.state, "equity.jsonl")), 1)
        self.decide(I + 1)
        self.assertEqual([r["date"] for r in read_jsonl(self.state, "equity.jsonl")], [self.day(I), self.day(I + 1)])

    def test_vix_earnings_overlays_corporate_actions_off(self):
        asked = []

        def fake(sym, rng="5y", max_age_hours=6.0):
            asked.append(sym)
            df = pd.DataFrame({c: [1.0, 2.0] for c in ("open", "high", "low", "close", "volume")},
                              index=pd.date_range("2026-11-01", periods=2))
            df.attrs["fetched_at"] = datetime(2026, 11, 3, tzinfo=UTC)
            return df

        with mock.patch.object(data, "fetch_daily", fake):
            m = data.load_market(self.cfg, "max", 0.1)
            self.assertNotIn("^VIX", asked)
            self.assertFalse({"vix", "_require_vix"} & set(m))
            data.load_market({"universe": {"SPY": "Index"}, "market": {"vix": True}}, "10y", 0.1)
            self.assertIn("^VIX", asked)  # the stock book still loads it

        def boom(*a, **k):
            raise AssertionError("a stock-only source was called on the crypto book")

        off = {"earnings_on": boom, "corporate_actions": boom, "_overlays_once_per_day": boom}
        out = self.decide(seed=self.seed({"BTC-USD": 0.3}, I), patches=off)
        self.assertTrue(out["decided_now"])
        self.assertEqual(read_jsonl(self.state, "decisions.jsonl")[-1]["earnings_blackout"], {})
        self.assertFalse({"earnings.json", "overlays.json"} & {f.name for f in self.state.iterdir()})
        text = next(self.reports.rglob("*.md")).read_text()
        self.assertNotIn("Quiver", text)
        self.assertNotIn("OpenInsider", text)

    def test_report_under_reports_crypto(self):
        out = self.decide()
        md = sorted(p.relative_to(self.reports) for p in self.reports.rglob("*.md"))
        self.assertEqual(md, [Path("reports/crypto") / f"{out['date']}.md"])
        text = (self.reports / md[0]).read_text()
        self.assertIn("מחיר אחרון BTC-USD", text)
        self.assertIn("מול קווי בסיס", text)
        self.assertIn("BTC-USD ", text.split("מול קווי בסיס")[1].splitlines()[0])
        self.assertNotIn("SPY", text)
        base = load(self.state, "latest.json")["baselines"]
        self.assertEqual(set(base), {"bench_since_start", "equal_weight_since_start"})


class Proposal(CryptoBook):
    def test_proposal_deleted_on_decision_crypto_only(self):
        self.at(I + 1, self.ts(I + 1, 0, 11), propose=True)
        self.assertTrue((self.state / "proposal.json").exists())
        self.decide()
        self.assertFalse((self.state / "proposal.json").exists())

        full = load_panel()  # the stock book keeps its proposal
        cfg = cfg_for(full)
        cfg["risk"]["min_score"] = -1.0
        stock = self.mkdtemp()
        with frozen_env(stock, None):
            cycle.load_config = lambda: cfg
            cycle.load_market = lambda c, rng="10y", age=0.1: {k: v.iloc[:FIRST_BAR] for k, v in full.items()}
            cycle.run_cycle(propose=True)
            out = cycle.run_cycle()
        self.assertTrue(out["decided_now"])
        self.assertTrue((stock / "proposal.json").exists())
        latest = load(stock, "latest.json")
        self.assertIn("spy_since_start", latest["baselines"])
        self.assertNotIn("bench_since_start", latest["baselines"])
        self.assertNotIn("exec_ts", load(stock, "pending.json"))


class Rulings(CryptoBook):
    def test_revised_close_audit_alerts_above_bps(self):
        """R6: the close the last decision used against the history value for that bar, once that bar is no longer
        the decision bar; above market.revised_close_alert_bps an event, a decisions.jsonl record and an alert."""
        self.cfg["market"]["close_source"] = "next_open"  # this test is about the next_open rule; the book ships "yahoo" (Task 11)
        self.assertEqual(self.cfg["market"]["revised_close_alert_bps"], 5)
        self.assertNotIn("revised_close_alert_bps", data.load_config("stocks")["market"])
        self.decide()
        self.set_bars(I + 1, 1)
        self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertFalse(any("bp" in e for e in self.sent))  # the decision bar itself is never audited

        revised = {**self.p, "close": self.p["close"].copy()}
        revised["close"].iloc[I, revised["close"].columns.get_loc("BTC-USD")] *= 1.001  # +10 bp on bar D
        # the D+2 00:12 run sees D+1 final but no D+2 row yet: D is audited, then D+1 is dropped (no decision)
        out = self.at(I + 1, self.ts(I + 2, 0, 12), panel=self.panel(I + 1, revised))
        self.assertFalse(out["decided_now"])
        alerts = [e for e in out["events"] if "BTC-USD" in e and "bp" in e]
        self.assertEqual(len(alerts), 1)
        self.assertNotIn("ETH-USD", alerts[0])
        self.assertTrue(any(alerts[0] in body for body in self.sent))
        rec = [r for r in read_jsonl(self.state, "decisions.jsonl") if r.get("event") == "revised_close"]
        self.assertEqual(len(rec), 1)
        self.assertEqual((rec[0]["date"], rec[0]["limit_bps"]), (self.day(I), 5))
        self.assertAlmostEqual(rec[0]["gaps_bps"]["BTC-USD"], 10.0, places=6)
        self.assertEqual(rec[0]["gaps_bps"]["ETH-USD"], 0.0)
        out = self.at(I + 1, self.ts(I + 2, 1, 7), panel=self.panel(I + 1, revised))  # deduped
        self.assertFalse([e for e in out["events"] if "bp" in e])
        self.assertEqual(len([r for r in read_jsonl(self.state, "decisions.jsonl") if r.get("event") == "revised_close"]), 1)

        self.setUp()  # 3 bp: inside the limit, audited without an alert
        self.decide()
        small = {**self.p, "close": self.p["close"].copy()}
        small["close"].iloc[I, small["close"].columns.get_loc("BTC-USD")] *= 1.0003
        out = self.decide(I + 1, panel=self.panel(I + 2, small))
        self.assertTrue(out["decided_now"])
        self.assertFalse([e for e in out["events"] if "bp" in e])
        self.assertNotIn("revised_close", [r.get("event") for r in read_jsonl(self.state, "decisions.jsonl")])

    def test_revised_close_audit_on_the_shipped_yahoo_source(self):
        """R6 under close_source "yahoo" (shipped, Task 11): a decision close that history later changes by more
        than the limit is alerted once the bar is no longer the decision bar; the same run decides the next bar."""
        self.assertEqual(self.cfg["market"]["close_source"], "yahoo")
        self.decide()
        self.set_bars(I + 1, 1)
        self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertFalse(any("bp" in e for e in self.sent))
        revised = {**self.p, "close": self.p["close"].copy()}
        revised["close"].iloc[I, revised["close"].columns.get_loc("BTC-USD")] *= 1.001  # +10 bp on bar D
        out = self.at(I + 1, self.ts(I + 2, 0, 12), panel=self.panel(I + 1, revised))
        self.assertTrue(out["decided_now"])
        alerts = [e for e in out["events"] if "BTC-USD" in e and "bp" in e]
        self.assertEqual(len(alerts), 1)
        self.assertNotIn("ETH-USD", alerts[0])
        self.assertEqual([r["date"] for r in read_jsonl(self.state, "decisions.jsonl") if r.get("event") == "revised_close"], [self.day(I)])

    def test_coinbase_breach_persisted_and_main_fills_exits_only(self):
        """R9a: a breach is persisted on the pending order; the main book fills exits-only, the shadow book does not."""
        held = {"BTC-USD": 0.10, "ETH-USD": 0.50}
        self.cb = lambda sym, day: self.agree(sym, day) * (1.03 if sym == "BTC-USD" else 1.0)
        self.decide(seed=self.seed(held, I))
        pend = self.pending()
        self.assertIs(pend["coinbase_breach"], True)
        self.assertAlmostEqual(pend["targets"]["BTC-USD"], 0.10, places=6)
        # BTC opens 60% lower at 01:00: its weight falls far under the clamped target, so a normal fill would buy it
        self.bars[("BTC-USD", self.ts(I + 1, 1), "1h")] = round(self.dclose(I, "BTC-USD") * 0.4, 2)
        self.bars[("ETH-USD", self.ts(I + 1, 1), "1h")] = round(self.dclose(I, "ETH-USD"), 2)
        control = self.mkdtemp()
        shutil.copytree(self.state, control, dirs_exist_ok=True)
        unflagged = load(control, "pending.json")
        unflagged.pop("coinbase_breach")
        (control / "pending.json").write_text(json.dumps(unflagged))

        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertEqual([(f["side"], f["symbol"]) for f in out["executed"]], [("SELL", "ETH-USD")])
        self.assertIn("BTC-USD", load(self.state, "shadow_portfolio.json")["positions"])  # the shadow is not clamped

        self.state = control
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        self.assertIn(("BUY", "BTC-USD"), [(f["side"], f["symbol"]) for f in out["executed"]])

        self.setUp()  # no breach: no flag
        self.decide(seed=self.seed(held, I))
        self.assertNotIn("coinbase_breach", self.pending())

    def test_stale_benchmark_no_decision(self):
        """R9b: the benchmark stale on the decision bar (prev, when last is not final) means no decision this run and
        an event. Crypto: the benchmark is a universe coin, so the run skips. Stocks: a pending fill still happens."""
        d_end = UtcDailyCalendar.bar_end(self.idx[I]) + timedelta(minutes=5)
        pn = self.panel(I + 1)
        pn["_fetched_at"] = {"BTC-USD": d_end - timedelta(minutes=2), "ETH-USD": d_end + timedelta(minutes=7)}
        out = self.at(I + 1, self.ts(I + 1, 1, 7), panel=pn)
        self.assertEqual((out["decided_now"], out["executed"]), (False, []))
        self.assertIn("BTC-USD", out["skipped"])
        self.assertIsNone(self.pending())

        full = load_panel()
        cfg = cfg_for(full)
        cfg["risk"]["min_score"] = -1.0
        stock = self.mkdtemp()
        idx = full["close"].index
        sent: list = []

        def end(d):
            return cycle._bar_end_utc(d, cfg)

        with frozen_env(stock, None):
            cycle.load_config = lambda: cfg
            cycle.load_market = lambda c, rng="10y", age=0.1: {k: v.iloc[:FIRST_BAR] for k, v in full.items()}
            self.assertTrue(cycle.run_cycle()["decided_now"])  # decides FIRST_BAR-1
            pn = {k: v.iloc[:FIRST_BAR + 2] for k, v in full.items()}
            fresh = end(idx[FIRST_BAR + 1]) + timedelta(minutes=30)
            pn["_fetched_at"] = {s: fresh for s in full["close"].columns}
            pn["_fetched_at"]["SPY"] = end(idx[FIRST_BAR]) - timedelta(minutes=10)  # stale on last AND on prev
            cycle.load_market = lambda c, rng="10y", age=0.1: pn
            cycle.notify.send = lambda title, body, cfg, prio="default": sent.append(body) or []
            prop = cycle.run_cycle(propose=True)
            out = cycle.run_cycle()
        self.assertIn("SPY", prop["skipped"])
        self.assertFalse(out["decided_now"])
        self.assertTrue(out["executed"])  # the earlier decision still fills at the next open
        self.assertEqual(load(stock, "pending.json")["decision_date"], str(idx[FIRST_BAR - 1].date()))
        self.assertTrue(any("SPY" in e and str(idx[FIRST_BAR].date()) in e for e in out["events"]))
        self.assertTrue(sent)

    def test_shipped_close_source_is_yahoo_and_decides_without_the_next_row(self):
        """Task 11 revised-close check: the open of the D+1 row is what Yahoo rewrites, so the book ships
        close_source "yahoo": the 00:12 run decides on D from Yahoo's close of D, with no D+1 row and no next_open log."""
        self.assertEqual(self.cfg["market"]["close_source"], "yahoo")
        out = self.at(I, self.ts(I + 1, 0, 12))  # rows up to D = I only
        self.assertTrue(out["decided_now"])
        pend = self.pending()
        self.assertEqual(pend["decision_date"], self.day(I))
        self.assertEqual(pend["decision_close"], {s: float(self.p["close"].iloc[I][s]) for s in self.coins})
        self.assertNotIn("close_source", read_jsonl(self.state, "decisions.jsonl")[-1]["diag"])

    def test_dropped_decision_bar_fill_path(self):
        """R9c: at D+1 00:12 Yahoo has no D+1 row yet (next_open drops bar D): no decision, no crash, and the pending
        order of D-1 still fills at its exec_ts hour."""
        self.cfg["market"]["close_source"] = "next_open"  # this test is about the next_open rule; the book ships "yahoo" (Task 11)
        self.decide(I - 1)  # decides D-1 = I-1 at I 00:12; exec_ts I 01:00
        for with_bars in (False, True):
            if with_bars:
                self.set_bars(I, 1)
            out = self.at(I, self.ts(I + 1, 0, 12))  # rows up to D = I only
            self.assertFalse(out["decided_now"])
            self.assertTrue(any(self.day(I) in e for e in out["events"]))
            self.assertEqual(self.pending()["decision_date"], self.day(I - 1))
            self.assertEqual(bool(out["executed"]), with_bars)
        self.assertEqual({t["fill_ts"] for t in self.trades()}, {self.ts(I, 1)})
        self.assertEqual(len([r for r in read_jsonl(self.state, "decisions.jsonl") if not r.get("event")]), 1)


class FinalReview(CryptoBook):
    """Final whole-branch review: item 3 (a stop that could not fill is carried, never waited out) and item 6 (the
    hourly fill walk is capped at market.fill_max_wait_hours and stops on an unreachable Yahoo)."""

    def old_pending(self, stopped: list, targets: dict) -> None:
        """An unfilled order of decision I-1 (exec_ts I 01:00) as cycle.py writes it; no bar ever priced it."""
        pend = {"decision_date": self.day(I - 1), "status": "pending", "rebalance": False, "exits_only": bool(stopped),
                "targets": targets, "targets_raw": dict(targets), "stopped_shadow": [], "shadow_hold": {},
                "stopped": stopped, "overrides": [], "earnings_blackout": {}, "preview_at_close": [], "new_entries": [],
                "logged_at": self.ts(I, 0, 12), "exec_ts": self.ts(I, 1)}
        (self.state / "pending.json").write_text(json.dumps(pend))

    def test_stop_in_expired_pending_is_forced_at_next_fill(self):
        held = {"BTC-USD": 0.3, "ETH-USD": 0.3}
        # control: the same book with no stop in the expired order keeps ETH (its price is above the stop line now)
        self.old_pending([], dict(held))
        self.decide(seed=self.seed(held, I - 1))
        self.assertIn("ETH-USD", self.pending()["targets"])
        self.assertNotIn("ETH-USD", self.pending()["stopped"])

        self.setUp()  # the I-1 decision stopped ETH; its exec_ts hour never got a price, so the stop never filled
        self.old_pending(["ETH-USD"], {"BTC-USD": 0.3})
        out = self.decide(seed=self.seed(held, I - 1))
        self.assertTrue(out["decided_now"])
        self.assertEqual([r.get("event") for r in read_jsonl(self.state, "decisions.jsonl")], ["expired_unfilled", None])
        pend = self.pending()
        self.assertNotIn("ETH-USD", pend["targets"])
        self.assertNotIn("ETH-USD", pend["targets_raw"])
        self.assertIn("ETH-USD", pend["stopped"])
        self.assertEqual(pend["carried_stops"], ["ETH-USD"])
        urgent = [b for b, pr in zip(self.sent, self.prios) if pr == "urgent"]
        self.assertEqual(len(urgent), 1)
        self.assertIn("ETH-USD", urgent[0])
        self.assertIn(f"stop could not fill on {self.day(I)}", urgent[0])
        self.assertTrue(any("ETH-USD" in e and "stop" in e for e in out["events"]))
        prop = self.at(I + 1, self.ts(I + 1, 0, 30), propose=True)  # the desk's view of the same date matches it
        self.assertEqual((prop["carried_stops"], "ETH-USD" in prop["targets"]), (["ETH-USD"], False))
        self.assertEqual(len([b for b, pr in zip(self.sent, self.prios) if pr == "urgent"]), 1)  # alerted once

        self.set_bars(I + 1, 1)  # the next fill sells it, as a stop (cooldown)
        out = self.at(I + 1, self.ts(I + 1, 1, 7))
        eth = [f for f in out["executed"] if f["symbol"] == "ETH-USD"]
        self.assertEqual([(f["side"], f["reason"]) for f in eth], [("SELL", "stop")])
        book = load(self.state, "portfolio.json")
        self.assertNotIn("ETH-USD", book["positions"])
        self.assertIn("ETH-USD", book["blocked"])

    def test_expired_regime_off_exit_is_decided_again(self):
        """Gate finding B1 (2026-11-11): the regime turns off, the exit order never fills and expires. The book's
        regime was saved at decision time, so the next decision sees no regime change; it must still be a full
        decision (not exits-only, which would hold the book) and sell. On the shipped one-coin profile, whose only
        exits are regime-off and the -50% step."""
        self.cfg = data.load_config("crypto", "crypto_base")
        self.coins = sorted(self.cfg["universe"])
        self.p = {k: v[self.coins] if isinstance(v, pd.DataFrame) and set(self.coins) <= set(v.columns) else v
                  for k, v in self.p.items()}
        reg = precompute_aux(self.p, self.cfg)["regime"]
        j = next(k for k in range(250, len(reg) - 3)
                 if reg.iloc[k - 1] == "risk_on" and all(reg.iloc[k:k + 2] == "risk_off"))
        seed = {**self.seed({"BTC-USD": 0.5}, j - 1), "regime": "risk_on", "dd_state": "normal", "last_rebalance": self.day(j - 2)}
        self.decide(j, seed=seed)
        first = self.pending()
        self.assertEqual((first["targets"], first["exits_only"]), ({}, False))  # the regime change sells everything
        out = self.decide(j + 1)  # no intraday bar came: the order expires at the next decision
        pend = self.pending()
        self.assertEqual([r.get("event") for r in read_jsonl(self.state, "decisions.jsonl")], [None, "expired_unfilled", None])
        self.assertTrue(out["decided_now"])
        self.assertFalse(pend["exits_only"])
        self.assertNotIn("BTC-USD", pend["targets"])
        self.set_bars(j + 2, 1)
        out = self.at(j + 2, self.ts(j + 2, 1, 7))
        self.assertEqual([(f["side"], f["symbol"]) for f in out["executed"]], [("SELL", "BTC-USD")])
        self.assertNotIn("BTC-USD", load(self.state, "portfolio.json")["positions"])

    def test_fill_walk_capped_at_fill_max_wait_hours(self):
        self.cfg["market"]["close_source"] = "next_open"  # this test is about the next_open rule; the book ships "yahoo" (Task 11)
        self.assertEqual(self.cfg["market"]["fill_max_wait_hours"], 24)
        self.assertNotIn("fill_max_wait_hours", data.load_config("stocks")["market"])
        self.decide()  # exec_ts I+1 01:00
        self.set_bars(I + 2, 1)  # first priced 24 h after exec_ts: past the cap
        out = self.at(I + 1, self.ts(I + 3, 5))  # a catch-up run 52 h later; no row I+2 yet, so no new decision
        self.assertFalse(out["decided_now"])
        self.assertEqual(out["executed"], [])
        self.assertEqual(self.pending()["status"], "pending")
        hours = sorted({ts for _, ts, _ in self.bar_calls})
        self.assertEqual((len(hours), hours[0], hours[-1]), (24, self.ts(I + 1, 1), self.ts(I + 2, 0)))
        self.assertTrue(any("24" in e and self.ts(I + 1, 1) in e for e in out["events"]))

    def test_fill_walk_stops_on_unreachable_yahoo(self):
        self.decide()
        calls = []

        def down(url, params=None, **k):
            calls.append(params)
            raise RuntimeError("GET failed: connection refused")

        self.bar = REAL_INTRADAY_OPEN
        with mock.patch.object(data, "_get_json", down):
            out = self.at(I + 1, self.ts(I + 1, 5, 7))  # 01:00 .. 05:00 are due; Yahoo answers none of them
        self.assertEqual(len(calls), 1)  # the walk stops at the first transport failure
        self.assertEqual(out["executed"], [])
        self.assertEqual(self.pending()["status"], "pending")
        self.assertTrue(any("Yahoo" in e for e in out["events"]))


if __name__ == "__main__":
    unittest.main()
