### Task 17: The drill script

**Kind:** BUILD. **Spec:** 11.1 (drills a-g), 11.2 (the pass marks of step 2).

**Files:** Create `scripts/drill_supervisor.py`. Test: `tests/test_supervise.py` (class `Drills`).

**Interfaces:** Consumes `supervise.main`, `dummy_child.py`, `engine_child.py`, `NtfyStub`, `clean_env`. Produces `python3 scripts/drill_supervisor.py DRILL... [--fast] [--rounds N]` with DRILL in `a b c d e f g all`. Each drill has its own temporary state directory, config copy and locks; it prints `PASS <drill> <numbers>` or `FAIL <drill> <why>`, and the script exits 0 only when every drill passed. The parent's clock is moved onto a session morning, so a drill runs on any day. Without `--fast` the numbers are those of `config.json`; `--fast` uses a scaled config that keeps their order (`healthy_seconds` 2, `restart_window_seconds` 10, `hang_seconds` 4, `stops_stale_seconds` 3, quote stubs of 4 s).

| Drill | Does | Passes when |
|-------|------|-------------|
| a | 6 `kill -9` of the dummy child, each more than `healthy_seconds` after the last, spread over more than `restart_window_seconds`; then once with the engine child holding 3 names | each time the next beat within 1 s; with the engine child every `held[*].checked_at` within 3 s; no trip; one R1 per kill |
| b | `kill -STOP` of the child, the kill switch on | replaced within `hang_seconds` + 10 s (190 s at the defaults); one `hang` row; one R2 |
| c | a child that always exits 1 | 5 restarts, one `tripped` row, one R3, the parent returns 75 |
| d | `kill -9` of the parent while the engine child sits in a 30 s scorer stub; a new parent at once | nothing of the old tree left; an engine beat within 5 s; no R5c |
| e | `--rounds` (200) times: `kill -9` at a random moment of an engine child that trades on stubs, then a start | every round `verify_chain` holds for the news chains; wherever the book disagrees with the journal's last row the next start sent E1. A broken chain is `FAIL e step 2 does not land: the torn-append repair goes through rule 4 first` |
| f | quote stubs of 60 s with one held name | one `stale_stops` start row, one R6, no kill |
| g | Task 5's loop with 50 starts beside 20 fetch-and-merge rounds | book and chains as they were; every start returned 0 or 7 |
| cloud DIR | not part of `all`: becomes a parent with the dummy child on state directory DIR (`--until 23:59`), in the foreground, for a session to launch as a tracked background command | - |
| cloud-check --alive DIR | while that parent runs, 90 s after its launch | the pid in DIR's parent lock is alive, the log has at least one `mark` row and no `sup_stop`. A parent that left with "orphaned" right after the launch fails here: live, that would be an endless relaunch loop |
| cloud-check DIR | after that parent was stopped from outside | no `supervise` and no child process of DIR left; both locks can be taken; a new parent's child beats within 30 s |

The script is also run by hand, in a session whose environment holds the real topic. Its first act, before it imports `helpers` or starts anything, is `guard(argv, os.environ, <ntfy_base_url of the drill's config copy>) -> str | None`: it removes the three phone variables from the environment; for every mode but `phone --with-owner` (Task 21) it ends the script with exit 2 when the address's host is not 127.0.0.1, and returns None; for `phone --with-owner` it returns the topic, which from then on lives only in a local variable. `phone` without the flag is refused.

- [ ] Write class `Drills(unittest.TestCase)`:

```python
    def test_the_fast_drills_pass(self):
        cp = subprocess.run([sys.executable, "scripts/drill_supervisor.py", "a", "c", "f", "--fast"], capture_output=True, text=True, env=no_phone.clean_env())
        self.assertEqual((cp.returncode, [l.split()[:2] for l in cp.stdout.splitlines() if l[:4] in ("PASS", "FAIL")]),
                         (0, [["PASS", "a"], ["PASS", "c"], ["PASS", "f"]]))

    def test_only_the_phone_drill_with_the_owner_keeps_the_topic_or_an_outside_address(self):
        drill = load_script("scripts/drill_supervisor.py")          # importlib; importing it runs no drill
        env = {"AITRADER_NTFY_TOPIC": "t0p1c-under-test"}
        self.assertEqual((drill.guard(["c"], env, "http://127.0.0.1:9"), env), (None, {}))
        env = {"AITRADER_NTFY_TOPIC": "t0p1c-under-test"}
        self.assertEqual((drill.guard(["phone", "--with-owner", "--phase", "peek"], env, "https://ntfy.sh"), env), ("t0p1c-under-test", {}))
        for argv in (["c"], ["cloud-check", "x"], ["phone"]):
            with self.assertRaises(SystemExit):
                drill.guard(argv, {}, "https://ntfy.sh")

    def test_cloud_check_alive_fails_for_a_parent_that_left_at_once(self):      # Review Focus 2: DIR holds a log of sup_start, sup_stop "orphaned"
        self.assertEqual((rc, out.split()[:1]), (1, ["FAIL"]))
```

- [ ] Run `-k Drills`. Expected: return code 2 (`No such file`).
- [ ] Write the script.
- [ ] Run `-k Drills`: 3 tests, `OK`. Then by hand `python3 scripts/drill_supervisor.py all --fast --rounds 20`: seven `PASS` lines. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/scripts/drill_supervisor.py ai-trader/tests/test_supervise.py`; message `test(ai-trader): drills a-g for the supervisor, on a temporary directory with stub children`.

