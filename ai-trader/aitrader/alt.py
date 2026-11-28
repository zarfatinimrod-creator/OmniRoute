"""Alternative data overlays: insider cluster buys (OpenInsider / SEC Form 4) and Quiver Quant
(congress, lobbying, gov contracts, insiders).

Policy: a new data source earns capital only after a forward track record. Until then each overlay
only LOGS predictions (source="insider_cluster", "congress_buy", ...) that the journal grades later,
and appears in the report for Claude's review. Promotion into the ensemble = a config change that
passes the time machine and the quant-critic.
"""

from __future__ import annotations

import html
import os
import re
from datetime import date, timedelta

import requests

from . import journal

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ai-trader/1.0"}
QUIVER = "https://api.quiverquant.com"


def _money(s: str) -> float:
    s = s.replace("$", "").replace(",", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def openinsider_cluster_buys(min_value: float = 100_000) -> list[dict]:
    """Latest cluster buys (2+ insiders buying). Mostly small caps; filter by value and later by liquidity."""
    r = requests.get("http://openinsider.com/latest-cluster-buys", headers=UA, timeout=20)
    r.raise_for_status()
    m = re.search(r'<table[^>]*class="tinytable"[^>]*>(.*?)</table>', r.text, re.S)
    if not m:
        return []
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S)[1:]:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 13:
            continue
        tick = re.search(r'href="/([A-Z.\-]{1,6})"', cells[3])
        text = [html.unescape(re.sub("<[^>]+>", "", c)).strip() for c in cells]
        if not tick or not text[7].startswith("P"):
            continue
        val = _money(text[12])
        if val < min_value:
            continue
        out.append({
            "filing_date": text[1][:10], "trade_date": text[2], "ticker": tick.group(1).replace(".", "-"),
            "company": text[4], "industry": text[5], "insiders": int(text[6] or 0), "price": _money(text[8]),
            "value": val, "delta_own": text[11],
        })
    return out


def quiver_get(path: str, params: dict | None = None):
    """GET a Quiver endpoint. The key comes from QUIVER_API_KEY or is injected by the environment proxy.

    Returns None when no valid key is configured (401/403) so callers can skip the overlay.
    """
    key = os.environ.get("QUIVER_API_KEY", "proxy-injected")  # dummy is replaced by the proxy secret
    r = requests.get(f"{QUIVER}{path}", params=params, timeout=30,
                     headers={**UA, "Authorization": f"Bearer {key}", "Accept": "application/json"})
    if r.status_code in (401, 403):
        return None
    r.raise_for_status()
    return r.json()


def quiver_congress_buys(days: int = 30) -> list[dict] | None:
    """Aggregate recent congressional purchases per ticker: distinct members buying minus selling."""
    rows = quiver_get("/beta/live/congresstrading")
    if rows is None:
        return None
    since = (date.today() - timedelta(days=days)).isoformat()
    agg: dict[str, dict] = {}
    for x in rows:
        t = (x.get("Ticker") or "").upper()
        # Point-in-time: the market learns of a trade at disclosure (ReportDate / upload), not TransactionDate.
        d = str(x.get("ReportDate") or x.get("Quiver_Upload_Time") or x.get("Filed") or "")[:10]
        if not t or d < since:
            continue
        kind = str(x.get("Transaction") or "").lower()
        who = x.get("Representative") or x.get("Name") or x.get("BioGuideID") or "?"
        a = agg.setdefault(t, {"ticker": t, "buyers": set(), "sellers": set(), "last": d})
        (a["buyers"] if "purchase" in kind or kind == "buy" else a["sellers"]).add(who)
        a["last"] = max(a["last"], d)
    out = [{"ticker": t, "buyers": len(a["buyers"]), "sellers": len(a["sellers"]),
            "net": len(a["buyers"]) - len(a["sellers"]), "last": a["last"]} for t, a in agg.items()]
    return sorted(out, key=lambda r: (-r["net"], -r["buyers"]))


def log_overlay_predictions(rows: list[dict], source: str, prices: dict, bench_px: float | None,
                            day: str, horizons=(20, 60)) -> int:
    """Record overlay calls (direction up) for forward grading. Dedupes on (date, symbol, horizon, source)."""
    existing = {(p["date"], p["symbol"], p["horizon"], p.get("source")) for p in journal.read("predictions.jsonl")}
    n = 0
    for r in rows:
        sym = r["ticker"]
        if sym not in prices or bench_px is None:
            continue
        for h in horizons:
            if (day, sym, h, source) in existing:
                continue
            journal.append("predictions.jsonl", {
                "date": day, "logged_at": journal.now_utc(), "symbol": sym, "horizon": h, "source": source,
                "score": 1.0, "direction": "up", "components": {}, "evidence": {k: v for k, v in r.items() if k != "ticker"},
                "price": prices[sym], "bench_price": bench_px, "status": "open"})
            n += 1
    return n
