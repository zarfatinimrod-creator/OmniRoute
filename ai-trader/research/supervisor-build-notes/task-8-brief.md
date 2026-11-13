### Task 8: A planned stop, and an engine that dies with its parent

**Kind:** BUILD. **Spec:** 5.3 (planned stop, supervised mode, code 143), 10 (`news.sleep_slice_seconds`).

**Files:** Modify `aitrader/news_live.py` (module: `STOP`, `request_stop`, `_set_pdeathsig`; `DEFAULTS`; `run`, `_run`, `NewsTrader._step`, `_beat`), `aitrader/__main__.py` (`news-live`: `--supervised PARENT_PID`), `config.json` (`news.sleep_slice_seconds`: 0.5, and a sentence in `news._note`). Test: `tests/test_news_supervised.py` (class `PlannedStop`), `tests/test_supervise.py` (class `EngineStop`).

**Interfaces:** Consumes the `_run` order of Task 7. Produces:

```python
STOP: threading.Event
def request_stop(signum=None, frame=None) -> None     # sets STOP; the handler of SIGTERM and SIGINT
def _set_pdeathsig() -> None                          # Linux: prctl(PR_SET_PDEATHSIG, SIGKILL) through ctypes; elsewhere nothing. A seam: in-process tests replace it
def run(until_ny="16:05", max_minutes=None, prime=True, check=False, supervised: int | None = None) -> int
def _run(until_ny, max_minutes, prime, *, locked: bool = True, supervised: int | None = None) -> int
```

- `run` installs `request_stop` for SIGTERM and SIGINT only when it is called on the main thread, clears `STOP` first and puts the earlier handlers back when it returns.
- `supervised=PID`, before the lock is taken: `_set_pdeathsig()`, then `os.getppid() != PID` prints one line and returns 143. At the top of every loop round a changed parent pid sets `STOP`. The heartbeat's `supervised` is true.
- A planned stop: the loop sees `STOP` at its top and between sleep slices of `news.sleep_slice_seconds`. `_step` starts no scorer batch and no headline quote once `STOP` is set, and takes the headlines it did not hand to the scorer back out of `self.seen` (on the merged tip also out of wave 3's pending record, so that the next engine logs them once: Baseline record (b)). The end-of-step look and the save run as always, then `_beat("stopping")`, and `_run` returns 143. A first look in progress is finished first.
- A supervised engine that leaves with 6 prints its line and sends nothing: its parent sends R5d (Task 13). Only the bare engine says it itself (Task 5).

- [ ] Write the tests. `PARENT` is a three-line script for `python3 -c`: it starts `engine_child.py` with `--supervised <its own pid>`, prints the child's pid and sleeps:

```python
class PlannedStop(_Engine):
    def test_a_wrong_parent_pid_leaves_with_143_before_the_lock(self):
        with mock.patch.object(news_live, "_set_pdeathsig", lambda: None), \
                mock.patch.object(news_live, "NewsTrader", mock.Mock(side_effect=AssertionError("must not be built"))):
            self.assertEqual(news_live.run(max_minutes=0.001, supervised=1), 143)
        self.assertFalse(journal._path("news_engine.lock").exists())

    def test_a_stop_between_batches_scores_no_more_and_leaves_the_rest_unseen(self):
        self.addCleanup(news_live.STOP.clear)        # batch_max 1; the poll marks k1, k2, k3 seen and returns them;
        self.nt.step()                               # the score_batch stand-in notes the key and sets STOP
        self.assertEqual(scored, ["k1"])
        self.assertEqual(sorted(self.nt.seen), ["k1"])

    def test_a_supervised_engine_leaves_the_missing_book_line_to_its_parent(self):   # one BUY row and no book file;
        self.assertEqual(news_live.run(max_minutes=0.001, supervised=os.getppid()), 6)   # _set_pdeathsig and load_config replaced
        self.assertEqual(self.sent, [])

class EngineStop(Procs):
    def test_sigterm_in_the_sleep_exits_143_within_1_s_with_the_book_saved(self):
        p = self.start_engine({"session": "open", "news": {"poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(lambda: self.beat().get("phase") == "idle")
        p.send_signal(signal.SIGTERM)
        self.assertEqual(p.wait(timeout=1), 143)
        self.assertIn("positions", json.loads((self.state / "news_book.json").read_text()))
        self.assertEqual(self.beat()["phase"], "stopping")

    def test_sigterm_during_a_slow_scorer_finishes_that_batch_and_leaves_the_next_unseen(self):
        polls = [[{"key": "k1", "symbol": "AAA", "title": "AAA one"}, {"key": "k2", "symbol": "BBB", "title": "BBB two"}]]
        p = self.start_engine({"session": "open", "polls": polls, "score_delay_s": 1.5, "news": {"batch_max": 1, "poll_seconds": 30}}, "--minutes", "5")
        self.wait_for(lambda: self.beat().get("phase") == "quotes")
        time.sleep(0.3); p.send_signal(signal.SIGTERM)
        time.sleep(0.2); p.send_signal(signal.SIGTERM)             # Review Focus 2: a second signal changes nothing
        self.assertEqual(p.wait(timeout=10), 143)
        self.assertEqual([r["id"] for r in self.rows("news_scores.jsonl")], ["k1"])
        seen = json.loads((self.state / "news_seen.json").read_text())
        self.assertEqual(("k1" in seen, "k2" in seen), (True, False))

    def test_sigterm_during_the_first_look_finishes_the_look(self):       # Review Focus 2; BBB held, "quote_delay_s" 1.5,
        p.send_signal(signal.SIGTERM)                                     # the signal goes out while the phase is "boot"
        self.assertEqual(p.wait(timeout=10), 143)
        self.assertIsNotNone(self.beat()["held"]["BBB"]["checked_at"])

    def test_kill_9_of_its_parent_takes_the_engine_with_it_and_frees_the_lock(self):
        parent = subprocess.Popen([sys.executable, "-c", PARENT, str(self.state), self.scenario({"news": {"poll_seconds": 30}})],
                                  stdout=subprocess.PIPE, text=True, env=no_phone.clean_env())
        child = int(parent.stdout.readline())
        self.wait_for(lambda: self.beat().get("pid") == child)
        parent.kill(); parent.wait()
        self.wait_for(lambda: self.dead(child), timeout=1)
        with open(self.state / "news_engine.lock", "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
```

- [ ] Run `-k PlannedStop` and `-k EngineStop`. Expected: `TypeError: run() got an unexpected keyword argument 'supervised'`; the process tests end with -15 where 143 is expected.
- [ ] Implement as above.
- [ ] Run both: 7 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/news_live.py ai-trader/aitrader/__main__.py ai-trader/config.json ai-trader/tests/test_news_supervised.py ai-trader/tests/test_supervise.py`; message `feat(ai-trader): SIGTERM is a planned stop that ends with 143, and a supervised engine dies with its parent`.

