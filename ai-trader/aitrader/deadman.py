"""The parent's road to ntfy (supervisor spec 6 and 8): one worker thread with a queue, so the parent's loop never
waits for the network (spec 4.3). Task 21 adds the dead-man switch here.

Standard library only (urllib, as the parent may not import requests). The topic works like a password and the
repository is public: it lives in the environment only, goes into a request and nowhere else, and a result names an
HTTP status or an exception's class, never a URL or an exception's text. That urllib reaches ntfy through the cloud
session's proxy and CA bundle is not verified (spec 6): `python3 -m aitrader.supervise --net-check` asks.
"""

from __future__ import annotations

import json
import os
import queue
import re
import ssl
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from urllib.parse import urlsplit

PRIORITY = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5}  # ownerlines' words as ntfy's numbers


def _opener(base: str, env: Mapping) -> urllib.request.OpenerDirector:
    """An opener that goes the way requests would with this environment: the proxy of its proxy variables, unless
    NO_PROXY names the host, and the CA bundle of SSL_CERT_FILE or REQUESTS_CA_BUNDLE (else the system's)."""
    proxies = {s: env.get(f"{s}_proxy") or env.get(f"{s.upper()}_PROXY") for s in ("http", "https", "no")}
    proxies = {s: v for s, v in proxies.items() if v}
    if urllib.request.proxy_bypass_environment(urlsplit(base).hostname or "", proxies):
        proxies = {}
    proxies.pop("no", None)
    ctx = ssl.create_default_context(cafile=env.get("SSL_CERT_FILE") or env.get("REQUESTS_CA_BUNDLE"))
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies), urllib.request.HTTPSHandler(context=ctx))


def _name(e: BaseException) -> str:
    """An exception's class name; for urllib's URLError, the class of what it wraps (ConnectionRefusedError, ...)."""
    reason = getattr(e, "reason", None)
    return type(reason).__name__ if isinstance(e, urllib.error.URLError) and isinstance(reason, BaseException) \
        else type(e).__name__


def _number(text, pattern: str = r"(\d+)") -> int | None:
    m = re.search(pattern, text or "")
    return int(m.group(1)) if m else None


class Sender:
    """Requests to ntfy at base_url, one at a time on a worker thread (sync=True: at once, in the caller's thread).
    publish and request only queue; results() hands back what came of them. With no topic nothing is requested and
    the result says not ok. env (default os.environ) gives the proxy and the CA bundle."""

    def __init__(self, base_url: str, topic: str | None, timeout: float, env: Mapping | None = None,
                 sync: bool = False):
        self.base, self.topic, self.timeout = base_url.rstrip("/"), topic, timeout
        self._env = os.environ if env is None else env
        self._opener = None  # built at the first request, inside its try: a bad CA file fails a request, not the parent
        self._done, self._lock = [], threading.Lock()
        self._jobs = None if sync else queue.Queue()
        if self._jobs is not None:
            threading.Thread(target=self._work, daemon=True, name="ntfy-sender").start()

    def publish(self, payload: dict, tag: str) -> None:
        """One JSON POST of payload, plus the topic, to base_url."""
        self._put((tag, "POST", None, payload))

    def request(self, method: str, suffix: str, tag: str) -> None:
        """method on <base>/<topic><suffix>: the cancel and the poll of the dead-man (Task 21)."""
        self._put((tag, method, suffix, None))

    def results(self) -> list[dict]:
        """What came of the requests since the last call, in order: {"tag", "ok", "status" (HTTP) or "error" (a class
        name), "left" and "reset_s" (the RateLimit header's r and t), "retry_after", "lines" (a GET's JSON lines, kept
        in memory only)}."""
        with self._lock:
            done, self._done = self._done, []
        return done

    def health(self) -> int | str:
        """GET <base>/v1/health, at once, with no topic and nothing published: the HTTP status, or the class name of
        what went wrong."""
        try:
            with self._open(urllib.request.Request(self.base + "/v1/health")) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            e.close()
            return e.code
        except Exception as e:  # noqa: BLE001 - every failure is an answer here
            return _name(e)

    def close(self) -> None:
        """The worker ends once the requests before this are done."""
        if self._jobs is not None:
            self._jobs.put(None)

    def _put(self, job: tuple) -> None:
        if self._jobs is None:
            self._run(*job)
        else:
            self._jobs.put(job)

    def _work(self) -> None:
        while (job := self._jobs.get()) is not None:
            self._run(*job)

    def _open(self, req: urllib.request.Request):
        if self._opener is None:
            self._opener = _opener(self.base, self._env)
        return self._opener.open(req, timeout=self.timeout)

    def _run(self, tag: str, method: str, suffix: str | None, payload: dict | None) -> None:
        r = {"tag": tag, "ok": False, "status": None, "error": None, "left": None, "reset_s": None,
             "retry_after": None, "lines": None}
        if self.topic:
            r.update(self._ask(method, suffix, payload))
        with self._lock:
            self._done.append(r)

    def _ask(self, method: str, suffix: str | None, payload: dict | None) -> dict:
        if suffix is None:  # a publish: the topic goes into the body here and nowhere else
            req = urllib.request.Request(self.base + "/", method=method, headers={"Content-Type": "application/json"},
                                         data=json.dumps({**payload, "topic": self.topic}).encode())
        else:
            req = urllib.request.Request(f"{self.base}/{self.topic}{suffix}", method=method)
        try:
            with self._open(req) as resp:
                status, headers, data = resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            status, headers, data = e.code, e.headers, b""
            e.close()
        except Exception as e:  # noqa: BLE001 - a refused connection, a timeout, a TLS or proxy failure: its class only
            return {"error": _name(e)}
        rate = headers.get("RateLimit")
        got = {"ok": 200 <= status < 300, "status": status, "left": _number(rate, r"\br=(\d+)"),
               "reset_s": _number(rate, r"\bt=(\d+)"), "retry_after": _number(headers.get("Retry-After"), r"^\s*(\d+)")}
        if method == "GET" and got["ok"]:
            got["lines"] = []
            for line in data.splitlines():
                try:
                    got["lines"].append(json.loads(line))
                except ValueError:
                    continue
        return got
