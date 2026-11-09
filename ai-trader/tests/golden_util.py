"""Frozen environment for the golden stock tests: deterministic clock, no network, no phone alerts."""

import contextlib
import pickle
import tempfile
from pathlib import Path

from aitrader import cycle, journal
from test_core import cfg_for

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIRST_BAR = 400  # bars of history visible on the first scripted day


def load_panel() -> dict:
    return pickle.loads((FIXTURES / "stock_panel.pkl").read_bytes())


@contextlib.contextmanager
def frozen_env(tmp_state: Path, panel_upto):
    """Patch journal/cycle for a reproducible run. panel_upto(n) -> panel sliced to the first n bars."""
    import aitrader.report as rep

    names = ["load_config", "load_market", "market_status", "earnings_on", "_overlays_once_per_day",
             "_market_opened", "_bar_is_final", "official_opens", "corporate_actions", "coinbase_close"]
    saved = {k: getattr(cycle, k) for k in names}
    saved_send, saved_now = cycle.notify.send, journal.now_utc
    saved_state, saved_rep = journal.STATE, rep.ROOT
    tick = iter(range(10**9))
    try:
        journal.STATE = Path(tmp_state)
        rep.ROOT = Path(tempfile.mkdtemp())
        journal.now_utc = lambda: f"2026-01-01T{(n := next(tick)) // 3600:02d}:{n // 60 % 60:02d}:{n % 60:02d}+00:00"
        cycle.notify.send = lambda *a, **k: []
        cycle.corporate_actions = lambda sym: []
        cycle.official_opens = lambda syms, day: {}
        cycle.coinbase_close = lambda sym, day: None  # the crypto price guard's source: unreachable, never the network
        cycle.market_status = lambda sym="SPY": {"is_open": False}
        cycle.earnings_on = lambda day: {}
        cycle._overlays_once_per_day = lambda cfg, ds, bench: {}
        cycle._market_opened = lambda d: True
        cycle._bar_is_final = lambda d: True
        yield
    finally:
        for k, v in saved.items():
            setattr(cycle, k, v)
        cycle.notify.send, journal.now_utc = saved_send, saved_now
        journal.STATE, rep.ROOT = saved_state, saved_rep


def run_scripted_cycle(days: int) -> dict:
    """Run `days` consecutive cycles (decide, fill, decide, ...) and return {file name: bytes} of the state dir."""
    full = load_panel()
    cfg = cfg_for(full)
    cfg["risk"]["min_score"] = -1.0  # make sure something trades on synthetic data
    tmp = Path(tempfile.mkdtemp())

    def upto(n):
        p = {k: v.iloc[:n] for k, v in full.items()}
        cycle.load_market = lambda c, rng="10y", age=0.1: p

    with frozen_env(tmp, upto):
        cycle.load_config = lambda: cfg
        for i in range(days):
            upto(FIRST_BAR + i)
            cycle.run_cycle()
    return {f.name: f.read_bytes() for f in sorted(tmp.iterdir()) if f.is_file()}
