"""Data rules (plan 2026-11-09-crypto-book-v1, Task 5; planning decisions 10 and 11, spec section 4).

* History: rng "max" fetches period1=0..now and asserts daily granularity (range=max silently returns monthly bars).
* Bar-final by fetch time: a bar is final only if its symbol was fetched after bar_end (stocks 16:05 New York, also on
  early-close days; crypto 00:05 UTC the next day). A frame/panel without fetch times counts as fresh (ruling R1).
* Stocks: a stale benchmark makes the newest bar not final; a stale or absent symbol is frozen (no buy, no sell).
* Crypto: any stale or absent coin skips the run before any decision or fill.
* next_open: the decision close of the last final bar D is the open of the D+1 row; no D+1 row, no decision on D.
* Coinbase guard: a gap above market.coinbase_guard_pct clamps the book (exits only); unreachable proceeds.
The network is stubbed everywhere.
"""

import contextlib
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from aitrader import cycle, data, journal
from aitrader.signals import compute_all
from aitrader.strategy import build_targets, precompute_aux
from golden_util import FIRST_BAR, frozen_env, load_panel
from test_core import cfg_for
from test_regime import crypto_panel

UTC, NY = timezone.utc, ZoneInfo("America/New_York")


def stock_end(d) -> datetime:
    return datetime(d.year, d.month, d.day, 16, 5, tzinfo=NY)


def crypto_end(d) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC) + timedelta(days=1, minutes=5)


def chart_json(granularity: str, n: int = 3) -> dict:
    t0 = 1_700_000_000 - 1_700_000_000 % 86400
    ts = [t0 + 86400 * k for k in range(n)]
    px = [100.0 + k for k in range(n)]
    return {"chart": {"result": [{
        "meta": {"dataGranularity": granularity, "exchangeTimezoneName": "UTC"},
        "timestamp": ts,
        "indicators": {"quote": [{"open": px, "high": px, "low": px, "close": px, "volume": [1.0] * n}],
                       "adjclose": [{"adjclose": px}]},
    }], "error": None}}


class HistoryAndFetchTime(unittest.TestCase):
    def setUp(self):
        self.cache = Path(tempfile.mkdtemp())
        self.patch = mock.patch.object(data, "CACHE", self.cache)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.cache, ignore_errors=True)

    def test_max_history_asserts_daily(self):
        calls = []

        def monthly(url, params=None, **k):
            calls.append(params)
            return chart_json("1mo")

        with mock.patch.object(data, "_get_json", monthly), self.assertRaises(ValueError) as ctx:
            data.fetch_daily("BTC-USD", "max", 0.0)
        self.assertIn("1mo", str(ctx.exception))
        self.assertEqual(calls[0]["period1"], 0)
        self.assertNotIn("range", calls[0])
        self.assertEqual(calls[0]["interval"], "1d")
        self.assertLess(abs(calls[0]["period2"] - time.time()), 120)
        self.assertEqual(list(self.cache.glob("*.csv")), [])  # a monthly answer is never cached

        before = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=1)
        with mock.patch.object(data, "_get_json", lambda url, params=None, **k: chart_json("1d")):
            df = data.fetch_daily("BTC-USD", "max", 0.0)
        t = df.attrs["fetched_at"]
        self.assertEqual(len(df), 3)
        self.assertIsNotNone(t.tzinfo)
        self.assertTrue(before <= t <= datetime.now(UTC))
        path = self.cache / "BTC-USD_max.csv"
        self.assertEqual(datetime.fromtimestamp(path.stat().st_mtime, UTC), t)  # the cache time is the fetch time
        self.assertEqual(data.fetch_daily("BTC-USD", "max", 1e6).attrs["fetched_at"], t)  # a cached read keeps it

        old = time.time() - 3 * 3600  # an outage falls back to the stale cache, which carries its old fetch time
        os.utime(path, (old, old))

        def down(url, params=None, **k):
            raise RuntimeError("429")

        with mock.patch.object(data, "_get_json", down), contextlib.redirect_stdout(io.StringIO()):
            stale = data.fetch_daily("BTC-USD", "max", 0.0)
        self.assertEqual(stale.attrs["fetched_at"], datetime.fromtimestamp(old, UTC))

    def test_fetch_panel_and_load_market_keep_fetched_at(self):
        """DataFrame attrs do not survive the concat into wide panels; panel["_fetched_at"] keeps each symbol's."""
        idx = pd.date_range("2026-11-01", periods=4, freq="D")
        times = {"BTC-USD": datetime(2026, 11, 5, 0, 12, tzinfo=UTC), "ETH-USD": datetime(2026, 11, 4, 23, 50, tzinfo=UTC),
                 "^VIX": datetime(2026, 11, 5, 0, 13, tzinfo=UTC)}

        def fake(sym, rng="5y", max_age_hours=6.0):
            if sym == "XRP-USD":
                raise RuntimeError("no chart data")
            df = pd.DataFrame({c: np.arange(4.0) + 1 for c in ("open", "high", "low", "close", "volume")}, index=idx)
            df.attrs["fetched_at"] = times[sym]
            return df

        with mock.patch.object(data, "fetch_daily", fake), contextlib.redirect_stdout(io.StringIO()):
            panel = data.fetch_panel(["BTC-USD", "ETH-USD", "XRP-USD"], "max", 0.1)
            market = data.load_market({"universe": {"BTC-USD": "Crypto", "ETH-USD": "Crypto"}}, "max", 0.1)
        want = {"BTC-USD": times["BTC-USD"], "ETH-USD": times["ETH-USD"]}
        self.assertEqual(panel["_fetched_at"], want)
        self.assertEqual(market["_fetched_at"], want)
        self.assertEqual(list(panel["close"].columns), ["BTC-USD", "ETH-USD"])
        end = crypto_end(idx[-1])  # bar 2026-11-04 ends 2026-11-05 00:05 UTC
        self.assertEqual(data.stale_symbols(panel, idx[-1], end, ["BTC-USD", "ETH-USD", "XRP-USD"]),
                         {"ETH-USD", "XRP-USD"})  # ETH fetched before the bar ended; XRP absent


class StaleSymbolsAndBarEnd(unittest.TestCase):
    def test_absent_and_early_fetches_are_stale(self):
        idx = pd.date_range("2026-11-02", periods=3, freq="D")
        close = pd.DataFrame({"A": [1.0, 2.0, 3.0], "B": [1.0, 2.0, np.nan]}, index=idx)
        end = crypto_end(idx[-1])
        panel = {"close": close, "_fetched_at": {"A": end - timedelta(minutes=1), "B": end}}
        self.assertEqual(data.stale_symbols(panel, idx[-1], end), {"A", "B"})  # A fetched early, B has no bar
        self.assertEqual(data.stale_symbols(panel, idx[-1], end, ["A", "B", "C"]), {"A", "B", "C"})  # C absent
        self.assertEqual(data.stale_symbols(panel, idx[-2], crypto_end(idx[-2])), set())
        self.assertEqual(data.stale_symbols({"close": close}, idx[-1], end), {"B"})  # ruling R1: no times = fresh

    def test_bar_end_stock_1605_new_york_even_on_early_close_crypto_0005_utc(self):
        stock, coins = cfg_for(load_panel()), data.load_config("crypto")
        friday = pd.Timestamp("2026-11-27")  # the day after Thanksgiving closes at 13:00; bar_end stays 16:05
        self.assertEqual(cycle._bar_end_utc(friday, stock), datetime(2026, 11, 27, 21, 5, tzinfo=UTC))
        self.assertEqual(cycle._bar_end_utc(pd.Timestamp("2026-07-02"), stock), datetime(2026, 7, 2, 20, 5, tzinfo=UTC))
        self.assertEqual(cycle._bar_end_utc(friday, coins), datetime(2026, 11, 28, 0, 5, tzinfo=UTC))


class StockStaleData(unittest.TestCase):
    def setUp(self):
        self.full = load_panel()
        self.cfg = cfg_for(self.full)
        self.cfg["risk"]["min_score"] = -1.0
        self.dirs: list[Path] = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def tmp(self) -> Path:
        self.dirs.append(Path(tempfile.mkdtemp()))
        return self.dirs[-1]

    def panel(self, n: int, fetched: dict | None = None) -> dict:
        p = {k: v.iloc[:n] for k, v in self.full.items()}
        if fetched is not None:
            p["_fetched_at"] = fetched
        return p

    def run_in(self, state: Path, panel: dict, propose: bool = False, seed: dict | None = None) -> dict:
        with frozen_env(state, None):
            cycle.load_config = lambda: self.cfg
            cycle.load_market = lambda c, rng="10y", age=0.1: panel
            if seed is not None and not (state / "portfolio.json").exists():
                journal.save_json("portfolio.json", seed)
            return cycle.run_cycle(propose=propose)

    def test_stale_bench_makes_last_not_final_stocks(self):
        idx = self.full["close"].index
        last, prev = idx[FIRST_BAR - 1], idx[FIRST_BAR - 2]
        others = {s: stock_end(last) + timedelta(minutes=25) for s in self.full["close"].columns}
        for spy_at, want in ((stock_end(last) - timedelta(minutes=1), prev), (stock_end(last), last)):
            state = self.tmp()
            out = self.run_in(state, self.panel(FIRST_BAR, {**others, "SPY": spy_at}))
            self.assertTrue(out["decided_now"])
            pend = journal_json(state, "pending.json")
            self.assertEqual(pend["decision_date"], str(want.date()), spy_at)
            self.assertNotIn("frozen", pend)  # every symbol was fetched after prev ended: nothing frozen

    def test_stale_symbol_frozen_stocks(self):
        idx = self.full["close"].index
        last = idx[FIRST_BAR - 1]
        prop = self.run_in(self.tmp(), self.panel(FIRST_BAR), propose=True)
        x = next(s for s in prop["diag"]["bottom_scores"] if s != "SPY")  # the weakest name: never a pick
        self.assertNotIn(x, prop["targets"])
        px = float(self.full["close"].at[last, x])
        qty = int(5000 // px)
        seed = {"cash": 100000.0 - qty * px, "peak_equity": 100000.0, "blocked": {},
                "positions": {x: {"qty": qty, "avg_cost": px, "entry_date": "2021-01-04", "peak_close": px, "last_price": px}}}

        control = self.tmp()  # fresh data: a rebalance day exits the weak name
        self.run_in(control, self.panel(FIRST_BAR), seed=seed)
        sells = [f for f in journal_json(control, "pending.json")["preview_at_close"] if f["symbol"] == x]
        self.assertEqual([(f["side"], f["reason"]) for f in sells], [("SELL", "exit")])

        state = self.tmp()  # x's data was fetched before the bar ended: frozen, held at its weight, not sold
        fetched = {s: stock_end(last) + timedelta(minutes=25) for s in self.full["close"].columns}
        fetched[x] = stock_end(last) - timedelta(minutes=30)
        out = self.run_in(state, self.panel(FIRST_BAR, fetched), seed=seed)
        pend = journal_json(state, "pending.json")
        self.assertEqual(pend["decision_date"], str(last.date()))  # the benchmark is fresh: the newest bar is final
        self.assertTrue(pend["rebalance"])
        self.assertEqual(pend["frozen"], [x])
        self.assertEqual(read_jsonl(state, "decisions.jsonl")[-1]["diag"]["frozen"], [x])
        self.assertNotIn(x, [f["symbol"] for f in pend["preview_at_close"]])
        self.assertTrue(pend["preview_at_close"])  # the rest of the book still trades
        self.assertAlmostEqual(pend["targets"][x], qty * px / 100000.0, places=9)
        self.assertLessEqual(sum(pend["targets"].values()), self.cfg["risk"]["max_gross"] + 1e-9)
        self.assertTrue(out["decided_now"])

        out = self.run_in(state, self.panel(FIRST_BAR + 1))  # next open: the stale decision still never trades x
        self.assertTrue(out["executed"])
        self.assertNotIn(x, [f["symbol"] for f in out["executed"]])
        self.assertEqual(journal_json(state, "portfolio.json")["positions"][x]["qty"], qty)


    def test_held_symbol_frozen_on_two_decisions_alerts_urgent(self):
        """Final review item 4: a held symbol frozen (stale or absent) on frozen_alert_runs consecutive decisions sends
        an urgent alert (its stop is not checked). state/frozen_runs.json counts the runs; with nothing frozen it is
        never written (the stock golden stays byte-identical), and a fresh decision resets it."""
        self.assertEqual(self.cfg["market"]["frozen_alert_runs"], 2)
        idx, cols = self.full["close"].index, self.full["close"].columns
        prop = self.run_in(self.tmp(), self.panel(FIRST_BAR), propose=True)
        x = next(s for s in prop["diag"]["bottom_scores"] if s != "SPY")
        last = idx[FIRST_BAR - 1]
        px = float(self.full["close"].at[last, x])
        qty = int(5000 // px)
        seed = {"cash": 100000.0 - qty * px, "peak_equity": 100000.0, "blocked": {},
                "positions": {x: {"qty": qty, "avg_cost": px, "entry_date": "2021-01-04", "peak_close": px, "last_price": px}}}
        state, sent = self.tmp(), []

        def run(n: int, stale: bool) -> dict:  # rows 0..n-1; x fetched before its decision bar ended when stale
            fetched = {s: stock_end(idx[n - 1]) + timedelta(minutes=25) for s in cols}
            if stale:
                fetched[x] = stock_end(idx[n - 1]) - timedelta(minutes=30)
            with frozen_env(state, None):
                cycle.load_config = lambda: self.cfg
                cycle.load_market = lambda c, rng="10y", age=0.1: self.panel(n, fetched)
                cycle.notify.send = lambda title, body, cfg, prio="default", **k: sent.append((prio, body)) or []
                if not (state / "portfolio.json").exists():
                    journal.save_json("portfolio.json", seed)
                return cycle.run_cycle()

        def urgent() -> list:
            return [b for pr, b in sent if pr == "urgent"]

        self.assertTrue(run(FIRST_BAR, True)["decided_now"])
        self.assertEqual(journal_json(state, "frozen_runs.json")["runs"], {x: 1})
        self.assertEqual(urgent(), [])  # one run: the normal event only
        self.assertTrue(run(FIRST_BAR + 1, True)["decided_now"])
        self.assertEqual(journal_json(state, "frozen_runs.json")["runs"], {x: 2})
        self.assertEqual(len(urgent()), 1)
        self.assertIn(f"{x} no data for 2 runs - stop not checked", urgent()[0])
        self.assertTrue(run(FIRST_BAR + 2, False)["decided_now"])  # fresh again: the count resets, no alert
        self.assertEqual(journal_json(state, "frozen_runs.json")["runs"], {})
        self.assertEqual(len(urgent()), 1)
        before = (state / "frozen_runs.json").read_bytes()
        self.assertTrue(run(FIRST_BAR + 3, False)["decided_now"])
        self.assertEqual((state / "frozen_runs.json").read_bytes(), before)  # unchanged: not rewritten

        control = self.tmp()  # nothing ever frozen: no file at all
        self.run_in(control, self.panel(FIRST_BAR), seed=seed)
        self.assertFalse((control / "frozen_runs.json").exists())

    def test_frozen_held_names_beyond_max_positions_leave_no_slot(self):
        """Final review item 10: more frozen held names than max_positions leaves no slot for a pick (the slice
        n - frozen held is floored at 0; a negative slice used to pick all but the last candidate)."""
        p = load_panel()
        cfg = cfg_for(p)
        cfg["risk"].update({"max_positions": 1, "min_score": -1.0})
        d = p["close"].index[FIRST_BAR - 1]
        sig, aux = compute_all(p, cfg), precompute_aux(p, cfg)
        held = {s: {"peak_close": float(p["close"].at[d, s])} for s in ("S01", "S02")}
        targets, diag = build_targets(d, p, sig, cfg["prior_weights"], cfg, 1.0, held, set(), aux, frozen=set(held))
        self.assertEqual(targets, {})  # the caller holds the two frozen names at their weights; nothing new is picked
        self.assertEqual(diag["frozen"], ["S01", "S02"])

class CryptoRun(unittest.TestCase):
    """The crypto book on a 7-day synthetic panel, through run_cycle (frozen env, temp state, no network)."""

    I = 213  # a risk-on day with both coins picked (BTC ~0.46, ETH ~0.18)

    def setUp(self):
        self.p = crypto_panel()
        self.idx = self.p["close"].index
        self.cfg = data.load_config("crypto")
        self.dirs: list[Path] = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def tmp(self) -> Path:
        self.dirs.append(Path(tempfile.mkdtemp()))
        return self.dirs[-1]

    def panel(self, upto: int, fetched_at: datetime | None = None, drop: str | None = None) -> dict:
        """Rows 0..upto. fetched_at: every coin's fetch time; drop: a coin Yahoo did not return."""
        p = {k: v.iloc[:upto + 1] for k, v in self.p.items()}
        if drop:
            p = {k: v.drop(columns=[drop]) for k, v in p.items()}
        if fetched_at is not None:
            p["_fetched_at"] = {s: fetched_at for s in p["close"].columns}
        return p

    def run_in(self, state: Path, panel: dict, final_upto=None, cb=None, propose: bool = False, seed: dict | None = None):
        """final_upto: the newest bar the clock calls final (default: every bar). The crypto clock is journal.now_utc
        (Task 6, UtcDailyCalendar): 01:07 UTC the day after final_upto, else an hour after the newest bar ended.
        cb: the Coinbase stub."""
        newest = final_upto if final_upto is not None else panel["close"].index[-1]
        clock = (crypto_end(newest) + timedelta(hours=1, minutes=2 if final_upto is not None else 0)).isoformat()
        with frozen_env(state, None):
            journal.now_utc = lambda: clock
            cycle.load_config = lambda: self.cfg
            cycle.load_market = lambda c, rng="10y", age=0.1: panel
            if seed is not None and not (state / "portfolio.json").exists():
                journal.save_json("portfolio.json", seed)
            with mock.patch.object(cycle, "coinbase_close", cb or (lambda sym, day: None)):
                return cycle.run_cycle(propose=propose)

    def test_crypto_skips_when_any_coin_stale_or_absent(self):
        """Review Focus 2: at 00:12 UTC Yahoo gives a 429 (the cache's newest bar was written at 23:50, before
        bar_end), or leaves ETH out, or ETH's newest bar is empty. The run skips before any decision or fill; a
        later run with fresh data decides."""
        d = self.idx[self.I]
        at_0012, at_2350 = crypto_end(d) + timedelta(minutes=7), crypto_end(d) - timedelta(minutes=15)
        btc_cached = self.panel(self.I, at_0012)
        btc_cached["_fetched_at"]["BTC-USD"] = at_2350
        eth_empty = self.panel(self.I, at_0012)
        eth_empty["close"] = eth_empty["close"].copy()
        eth_empty["close"].iloc[-1, eth_empty["close"].columns.get_loc("ETH-USD")] = np.nan
        for name, panel in (("btc stale cache", btc_cached), ("eth absent", self.panel(self.I, at_0012, drop="ETH-USD")),
                            ("eth empty bar", eth_empty)):
            state = self.tmp()
            for propose in (True, False):
                out = self.run_in(state, panel, propose=propose)
                self.assertEqual(set(out), {"skipped", "executed", "decided_now", "events"}, name)
                self.assertEqual((out["executed"], out["decided_now"], out["events"]), ([], False, [out["skipped"]]), name)
                self.assertIn(str(d.date()), out["skipped"], name)
            self.assertEqual([f.name for f in state.iterdir()], ["skips.jsonl"], name)  # nothing decided or filled; the skip is logged once (R7)
            self.assertEqual(len((state / "skips.jsonl").read_text().splitlines()), 1, name)

        from aitrader.__main__ import main  # the CLI reports a skip instead of crashing on the missing diag
        with frozen_env(self.tmp(), None), contextlib.redirect_stdout(io.StringIO()) as buf:
            cycle.load_config = lambda: self.cfg
            cycle.load_market = lambda c, rng="10y", age=0.1: btc_cached
            self.assertEqual(main(["cycle", "--propose"]), 0)
        self.assertIn('"skipped"', buf.getvalue())

        state = self.tmp()  # the retry at 01:12 sees D+1's first bar: D is final and fresh
        out = self.run_in(state, self.panel(self.I + 1, at_0012 + timedelta(hours=1)), final_upto=d)
        self.assertTrue(out["decided_now"])
        self.assertEqual(journal_json(state, "pending.json")["decision_date"], str(d.date()))

    def test_next_open_close_source_and_missing_row(self):
        self.cfg["market"]["close_source"] = "next_open"  # this test is about the next_open rule; the book ships "yahoo" (Task 11)
        p, d = self.p, self.idx[self.I]
        nxt = self.idx[self.I + 1]
        panel = {k: v.iloc[:self.I + 2] for k, v in p.items()}
        out = data.apply_close_source(panel, "next_open", d)
        pd.testing.assert_series_equal(out["close"].loc[d], p["open"].loc[nxt], check_names=False)
        pd.testing.assert_frame_equal(out["close"].drop(index=d), panel["close"].drop(index=d))
        pd.testing.assert_frame_equal(panel["close"], p["close"].iloc[:self.I + 2])  # the input is not changed
        self.assertEqual(out["_close_source"], {"bar": str(d.date()),
                                                "yahoo_close": {s: float(p["close"].at[d, s]) for s in p["close"]},
                                                "next_open": {s: float(p["open"].at[nxt, s]) for s in p["open"]}})
        self.assertIs(data.apply_close_source(panel, "yahoo", d), panel)

        upto_d = {k: v.iloc[:self.I + 1] for k, v in p.items()}  # no D+1 row: bar D is dropped
        for dropped in (data.apply_close_source(upto_d, "next_open", d), data.apply_close_source(upto_d, "next_open")):
            for k in ("open", "high", "low", "close", "volume"):
                pd.testing.assert_frame_equal(dropped[k], p[k].iloc[:self.I])
        no_open = {**panel, "open": panel["open"].copy()}
        no_open["open"].loc[nxt, "ETH-USD"] = np.nan  # D+1 has no ETH open yet: D is dropped too
        self.assertNotIn(d, data.apply_close_source(no_open, "next_open", d)["close"].index)

        # Through run_cycle: decide D-1 on D's open; the 00:12 run without a D+1 row makes no decision on D; the
        # retry with the D+1 row decides D on D+1's open. The D+1 row is never visible to the decision otherwise.
        state, prev = self.tmp(), self.idx[self.I - 1]
        self.run_in(state, self.panel(self.I), final_upto=prev)
        self.assertEqual(journal_json(state, "pending.json")["decision_date"], str(prev.date()))
        out = self.run_in(state, self.panel(self.I))
        self.assertFalse(out["decided_now"])
        # decision records only: this synthetic panel's open[D+1] != close[D], so the R6 audit (Task 6) adds an event row
        self.assertEqual(len([r for r in read_jsonl(state, "decisions.jsonl") if "event" not in r]), 1)
        out = self.run_in(state, self.panel(self.I + 1), final_upto=d)
        self.assertTrue(out["decided_now"])
        dec = read_jsonl(state, "decisions.jsonl")[-1]
        self.assertEqual(dec["date"], str(d.date()))
        self.assertEqual(dec["diag"]["close_source"]["next_open"], {s: float(p["open"].at[nxt, s]) for s in p["open"]})
        self.assertEqual(dec["diag"]["regime_px"], round(float(p["open"].at[nxt, "BTC-USD"]), 4))

    def seed(self, weights: dict, day) -> dict:
        """A crypto book worth 100,000 holding `weights` at the decision close of `day` (the next row's open)."""
        px = {s: float(self.p["open"].iloc[self.idx.get_loc(day) + 1][s]) for s in weights}
        pos = {s: {"qty": round(w * 100000.0 / px[s], 6), "avg_cost": px[s], "entry_date": "2024-06-01",
                   "peak_close": px[s], "last_price": px[s]} for s, w in weights.items()}
        return {"cash": 100000.0 - sum(p["qty"] * px[s] for s, p in pos.items()), "peak_equity": 100000.0,
                "blocked": {}, "positions": pos}

    def decide(self, i: int, weights: dict, cb):
        """Seed a book, decide day i (the D+1 row is the first hourly bar of the next day); return the run summary,
        the pending decision and the decision record."""
        d, state = self.idx[i], self.tmp()
        out = self.run_in(state, self.panel(i + 1), final_upto=d, cb=cb, seed=self.seed(weights, d))
        return out, journal_json(state, "pending.json"), read_jsonl(state, "decisions.jsonl")[-1]

    def agree(self, sym, day):
        return float(self.p["open"].iloc[self.idx.get_loc(pd.Timestamp(day)) + 1][sym])

    def test_coinbase_breach_exits_only(self):
        self.cfg["market"]["close_source"] = "next_open"  # this test is about the next_open rule; the book ships "yahoo" (Task 11)
        held = {"BTC-USD": 0.10, "ETH-USD": 0.50}
        _, pend, dec = self.decide(self.I, held, self.agree)
        self.assertEqual(dec["diag"]["coinbase_guard"]["status"], "ok")
        sides = {(f["side"], f["symbol"]) for f in pend["preview_at_close"]}
        self.assertEqual(sides, {("BUY", "BTC-USD"), ("SELL", "ETH-USD")})  # without the guard: add BTC, trim ETH

        def gap(sym, day):  # Coinbase's close is 3% off Yahoo's for BTC
            return self.agree(sym, day) * (1.03 if sym == "BTC-USD" else 1.0)

        out, pend, dec = self.decide(self.I, held, gap)
        g = dec["diag"]["coinbase_guard"]
        self.assertEqual(g["status"], "breach")
        self.assertAlmostEqual(g["gaps"]["BTC-USD"], 1 / 1.03 - 1, places=9)
        self.assertEqual([(f["side"], f["symbol"]) for f in pend["preview_at_close"]], [("SELL", "ETH-USD")])
        self.assertAlmostEqual(pend["targets"]["BTC-USD"], 0.10, places=6)  # min(target, current weight)
        self.assertLess(pend["targets"]["ETH-USD"], 0.5)  # trims still happen
        self.assertTrue(any("Coinbase" in e for e in out["events"]))

        risk_off = 320  # regime off: the clamp keeps the exit
        _, pend, dec = self.decide(risk_off, {"BTC-USD": 0.5}, gap)
        self.assertEqual(dec["diag"]["regime"], "risk_off")
        self.assertEqual(dec["diag"]["coinbase_guard"]["status"], "breach")
        self.assertEqual([(f["side"], f["symbol"], f["reason"]) for f in pend["preview_at_close"]], [("SELL", "BTC-USD", "exit")])

    def test_coinbase_down_proceeds(self):
        held = {"BTC-USD": 0.10, "ETH-USD": 0.50}
        _, base, _ = self.decide(self.I, held, self.agree)
        out, pend, dec = self.decide(self.I, held, lambda sym, day: None)
        self.assertEqual(dec["diag"]["coinbase_guard"]["status"], "unreachable")
        self.assertEqual(pend["targets"], base["targets"])  # no clamp
        self.assertIn(("BUY", "BTC-USD"), {(f["side"], f["symbol"]) for f in pend["preview_at_close"]})
        self.assertTrue(any("Coinbase" in e for e in out["events"]))


class CoinbaseClose(unittest.TestCase):
    def test_parses_the_utc_daily_candle_and_returns_none_when_down(self):
        t0 = int(datetime(2026, 11, 8, tzinfo=UTC).timestamp())
        seen = []

        def ok(url, params=None, **k):
            seen.append((url, params))
            return [[t0 + 86400, 1.0, 2.0, 1.5, 1.7, 9.0], [t0, 74000.0, 76000.0, 75000.0, 74719.82, 123.0]]

        with mock.patch.object(data, "_get_json", ok):
            self.assertEqual(data.coinbase_close("BTC-USD", pd.Timestamp("2026-11-08")), 74719.82)
        url, params = seen[0]
        self.assertEqual(url, "https://api.exchange.coinbase.com/products/BTC-USD/candles")
        self.assertEqual(params["granularity"], 86400)
        self.assertEqual(params["start"], "2026-11-08T00:00:00Z")

        def down(url, params=None, **k):
            raise RuntimeError("GET failed")

        for stub in (down, lambda url, params=None, **k: [], lambda url, params=None, **k: {"message": "NotFound"}):
            with mock.patch.object(data, "_get_json", stub):
                self.assertIsNone(data.coinbase_close("ETH-USD", "2026-11-08"))


def journal_json(state: Path, name: str):
    return json.loads((state / name).read_text())


def read_jsonl(state: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in (state / name).read_text().splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
