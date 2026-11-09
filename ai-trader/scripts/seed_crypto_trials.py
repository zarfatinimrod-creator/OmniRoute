"""Seed state/crypto/trials.jsonl with the 145 looks taken before the crypto sweep, so the sweep's Deflated Sharpe
counts them (research/2026-11-09-crypto-dsr-seed.md; plan 2026-11-09-crypto-book-v1, planning decision 14).

  risk lens a4_regime: 8 variants x 3 coins x 4 windows = 96. a4_regime.txt reports 80 of them (BTC 4 windows,
    ETH and SOL 3 each) with an annualised Sharpe ("sharpe0"); the 16 it does not report count toward N only;
  spec review 1, power.py: base and candidate x 7 phases = 14 (no Sharpe in the files: N only);
  spec review 2, ablate.py + ablate2.py: 5 variants x 7 phases = 35 (N only).

Sharpes are stored annualised ("sharpe") and per period ("sharpe_pp" = sharpe / sqrt(365)). buy&hold rows are
benchmarks: they count toward N and stay out of the Sharpe spread. Idempotent: a second run finds the seed record
and writes nothing. Run from ai-trader/:  python3 scripts/seed_crypto_trials.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aitrader import journal  # noqa: E402

SEED_ID = "2026-11-09-crypto-dsr-seed"
REPLAYS = ROOT / "research" / "2026-11-09-crypto-replays"
PERIODS_PER_YEAR = 365  # the Sharpes in a4_regime.txt are annualised over 365 daily bars
A4_VARIANTS, A4_COINS, A4_WINDOWS = 8, 3, 4
REVIEWS = [("power.py", ["base", "candidate"]),
           ("ablate.py", ["base", "candidate", "candidate without breaker", "candidate without stop"]),
           ("ablate2.py", ["base + breaker -25/-50"])]
PHASES = 7


def _row(source: str, sharpe: float | None, benchmark: bool = False, **what) -> dict:
    pp = None if sharpe is None else round(sharpe / PERIODS_PER_YEAR ** 0.5, 8)
    return {"source": source, **what, "sharpe": sharpe, "sharpe_pp": pp, "benchmark": benchmark}


def a4_rows() -> list[dict]:
    """The risk-lens grid. Table columns are fixed width (coin 0-8, period 8-25, then the variant and 7 numbers)."""
    lines = (REPLAYS / "a4_regime.txt").read_text().splitlines()
    rows, coin, period, variants = [], None, None, []
    for ln in lines[2:]:
        if not ln.strip():
            break  # the crash-window section follows the table
        coin = ln[:8].strip() or coin
        period = ln[8:25].strip() or period
        parts = ln[25:].split()
        variant, sharpe = " ".join(parts[:-7]), float(parts[-7:][2])  # CAGR vol sharpe0 maxDD worst30d in_mkt switch/yr
        variants += [variant] if variant not in variants else []
        rows.append(_row("a4_regime.txt", sharpe, variant == "buy&hold", coin=coin, window=period, variant=variant))
    assert len(variants) == A4_VARIANTS, variants
    for c in sorted({r["coin"] for r in rows}):
        missing = A4_WINDOWS - len({r["window"] for r in rows if r["coin"] == c})
        rows += [_row("a4_regime.txt", None, v == "buy&hold", coin=c, window=f"unreported window {k + 1}", variant=v)
                 for k in range(missing) for v in variants]
    assert len({r["coin"] for r in rows}) == A4_COINS and len(rows) == A4_VARIANTS * A4_COINS * A4_WINDOWS, len(rows)
    return rows


def review_rows() -> list[dict]:
    return [_row(src, None, variant=v, phase=k, window="2018-01-01+") for src, vs in REVIEWS for v in vs for k in range(PHASES)]


def seed_rows() -> list[dict]:
    rows = a4_rows() + review_rows()
    assert len(rows) == 145, len(rows)
    return rows


def seed() -> int:
    """Append the seed record to the crypto book's trials.jsonl unless it is there already. Returns rows written."""
    with journal.use_book("crypto"):
        if any(t.get("seed") == SEED_ID for t in journal.read("trials.jsonl")):
            return 0
        rows = seed_rows()
        journal.append("trials.jsonl", {"logged_at": journal.now_utc(), "seed": SEED_ID,
                                        "source": "research/2026-11-09-crypto-dsr-seed.md", "rows": rows})
        return len(rows)


if __name__ == "__main__":
    n = seed()
    print(f"seeded {n} looks into state/crypto/trials.jsonl" if n else "already seeded: nothing written")
