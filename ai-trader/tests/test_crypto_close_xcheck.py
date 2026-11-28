"""Backlog 72: the decision close against Coinbase's daily candle at a tight line (market.close_xcheck_bp), LOG MODE.

* diag.close_xcheck = {mode, bp, symbols: {sym: {close, coinbase, gap_bp}}, would_decline, unreachable, close_missing,
  coinbase_missing}; unreachable is the sorted union of the two missing lists (step 2).
* A gap exactly on the line is not declined (strictly above only).
* Log mode without the Coinbase guard (coinbase_guard_pct 0) is refused: no field, no fetch, one printed line.
* Log mode changes nothing else: the decision, targets, pending order, events, alerts and every state file are the
  same as with the check off (the key property; an enforce mode is a separate rule-4 change).
* The value is the one the Coinbase guard already fetched: one coinbase_close call per symbol, for the decision
  date only (no look-ahead).
* Off (mode off, bp 0, keys missing, the stock book): no field, no call.
Network stubbed everywhere (test_crypto_cycle.CryptoBook).
"""

import contextlib
import copy
import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import test_crypto_cycle as tcc  # the module, not the classes: its tests must not be collected twice
from aitrader import cycle, data, journal
from golden_util import FIRST_BAR, frozen_env, load_panel
from test_core import cfg_for

I = tcc.I
HELD = {"BTC-USD": 0.10, "ETH-USD": 0.50}
CHAIN = ("hash", "prev_hash")


def strip(x):
    """x without diag.close_xcheck and without the chain hashes (they cover the diagnostics)."""
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k != "close_xcheck" and k not in CHAIN}
    return [strip(v) for v in x] if isinstance(x, list) else x


def finite(x) -> bool:
    if isinstance(x, dict):
        return all(finite(v) for v in x.values())
    if isinstance(x, list):
        return all(finite(v) for v in x)
    return not isinstance(x, float) or math.isfinite(x)


class Xcheck(tcc.CryptoBook):
    def run_mode(self, mode, cb, bp=5, guard=None) -> dict:
        """One decision of bar I in a fresh state dir. mode None: both keys missing from the market block.
        guard: market.coinbase_guard_pct (None: as shipped)."""
        self.setUp()
        self.cfg = copy.deepcopy(self.cfg)
        m = self.cfg["market"]
        if guard is not None:
            m["coinbase_guard_pct"] = guard
        m.pop("close_xcheck_mode", None), m.pop("close_xcheck_bp", None)
        if mode is not None:
            m.update(close_xcheck_mode=mode, close_xcheck_bp=bp)
        self.calls = []

        def counted(sym, day):
            self.calls.append((sym, str(day)[:10]))
            return cb(sym, day)

        self.cb = counted
        out = self.decide(seed=self.seed(HELD, I))
        self.assertTrue(out["decided_now"])
        files = {}
        for f in sorted(self.state.iterdir()):
            if f.is_file():
                text = f.read_text()
                files[f.name] = [json.loads(x) for x in text.splitlines() if x.strip()] if f.suffix == ".jsonl" else json.loads(text)
        return {"out": out, "files": files, "sent": list(self.sent), "prios": list(self.prios), "calls": list(self.calls)}

    def gap(self, bp_by_sym: dict):
        """Coinbase such that the decision close sits bp above it (the 1% guard stays quiet)."""
        return lambda sym, day: self.agree(sym, day) / (1 + bp_by_sym.get(sym, 0.0) / 1e4)

    def xc(self, run: dict) -> dict:
        return self.row(run)["diag"]["close_xcheck"]

    def row(self, run: dict) -> dict:
        """The decision row of bar I in decisions.jsonl (pending.json carries no diagnostics)."""
        rows = [r for r in run["files"]["decisions.jsonl"] if r.get("date") == self.day(I) and "diag" in r]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def same_but_for_the_field(self, log: dict, off: dict):
        self.assertEqual(strip(log["files"]), strip(off["files"]))
        self.assertEqual(sorted(log["files"]), sorted(off["files"]))
        self.assertEqual(strip(json.loads(json.dumps(log["out"], default=str))), strip(json.loads(json.dumps(off["out"], default=str))))
        self.assertEqual((log["sent"], log["prios"]), (off["sent"], off["prios"]))
        self.assertEqual(log["calls"], off["calls"])  # no extra network call in log mode
        self.assertNotIn("close_xcheck", json.dumps(off["files"]))
        self.assertNotIn("close_xcheck", json.dumps(off["out"], default=str))
        self.assertNotIn("close_xcheck", json.dumps(log["files"]["pending.json"]))  # the order file is untouched

    def test_gap_above_the_line_is_logged_and_changes_nothing(self):
        cb = self.gap({"BTC-USD": 8.0, "ETH-USD": -2.0})
        log, off = self.run_mode("log", cb), self.run_mode("off", cb)
        x = self.xc(log)
        self.assertEqual((x["mode"], x["bp"]), ("log", 5))
        self.assertEqual(x["would_decline"], ["BTC-USD"])
        self.assertEqual(x["unreachable"], [])
        self.assertAlmostEqual(x["symbols"]["BTC-USD"]["gap_bp"], 8.0, places=1)
        self.assertAlmostEqual(x["symbols"]["ETH-USD"]["gap_bp"], -2.0, places=1)
        btc = x["symbols"]["BTC-USD"]
        self.assertAlmostEqual(btc["close"], self.dclose(I, "BTC-USD"), places=6)
        self.assertAlmostEqual((btc["close"] / btc["coinbase"] - 1) * 1e4, 8.0, places=1)
        self.assertTrue(log["files"]["pending.json"]["targets"])  # a real order, not an empty decision
        self.assertEqual(self.row(log)["diag"]["coinbase_guard"]["status"], "ok")
        self.same_but_for_the_field(log, off)

    def test_negative_gap_counts_by_size(self):
        self.assertEqual(self.xc(self.run_mode("log", self.gap({"ETH-USD": -9.0})))["would_decline"], ["ETH-USD"])

    def test_gap_below_the_line(self):
        cb = self.gap({"BTC-USD": 3.0, "ETH-USD": -4.0})
        log = self.run_mode("log", cb)
        self.assertEqual(self.xc(log)["would_decline"], [])
        self.assertEqual(sorted(self.xc(log)["symbols"]), self.coins)
        self.same_but_for_the_field(log, self.run_mode("off", cb))

    def test_coinbase_none_is_unreachable(self):
        cb = lambda sym, day: None if sym == "BTC-USD" else self.agree(sym, day)  # noqa: E731
        log = self.run_mode("log", cb)
        x = self.xc(log)
        self.assertEqual(x["unreachable"], ["BTC-USD"])
        self.assertEqual((x["coinbase_missing"], x["close_missing"]), (["BTC-USD"], []))
        self.assertEqual(sorted(x["symbols"]), ["ETH-USD"])
        self.assertEqual(x["would_decline"], [])
        self.same_but_for_the_field(log, self.run_mode("off", cb))

    def test_http_layer_down_or_garbage_never_breaks_the_decision(self):
        """The real data.coinbase_close over a failing / odd HTTP layer: unreachable, JSON-safe, same decision."""
        def down(url, params=None, **k):
            raise RuntimeError("GET failed")

        for stub in (down, lambda url, params=None, **k: [[0, 1, 1, 1, float("nan"), 1]], lambda url, params=None, **k: {"message": "x"}):
            with mock.patch.object(data, "_get_json", stub):
                log, off = self.run_mode("log", data.coinbase_close), self.run_mode("off", data.coinbase_close)
            self.assertEqual(self.xc(log)["unreachable"], self.coins)
            self.assertEqual(self.xc(log)["symbols"], {})
            self.assertTrue(finite(log["files"]))
            self.same_but_for_the_field(log, off)

    def test_non_finite_coinbase_value_is_never_written(self):
        log = self.run_mode("log", lambda sym, day: float("inf") if sym == "BTC-USD" else float("nan"))
        self.assertEqual(self.xc(log)["unreachable"], self.coins)
        self.assertTrue(finite(self.xc(log)))
        json.dumps(self.xc(log), allow_nan=False)

    def test_off_means_no_field_and_no_extra_call(self):
        cb = self.gap({"BTC-USD": 8.0})
        runs = [self.run_mode("off", cb), self.run_mode("log", cb, bp=0), self.run_mode(None, cb)]
        for r in runs:
            self.assertNotIn("close_xcheck", json.dumps(r["files"]))
            self.assertEqual(sorted(r["calls"]), [(s, self.day(I)) for s in self.coins])  # the guard's own, once each
        self.assertEqual(runs[0]["files"], runs[1]["files"])
        self.assertEqual(runs[0]["files"], runs[2]["files"])

    def test_one_call_per_symbol_for_the_decision_date_only(self):
        log = self.run_mode("log", self.gap({}))
        self.assertEqual(sorted(log["calls"]), [(s, self.day(I)) for s in self.coins])  # no look-ahead, no second call

    def test_unknown_mode_is_off(self):
        r = self.run_mode("enforce", self.gap({"BTC-USD": 8.0}))  # not built: must not act, must not log as if it did
        self.assertNotIn("close_xcheck", json.dumps(r["files"]))

    def direct(self, closes: dict, seen: dict, bp=5.0, guard=0.01):
        """cycle._close_xcheck alone, on one decision row."""
        d = pd.Timestamp("2026-11-20")
        cfg = {"universe": {"BTC-USD": "c", "ETH-USD": "c"},
               "market": {"close_xcheck_mode": "log", "close_xcheck_bp": bp, "coinbase_guard_pct": guard}}
        return cycle._close_xcheck(pd.DataFrame(closes, index=[d]), d, cfg, seen)

    def test_a_gap_exactly_on_the_line_is_not_declined(self):
        """Gate note 1: strictly above the line only (a ">=" check would decline the first case)."""
        closes, seen = {"BTC-USD": 100.05, "ETH-USD": 99.95}, {"BTC-USD": 100.0, "ETH-USD": 100.0}
        up, down = (100.05 / 100.0 - 1) * 1e4, (99.95 / 100.0 - 1) * 1e4
        self.assertTrue(up > 0 > down)
        self.assertEqual(self.direct(closes, seen, bp=max(up, -down))["would_decline"], [])
        self.assertEqual(self.direct(closes, seen, bp=up)["would_decline"], ["ETH-USD"] if -down > up else [])
        self.assertEqual(self.direct(closes, seen, bp=math.nextafter(up, 0))["would_decline"][0], "BTC-USD")
        self.assertIn("ETH-USD", self.direct(closes, seen, bp=math.nextafter(-down, 0))["would_decline"])

    def test_which_side_is_missing(self):
        """Gate note 2: close_missing and coinbase_missing say which side had no value; unreachable is their union."""
        nan = float("nan")
        x = self.direct({"BTC-USD": nan, "ETH-USD": 100.0}, {"BTC-USD": 100.0, "ETH-USD": 100.0})
        self.assertEqual((x["close_missing"], x["coinbase_missing"], x["unreachable"]), (["BTC-USD"], [], ["BTC-USD"]))
        x = self.direct({"BTC-USD": nan, "ETH-USD": 100.0}, {"BTC-USD": None, "ETH-USD": float("inf")})
        self.assertEqual((x["close_missing"], x["coinbase_missing"]), (["BTC-USD"], ["BTC-USD", "ETH-USD"]))  # BTC in both
        self.assertEqual((x["unreachable"], x["symbols"], x["would_decline"]), (["BTC-USD", "ETH-USD"], {}, []))
        x = self.direct({"ETH-USD": 100.0}, {"ETH-USD": 100.0})  # no column, and the guard never asked
        self.assertEqual((x["close_missing"], x["coinbase_missing"], x["unreachable"]), (["BTC-USD"], ["BTC-USD"], ["BTC-USD"]))
        json.dumps(x, allow_nan=False)

    def test_log_mode_without_the_coinbase_guard_is_refused(self):
        """Gate note 4: with coinbase_guard_pct 0 nothing fetched Coinbase; the check must not fetch it itself (it would
        run in _decide outside any try) and must not raise: no field, one printed line, the same decision."""
        def boom(sym, day):
            raise RuntimeError("Coinbase must not be asked")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            log = self.run_mode("log", boom, guard=0)
        self.assertEqual(buf.getvalue().count("coinbase_guard_pct is 0"), 1)
        off = self.run_mode("off", boom, guard=0)
        self.assertEqual((log["calls"], off["calls"]), ([], []))
        self.assertNotIn("close_xcheck", json.dumps(log["files"]))
        self.assertEqual(log["files"], off["files"])
        self.assertTrue(log["files"]["pending.json"]["targets"])
        with mock.patch.object(cycle, "coinbase_close", boom), contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(self.direct({"BTC-USD": 1.0, "ETH-USD": 1.0}, {}, guard=0))
            self.assertIsNone(self.direct({"BTC-USD": 1.0, "ETH-USD": 1.0}, {}, guard=None))

    def test_shipped_config_is_log_mode_at_5bp(self):
        for profile in ("crypto", data.load_config("crypto")["profile"]):
            m = data.load_config("crypto", profile)["market"]
            self.assertEqual((m["close_xcheck_mode"], m["close_xcheck_bp"]), ("log", 5))
        stock = data.load_config("stocks")["market"]
        self.assertNotIn("close_xcheck_mode", stock)
        self.assertNotIn("close_xcheck_bp", stock)


class StockBook(unittest.TestCase):
    def test_stock_cycle_never_asks_coinbase_and_has_no_field(self):
        full = load_panel()
        cfg = cfg_for(full)
        cfg["risk"]["min_score"] = -1.0
        calls = []
        p = {k: v.iloc[:FIRST_BAR] for k, v in full.items()}
        with tempfile.TemporaryDirectory() as tmp, frozen_env(tmp, None):
            cycle.load_config = lambda: cfg
            cycle.load_market = lambda c, rng="10y", age=0.1: p
            cycle.coinbase_close = lambda sym, day: calls.append(sym)
            cycle.run_cycle()
            pend = journal.load_json("pending.json")
            self.assertTrue(pend and pend["status"] == "pending")
            self.assertNotIn("close_xcheck", json.dumps(pend))
            self.assertNotIn("close_xcheck", (Path(tmp) / "decisions.jsonl").read_text())
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
