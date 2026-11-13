# Task 14 re-review, fix round 1

Fix base 9f6190ae41cad87fcccecb586740603194509291, head e1ea314ebc6f00e3dc72b5fd1b013fe892db7d16 (one commit,
e1ea314e). Package: review-task-14-fix1.diff. Gate clone tree clean at head. Read-only review; no test re-run.

### Finding Verdicts

- **F2: ADDRESSED.**
  - Which rule binds is now on record. The fix report (task-14-report.md, "Fix round 1", F2) says the controller note
    of 12:19 UTC 2026-11-11 wins and replaces departure 7. The commit message and the `_live` docstring
    (supervise.py:536-541) cite the note too.
  - `_live` (supervise.py:535-547) no longer reads the lock file's text. It stats the lock file for `st_ino` and reads
    `/proc/locks`. `FLOCK_ROW` (:532) keeps only holding FLOCK rows: `^\d+:\s+FLOCK` cannot match a waiting `-> FLOCK`
    row. Rows are matched on the inode alone, as the finding allowed, and the `ponytail:` comment (:529-531) names the
    limit. The cmdline check stays, as exact element match: `name in _argv(pid)`. There is no flock call.
  - I checked the regex against the kernel's line format and against the live `/proc/locks` here
    (`1: FLOCK  ADVISORY  WRITE 93 fe:00:679940 0 EOF`). It matches: major and minor in hex, the inode in decimal.
  - The engine's lock is a real flock too (news_live.py:1844), so the engine side reads correctly.
  - Case (a), a held lock whose text names an older pid: `status()` gets the holder pid from :585. `none`,
    `replace_parent` and `kill_stray` (:603, `_ppid(engine) != parent`) all use that pid. `clear_halt` (:671-673)
    exits 3 and prints the holder's pid, not `_holder`'s.
  - Case (b), a recycled pid that is another `aitrader.supervise` run with no lock: it is no longer in the holders
    list, so it is not alive.
  - The tests now take real locks:
    - The `STAND_IN` stand-in holds a real flock when it is given a lock file (test_supervise.py:1548-1554).
      `live()` returns only after the stand-in prints "held" (:1564-1570).
    - Every stand-in that plays a parent or an engine holds its lock (:1593, :1600, :1665, :1707).
    - New test at :1714 is the finding's own test: the text names a live `aitrader.supervise` that holds no lock, and
      the result is alive False, action `launch`. The same test adds two more cases: another file's lock (inode
      matching) and this lock held by `news-live` (cmdline check).
    - New test at :1722 is case (a): `(True, holder pid, "replace_parent")`, then `kill_stray`'s why carries the
      engine pid from its lock.
    - :1706, the clear-halt test with text 99999999, proves the lock decides and that the check does not run.
  - The RED output in the report fits the old code on these tests. Example: the clear-halt `(3, 4, True)`. With the
    old reading, the check ran and only `take_lock` refused.

### New Breakage in the Fix Diff

None.

What I checked:
- `relay` takes no lock, so the parent stand-in that now holds `paths.lock` in the unsent test (:1665) does not
  disturb `--relayed`.
- Each stand-in in the `status()` helper is killed and reaped before its file is restored. `holds()` uses
  `write_text`, which keeps the inode, so the stand-in's flock survives the text rewrite.
- An engine whose flock fails ("running without it", news_live.py:1850-1853) writes no text either. The old reading
  could not see it, so there is no regression there.
- A stand-in that cannot take its lock exits, and the `readline` assertion fails fast instead of hanging.
- Test counts check out against the clone: 111 `def test_` at 9f6190ae, 113 at e1ea314e.

### Out-of-Scope Observations

- `clear_halt`'s refusal after the check (supervise.py:688) still names `_holder(paths.lock)`, the pid from the
  text. In case (a) that pid can be stale. It is a hint-only message on a refusal, in code the fix did not touch.
- The inode-only match (the `ponytail:` comment at :529-531) is a documented ceiling. A same-inode flock on another
  filesystem, held by another clone's parent, would read as alive. This is unlikely, and the finding allowed it.
- While `--clear-halt` holds the parent lock for a moment (`take_lock` at :686), a concurrent `--status` reads that
  process as a live parent: its argv names `aitrader.supervise`. This was the same under the old reading, because
  `take_lock` also writes the text.

### Verdict

F2 is addressed. The fix introduces no breakage. The fix report shows the covering tests, the command and the output:
`tests/test_supervise.py` three times, `Ran 113 tests` / `OK`, and the whole suite, `Ran 799 tests` / `OK`. Task 14's
fix round 1 passes re-review.
