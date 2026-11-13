### Task 3: The engine child for tests, and a lock that names its holder

**Kind:** BUILD. **Spec:** 5.2, 11.1 (`engine_child.py`).

**Files:** Create `tests/helpers/engine_child.py`, `tests/test_news_supervised.py`, `tests/test_supervise.py`. Modify `aitrader/news_live.py` (`run`, `_run`, the heartbeat write, new `owner_line`), `config.json` (a first `supervisor` block: `max_line_bytes` 1200, `held_names_in_line` 6, `free_text_max_chars` 200; Task 10 adds the rest), `tests/test_news_guards.py` (`OneEngine`: its stand-ins for `_run` and `run` take keywords, and the `_run` stand-in returns 0).

**Interfaces:** Consumes `ownerlines.render`, `no_phone.clean_env`. Produces:

- `news_live.owner_line(cfg: dict, line_id: str, **fields) -> str`: `ownerlines.render` with `max_bytes` and `free_chars` from `cfg["supervisor"]`. Every line of spec 8 that the engine sends (E1, E2, the bare engine's R5d) goes through it.
- `state/news_engine.lock` is opened with "a+" and, once `flock` succeeded, rewritten with one JSON line `{"pid": <int>, "started_at": "<UTC, whole seconds>"}`.
- A refused start prints `[news] another news engine holds the book (pid <pid>, started <started_at>): this one does not start (exit 3)`, returns 3, reads and writes no state file and sends nothing.
- `_run(until_ny, max_minutes, prime, *, locked: bool = True) -> int`; `run()` returns what `_run` returns (0 in this task). When `flock` raises `OSError` the engine runs with `locked=False`: one `notify.send("AI Trader - תקלה", <E2>, cfg, "urgent")` from `_run` (Task 7 fixes its place: after the first stop look), and the heartbeat carries `"lock": false` (true otherwise).
- `python3 tests/helpers/engine_child.py --state-dir DIR --scenario FILE --sent FILE [news-live options]`: points `journal.STATE` at DIR, replaces every call that leaves the process (the list of Baseline record (c)), installs the tripwire, then `sys.exit(aitrader.__main__.main(["news-live", *options]))`. The checker seams answer as `tests/test_core.py` sets them. Scenario keys, all optional:

| Key | Default | Replaces |
|-----|---------|----------|
| `session` | "closed" | "open": `market_open_now()` is true and a quote the stub stamped counts as live (`NewsTrader._quote_is_live`) |
| `calendar_covers` | true | `journal.calendar_covers` |
| `universe`, `news` | `{"AAA": "Tech", "BBB": "Tech", "SPY": "Index"}`, `{}` | `cfg["universe"]`; keys merged over `cfg["news"]` (through `news_live.load_config`) |
| `prices` | 100.0 | `live_price`: per symbol a list, one value per call, the last repeats; null = no quote; each call stamps `QUOTE_TIME` |
| `quote_delay_s` | 0 | a sleep inside every `live_price` |
| `polls` | `[]` | the function `poll_headlines` calls per symbol (`_feed` on the merged tip) and `fetch_headlines`, both: poll n is a list of `{key, symbol, title}`, `published` = now; after the list, nothing |
| `opens` | `{}` | `official_opens` (the queue at the open): `{symbol: price}`; a name not in it takes the stub's live quote |
| `scores`, `score_delay_s`, `score_orphan` | `{}` (5), 0, false | `score_batch`: `{key: score}`; a sleep ("never" = for good); true starts `sleep 60` as a child, writes its pid to `<sent file>.orphan` and leaves it |
| `send_ok` | true | `notify.send` appends `{at, title, body, priority}` to the `--sent` file and returns `["ntfy"]` (false: `[]`) |
| `bars`, `commit` | `[]`, "abc1234" | `bars_since`, `code_stamp` |

- The tripwire, installed before `main`: `requests.sessions.Session.request`, `urllib.request.urlopen` and `socket.create_connection` to a host other than 127.0.0.1, and a `subprocess.Popen` whose program is `claude` or `git`, each append one line (the call's name) to `<sent file>.tripwire` and end the process with `os._exit(97)`. It does not raise: the engine's loop catches every `Exception` and would go on.
- `tests/test_news_supervised.py`: `hold(nt, sym="BBB", entry=50.0)`, the body of `NothingSlowBeforeASale._held` in `tests/test_news_guards.py` (10 shares, stop at 97% of the entry).
- `tests/test_supervise.py`: base class `Procs`: a temporary directory with `state/`; `scenario(dict) -> path`; `start_engine(scenario, *options) -> Popen` (`env=no_phone.clean_env()`, text pipes, `--sent self.sent_file`; when `news_seen.json` is absent it first writes one with a single key stamped now, so that a start does not prime); `write_book({sym: entry})`; `beat() -> dict` (`{}` when there is no file); `wait_beat() -> dict`; `rows(name) -> list`; `sent_rows() -> list`; `wait_for(fn, timeout=5)`; `step_done() -> bool` (the heartbeat and `news_queue.json` exist and the beat's phase, "idle" when the key is absent, is "idle": the first step has ended); `dead(pid) -> bool` (no `/proc/<pid>`, or a zombie); `tearDown` kills what is left, the orphan too, and fails the test when `<sent file>.tripwire` exists.

- [ ] Write the tests:

```python
class Lock(_Engine):                                   # tests/test_news_supervised.py
    def test_a_lock_that_cannot_be_taken_is_said_once_and_is_in_the_heartbeat(self):
        with mock.patch.object(news_live.fcntl, "flock", side_effect=OSError(37, "no locks available")), \
                mock.patch.object(news_live.NewsTrader, "poll_headlines", lambda self, *a, **k: []), \
                mock.patch.object(news_live.time, "sleep", lambda s: None), \
                mock.patch.object(news_live, "load_config", lambda: self.cfg):
            self.assertEqual(news_live.run(max_minutes=0.0005, prime=False), 0)
        self.assertEqual([p for p, b in self.sent if b.startswith("מנוע החדשות רץ בלי נעילה")], ["urgent"])
        self.assertIs(journal.load_json("news_heartbeat.json")["lock"], False)

class EngineLock(Procs):                               # tests/test_supervise.py
    def test_a_second_engine_exits_3_within_2_s_names_the_holder_and_touches_no_state(self):
        a = self.start_engine({"news": {"poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(self.step_done)                  # a sleeps 30 s now: nothing of its own changes the files
        before = {p.name: p.read_bytes() for p in self.state.iterdir()}
        b = self.start_engine({}, "--minutes", "5")
        self.assertEqual(b.wait(timeout=2), 3)
        self.assertEqual({p.name: p.read_bytes() for p in self.state.iterdir()}, before)
        self.assertIn(f"pid {a.pid}", b.stdout.read())
        self.assertEqual(json.loads((self.state / "news_engine.lock").read_text())["pid"], a.pid)

    def test_after_kill_9_of_the_holder_a_new_start_takes_the_lock(self):     # a as above, then a.kill()
        self.assertEqual(self.start_engine({}, "--minutes", "0.001").wait(timeout=10), 0)

    def test_the_lock_is_free_while_an_orphan_of_the_dead_engine_still_runs(self):
        # a: one headline in "polls", "score_orphan" true; wait for a news_scores.jsonl row; a.kill()
        self.assertFalse(self.dead(int(Path(str(self.sent_file) + ".orphan").read_text())))
        self.assertEqual(self.start_engine({}, "--minutes", "0.001").wait(timeout=10), 0)

    def test_an_open_session_with_a_queued_name_and_a_headline_reaches_nothing_outside(self):
        (self.state / "news_queue.json").write_text(json.dumps([{"symbol": "BBB", "score": 9, "why": "x", "id": "q1", "queued_at": "2026-11-12T13:00:00+00:00"}]))
        p = self.start_engine({"session": "open", "polls": [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}]]}, "--minutes", "0.002")
        self.assertEqual(p.wait(timeout=20), 0)        # 97 = the tripwire
        self.assertFalse(Path(str(self.sent_file) + ".tripwire").exists())
```

- [ ] Run both files with `-k Lock`. Expected: `AssertionError: [] != ['urgent']` in the first file, `FileNotFoundError` for `engine_child.py` in the second.
- [ ] Write `tests/helpers/engine_child.py` to the table above; add the three keys to `config.json`; add `owner_line`, change `run` and `_run` in `aitrader/news_live.py`; add `"lock"` to the heartbeat write; let the stand-ins in `OneEngine` take `**k`, the one for `_run` returning 0.
- [ ] Run both files again: 5 tests, `OK`. Then the whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/config.json ai-trader/tests/helpers/engine_child.py ai-trader/tests/test_news_supervised.py ai-trader/tests/test_supervise.py ai-trader/tests/test_news_guards.py`; message `feat(ai-trader): the engine lock names its holder and says when it cannot be taken`.

