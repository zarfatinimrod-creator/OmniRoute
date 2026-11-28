"""A local server that plays ntfy for the supervisor's tests (supervisor spec 11.1). It listens on 127.0.0.1 only and
reaches nothing: what it is sent stays in memory (`requests`, `pending`, `delivered`), never in a file.

    stub = NtfyStub([{"status": 500}, {"hang": True}])     # then {"status": 200, "left": 249} for every publish
    ... stub.url ...
    stub.stop()

It answers what the parent and the dead-man ask:
- POST /               a JSON publish. A message with a `delay` waits in `pending` under its sequence id (a publish
                       with the same sequence id replaces it); one with none is delivered at once.
- DELETE /<topic>/<seq>, GET /<topic>/<seq>/delete
                       the cancel of a waiting message.
- GET /<topic>/json?poll=1&sched=1&since=...
                       one JSON line per delivered and per waiting message, with ntfy's fields (ruling P10): id, time,
                       event, topic, message, title, priority, sequence_id. A waiting one has `time` in the future
                       (working rule H1).
- GET /v1/health       200.
Publishes take their answers from `answers`, cancels and polls from `cancel_answers`, in order, then the default. An
answer: {"status": 200, "left": 181} (header `RateLimit: "messages";r=181;t=3600`), {"status": 429, "retry_after": 5}
(header `Retry-After`), {"status": 429} (no ntfy header), {"status": 500}, {"hang": True} (no answer until stop()).
The stub keeps a clock of its own, in whole Unix seconds: advance() moves it, and what is past its delay is delivered.
"""

from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

DEFAULT = {"status": 200, "left": 249}
UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


class NtfyStub:
    def __init__(self, answers: list[dict] | None = None, cancel_answers: list[dict] | None = None):
        self._answers, self._cancel_answers = list(answers or []), list(cancel_answers or [])
        self.requests: list[dict] = []     # {"method", "path", "json"}, in the order they came
        self.pending: dict[str, dict] = {}  # sequence_id -> the message that waits
        self.delivered: list[dict] = []     # the messages the phone would show
        self.clock = int(time.time())      # whole seconds, so that two times differ by exactly what was added
        self._lock, self._stopped, self._n = threading.Lock(), threading.Event(), 0
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.stub = self
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True,
                         name="ntfy-stub").start()     # shutdown() waits up to one poll interval

    def advance(self, seconds: float) -> None:
        """Moves the stub's clock; what is past its delay is delivered, at its own time."""
        with self._lock:
            self.clock += seconds
            for seq, msg in sorted(self.pending.items(), key=lambda kv: kv[1]["at"]):
                if msg["at"] <= self.clock:
                    self.delivered.append(self.pending.pop(seq))

    def stop(self) -> None:
        """Closes the port (a later request is refused) and lets every request that hangs go. Safe to call twice."""
        if not self._stopped.is_set():
            self._stopped.set()
            self._server.shutdown()
            self._server.server_close()

    # what the handler asks
    def _answer(self, cancel: bool) -> dict:
        with self._lock:
            queue = self._cancel_answers if cancel else self._answers
            return queue.pop(0) if queue else DEFAULT

    def _publish(self, body: dict) -> dict:
        with self._lock:
            self._n += 1
            msg = {"id": f"stub{self._n}", "topic": body.get("topic"), "title": body.get("title"),
                   "message": body.get("message"), "priority": body.get("priority", 3),
                   "sequence_id": body.get("sequence_id") or f"stub{self._n}", "at": self.clock}
            self.pending.pop(msg["sequence_id"], None)  # the same sequence id replaces a message that waits
            delay = _seconds(body.get("delay"))
            if delay:
                msg["at"] = self.clock + delay
                self.pending[msg["sequence_id"]] = msg
            else:
                self.delivered.append(msg)
            return msg

    def _cancel(self, seq: str) -> None:
        with self._lock:
            self.pending.pop(seq, None)

    def _poll(self) -> list[dict]:
        with self._lock:
            return [_line(m) for m in [*self.delivered, *self.pending.values()]]


def _seconds(delay) -> int:
    """A delay as ntfy takes it here: a number of seconds, or "6m", "10m", "30s", "2h", "1d"; 0 for none."""
    if isinstance(delay, (int, float)):
        return int(delay)
    m = re.fullmatch(r"\s*(\d+)\s*([smhd]?)\s*", str(delay or ""))
    return int(m.group(1)) * UNITS[m.group(2) or "s"] if m else 0


def _line(msg: dict) -> dict:
    """A message as ntfy's poll gives it (ruling P10)."""
    return {"id": msg["id"], "time": msg["at"], "event": "message", "topic": msg["topic"], "message": msg["message"],
            "title": msg["title"], "priority": msg["priority"], "sequence_id": msg["sequence_id"]}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:  # nothing on stderr: the test output stays clean
        pass

    def _handle(self) -> None:
        stub: NtfyStub = self.server.stub
        size = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(size) if size else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = None
        stub.requests.append({"method": self.command, "path": self.path, "json": body})
        parts = [p for p in urlsplit(self.path).path.split("/") if p]
        if parts == ["v1", "health"]:
            return self._send(200, {}, {"healthy": True})
        answer = stub._answer(cancel=self.command != "POST")
        if answer.get("hang"):
            stub._stopped.wait()  # no answer at all, until the stub stops
            return
        status, headers = answer["status"], {}
        if "left" in answer:
            headers["RateLimit"] = f'"messages";r={answer["left"]};t=3600'
        if "retry_after" in answer:
            headers["Retry-After"] = str(answer["retry_after"])
        if status != 200:
            return self._send(status, headers, {"code": status, "error": "stub"})
        if self.command == "POST":
            return self._send(200, headers, _line(stub._publish(body or {})))
        if self.command == "DELETE" and len(parts) == 2:
            stub._cancel(parts[1])
            return self._send(200, headers, {"event": "message_delete", "sequence_id": parts[1]})
        if self.command == "GET" and len(parts) == 3 and parts[2] == "delete":
            stub._cancel(parts[1])
            return self._send(200, headers, {"event": "message_delete", "sequence_id": parts[1]})
        if self.command == "GET" and len(parts) == 2 and parts[1] == "json":
            text = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in stub._poll())
            return self._send(200, headers, None, text.encode())
        return self._send(404, {}, {"code": 404, "error": "stub: no such path"})

    do_GET = do_POST = do_DELETE = _handle

    def _send(self, status: int, headers: dict, obj, data: bytes | None = None) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode() if data is None else data
        self.send_response(status)
        for k, v in {"Content-Type": "application/json", "Content-Length": str(len(data)), **headers}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)
