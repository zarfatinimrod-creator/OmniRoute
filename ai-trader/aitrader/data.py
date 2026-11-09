"""Market data: Yahoo Finance chart API (no key), news RSS, SEC EDGAR.

Only stdlib + requests + pandas. Daily bars are split/dividend adjusted
(open/high/low scaled by adjclose/close) so returns are total returns.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

try:  # untrusted XML from RSS/SEC: block entity expansion attacks
    import defusedxml.ElementTree as ET
    from defusedxml import DefusedXmlException as _XmlSecurityError
except ImportError:  # pragma: no cover - expat>=2.4 already blocks XXE/billion-laughs
    import xml.etree.ElementTree as ET  # noqa: N817

    class _XmlSecurityError(Exception):
        pass

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
COINBASE_CANDLES = "https://api.exchange.coinbase.com/products/{sym}/candles"  # public, no key
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ai-trader/1.0"}

_session = requests.Session()
_session.headers.update(UA)


def _get_json(url: str, params: dict | None = None, retries: int = 3, headers: dict | None = None):
    last = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=20, headers=headers)
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:  # network or bad JSON
            last = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"GET failed {url}: {last}")


def _chart(sym: str, rng: str, interval: str) -> dict:
    """One Yahoo chart call. rng "max" asks for period1=0..now: range=max silently returns monthly bars, so the
    granularity Yahoo actually sent is checked (ValueError, not cached, no stale-cache fallback)."""
    if rng == "max":
        params = {"period1": 0, "period2": int(time.time()), "interval": interval, "events": "div,splits"}
    else:
        params = {"range": rng, "interval": interval, "events": "div,splits"}
    data = _get_json(CHART_URL.format(sym=sym), params)
    res = (data.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError(f"no chart data for {sym}: {(data.get('chart') or {}).get('error')}")
    got = (res[0].get("meta") or {}).get("dataGranularity")
    if rng == "max" and got != interval:
        raise ValueError(f"{sym}: full history asked for {interval} bars, Yahoo returned meta.dataGranularity={got!r}")
    return res[0]


def _bars_from_chart(res: dict) -> pd.DataFrame:
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    tz = res["meta"].get("exchangeTimezoneName", "America/New_York")
    idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(tz).normalize().tz_localize(None)
    df = pd.DataFrame(
        {
            "open": q.get("open"),
            "high": q.get("high"),
            "low": q.get("low"),
            "close": q.get("close"),
            "volume": q.get("volume"),
            "adjclose": adj if adj else q.get("close"),
        },
        index=idx,
    ).astype("float64")
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
    ratio = (df["adjclose"] / df["close"]).fillna(1.0)
    for c in ("open", "high", "low"):
        df[c] = df[c] * ratio
    df["close"] = df["adjclose"]
    return df.drop(columns=["adjclose"])


def _events_from_chart(res: dict) -> dict:
    ev = res.get("events") or {}
    tz = res["meta"].get("exchangeTimezoneName", "America/New_York")

    def day(ts):
        return str(pd.Timestamp(int(ts), unit="s", tz="UTC").tz_convert(tz).date())

    splits = [{"date": day(v["date"]), "ratio": float(v["numerator"]) / float(v["denominator"])}
              for v in (ev.get("splits") or {}).values() if v.get("denominator")]
    divs = [{"date": day(v["date"]), "amount": float(v["amount"])} for v in (ev.get("dividends") or {}).values()]
    return {"splits": sorted(splits, key=lambda x: x["date"]), "dividends": sorted(divs, key=lambda x: x["date"])}


def _read_cache(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.attrs["fetched_at"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return df


def fetch_daily(sym: str, rng: str = "5y", max_age_hours: float = 6.0) -> pd.DataFrame:
    """Daily adjusted OHLCV for one symbol, cached on disk (atomic write; events saved alongside).
    df.attrs["fetched_at"] (aware, UTC) is when Yahoo was asked: the cache file's mtime is set to that time, so a
    cached or outage-fallback read carries its real fetch time and its newest bar can be judged (stale_symbols)."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{sym.replace('^', '_')}_{rng}.csv"
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600:
        return _read_cache(path)
    t0 = time.time()
    try:
        res = _chart(sym, rng, "1d")
    except RuntimeError:
        if path.exists():  # outage: a stale cache beats a crash; its old fetch time keeps its newest bar unfinal
            print(f"[data] {sym}: fetch failed, using stale cache")
            return _read_cache(path)
        raise
    df = _bars_from_chart(res)
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp)
    os.utime(tmp, (t0, t0))
    tmp.replace(path)
    (CACHE / f"{sym.replace('^', '_')}_events.json").write_text(json.dumps(_events_from_chart(res)))
    df.attrs["fetched_at"] = datetime.fromtimestamp(t0, timezone.utc)
    return df


def corporate_actions(sym: str) -> dict:
    """Splits and dividends seen in the last daily fetch of `sym` (empty if unknown)."""
    p = CACHE / f"{sym.replace('^', '_')}_events.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {"splits": [], "dividends": []}
    except ValueError:
        return {"splits": [], "dividends": []}


def fetch_panel(symbols: list[str], rng: str = "5y", max_age_hours: float = 6.0) -> dict[str, pd.DataFrame]:
    """Wide panels {field: DataFrame(dates x symbols)}. Missing symbols are skipped and reported.
    panel["_fetched_at"] = {symbol: fetch time} (frame attrs do not survive the concat into wide panels)."""
    frames: dict[str, pd.DataFrame] = {}
    failed: list[str] = []

    def one(s):
        try:
            return s, fetch_daily(s, rng, max_age_hours)
        except Exception as e:  # noqa: BLE001 - report and continue
            return s, e

    with ThreadPoolExecutor(max_workers=8) as ex:
        for s, df in ex.map(one, symbols):
            if isinstance(df, Exception) or df is None or df.empty:
                failed.append(s)
            else:
                frames[s] = df
    if failed:
        print(f"[data] failed symbols: {failed}")
    panel = {}
    for field in ("open", "high", "low", "close", "volume"):
        panel[field] = pd.DataFrame({s: f[field] for s, f in frames.items()}).sort_index()
    # Drop dates where the benchmark-heavy majority is missing (holidays in some feeds).
    valid = panel["close"].notna().sum(axis=1) >= max(1, int(0.5 * len(frames)))
    for field in panel:
        panel[field] = panel[field].loc[valid]
    panel["_fetched_at"] = {s: f.attrs["fetched_at"] for s, f in frames.items() if f.attrs.get("fetched_at")}
    return panel


def stale_symbols(panel: dict, bar, bar_end_utc: datetime, symbols=None) -> set[str]:
    """Symbols whose `bar` is not a final bar: absent (no column, or no close on `bar`) or fetched before
    bar_end_utc (the bar's end + 5 min). symbols: the ones to check (default: the panel's columns and fetch times).
    A panel or symbol without a fetch time counts as fresh (ruling R1: stubs and older tests)."""
    close = panel["close"]
    fetched = panel.get("_fetched_at") or {}
    syms = set(symbols) if symbols is not None else set(close.columns) | set(fetched)
    bar = pd.Timestamp(bar)
    out = set()
    for s in syms:
        absent = s not in close.columns or bar not in close.index or pd.isna(close.at[bar, s])
        if absent or (fetched.get(s) is not None and fetched[s] < bar_end_utc):
            out.add(s)
    return out


def apply_close_source(panel: dict, source: str, bar=None) -> dict:
    """The decision close of the last final bar `bar` (default: the panel's newest row, i.e. every row is final).
    yahoo: the panel as fetched. next_open (a 24/7 market, where D's close and D+1's open are the same instant):
    Yahoo rewrites the latest completed close, so close[D] = open of the D+1 row, for bar D only (spec 4). Without a
    D+1 row that is the next calendar day and has an open for every symbol D has, bar D is dropped from every frame:
    no decision on it, a later run retries. Rows after D stay as fetched. Frames are copied, never changed in place;
    out["_close_source"] logs both closes."""
    if source == "yahoo":
        return panel
    if source != "next_open":
        raise ValueError(f"unknown market.close_source {source!r} (yahoo | next_open)")
    close, opn = panel["close"], panel["open"]
    d = close.index[-1] if bar is None else pd.Timestamp(bar)
    pos = close.index.get_loc(d)
    nxt = close.index[pos + 1] if pos + 1 < len(close.index) else None
    have = close.columns[close.loc[d].notna()]
    if nxt is None or nxt - d != pd.Timedelta(days=1) or opn.loc[nxt, have].isna().any():
        return {k: (v.drop(index=d) if isinstance(v, (pd.DataFrame, pd.Series)) and d in v.index else v)
                for k, v in panel.items()}
    c = close.copy()
    c.loc[d, have] = opn.loc[nxt, have]
    log = {"bar": str(d.date()), "yahoo_close": {s: float(close.at[d, s]) for s in have},
           "next_open": {s: float(opn.at[nxt, s]) for s in have}}
    return {**panel, "close": c, "_close_source": log}


def coinbase_close(sym: str, day) -> float | None:
    """Close of the UTC daily candle `day` for a Yahoo-style pair (BTC-USD) from Coinbase Exchange's public
    candles (no key; rows are [time, low, high, open, close, volume]). None when unreachable or missing."""
    d = pd.Timestamp(pd.Timestamp(day).date())
    t0 = int(d.tz_localize("UTC").timestamp())
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    params = {"granularity": 86400, "start": d.strftime(fmt), "end": (d + pd.Timedelta(days=1)).strftime(fmt)}
    try:
        rows = _get_json(COINBASE_CANDLES.format(sym=sym), params)
        for r in rows if isinstance(rows, list) else []:
            if int(r[0]) == t0 and float(r[4]) > 0:
                return float(r[4])
    except (RuntimeError, TypeError, ValueError, IndexError):
        pass
    return None


def market_status(sym: str = "SPY") -> dict:
    """Live market session info from Yahoo meta (regular session open/close, last price time)."""
    res = _chart(sym, "1d", "5m")
    meta = res["meta"]
    now = datetime.now(timezone.utc).timestamp()
    reg = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    start, end = reg.get("start", 0), reg.get("end", 0)
    return {
        "is_open": bool(start <= now <= end),
        "regular_start_utc": datetime.fromtimestamp(start, timezone.utc).isoformat() if start else None,
        "regular_end_utc": datetime.fromtimestamp(end, timezone.utc).isoformat() if end else None,
        "last_trade_utc": datetime.fromtimestamp(meta.get("regularMarketTime", 0), timezone.utc).isoformat(),
        "price": meta.get("regularMarketPrice"),
    }


def live_prices(symbols: list[str]) -> dict[str, float]:
    """Latest trade price per symbol (regularMarketPrice). Delayed up to ~15 min for some feeds."""

    def one(s):
        try:
            return s, float(_chart(s, "1d", "5m")["meta"]["regularMarketPrice"])
        except Exception:  # noqa: BLE001
            return s, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        return {s: p for s, p in ex.map(one, symbols) if p}


def news_headlines(sym: str, limit: int = 8) -> list[dict]:
    """Recent headlines from Yahoo Finance RSS, Google News RSS as fallback."""
    urls = [
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US",
        f"https://news.google.com/rss/search?q={sym}+stock&hl=en-US&gl=US&ceid=US:en",
    ]
    for url in urls:
        try:
            r = _session.get(url, timeout=15)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            items = []
            for it in root.iter("item"):
                items.append(
                    {
                        "title": (it.findtext("title") or "").strip(),
                        "date": (it.findtext("pubDate") or "").strip(),
                        "link": (it.findtext("link") or "").strip(),
                    }
                )
                if len(items) >= limit:
                    break
            if items:
                return items
        except (requests.RequestException, ET.ParseError, _XmlSecurityError):
            continue
    return []


def sec_recent_form4(user_agent: str, count: int = 100) -> list[dict]:
    """Latest Form 4 (insider transaction) filings from the SEC atom feed. Needs a contact User-Agent."""
    url = "https://www.sec.gov/cgi-bin/browse-edgar"
    params = {"action": "getcurrent", "type": "4", "owner": "include", "count": count, "output": "atom"}
    r = _session.get(url, params=params, timeout=20, headers={"User-Agent": user_agent})
    r.raise_for_status()
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(r.content)
    out = []
    for e in root.findall("a:entry", ns):
        out.append(
            {
                "title": e.findtext("a:title", default="", namespaces=ns),
                "updated": e.findtext("a:updated", default="", namespaces=ns),
                "link": (e.find("a:link", ns).attrib.get("href") if e.find("a:link", ns) is not None else ""),
            }
        )
    return out


REPLACED = ("universe", "prior_weights", "signals", "benchmark")  # a book block replaces these whole
PROFILE_UNIVERSE = {"crypto": {"BTC-USD", "ETH-USD"}, "crypto_base": {"BTC-USD"}}  # load-time guard (spec 3.1)


def _merge(base: dict, over: dict) -> dict:
    """A book block over a config: REPLACED keys and plain values replace; every other block merges key by key."""
    out = dict(base)
    for k, v in over.items():
        merge = k not in REPLACED and isinstance(v, dict) and isinstance(out.get(k), dict)
        out[k] = {**out[k], **v} if merge else v
    return out


def load_config(book: str | None = None, profile: str | None = None) -> dict:
    """The config of a book (default: the active one, journal.BOOK). Stocks: config.json without 'books'.
    Crypto: books.crypto merged over that, then books.<profile> over it when the profile is not 'crypto'; the
    profile defaults to books.crypto.ship_profile. A crypto profile with the wrong universe, or priors that do not
    name every registered signal or do not sum to 1, raises ValueError."""
    from . import journal
    from .signals import REGISTRY

    raw = json.loads((ROOT / "config.json").read_text())
    books = raw.pop("books", {})
    book = book or journal.BOOK
    if book == "stocks":
        return raw
    if book != "crypto":
        raise ValueError(f"unknown book {book!r} (stocks | crypto)")
    profile = profile or books["crypto"]["ship_profile"]
    if profile not in PROFILE_UNIVERSE:
        raise ValueError(f"unknown crypto profile {profile!r} ({' | '.join(PROFILE_UNIVERSE)})")
    cfg = _merge(raw, books["crypto"])
    if profile != "crypto":
        cfg = _merge(cfg, books[profile])
    if set(cfg["universe"]) != PROFILE_UNIVERSE[profile]:
        raise ValueError(f"{profile}: universe {sorted(cfg['universe'])} != {sorted(PROFILE_UNIVERSE[profile])}")
    pw = cfg["prior_weights"]
    if set(pw) != set(REGISTRY) or abs(sum(pw.values()) - 1.0) > 1e-3:
        raise ValueError(f"{profile}: prior_weights must name every signal in {sorted(REGISTRY)} and sum to 1, got {pw}")
    return cfg


def earnings_on(day: str) -> dict[str, str] | None:
    """{symbol: time} for companies reporting on a calendar day (Nasdaq public calendar, unofficial).
    Returns None when the calendar could not be read (callers must not treat that as 'no earnings')."""
    h = {**UA, "Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
    try:
        r = _session.get("https://api.nasdaq.com/api/calendar/earnings", params={"date": day}, headers=h, timeout=20)
        r.raise_for_status()
        rows = ((r.json().get("data") or {}).get("rows")) or []
        return {x["symbol"].replace(".", "-"): x.get("time", "") for x in rows if x.get("symbol")}
    except (requests.RequestException, ValueError, KeyError, AttributeError):
        return None


def load_market(cfg: dict, rng: str = "10y", max_age_hours: float = 6.0) -> dict:
    """Universe panel plus non-tradable regime inputs (VIX) under panel['vix']; panel['_fetched_at'] holds each
    universe symbol's fetch time (the bar-final rule reads it)."""
    panel = fetch_panel(list(cfg["universe"]), rng, max_age_hours)
    panel["_require_vix"] = True  # production: a missing VIX must fail closed (defensive), not silently off
    try:
        vix = fetch_daily("^VIX", rng, max_age_hours)["close"].dropna()
        idx = panel["close"].index
        panel["vix"] = vix.reindex(idx).ffill().where(idx <= vix.index[-1])  # never carry a stale VIX past its last bar
    except Exception as e:  # noqa: BLE001 - regime input is optional
        print(f"[data] VIX unavailable: {type(e).__name__}")
    return panel


def official_opens(symbols: list[str], day) -> dict[str, float]:
    """Opening price of the 09:30 New York 1-minute bar on `day` (the real opening trade).

    Yahoo's DAILY bar 'open' can be wrong early in the session (seen 2026-11-09: SPY daily open 734.82 vs the
    09:30 trade at 741.93; JNJ 267.56 vs 278.16), so paper fills must not use it. 1-minute data is only kept
    for a few days; symbols without it are left out and the caller falls back to the daily open."""
    d = pd.Timestamp(day).date()

    def one(sym):
        try:
            res = _chart(sym, "5d", "1m")
            q = res["indicators"]["quote"][0]
            ts = pd.to_datetime(res.get("timestamp") or [], unit="s", utc=True).tz_convert("America/New_York")
            for t, o in zip(ts, q.get("open") or []):
                if t.date() == d and (t.hour, t.minute) == (9, 30) and o:
                    return sym, float(o)
        except Exception:  # noqa: BLE001 - caller falls back
            pass
        return sym, None

    with ThreadPoolExecutor(max_workers=8) as ex:
        return {s: p for s, p in ex.map(one, sorted(set(symbols))) if p}
