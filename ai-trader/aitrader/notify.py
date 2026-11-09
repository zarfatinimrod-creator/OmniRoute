"""Phone alerts. ntfy.sh needs no account (install the ntfy app, subscribe to your topic).

Configure with env vars (never commit them): AITRADER_NTFY_TOPIC, or AITRADER_TELEGRAM_TOKEN +
AITRADER_TELEGRAM_CHAT. With neither set, alerts are only printed (the Claude session relays them).
"""

from __future__ import annotations

import os

import requests


def send(title: str, body: str, cfg: dict, priority: str = "default") -> list[str]:
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
