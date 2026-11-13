# Task 10 review: the parent's foundations (config, calendar, log, state file, lock, the dummy child)

Diff reviewed: 634c70eb..52ea9265 (2 commits), from the review package
`/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor/review-task-10.diff`, read in one pass. No hunk was cut off.
Read against: task-10-brief.md, constraints.md, controller-notes.md, rulings-10-28.md (the Task 10 section and the
controller's additions), and spec sections 4.1, 4.3, 4.5, 4.6, 10 and 11.1.

### Spec Compliance

Compliant. Every file the brief lists has its hunk, every interface has the signature the brief gives, and every
named test is there under its name with the plan's assertion.

- `supervise.py` interfaces: `load_cfg`, `session_hours`, `Paths` (all ten attributes, file names as spec 4.1 gives
  them), `append_row`, `read_rows`, `prune_rows`, `load_state`, `save_state` and `take_lock` all match the brief.
  Diff lines 95-253.
- State file layout and the rule for another day (supervise.py `_new_state`, `KEPT_ACROSS_DAYS`, `load_state`): the
  counts and `alerts` are reset and `handover` is cleared; `halt`, `reported_through` and `last_commit` are kept. A
  file that does not parse gives a new day's state. The brief says exactly this.
- `load_error` with the class name only (controller's P18(c) addition): present, and it has its own test.
- `config.json`: every key of spec 10 is at its default, except `slots` and `watcher.drill_from`, which the brief
  defers to later tasks. Also present: `until_ny` "16:05", `free_text_max_chars` 200, the five switches set to false,
  and the `deadman` block exactly as spec 10 writes it. The `_note` names the spec and the `planned_stop_grace_seconds`
  / `news.guards` rule. `alerts.ntfy_base_url` = "https://ntfy.sh". I checked every key against the spec 10 table.
- `notify.send` builds its URL with exactly the brief's expression (diff line 57).
- `.gitignore` has the four lines spec 4.1 lists.
- `dummy_child.py`: the options, the run keys and their defaults, the start-n / `.n` count, `stop_age_s` (a number or
  `[age, beats]` pairs with the last age repeating), heartbeat fields, `--supervised`, 143 on SIGTERM, "hang" and
  "crash" all match the brief.
  - The heartbeat field set is the same as `NewsTrader._beat` (news_live.py:1690-1706, checked).
  - The `code` keys match `code_stamp` (news_live.py:363, checked).
  - The prctl and getppid handling is the same as `news_live.run` (news_live.py:104, 1821-1828, 1954, checked).
- The 8 named tests are there under their names with the plan's assertions. Extra assertions were added to tests 3-6;
  none of them weakens the plan's assertion.
- The 3 extra tests are each authorised: the owner-line pin by the controller ruling of 11:00 UTC, the `load_error`
  test by P18(c), and the dummy-ignores-`--until` test by P1 together with the "a behaviour-changing ruling gets one
  test" addition. They are not extra features.
- The lock text is `{pid, started_at}` with `started_at` in UTC, whole seconds. This is the same as the engine's
  (news_live.py:1845, journal.now_utc at journal.py:54-55, checked).
- Commit messages carry no attribution lines (checked with `git log --format=%B`).

Cannot verify from this diff:
- The `--state-dir DIR` layout (state in DIR, logs in DIR/.cache) and the default `ai-trader/state` + `.cache` are
  built by Task 11's `main`. `Paths` has no default constructor yet.
- `main` writing `load_error` to `.cache/supervise.log` and dropping the key before the first save is Task 11
  (P18(c)).
- Spec 4.6 says a damaged line must never stop the parent. `append_row` raises on a failed write (for example a full
  disk), so Task 11's caller must guard its writes.
- Task 11 must create the state and cache directories before `take_lock` and the log.
- Nothing yet exercises the dummy's SIGTERM -> 143, `ignore_term`, `--supervised`, "hang", "crash" and `first_after_s`
  paths. Task 11-12 process tests should cover them.
- The rule-4 gate on this change to `config.json` (and to the engine's `notify.py`) belongs to the landing, not this
  task.
- The 704-test whole-suite result is the implementer's claim. I did not re-run it, as instructed. The reported output
  has its last lines and wall time and no noise.

### Strengths

- `supervise.py` uses the standard library only and has one responsibility per function. Each function's docstring
  states its contract and the spec section it comes from. The import test runs it in a clean subprocess.
- `read_rows` splits lines as bytes, so a U+2028 in a Hebrew field cannot split a row. It skips bad UTF-8 as well as
  bad JSON, and it keeps only dicts, so `r["ev"]` never meets a bare number.
- `prune_rows` keeps a line whose age is unknown and keeps every other line byte for byte. It does not touch the
  tracked file when nothing goes. It rewrites through `<name>.tmp` and `replace`, and the existing `state/**/*.tmp`
  ignore line covers that name.
- `load_state` cannot raise for a list, null, a number, a directory, bad UTF-8 or torn JSON: every non-object case
  becomes `load_error` = the class name, with no text. A same-day file keeps its values over the defaults.
- `take_lock` matches the engine's lock exactly:
  - `BlockingIOError` returns None; any other `OSError` is raised.
  - "a+" leaves the holder's text alone for a refused start.
  - The file is non-inheritable, so a child cannot keep the lock alive.
- The owner-line pin test reads the numbers out of the Hebrew templates rather than formatting the config. A tuned
  value such as 390 s cannot pass by rounding.
- The dummy refuses unknown run keys (exit 2). A misspelt key therefore cannot quietly play a default and let a parent
  test pass for the wrong reason.
- The implementer's mutation pass found one surviving mutant (`session_hours` ignoring `years`) and closed it with a
  new assertion. That assertion is written against the config's last year, so it does not break when 2028 is added.
- Test 8 needs no network: `requests.post` is replaced, the base URL is `127.0.0.1:9`, the topic is invented and set
  only for that call, and stdout is captured.

### Issues

#### Critical (Must Fix)

None.

#### Important (Should Fix)

None.

#### Minor (Nice to Have)

- `tests/test_supervise.py` test `test_notify_posts_to_the_configured_address` (diff lines 644-656): this test depends
  on `market.quiet_hours`.
  - What is wrong: it calls `notify.send(..., cfg, "high")` with the real config and `force` left False. `send`
    queues instead of posting while `market.quiet_hours` covers the current time (notify.py:42-48). Today the value is
    `null` (config.json:38), so the test is correct.
  - Why it matters: if quiet hours are ever set for the stock book, the gate (run after 16:05 New York, inside
    23:00-08:00 Jerusalem) would fail this test. It would also write "a title / a body" into the clone's real
    `state/alert_queue.json` through `journal.save_json`, which is the live-state write the constraints forbid.
  - Fix: one line, either set `cfg.setdefault("market", {})["quiet_hours"] = None` in the test or pass `force=True`.
- `aitrader/supervise.py:172-176`: `_older` swallows `TypeError`. A caller that passes a naive `now` (for example
  `datetime.now()`) would make every comparison with the aware row times raise `TypeError`, so `prune_rows` would keep
  every row and nobody would notice. Fix: reject a naive `now` in `prune_rows` with an assert or a `ValueError`.
- `aitrader/supervise.py:215-216`: the same-day merge is shallow. A same-day file with a partial `alerts` object (for
  example missing `capped`) replaces the default `alerts` whole. Harmless while only `save_state` writes the file
  whole; worth a note for Task 13, which reads `alerts`.
- `aitrader/supervise.py:100-109`: 9:30, 16:00 and 13:00 are literals in the logic. This mirrors
  `journal.session_hours`, the calendar block has no hours, and P18(d) accepted it with the equality test as its
  guard. Recorded here only as the known ceiling.
- `tests/test_supervise.py` test `test_the_dummy_child_plays_run_n_at_start_n_and_never_ends_on_until` covers only the
  "exit" path without `--supervised`. The dummy's SIGTERM -> 143, `ignore_term`, `--supervised` exit 143, "hang" and
  "crash" (`os._exit(code or 1)`) paths are behaviours the brief specifies, and none of them is exercised here. Task
  11 will lean on them, so one small process test now would localise a dummy bug before it shows up as a parent bug.
- `tests/helpers/dummy_child.py:443`: the SIGTERM handler is installed only after the script is read and the `.n`
  count is written. A SIGTERM in the first few milliseconds ends the dummy by signal (-15), not 143. The real engine
  has the same window, and a wider one because of its pandas import, so the dummy is faithful. Note it for any Task 11
  test that sends SIGTERM to a child just after it starts.

### Assessment

Task quality: Approved. The diff does what the brief, the controller notes and rulings P1, P13 and P18 require, with
tests that check real behaviour. Nothing here touches a trading rule, a stop look, the phone or the network. What
remains is minor hardening: making test 8 independent of quiet hours, and checking that `prune_rows` gets an aware
clock.
