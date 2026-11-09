"""Task 10: the dashboard snapshot carries both books (spec 8). The crypto rows come from <state>/crypto via
journal.use_book("crypto"); the stock rows stay as they were; building a snapshot writes nothing to either book.

The network never runs: dashboard._px is stubbed, and every state file lives in a temp dir.
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from aitrader import dashboard, journal

NOW = datetime(2026, 11, 13, 6, 30, tzinfo=timezone.utc)
PRICES = {"SPY": 510.0, "^VIX": 15.0, "AAPL": 170.0, "BTC-USD": 76000.0, "ETH-USD": 2600.0}
BTC_QTY = 0.133485  # fractional: the page's ',d' integer format would print 0 (Task 3 note)


class FixedNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz is None else NOW.astimezone(tz)


def stock_book(tmp: Path) -> None:
    pos = {"AAPL": {"qty": 10, "avg_cost": 150.0, "entry_date": "2026-11-02", "last_price": 160.0, "peak_close": 160.0}}
    journal.save_json("portfolio.json", {"cash": 98400.0, "positions": pos, "created": "2026-11-01",
                                         "start_prices": {"SPY": 500.0}, "peak_equity": 100100.0, "regime": "risk_off"})
    journal.save_json("shadow_portfolio.json", {"cash": 98400.0, "positions": pos})
    journal.save_json("pending.json", {"decision_date": "2026-11-12", "status": "pending", "overrides": [],
                                       "preview_at_close": [{"symbol": "AAPL", "side": "SELL", "qty": 10, "price": 170.0, "value": 1700.0}]})
    journal.save_json("latest.json", {"regime": "risk_off", "dd_state": "normal"})
    journal.append("equity.jsonl", {"date": "2026-11-12", "logged_at": "2026-11-12T21:22:00+00:00", "equity": 100100.0,
                                    "shadow_equity": 100050.0, "bench_price": 505.0})
    journal.append("trades.jsonl", {"date": "2026-11-03", "symbol": "AAPL", "side": "BUY", "qty": 10, "price": 150.0,
                                    "value": 1500.0, "realized_pnl": 0.0, "reason": "entry", "logged_at": "2026-11-03T14:52:00+00:00"})


def crypto_book(dsr=0.41) -> None:
    """Writes into journal.STATE: call inside journal.use_book("crypto")."""
    btc = {"qty": BTC_QTY, "avg_cost": 74950.0, "entry_date": "2026-11-12", "last_price": 75000.0, "peak_close": 75000.0}
    journal.save_json("portfolio.json", {"cash": 89900.0, "positions": {"BTC-USD": btc}, "created": "2026-11-12",
                                         "start_prices": {"BTC-USD": 75000.0, "ETH-USD": 2500.0}, "peak_equity": 100200.0,
                                         "fees_paid": 50.12, "regime": "risk_on", "dd_state": "normal"})
    journal.save_json("shadow_portfolio.json", {"cash": 84900.0, "positions": {"BTC-USD": {**btc, "qty": 0.2}},
                                                "fees_paid": 75.0})
    fill = {"date": "2026-11-13", "symbol": "BTC-USD", "side": "BUY", "qty": BTC_QTY, "price": 74950.0, "value": 10004.7,
            "realized_pnl": -50.02, "fee": 50.0235, "reason": "entry"}
    journal.save_json("pending.json", {"decision_date": "2026-11-12", "status": "executed", "overrides": [],
                                       "exec_ts": "2026-11-13T01:00:00+00:00", "fill_ts": "2026-11-13T01:00:00+00:00",
                                       "fill_source": "1h", "fills": [fill],
                                       "preview_at_close": [{**fill, "price": 75000.0, "value": 10011.38}]})
    journal.save_json("latest.json", {"as_of_utc": "2026-11-13T01:07:00+00:00", "regime": "risk_on",
                                      "baselines": {"bench_since_start": 0.0, "equal_weight_since_start": 0.0}})
    journal.append("equity.jsonl", {"date": "2026-11-12", "logged_at": "2026-11-13T00:12:00+00:00", "equity": 100000.0,
                                    "shadow_equity": 100000.0, "bench_price": 75000.0, "decided": True})
    journal.append("trades.jsonl", {**fill, "decision_date": "2026-11-12", "fill": "open", "fill_source": "1h",
                                    "fill_ts": "2026-11-13T01:00:00+00:00", "logged_at": "2026-11-13T01:07:00+00:00"})
    journal.append("decisions.jsonl", {"date": "2026-11-12", "logged_at": "2026-11-13T00:12:00+00:00",
                                       "diag": {"date": "2026-11-12", "regime": "risk_on", "regime_px": 75000.0,
                                                "regime_sma": 70000.0, "regime_state": "on", "dd_state": "normal"}})
    journal.append("decisions.jsonl", {"event": "revised_close", "date": "2026-11-12", "logged_at": "2026-11-13T01:07:00+00:00"})
    if dsr is not None:
        journal.save_json("dsr.json", {"profile": "crypto", "value": dsr, "n": 160})


class Snapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = journal.STATE, journal.BOOK, journal._BASE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE, journal.BOOK, journal._BASE = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tree(self) -> dict:
        return {str(p.relative_to(self.tmp)): (p.read_bytes() if p.is_file() else None) for p in sorted(self.tmp.rglob("*"))}

    def build(self) -> list[dict]:
        with mock.patch.object(dashboard, "_px", lambda s: (PRICES.get(s), None)), \
                mock.patch.object(dashboard, "datetime", FixedNow):
            rows = dashboard.build()
        self.assertEqual((journal.STATE, journal.BOOK, journal._BASE), (self.tmp, "stocks", self._saved[2]))
        return rows

    @staticmethod
    def of(rows, t) -> list[dict]:
        return [r for r in rows if r["t"] == t]

    def test_snapshot_has_both_books_and_no_stock_state_written(self):
        stock_book(self.tmp)
        stock_only = [r for r in self.build() if not r["t"].startswith("c")]
        with journal.use_book("crypto"):
            crypto_book()
        before = self.tree()
        rows = self.build()
        self.assertEqual(self.tree(), before)  # read-only: no file and no dir written in either book
        self.assertEqual([r for r in rows if not r["t"].startswith("c")], stock_only)  # the stock rows are unchanged
        self.assertEqual({"ckpi", "cpos", "corder", "ctrade", "ceq", "cregime"} - {r["t"] for r in rows}, set())

        k = self.of(rows, "ckpi")[0]
        eq = 89900.0 + BTC_QTY * PRICES["BTC-USD"]
        sh = 84900.0 + 0.2 * PRICES["BTC-USD"]
        self.assertEqual((k["live"], k["started"], k["equity"], k["ret"]), (True, "2026-11-12", round(eq), round(eq / 100000 - 1, 4)))
        self.assertEqual((k["shadow_ret"], k["claude_effect"]), (round(sh / 100000 - 1, 4), round((eq - sh) / 100000, 4)))
        self.assertEqual(k["bench_since_start"], round(76000 / 75000 - 1, 4))  # BTC buy-and-hold from the live price
        self.assertEqual(k["vs_bench"], round((eq / 100000 - 1) - (76000 / 75000 - 1), 4))
        self.assertEqual((k["fees_paid"], k["fee_pct"], k["n_positions"]), (50.12, 0.005, 1))
        self.assertEqual((k["decision_date"], k["pending_status"]), ("2026-11-12", "בוצע"))
        self.assertEqual(k["exec_il"], "13.11 03:00")  # 01:00 UTC = 03:00 Israel (winter)
        self.assertIn("מגמה חיובית", k["regime"])

        p = self.of(rows, "cpos")
        self.assertEqual([(r["symbol"], r["qty"]) for r in p], [("BTC-USD", BTC_QTY)])  # fractional units survive
        self.assertEqual(p[0]["value"], round(BTC_QTY * 76000))
        o = self.of(rows, "corder")[0]
        self.assertEqual((o["symbol"], o["qty"], o["price"], o["status"], o["when"]), ("BTC-USD", BTC_QTY, 74950.0, "בוצע", "13.11 03:00"))
        t = self.of(rows, "ctrade")[0]
        self.assertEqual((t["qty"], t["fee"], t["pnl"], t["source"], t["time"]), (BTC_QTY, 50.02, -50.0, "1h", "13.11 03:00"))

        e = self.of(rows, "ceq")
        self.assertEqual({r["book"] for r in e}, {"crypto", "shadow", "btc"})
        btc_now = [r for r in e if r["book"] == "btc"][-1]
        self.assertEqual((btc_now["ts"], btc_now["ret"]), (NOW.isoformat(timespec="seconds"), round(76000 / 75000 - 1, 4)))

        g = self.of(rows, "cregime")[0]  # the last decision row; the event row after it is skipped (Task 6 note)
        self.assertEqual((g["date"], g["px"], g["sma"], g["state"]), ("2026-11-12", 75000.0, 70000.0, "on"))
        self.assertEqual((g["cash_line"], g["back_line"], g["band"]), (68600.0, 71400.0, 0.02))
        self.assertEqual((g["dist_cash"], g["dist_back"]), (round(75000 / 68600 - 1, 4), round(75000 / 71400 - 1, 4)))

        # no crypto book yet: the section still has its summary row, and the dashboard does not create <state>/crypto
        shutil.rmtree(self.tmp / "crypto")
        before = self.tree()
        rows = self.build()
        self.assertEqual(self.tree(), before)
        self.assertFalse((self.tmp / "crypto").exists())
        k = self.of(rows, "ckpi")[0]
        self.assertEqual((k["live"], k["equity"], k["ret"], k["proven_edge"]), (False, 100000, 0.0, False))
        self.assertEqual([r for r in rows if r["t"] in ("cpos", "corder", "ctrade", "cregime", "clesson")], [])

    def test_no_proven_edge_until_dsr_095(self):
        stock_book(self.tmp)
        for dsr, proven in ((None, False), (0.41, False), (0.9499, False), (0.95, True), (0.97, True)):
            with journal.use_book("crypto"):
                crypto_book(dsr)
                if dsr is None:
                    (journal.STATE / "dsr.json").unlink(missing_ok=True)
            k = self.of(self.build(), "ckpi")[0]
            self.assertEqual((k["proven_edge"], k["dsr"], k["dsr_gate"]), (proven, dsr, 0.95), dsr)
        with journal.use_book("crypto"):
            journal.save_json("dsr.json", {"profile": "crypto", "value": None, "n": 160})  # a non-finite DSR is stored as null
        self.assertFalse(self.of(self.build(), "ckpi")[0]["proven_edge"])

    def test_lessons_tagged_crypto_shown_in_crypto_section(self):
        stock_book(self.tmp)
        (self.tmp / "lessons.md").write_text(
            "# Lessons\n\n"
            "- 2026-11-10 | AAPL earnings gap ate the stop | trades.jsonl | medium | a second gap\n"
            "- 2026-11-13 | crypto: BTC-USD fill slipped one hour on a missing bar | trades.jsonl | low | a second slip\n",
            encoding="utf-8")
        rows = self.build()
        self.assertEqual([(r["date"], r["text"], r["confidence"]) for r in self.of(rows, "lesson")],
                         [("2026-11-10", "AAPL earnings gap ate the stop", "medium")])
        self.assertEqual([(r["date"], r["text"], r["confidence"]) for r in self.of(rows, "clesson")],
                         [("2026-11-13", "BTC-USD fill slipped one hour on a missing bar", "low")])
        with journal.use_book("crypto"):  # the dashboard reads the one shared file even when built inside the crypto book
            rows = self.build_in_book()
        self.assertEqual(len(self.of(rows, "clesson")), 1)
        self.assertFalse((self.tmp / "crypto" / "lessons.md").exists())

    def build_in_book(self) -> list[dict]:
        with mock.patch.object(dashboard, "_px", lambda s: (PRICES.get(s), None)), \
                mock.patch.object(dashboard, "datetime", FixedNow):
            return dashboard.build()

    def test_regime_labels_are_book_aware(self):
        self.assertIn("חצי חשיפה", dashboard._regime_he("risk_off"))
        self.assertIn("מזומן", dashboard._regime_he("risk_off", "crypto"))
        self.assertNotIn("חצי", dashboard._regime_he("risk_off", "crypto"))
        for book in ("stocks", "crypto"):
            self.assertNotIn("no-data", dashboard._regime_he("risk_off(no-data)", book))
        self.assertEqual(dashboard._regime_he("risk_on+defensive"), "מגמה חיובית + VIX גבוה (75%)")  # stock labels unchanged


    def test_crypto_night_runs_in_the_schedule(self):
        """Final review item 12: the schedule table lists the crypto night runs in Israel time, and says which clock
        is fixed (the UTC decide/fill; the summary on Israel time)."""
        stock_book(self.tmp)
        slots = {r["name"]: r for r in self.of(self.build(), "slot")}
        crypto = {n: r for n, r in slots.items() if "קריפטו" in n}
        self.assertEqual(sorted(r["time_il"] for r in crypto.values()), ["02:12", "03:07", "08:03"])
        what = " ".join(r["what"] for r in crypto.values())
        for fixed in ("UTC 00:12", "UTC 01:07"):
            self.assertIn(fixed, what)
        self.assertIn("שעון קיץ", what)
        self.assertEqual(len(slots), len(self.of(self.build(), "slot")))  # unique names (data-row-key="name")


class Page(unittest.TestCase):
    def test_claude_tile_carries_the_no_proven_edge_mark(self):
        """Final review item 11: #ck-claude's .sub shows the no-proven-edge mark like #ck-bench (same one-writer
        pick: a static span shown by the proven_edge pick)."""
        html = (Path(dashboard.__file__).resolve().parent.parent / "dashboard" / "index.html").read_text(encoding="utf-8")

        def sub(tile: str) -> str:
            block = html.split(f'id="{tile}"', 1)[1].split('<div class="card', 1)[0]
            return block.split('<div class="sub">', 1)[1].split("</div>", 1)[0]

        mark = ('<span class="pick"><span class="noedge" data-when="false"> · אין יתרון מוכח</span><span data-draw="pick" '
                'data-source="ckpi" data-field="proven_edge" data-row="0"></span></span>')
        self.assertIn(mark, sub("ck-bench"))
        self.assertIn(mark, sub("ck-claude"))

if __name__ == "__main__":
    unittest.main()
