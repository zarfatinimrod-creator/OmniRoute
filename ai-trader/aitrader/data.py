"""Market data: Yahoo Finance chart API (no key), news RSS, SEC EDGAR.

Only stdlib + requests + pandas. Daily bars are split/dividend adjusted
(open/high/low scaled by adjclose/close) so returns are total returns.
"""

from __future__ import annotations

import json
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
    data = _get_json(CHART_URL.format(sym=sym), {"range": rng, "interval": interval, "events": "div,splits"})
    res = (data.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError(f"no chart data for {sym}: {(data.get('chart') or {}).get('error')}")
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


def fetch_daily(sym: str, rng: str = "5y", max_age_hours: float = 6.0) -> pd.DataFrame:
    """Daily adjusted OHLCV for one symbol, cached on disk (atomic write; events saved alongside)."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"{sym.replace('^', '_')}_{rng}.csv"
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_hours * 3600:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    try:
        res = _chart(sym, rng, "1d")
    except RuntimeError:
        if path.exists():  # outage: a stale cache beats a crash; the cycle still sees the last known bars
            print(f"[data] {sym}: fetch failed, using stale cache")
            return pd.read_csv(path, index_col=0, parse_dates=True)
        raise
    df = _bars_from_chart(res)
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp)
    tmp.replace(path)
    (CACHE / f"{sym.replace('^', '_')}_events.json").write_text(json.dumps(_events_from_chart(res)))
    return df


def corporate_actions(sym: str) -> dict:
    """Splits and dividends seen in the last daily fetch of `sym` (empty if unknown)."""
    p = CACHE / f"{sym.replace('^', '_')}_events.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {"splits": [], "dividends": []}
    except ValueError:
        return {"splits": [], "dividends": []}


def fetch_panel(symbols: list[str], rng: str = "5y", max_age_hours: float = 6.0) -> dict[str, pd.DataFrame]:
    """Wide panels {field: DataFrame(dates x symbols)}. Missing symbols are skipped and reported."""
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
    return panel


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


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text())


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
    """Universe panel plus non-tradable regime inputs (VIX) under panel['vix']."""
    panel = fetch_panel(list(cfg["universe"]), rng, max_age_hours)
    try:
        vix = fetch_daily("^VIX", rng, max_age_hours)["close"]
        panel["vix"] = vix.reindex(panel["close"].index).ffill()
    except Exception as e:  # noqa: BLE001 - regime input is optional
        print(f"[data] VIX unavailable: {type(e).__name__}")
    return panel
