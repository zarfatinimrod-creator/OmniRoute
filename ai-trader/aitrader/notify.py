"""Phone alerts. ntfy.sh needs no account (install the ntfy app, subscribe to your topic).

Configure with env vars (never commit them): AITRADER_NTFY_TOPIC, or AITRADER_TELEGRAM_TOKEN +
AITRADER_TELEGRAM_CHAT. With neither set, alerts are only printed (the Claude session relays them).
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from . import journal


def in_quiet_hours(cfg: dict, now: str | None = None) -> bool:
    """True when market.quiet_hours (tz, from, to as HH:MM; may wrap midnight) covers now in its own tz (DST-aware)."""
    q = (cfg.get("market") or {}).get("quiet_hours")
    if not q:
        return False
    t = datetime.fromisoformat(now or journal.now_utc()).astimezone(ZoneInfo(q["tz"])).strftime("%H:%M")
    a, b = q["from"], q["to"]
    return (a <= t < b) if a <= b else (t >= a or t < b)


def send(title: str, body: str, cfg: dict, priority: str = "default", force: bool = False) -> list[str]:
    if not force and in_quiet_hours(cfg):  # waits in alert_queue.json for the morning summary
        queue = journal.load_json("alert_queue.json", []) or []
        queue.append({"queued_at": journal.now_utc(), "title": title, "body": body, "priority": priority})
        journal.save_json("alert_queue.json", queue)
        print(f"[notify] quiet hours: queued - {title}")
        return ["queued"]
    sent = []
    a = cfg.get("alerts", {})
    topic = os.environ.get(a.get("ntfy_topic_env", "AITRADER_NTFY_TOPIC"))
    if topic:
        try:
            prio = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5}.get(priority, 3)
            r = requests.post("https://ntfy.sh/", timeout=15,  # JSON publish keeps Hebrew intact
                              json={"topic": topic, "title": title, "message": body, "priority": prio, "tags": ["chart_with_upwards_trend"]})
            if r.ok:
                sent.append("ntfy")
        except requests.RequestException as e:
            print(f"[notify] ntfy failed: {type(e).__name__}")
    token = os.environ.get(a.get("telegram_token_env", "AITRADER_TELEGRAM_TOKEN"))
    chat = os.environ.get(a.get("telegram_chat_env", "AITRADER_TELEGRAM_CHAT"))
    if token and chat:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=15,
                              json={"chat_id": chat, "text": f"{title}\n\n{body}"})
            if r.ok:
                sent.append("telegram")
        except requests.RequestException as e:
            print(f"[notify] telegram failed: {type(e).__name__}")
    print(f"ALERT: {title}\n{body}")
    return sent


def _age_hours(ts: str, now: datetime) -> float:
    return (now - datetime.fromisoformat(ts)).total_seconds() / 3600


def build_summary(cfg: dict) -> dict:
    """The crypto morning summary (spec 6.1/6.2, planning decision 15) for the active book: {urgent, text, newest}.
    Urgent leads: urgent queued alerts, a broken chain, a missing expected decision, a stale latest.json, and
    skips on 2+ runs in the last 24 h (ruling R7; crypto never freezes a held coin, a stale coin skips the run). Reads state only; changes nothing."""
    from .market import UtcDailyCalendar

    now = datetime.fromisoformat(journal.now_utc())
    queue = journal.load_json("alert_queue.json", []) or []
    urgent = [f"{q['title']}: {q['body']}" for q in queue if q.get("priority") == "urgent"]
    bad = journal.broken_chains(journal.MAIN_CHAINED)
    if bad:
        urgent.append("hash chain broken: " + ", ".join(bad))
    expected = str(UtcDailyCalendar.last_final_bar(now))
    dates = [r["date"] for r in journal.read("decisions.jsonl") if "event" not in r and r.get("date")]
    dates.append((journal.load_json("pending.json", {}) or {}).get("decision_date") or "")
    last = max(dates)
    if last < expected:
        urgent.append(f"missing decision for {expected} (last: {last or 'none'})")
    latest = journal.load_json("latest.json", {}) or {}
    max_age = cfg["market"]["latest_max_age_hours"]
    if not latest.get("as_of_utc") or _age_hours(latest["as_of_utc"], now) > max_age:
        urgent.append(f"latest.json is stale (as of {latest.get('as_of_utc') or 'never'}, limit {max_age} h)")
    recent = lambda rows: [r for r in rows if r.get("logged_at") and _age_hours(r["logged_at"], now) <= 24]  # noqa: E731
    skips = recent(journal.read("skips.jsonl"))
    if len(skips) >= 2:
        urgent.append(f"{len(skips)} skipped runs in 24 h (last: {skips[-1].get('reason', '?')})")
    lines = ["URGENT"] + [f"- {u}" for u in urgent] if urgent else []
    rest = [q for q in queue if q.get("priority") != "urgent"]
    if rest:
        lines += ["Queued overnight"] + [f"- {q['queued_at'][11:16]}Z {q['title']}: {q['body']}" for q in rest]
    lines.append(f"Decision {last or 'none'} (expected {expected}); latest.json {latest.get('as_of_utc') or 'never'}")
    return {"urgent": urgent, "text": "\n".join(lines), "newest": max((q["queued_at"] for q in queue), default=None)}


def ack(upto: str | None) -> int:
    """Drop queued alerts with queued_at <= upto (None: nothing). Returns how many were removed."""
    queue = journal.load_json("alert_queue.json", []) or []
    keep = [q for q in queue if upto is None or q["queued_at"] > upto]
    if len(keep) != len(queue):
        journal.save_json("alert_queue.json", keep)
    return len(queue) - len(keep)
