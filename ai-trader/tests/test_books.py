"""Books: config profiles merged over the base config, the book switch (journal.use_book) and state isolation.

Crypto groundwork (plan 2026-11-09-crypto-book-v1, Task 1). No crypto trading logic is tested here: only that the
profiles load as specified and that a crypto run lives in its own state dir.
"""

import contextlib
import copy
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from aitrader import __main__ as cli
from aitrader import backtest, crypto_sweep, cycle, data, journal
from aitrader.signals import REGISTRY
from golden_util import FIRST_BAR, frozen_env, load_panel
from test_core import cfg_for

ROOT = Path(__file__).resolve().parent.parent

STOCK_MARKET = {  # plan, planning decision 6: the stock column = today's behaviour
    "calendar": "nyse", "periods_per_year": 252, "history": "10y", "vix": True, "earnings_blackout": True,
    "overlays": True, "corporate_actions": True, "news_engine": True, "fill_regime_on_no_picks": False,
    "equity_mark_per_bar": False, "delete_proposal_on_decision": False, "grading": "excess",
    "stale_skips_run": False, "close_source": "yahoo", "coinbase_guard_pct": 0, "report_dir": "reports",
    "intraday_alert_pct": 0.06, "latest_max_age_hours": 30, "state_subdir": "",
    "etf_groups": ["Index", "SectorETF", "Bonds", "Gold"], "quiet_hours": None,
    "frozen_alert_runs": 2,  # final review item 4: urgent alert on a held symbol frozen this many decisions in a row
}
CRYPTO_MARKET = {
    "calendar": "utc_daily", "periods_per_year": 365, "history": "max", "vix": False, "earnings_blackout": False,
    "overlays": False, "corporate_actions": False, "news_engine": False, "fill_regime_on_no_picks": True,
    "equity_mark_per_bar": True, "delete_proposal_on_decision": True, "grading": "absolute",
    "stale_skips_run": True, "close_source": "yahoo", "coinbase_guard_pct": 0.01, "report_dir": "reports/crypto",
    "intraday_alert_pct": 0.08, "latest_max_age_hours": 26, "state_subdir": "crypto", "etf_groups": [],
    "quiet_hours": {"tz": "Asia/Jerusalem", "from": "23:00", "to": "08:00"},
    "revised_close_alert_bps": 5,  # ruling R6 (Task 6): crypto only
    "frozen_alert_runs": 2,  # inherited from the stock block (crypto skips a stale run instead of freezing)
    "fill_max_wait_hours": 24, "fill_urgent_after_hours": 3,  # final review items 6 and 5: crypto only
}
SPEC_RISK_KEYS = {  # spec 3.3: the crypto risk block lists every key it uses (nothing inherited from stocks)
    "target_vol_annual", "max_gross", "max_position_pct", "max_position_pct_by_symbol", "max_sector_pct",
    "max_positions", "min_score", "exit_score", "keep_rank_mult", "regime_sma_days", "regime_band_pct",
    "regime_band_mode", "risk_off_gross_mult", "dd_halve", "dd_flat", "dd_reentry_days", "atr_days", "atr_stop_mult",
    "rebalance_band_pct", "min_trade_value", "vol_lookback_days", "rebalance_every_days", "stop_cooldown_days",
    "lowvol_exclude_top_pct",
}
STOCK_ONLY = ("desk", "brief", "news", "news-live", "news-score", "news-status")


def raw_config() -> dict:
    return json.loads((ROOT / "config.json").read_text())


def report_files(root: Path) -> dict:
    """The stock reports under a report root (reports/<date>.md), not the crypto ones in reports/crypto/."""
    return {p.name: p.read_bytes() for p in sorted((root / "reports").glob("*.md"))}


class TempState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._state, self._book, self._base = journal.STATE, journal.BOOK, journal._BASE
        journal.STATE = self.tmp

    def tearDown(self):
        journal.STATE, journal.BOOK, journal._BASE = self._state, self._book, self._base
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def files(self, exclude: str | None = None) -> dict:
        return {str(p.relative_to(self.tmp)): p.read_bytes() for p in sorted(self.tmp.rglob("*"))
                if p.is_file() and (exclude is None or p.relative_to(self.tmp).parts[0] != exclude)}


class Profiles(unittest.TestCase):
    def test_stock_config_unchanged(self):
        raw = raw_config()
        raw.pop("books")
        self.assertEqual(data.load_config(), raw)
        self.assertEqual(data.load_config("stocks"), raw)
        self.assertEqual(raw["market"], STOCK_MARKET)
        cfg = data.load_config()
        cfg["risk"]["max_gross"] = 99  # callers mutate the config they get; the next load must not see it
        self.assertEqual(data.load_config()["risk"], raw["risk"])

    def test_crypto_universe_and_priors(self):
        c = data.load_config("crypto", "crypto")
        self.assertEqual(set(c["universe"]), {"BTC-USD", "ETH-USD"})
        self.assertEqual(set(c["prior_weights"]), set(REGISTRY))
        self.assertAlmostEqual(sum(c["prior_weights"].values()), 1.0, delta=1e-3)
        self.assertEqual({k: v for k, v in c["prior_weights"].items() if v},
                         {"tsmom": 0.3846, "trend": 0.3077, "breakout": 0.3077})
        self.assertEqual(c["benchmark"], "BTC-USD")
        self.assertEqual(set(c["signals"]), set(REGISTRY))  # replaced whole, every registered signal explicit
        self.assertEqual((c["signals"]["tsmom"], c["signals"]["trend"], c["signals"]["breakout"]),
                         ({"lookback": 365, "skip": 30}, {"fast": 50, "slow": 200}, {"lookback": 80}))
        market = dict(c["market"])
        # Task 11 revised-close check (research/2026-11-11-crypto-revised-close.md): the open moved, so yahoo
        self.assertIn("the open moved", market.pop("close_source_note"))
        self.assertEqual(market, CRYPTO_MARKET)
        self.assertEqual(c["costs"], {"slippage_bps": 5, "commission_per_share": 0.0, "fee_bps": 50,
                                      "exec_delay_bps": 10, "qty_step": 1e-6})
        self.assertEqual({k: c["learning"][k] for k in ("enabled", "default_horizon", "horizons_days")},
                         {"enabled": False, "default_horizon": 30, "horizons_days": [7, 30, 90]})
        # XRP-USD: read only by the sweep's BTC+XRP hindsight control (ruling R13); XRP is in no profile's universe
        self.assertEqual(c["risk"]["max_position_pct_by_symbol"], {"BTC-USD": 1.0, "ETH-USD": 0.6, "XRP-USD": 0.6})
        self.assertNotIn("books", c)
        ship = raw_config()["books"]["crypto"]["ship_profile"]
        self.assertEqual(ship, "crypto_base")  # Task 11: the sweep of 2026-11-11 shipped crypto_base (state/crypto/dsr.json)
        self.assertEqual(data.load_config("crypto"), data.load_config("crypto", ship))  # the profile defaults to ship_profile

    def test_crypto_risk_lists_every_key(self):
        books = raw_config()["books"]
        self.assertEqual(SPEC_RISK_KEYS - set(books["crypto"]["risk"]), set())
        r = data.load_config("crypto", "crypto")["risk"]
        self.assertEqual((r["target_vol_annual"], r["dd_halve"], r["dd_flat"], r["atr_stop_mult"],
                          r["regime_band_mode"], r["risk_off_gross_mult"], r["min_trade_value"]),
                         (0.30, -0.25, -0.5, 3.0, "hysteresis", 0, 100))
        self.assertEqual(r["defensive_vix_pct"], 0)  # falsy: the VIX defensive block never runs for crypto
        self.assertEqual(data.load_config("crypto", "crypto_base")["risk"]["defensive_vix_pct"], 0)
        # the stock-only keys the crypto risk block still inherits (all unused by crypto); a new leak shows up here
        self.assertEqual(set(r) - SPEC_RISK_KEYS - {"defensive_vix_pct"},
                         {"defensive_gross_mult", "earnings_blackout_days", "earnings_max_position_pct",
                          "lowvol_exclude_lookback", "lowvol_exclude_min_names", "max_etf_position_pct"})
        self.assertNotIn("dd_reentry_ref", r)  # planning decision 1: the candidate inherits the default -0.375

    def test_crypto_base_universe(self):
        b = data.load_config("crypto", "crypto_base")
        self.assertEqual(set(b["universe"]), {"BTC-USD"})
        self.assertEqual({k: v for k, v in b["prior_weights"].items() if v}, {"trend": 1.0})
        self.assertEqual(set(b["prior_weights"]), set(REGISTRY))
        self.assertEqual({k: b["risk"][k] for k in ("min_score", "exit_score", "atr_stop_mult", "dd_halve", "dd_reentry_ref")},
                         {"min_score": -1, "exit_score": -1.01, "atr_stop_mult": 0, "dd_halve": -1.0, "dd_reentry_ref": -0.25})
        c = data.load_config("crypto", "crypto")
        for block in ("signals", "benchmark", "costs", "market", "account", "learning"):
            self.assertEqual(b[block], c[block], block)  # everything else is the candidate's
        self.assertEqual(b["risk"]["target_vol_annual"], 0.30)

    def test_account_merge(self):
        c = data.load_config("crypto", "crypto")
        self.assertEqual(c["account"]["cash_yield_annual"], 0)
        self.assertEqual(c["account"]["starting_cash"], 100000)
        self.assertIs(c["account"]["paper_only"], True)  # key by key: the rest of the stock block stays

    def test_profile_guards_reject_a_bad_config(self):
        bad = [("crypto_base", lambda c: c["books"]["crypto_base"]["universe"].update({"ETH-USD": "Crypto"})),
               ("crypto", lambda c: c["books"]["crypto"]["universe"].pop("ETH-USD")),
               ("crypto", lambda c: c["books"]["crypto"]["prior_weights"].pop("lowvol")),
               ("crypto", lambda c: c["books"]["crypto"]["prior_weights"].update({"tsmom": 0.5}))]
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for profile, breakit in bad:
            c = copy.deepcopy(raw_config())
            breakit(c)
            (tmp / "config.json").write_text(json.dumps(c))
            with mock.patch.object(data, "ROOT", tmp), self.assertRaises(ValueError):
                data.load_config("crypto", profile)
        with self.assertRaises(ValueError):
            data.load_config("crypto", "btc_xrp")  # in-sweep controls never go through load_config
        with self.assertRaises(ValueError):
            data.load_config("forex")


class UseBook(TempState):
    def test_use_book_restores_and_nests(self):
        base_before = journal._BASE
        with journal.use_book("stocks"):  # the active book: a no-op
            self.assertEqual(journal.STATE, self.tmp)
        with journal.use_book("crypto"):
            self.assertEqual((journal.STATE, journal.BOOK, journal._BASE), (self.tmp / "crypto", "crypto", self.tmp))
            self.assertEqual(data.load_config()["benchmark"], "BTC-USD")  # no argument: the active book
            with journal.use_book("crypto"):
                self.assertEqual(journal.STATE, self.tmp / "crypto")
            self.assertEqual(journal.STATE, self.tmp / "crypto")
            with journal.use_book("stocks"):
                self.assertEqual((journal.STATE, journal.BOOK), (self.tmp, "stocks"))
                self.assertEqual(data.load_config()["benchmark"], "SPY")
            self.assertEqual((journal.STATE, journal.BOOK), (self.tmp / "crypto", "crypto"))
        self.assertEqual((journal.STATE, journal.BOOK, journal._BASE), (self.tmp, "stocks", base_before))
        with self.assertRaises(RuntimeError), journal.use_book("crypto"):
            raise RuntimeError("a crash inside the book")
        self.assertEqual((journal.STATE, journal.BOOK, journal._BASE), (self.tmp, "stocks", base_before))
        with self.assertRaises(ValueError), journal.use_book("crypto_base"):
            pass

    def test_context_reads_lessons_from_base(self):
        (self.tmp / "lessons.md").write_text("2026-11-02 crypto: BTC-USD stop fired on a wick (trades.jsonl)\n"
                                             "2026-11-03 AAPL earnings gap ate the stop (trades.jsonl)\n")
        journal.append("predictions.jsonl", {"date": "2026-11-02", "symbol": "BTC-USD", "horizon": 20, "direction": "up"})
        with journal.use_book("crypto"):
            journal.append("predictions.jsonl", {"date": "2026-11-08", "symbol": "BTC-USD", "horizon": 30, "direction": "up"})
            ctx = journal.context("BTC-USD")
        self.assertEqual(ctx["lessons"], ["2026-11-02 crypto: BTC-USD stop fired on a wick (trades.jsonl)"])
        self.assertEqual(len(ctx["recent_lessons_any"]), 2)
        self.assertEqual([p["date"] for p in ctx["recent_predictions"]], ["2026-11-08"])  # calls: the crypto book's
        self.assertFalse((self.tmp / "crypto" / "lessons.md").exists())


class Cli(TempState):
    def test_cli_book_flag(self):
        journal.save_json("latest.json", {"date": "stock"})
        (self.tmp / "crypto").mkdir()
        (self.tmp / "crypto" / "latest.json").write_text(json.dumps({"date": "crypto"}))
        for argv in (["--book", "crypto", "status"], ["status", "--book", "crypto"]):
            code, out, _ = self.cli(*argv)
            self.assertEqual((code, json.loads(out)), (0, {"date": "crypto"}), argv)
        self.assertEqual((journal.STATE, journal.BOOK), (self.tmp, "stocks"))
        self.assertEqual(json.loads(self.cli("status")[1]), {"date": "stock"})

        def chains(out):
            return {ln.split(":")[0] for ln in out.splitlines() if ln.endswith(" records)")}
        code, out, _ = self.cli("--book", "crypto", "verify")
        self.assertEqual((code, chains(out)), (0, journal.MAIN_CHAINED))  # the news chains are stock-only
        self.assertEqual(chains(self.cli("verify")[1]), journal.CHAINED)

        before = self.files()
        desk = ["BTC-USD", "Buy", "--prob", "0.6", "--thesis", "t", "--invalidation", "i"]
        refused = [["desk", "--book", "crypto", *desk], ["--book", "crypto", "desk", *desk],
                   ["brief", "--book", "crypto", "BTC-USD"], ["news", "--book", "crypto", "BTC-USD"],
                   ["news-live", "--book", "crypto"], ["news-score", "--book", "crypto"], ["news-status", "--book", "crypto"]]
        self.assertEqual({r[0] if r[0] != "--book" else r[2] for r in refused}, set(STOCK_ONLY))
        for argv in refused:
            code, out, err = self.cli(*argv)
            self.assertNotEqual(code, 0, argv)
            self.assertIn("stock-only", err, argv)
            self.assertEqual(out, "", argv)
        self.assertEqual(self.files(), before)

    def test_crypto_entry_points_never_touch_stock_state(self):
        """Review Focus 1: every CLI entry point that takes --book crypto, driven against a stock book with history;
        the stock state files must come out byte-identical and the crypto writes must land in <state>/crypto."""
        full = load_panel()
        stock_cfg = cfg_for(full)
        stock_cfg["risk"]["min_score"] = -1.0
        coins = {k: v[["SPY", "S00"]].set_axis(["BTC-USD", "ETH-USD"], axis=1) for k, v in full.items()}
        coins3 = {k: v[["SPY", "S00", "S01"]].set_axis(list(crypto_sweep.SYMBOLS), axis=1) for k, v in full.items()}
        idx = full["close"].index
        start = str(idx[FIRST_BAR].date())
        real_sweep = crypto_sweep.run_sweep

        def short_sweep(panel, start, split, end=None, phases=7, **kw):  # the real sweep, 1 phase on 63 bars
            return real_sweep(panel, start, str(idx[FIRST_BAR + 31].date()), str(idx[FIRST_BAR + 62].date()), phases=1, **kw)

        def market(panel, n):
            cycle.load_market = lambda c, rng="10y", age=0.1: {k: v.iloc[:n] for k, v in panel.items()}

        with frozen_env(self.tmp, None):
            cycle.load_config = lambda: stock_cfg
            for i in range(2):  # a stock book with a decision and a fill
                market(full, FIRST_BAR + i)
                self.assertEqual(self.cli("cycle")[0], 0)
            self.assertEqual(self.cli("veto", "S01", "--reason", "stock veto")[0], 0)
            (self.tmp / "lessons.md").write_text("2026-11-02 S01 lesson (trades.jsonl)\n")
            before = self.files()
            self.assertIn("portfolio.json", before)
            import aitrader.report as rep  # frozen_env points the report root at its own temp dir

            reports = Path(rep.ROOT)
            stock_reports = report_files(reports)
            self.assertTrue(stock_reports)
            self.assertFalse((reports / "reports" / "crypto").exists())

            cycle.load_config = data.load_config  # the active book's real profile
            prices = mock.patch.object(data, "live_prices", lambda syms: {s: 100.0 for s in syms})
            status = mock.patch.object(data, "market_status", lambda sym="SPY": {"is_open": True})
            loader = mock.patch.object(data, "load_market", lambda cfg, rng="10y", age=6.0: coins)
            sweep = mock.patch.object(backtest, "sweep", lambda *a, **k: pd.DataFrame([{"variant": "stub", "sharpe_med": 0.1}]))
            fetch = mock.patch.object(data, "fetch_panel", lambda syms, rng="5y", age=6.0: {k: v[list(syms)] for k, v in coins3.items()})
            csweep = mock.patch.object(crypto_sweep, "run_sweep", short_sweep)  # backtest --book crypto routes here (Task 9)
            with prices, status, loader, sweep, fetch, csweep:
                self.assertEqual(crypto_sweep.seed_script().seed(), 145)  # the sweep refuses to run without it
                for i in range(2):
                    market(coins, FIRST_BAR + i)
                    self.assertEqual(self.cli("--book", "crypto", "cycle")[0], 0)
                market(coins, FIRST_BAR + 2)
                runs = [["cycle", "--propose"], ["cycle", "--dry-run"], ["status"], ["scorecard"], ["verify"],
                        ["context", "BTC-USD"], ["predict", "BTC-USD", "up", "--horizon", "30"],
                        ["veto", "ETH-USD", "--reason", "crypto veto"], ["shrink", "BTC-USD", "0.5", "--reason", "crypto shrink"],
                        ["backtest", "--start", start], ["backtest", "--start", start, "--sweep"]]
                for argv in runs:
                    code, out, err = self.cli(argv[0], "--book", "crypto", *argv[1:])
                    self.assertEqual(code, 0, (argv, err[-500:]))
            self.assertEqual(report_files(reports), stock_reports)  # a crypto run never writes reports/<date>.md
            self.assertTrue(list((reports / "reports" / "crypto").glob("*.md")))  # market.report_dir
            self.assertTrue(list((reports / "research").glob("*-crypto-sweep.md")))  # the sweep report: the report root
        self.assertEqual(self.files(exclude="crypto"), before)
        crypto = set(self.files()) - set(before)
        for name in ("portfolio.json", "decisions.jsonl", "predictions.jsonl", "overrides.json", "trials.jsonl", "dsr.json"):
            self.assertIn(f"crypto/{name}", crypto)
        self.assertEqual(json.loads((self.tmp / "crypto" / "overrides.json").read_text())["vetoes"].keys(), {"ETH-USD"})


if __name__ == "__main__":
    unittest.main()
