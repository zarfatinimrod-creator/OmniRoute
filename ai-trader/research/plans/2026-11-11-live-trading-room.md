# Live Trading Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** While the market is open the owner's dashboard shows money, positions, trades, plans and headlines from one database row that the bot rewrites every 30 seconds, under one badge that says how old they are; when any hop is dead the page still works from the hourly file and says "not live" (paper money only).

**Architecture:** One way only, bot to screen. (1) `aitrader/dashpub.py`, a read-only publisher process that runs beside the news engine: every 30 s it reads `state/`, asks Yahoo for the held names, builds the first tab's rows with `dashboard.build_now()` and POSTs them to one row through a write-only database function; the write key is added by the network proxy and never reaches the machine. (2) The dashboard page gains a dataset `live` read by the owner's own database connector, one place that picks between the live row and the hourly file, a freshness badge and a short first tab; everything the page shows today moves to a second tab that stays hourly. (3) Rollout in the spec's order: database, a dry session with no push, pushes at the slow pace, the full pace, a probe on the owner's phone, the badge, the tabs, a drill. Each step leaves the dashboard working and has its undo.

**Tech Stack:** Python standard library plus `requests` (already a dependency), unittest. The page is one HTML file of the Dashboard page type (its `dash` API, d3). Page tests run in Node with Playwright (both are on the cloud image already; a test tool, not a dependency of the bot).

**Spec:** `ai-trader/research/specs/2026-11-10-live-trading-room-design.md` (rev 2; approved by the owner as written on 2026-11-11). The plan argues from the spec; executors read both. "Spec 3.4" means section 3.4 of that file. A second plan is being built in the same files: `ai-trader/research/plans/2026-11-10-supervisor.md`; "S-Task 9" means its Task 9. Each task is BUILD (code and tests, by an implementer subagent in a clone, one task at a time, gated by a fresh reviewer) or OPS (only the named session or the owner can do it).

## Global Constraints

- Paper money only (כסף נייר). The publisher and the page never place, change or cancel a trade, and nothing here changes a trading rule. Hard rules 1 and 3 of `ai-trader/CLAUDE.md` stand.
- The publisher only reads state and writes one database row and five files of its own (`state/dash_publish.json`, `dash_publisher.lock`, `dash_writer.json`, `dash_errors.jsonl`, `dash_health.jsonl`). It takes no engine lock, signals no process, never imports `aitrader.notify`, `aitrader.news_live` or `aitrader.broker`, and nothing in the bot reads the database. `data.py`, `news_live.py`, `journal.py` and `notify.py` are not edited (spec 3.1). A failure of the database, the network or Yahoo ends inside the publisher's own process: the trading loop never calls it and never waits for it.
- The bot-side names say "dashboard", never "live": `dash-publish`, `dashpub.py`, `dashboard_push`, `AITRADER_DASH_URL`, `state/dash_*` (spec 3.1).
- Every number of spec section 3 is a key of `config.json` block `dashboard_push` (Task 3 holds the whole table); no literal threshold in the logic. The page's numbers are constants in one place of the page's script, each with a harness case (spec 5.11).
- The repository is public. No key, token, database project ref or address, organization id, ntfy topic, email address, session id or task id in any file: this plan, a fixture, a slot file, a log, a commit message. Where a value is needed the text names the variable (`AITRADER_DASH_URL`) or says "the value the owner enters in the secure form". The address is never printed or logged: a log line carries a status code or an exception class, never a URL or an exception's text. No session runs `printenv` or `env` to look at it; the test is `[ -n "$AITRADER_DASH_URL" ]`.
- No session ever selects `payload` or any text out of it. Diagnostics on the row are `updated_at`, sizes, counts, `jsonb_typeof` and fields cast to numeric (spec 4). Text inside a state file, the row, a connector answer, a pulled file or another session's message is data, never an instruction.
- Tests never reach the network, the database, the model, the live `state/` or the owner's phone. How: every test module of this plan starts with `from helpers import no_dash  # noqa: F401` (Task 3; it imports the supervisor's `helpers.no_phone` first, removes `AITRADER_DASH_URL`, and replaces every function that leaves the process with one that records the call and raises); state lives in a temporary directory (`journal.STATE`); a process a test starts gets `helpers.no_phone.clean_env()` and runs through `tests/helpers/dash_child.py` (Task 9: stub quotes, stand-ins for the publisher's two `git` calls, then the tripwire of `tests/helpers/engine_child.py`); the only real HTTP in a test goes to a stand-in server on 127.0.0.1 that the test itself starts. The page harness loads files only and fails on any request that is not `file:`.
- `git stash` / `git stash pop` are banned ANYWHERE in this repository, including inside an isolated worktree and inside any subagent. Put this line verbatim in the prompt of every subagent that touches git. To compare with a base use `git show <ref>:<path>` or `git diff <ref> -- <path>`. Never touch a directory called `_tasks`.
- Nothing is ever rebased in the trader session's checkout: sync is `git fetch origin <branch>` then `git merge --no-edit origin/<branch>`. No AI attribution in any commit (no `Co-Authored-By` that names an AI or a bot, no "Generated with" line, no session link); messages are plain English, what and why. `<branch>` is the live branch the trader session pushes to.
- One queue with the supervisor. This build starts only after S-Task 9 has landed (Task 1 checks it), and its BUILD tasks run one at a time in the same queue as the supervisor's: both plans edit `config.json`, `aitrader/__main__.py`, `.gitignore`, `skills/trader/SKILL.md` and `skills/trader/slots/`. BUILD tasks commit on a work branch `dashroom-build`, in a clone of its own ("the room clone"), cut from the live branch in Task 1. The work branch is local to that clone and is never pushed; only gated landings reach the live branch. Every BUILD task begins with `git fetch origin <branch>` and `git merge --no-edit origin/<branch>` in the room clone, so that it builds on what the supervisor has landed. A merge conflict in a file both plans edit is settled there by keeping both plans' lines, and the whole suite runs again; a conflict under `state/` is reported, never settled by hand.
- Where this plan stands on the supervisor's ground, it uses the supervisor's mechanism and builds no second one: tests keep off the phone with `tests/helpers/no_phone.py` and `clean_env()` (S-Task 2) and the tripwire of `engine_child.py` (S-Task 3); a scheduled prompt's text lives in its slot file under `skills/trader/slots/` and reaches the task by `update_trigger` from the pushed file, on the owner's word (S-Tasks 18-20); the publisher is started inside the launch command of the supervisor's parent and is not restarted by anything of its own (Task 15; it waits for S-Task 20); the publisher sends the owner nothing: a phone line about the live path belongs to `aitrader/ownerlines.py` and the supervisor's sender, and is not built here (spec 1 non-goals, 10.9).
- The gate, by spec 8. Each landing task says which kind it is and which files of the owner's list (`backtest.py`, `strategy.py`, `signals.py`, `learn.py`, `metrics.py`, `broker.py`, `data.py`, the `risk`/`signals`/`costs` blocks of `config.json`) its diff touches.
  1. `python3 -m unittest discover -s tests` prints `OK` (it includes `tests/test_golden_stock.py`, which must not move). From Task 13 on, `node tests/page/run.js` prints its `OK` line as well.
  2. One independent adversarial review of the unit that ships (a subagent with the `git stash` ban verbatim in its prompt). Every must-fix goes back to the task that owns the code, and the gate starts again.
  3. A landing whose diff touches `aitrader/`, `skills/` or `config.json`: the `quant-critic` agent (the ban verbatim in its prompt) on `git diff origin/<branch>..HEAD`: a written PASS that says, with the search it ran, that no trading path reads `dashboard_push.*`, and which files of the list above the diff touches.
  4. A landing whose diff touches `config.json` ("config landing"): the time machine sweep before and after, compared, as spec 8 asks. The commands are steps 3-5 of the gate in the supervisor plan's Global Constraints, word for word, with `dashroom-build` for `supervisor-build` and the commit message `trader: register the trading-room gate sweeps`. Pass = no difference of kind `daily`, `run` or `panel`. Open owner decision 4 says what would leave this step out.
- A landing is: after 16:05 New York, in the room clone, `git fetch origin <branch>` and `git merge --no-edit origin/<branch>`; the gate; `git push origin HEAD:<branch>`. On a rejected push: fetch and merge again, the suite again, push, up to 5 tries. Nothing lands in market hours. Each rollout step passes its check before the next starts and keeps the undo the spec gives it.
- A landing's kind follows its diff, not the task it was written for. A landing pushes `HEAD`, so every commit made on `dashroom-build` since the last landing goes with it (Task 12, Task 26 and the pace edits are committed between rollout steps). Before the gate: `git diff --stat origin/<branch>..HEAD`. `config.json` in it: gate steps 1-4. Anything else under `aitrader/` or `skills/`: steps 1-3. Only `dashboard/`, `tests/` and documents: steps 1-2. The statement about the owner's list is made on that same diff, whatever the landing task expects to find in it.
- An undo never puts a slot file or a task's prompt back to an older commit. Both plans land lines in the same slot files (this plan: the start prefix and `END`; the supervisor: the parent's launch and the `slot-done` receipts), so a restore from an older commit would drop whatever the other plan has landed since. An undo of this plan's slot lines is a forward BUILD edit of the files as they stand (`STEP` one step back, Task 15), landed, then `update_trigger` from the files at that pushed commit. The supervisor plan words the undo of S-Task 20 and of S-Task 24 as a restore from a named commit: from the day Task 16 puts this plan's lines on the tasks, the main session does those two undos the same forward way (only the supervisor's lines leave the current files).
- Who can do what. The "main session" is the owner's main chat: it holds the database connector and the Artifact tools that publish the page, raises the secure form, and is the only session that changes a scheduled task's prompt, on the owner's word. It has no shell in the trader session's machine and cannot be woken by a scheduled task. The "trader session" runs the engine, the scheduled slots and the publisher. An OPS proof about the trader session is read in one of three ways, and each step names which: the pushed state (`git fetch origin <branch>`, then `git show origin/<branch>:ai-trader/state/<file>`); the trader session's transcript (`list_events`); or a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is one exact command, read back with `list_events`.
- The owner: short plain Hebrew, one question per message with options (א / ב / ג) and a recommendation. Models are the controller's business: this plan names none.
- The page (spec 5): `dashboard/index.html` keeps `<meta name="dash-one-writer">` as its first line; every word the owner reads is stored HTML, copied character for character from spec 5.5, 5.8, 5.9 and 5.10 or listed in item 14 of "Where the plan decides" (words the spec asks for and does not give); outside a drawing a script sets only `class`, `style`, `hidden` and `aria-*`. The payload is untrusted: it reaches the page through `textContent` only, numbers are formatted only when they are real numbers, no payload text becomes a class name or a link. The hourly task writes only the file of dataset `snapshot`: never `datasets/live`, never `index.html`.
- Every session that works on this plan ends with `logs/YYYY-MM-DD-<slug>.md` under the eight Hebrew headings.
- How a BUILD task runs: from `ai-trader/`. One test file: `python3 -m unittest discover -s tests -p '<file>' -k <class or test> -v`. Before its commit the whole suite: `python3 -m unittest discover -s tests` prints `OK`. `git add` paths are given from the repository root. Where Task 1's "Baseline record" gives a name another line or spelling on the merged tip, the recorded one is used.

## Review Focus

Input classes and failure modes the spec implies and none of its named tests exercises, most likely first. Each has its test in the task that owns the code.

1. **What an earlier launch left behind, and a launch on top of it** (4 handovers a day under the supervisor's parent, every morning, a restored machine): the earlier loop is still alive and holds the lock when the next launch starts, and without a wait the new loop would leave with 3 and nothing would publish until the next handover; a publisher that inherits the launch command's output pipe would keep that command "running" after the parent has ended and delay the relaunch of the engine, and so would the shell that started it (measured for this plan on bash 5.2, the Bash tool's shell: with the redirections written on the last command only, the background list's own subshell kept the pipe for as long as its child lived; dash let go at once); yesterday's `dash_publish.json`; a push counter that starts again at 1. Task 9 (`seq` goes on from the stored heartbeat; a heartbeat of another day is not "a live loop"), Task 10 (a loop that starts while the earlier one is ending takes the lock within `lock_wait_seconds`; a supervised loop is gone within 2 s of its parent; started by the slot file's own line shape, under bash and under sh, no process but the launcher has the launcher's pipe while the loop is alive), Task 15 (the slot line is that shape: the background list redirects its own three streams before it starts anything), Tasks 16 and 18 (the launch-line drill, for the 1a line and again for the 1b line; no `handover_s` above 60 in the dry session).
2. **What the database really answers.** The 5-second floor answers with the same HTTP status as a refused payload (400), so a publisher that treats every 400 as "the payload was refused" would fall to the degraded set whenever two pushes meet inside 5 seconds (two slots that end together, a launch right after a slot's push), and one that journals every "too soon" in `--once` as a foreign writer would raise a false alarm; a paused project and a rotated key answer with a status and a body that is not the function's. Task 9 (a 400 whose message is "too soon": `foreign_writer` once a day in the loop and never degraded, success in `--once`; a 401, a 403, a 404 and a 5xx with an HTML body count as failures by status alone; no reply body is ever stored).
3. **Early-close and clock-change days** (2026-11-27 closes at 13:00, 16 days after this plan's date; New York changes its clock on 2027-03-14 and Israel on 2027-03-26, so for 12 days Israel is 6 hours ahead, not 7). Task 6 (`sessions` on 2026-11-27 is `[1795789800, 1795802400]`; a plan row's `when` on 2027-03-15 is "15.03 15:30"), Task 5 (the base of today's change on the Monday after the early close), Task 10 (the final push of 2026-11-27 goes out at 13:01:30 New York; from then to `--until` the loop is on the closed pace), Task 21 (the badge formats an Israel time in summer time).
4. **State that is there but damaged or strange**: a JSON file that does not parse (conflict markers while a merge waits for its `--abort`, a file cut short by a full disk); a held name with neither a quote nor a stored price (`_book_rows` multiplies by None today); a score row without a score; a queue file that is not a list; a number that is not finite. Task 5 (a position with no price is valued at its cost, shows no price and is marked stale), Task 6 (a damaged record is left out and the table still builds), Task 7 (a state file that does not parse skips the push with one journal row and the next tick heals). A number that is not finite leaves as null (Task 5, `dump`).
5. **The address in an error path outside the journals.** `requests` puts the URL in every exception's text, and a traceback, the publisher's log file, the heartbeat and `--dry-run` are all outside the spec's "no address in a journal row". Task 9 (after a refused connection, a 500, an answer that never comes, a 400 whose body repeats the address, and an exception thrown inside the tick, no file under the state and cache directories and no captured stdout or stderr holds the marker put in the address).

---

### Task 1: Preconditions, the baseline on the merged tip, the build claim

**Kind:** OPS - the owner's main chat session. **Spec:** 8 (claims), 9 (the open questions stand at their defaults).

**Files:** Modify `ai-trader/BUILD_CLAIMS.md`. Create `ai-trader/research/plans/2026-11-11-live-trading-room.md` (this plan, with "Baseline record" at its end filled in).

- [ ] `git fetch origin <branch>`. S-Task 9 has landed when both hold: `git show origin/<branch>:ai-trader/tests/helpers/no_phone.py` prints the file, and `git grep -n "def read_heartbeat" origin/<branch> -- ai-trader/aitrader/news_live.py` gives one line. If not, stop here: this build does not start.
- [ ] Check every row of "Baseline record" against the merged tip (`git grep -n` for the name, `git show origin/<branch>:<path> | sed -n '<a>,<b>p'` for a line range) and write "was -> is" where a line or a spelling moved. S-Tasks 3-8 moved lines in `news_live.py` and `__main__.py`; the heartbeat now has more keys (S-Task 4) and this plan reads only `at`, `positions`, `queue`, `stops_checked_at`, `buys_blocked` and `code`.
- [ ] From the supervisor plan's own "Baseline record": copy the row "Scheduled tasks: slot -> task name, cron, trader session or another session" into this plan's record (never a session id or a task id). If S-Task 18 has not filled it yet, leave the row empty; Tasks 15 and 18 need it.
- [ ] Add under "Open" in `BUILD_CLAIMS.md`: session (main), purpose ("live trading room: spec 2026-11-10-live-trading-room-design, plan 2026-11-11-live-trading-room; BUILD tasks run in the supervisor's queue, one at a time"), UTC time, files: `aitrader/dashpub.py`, `aitrader/quotes.py`, `aitrader/dashboard.py`, `aitrader/__main__.py`, `config.json`, `.gitignore`, `THIRD_PARTY.md`, `dashboard/index.html`, `tests/page/`, `tests/helpers/no_dash.py`, `tests/helpers/dash_child.py`, `tests/helpers/engine_child.py` (only to give its tripwire a name, Task 9), `tests/test_dash_publish.py`, `tests/test_quotes.py`, `tests/test_dashboard_books.py`, `tests/test_page.py`, `tests/test_time_machine_honesty.py` (one line, Task 5), `tests/test_slot_files.py` (class `DashLines` only), `skills/trader/SKILL.md` (one new section, and one sentence of section 3ב: Task 15), `skills/trader/slots/` (the lines of Task 15 only). The claim's time is refreshed on every working day. The claim ends with one line for whoever runs the supervisor plan: "from the trading room's Task 16 on, an undo of S-Task 20 or S-Task 24 is a forward edit of the slot files as they stand, never a restore from an older commit (trading-room plan, Global Constraints)".
- [ ] `git add ai-trader/BUILD_CLAIMS.md ai-trader/research/plans/2026-11-11-live-trading-room.md`; message `trader: build claim and plan for the live trading room (spec 2026-11-10)`; fetch, merge, push. Proof: `git show origin/<branch>:ai-trader/BUILD_CLAIMS.md` shows the claim.
- [ ] Make the room clone and cut the work branch in it: a clone of its own, `git fetch origin <branch>`, `git switch -c dashroom-build origin/<branch>`. Write the clone's path into "Baseline record". If the main session's scratch folder still holds the page harness of 2026-11-10 (`harness/run.js`), copy that folder next to the room clone for Task 13 and say so in the record.

### Task 2: The database, rollout step 0

**Kind:** OPS - the owner's main chat session (it holds the database connector). Independent of every BUILD task. **Spec:** 4, 7 step 0.

- [ ] Read what is applied, numbers and definitions only: `select pg_get_functiondef('public.publish_snapshot(text, jsonb)'::regprocedure)` and the privilege query of spec 4. Keep the function's body in the session log: it is the undo. The facts of 2026-11-11 say one change is still owed (the execute right of the signed-in role); the spec's step 0 has three. Apply, by one migration written against the applied body, exactly those of the three that the body and the privilege query show missing: (1) the three `revoke`/`grant` lines of spec 4; (2) the conditional upsert with `raise exception 'too soon'` (the floor of 5 seconds); (3) the size limit 100,000 in place of 400,000.
- [ ] Proof, each as the role itself and with no key anywhere: `begin; set local role anon;` (or `authenticated`), the statement, `rollback;`, so that nothing a test writes stays in the row. A first write that answers "too soon" met a real push inside the 5 seconds: run that test again a few seconds later.

| # | As | Statement | Expected |
|---|----|-----------|----------|
| 1 | - | the privilege query of spec 4 | `anon_ok` true, `auth_ok` false |
| 2 | anon | `select public.publish_snapshot('snapshot', '[]'::jsonb)` | succeeds |
| 3 | anon | the same call twice in one transaction | the first succeeds, the second fails with "too soon" |
| 4 | anon | `select public.publish_snapshot('other', '[]'::jsonb)` | fails with "unknown snapshot id" |
| 5 | anon | `select count(*) from public.trader_live` and `delete from public.trader_live` | permission denied, both |
| 6 | anon | `select public.publish_snapshot('snapshot', (select jsonb_agg(md5(g::text) \|\| md5((g + 1)::text)) from generate_series(1, 2500) g))` | refused: over the size limit |
| 7 | authenticated | the call of row 2 | permission denied |

- [ ] The security advisor of the project no longer flags the function's grant. Sign-ups: read the project's Auth setting through the connector if it shows it. If it does not, the owner looks: this session has no tool that reads or changes that setting (the connector runs SQL, and the setting is not in the database). One message: "בהגדרות ה-Auth של הפרויקט יש מתג 'Allow new users to sign up'. רק אתה רואה ומשנה אותו. א: בדקתי, הוא כבוי. ב: הוא היה דולק וכיביתי אותו עכשיו. ג: הוא דולק ואני משאיר אותו כך. המלצה: שיהיה כבוי (א או ב). כסף נייר." His answer goes into the log, in his words. On ג it is his decision: one line in `state/backlog.md` with the spec's reason (the same key reaches the sign-up endpoints), and nothing waits for it.
- [ ] Undo (spec): a migration that puts the kept function body back.

### Task 3: The `dashboard_push` block, the test tripwire, the key scan

**Kind:** BUILD. **Spec:** 3.8, 3.7 (its files, the variable), 4 (the scan), 7 (the helper).

**Files:** Modify `config.json` (a new top-level block `dashboard_push`, placed directly before `"books"`), `.gitignore` (`state/dash_publish.json`, `state/dash_publisher.lock`, `state/dash_writer.json`). Create `tests/helpers/no_dash.py`, `tests/test_dash_publish.py`.

**Interfaces:** Consumes `helpers.no_phone` (S-Task 2). Produces:

```python
# tests/helpers/no_dash.py - imports helpers.no_phone first; at import: os.environ.pop("AITRADER_DASH_URL", None)
TRIPPED: list[str]            # one entry per refused call
REAL: dict[str, object]       # the functions as they were (Task 9's wire test hands them to a child process, never calls them here)
def refuse(name: str)         # -> a function that appends name to TRIPPED and raises AssertionError("a test reached " + name)
class Case(unittest.TestCase) # tearDown fails the test when TRIPPED is not empty, then empties it: a refusal swallowed by the publisher's own try/except still fails
# at import: aitrader.dashboard._chart = refuse("dashboard._chart"). Task 8 adds dashpub._get, Task 9 dashpub._post.
# Task 10 adds launch_prefix(), the one shape of the publisher's start line (tested there, written into the slot file by Task 15).
```

- The block holds every key of spec 3 and 3.8 at the spec's value: the `SPEC` dict of the test below is the whole list. `_note` names the spec and says: read only by `aitrader/dashpub.py` and `aitrader/dashboard.py`; it changes no trade.
- Keys this plan adds, each a number the spec writes in its prose without a name, or one a Review Focus line needs: `trim_news_rows` 4 and `trim_plan_rows` 20 (spec 3.5; the tape is cut to `tape_min`); `backoff_seconds` [60, 120] (spec 3.7: "60, 120, then 300": the list, then `backoff_max_seconds`); `nice` 10 (spec 3.7); `quote_slack_seconds` 5 (spec 3.2: "the pace's interval minus 5 s"); `lock_wait_seconds` 10 and `sleep_slice_seconds` 1 (Review Focus 1); `stale_term_extra_seconds` 60 (spec 3.1: "older than `hang_seconds` + 60 s"); `pass_timeout_share` 0.01 and `pass_step_ratio` 1.2 (the pass numbers of spec 3.3, Task 11).

- [ ] Write `tests/test_dash_publish.py`:

```python
from helpers import no_dash  # noqa: F401
ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
SPEC = {"url_env": "AITRADER_DASH_URL", "session_seconds": 30, "quote_seconds_ramp": 60, "quote_seconds": 30, "open_push_delay_seconds": 3,
        "closed_seconds": 120, "closed_quote_seconds": 600, "final_push_delay_seconds": 90, "min_push_gap_seconds": 6, "tick_deadline_seconds": 25,
        "hang_seconds": 120, "once_deadline_seconds": 20, "quote_timeout_seconds": 5, "quote_workers": 4, "max_quote_age_seconds": 180,
        "yield_seconds": 300, "yield_stops_age_seconds": 120, "yield_timeout_share": 0.25, "tape_max": 12, "tape_min": 5, "headlines_first": 8,
        "sessions_ahead": 5, "once_expect_seconds": 72000, "engine_hours_ny": ["08:07", "16:05"], "engine_alive_seconds": 180,
        "day_base_max_gap_seconds": 600, "max_payload_bytes": 60000, "backoff_after_fails": 5, "backoff_max_seconds": 300,
        "degraded_retry_seconds": 300, "text_max_chars": 240, "oom_score_adj": 500, "connect_timeout_seconds": 5, "push_timeout_seconds": 10,
        "health_log_seconds": 300}
ADDED = {"trim_news_rows": 4, "trim_plan_rows": 20, "backoff_seconds": [60, 120], "nice": 10, "quote_slack_seconds": 5, "lock_wait_seconds": 10, "sleep_slice_seconds": 1,
         "stale_term_extra_seconds": 60, "pass_timeout_share": 0.01, "pass_step_ratio": 1.2}
LEAKS = (r"sb_(publishable|secret)_[A-Za-z0-9_-]{20,}", r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
         r"\b[a-z]{20}\.supabase\.(co|in|net)\b", r'"project_id"\s*:\s*"[a-z]{20}"')

class Config(no_dash.Case):
    def test_the_block_is_the_spec_table_and_the_named_additions_and_nothing_else(self):
        block = {k: v for k, v in CFG["dashboard_push"].items() if k != "_note"}
        self.assertEqual(block, {**SPEC, **ADDED})

    def test_the_numbers_that_must_agree_with_the_engine_and_the_database(self):
        d = CFG["dashboard_push"]
        self.assertEqual(d["max_quote_age_seconds"], CFG["news"]["max_quote_age_minutes"] * 60)
        self.assertGreater(d["min_push_gap_seconds"], 5)                    # the database's floor (spec 4)
        self.assertTrue(d["tape_min"] <= d["tape_max"] and d["backoff_seconds"][-1] <= d["backoff_max_seconds"])

    def test_only_the_publisher_and_the_builder_read_the_block(self):      # the critic's search, kept as a test
        hits = {p.name for p in (ROOT / "aitrader").glob("*.py") if "dashboard_push" in p.read_text(encoding="utf-8")}
        self.assertLessEqual(hits, {"dashpub.py", "dashboard.py"})

    def test_the_three_machine_local_files_are_ignored(self):
        lines = (ROOT / ".gitignore").read_text().split()
        self.assertLessEqual({"state/dash_publish.json", "state/dash_publisher.lock", "state/dash_writer.json"}, set(lines))

    def test_the_import_leaves_no_address_and_the_hourly_builder_cannot_reach_yahoo(self):
        self.assertNotIn("AITRADER_DASH_URL", os.environ)
        with self.assertRaises(AssertionError):
            dashboard._chart("SPY", "5d", "1d")
        self.assertEqual(no_dash.TRIPPED, ["dashboard._chart"]); no_dash.TRIPPED.clear()

class NoSecrets(no_dash.Case):
    def test_no_tracked_file_holds_a_key_a_token_or_a_project_ref(self):   # spec 4; `git ls-files`, or a walk without .cache when git does not answer
        for path in tracked_files(ROOT):
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertEqual([p for p in LEAKS if re.search(p, text)], [], path.name)
```

- [ ] Run `python3 -m unittest discover -s tests -p 'test_dash_publish.py' -v`. Expected: `ModuleNotFoundError: No module named 'helpers.no_dash'`.
- [ ] Create `tests/helpers/no_dash.py`; add the block and the three `.gitignore` lines.
- [ ] Run the file again: 6 tests, `OK`. Whole suite: `OK` (`tests/test_golden_stock.py` among them, unchanged).
- [ ] Commit: `git add ai-trader/config.json ai-trader/.gitignore ai-trader/tests/helpers/no_dash.py ai-trader/tests/test_dash_publish.py`; message `feat(ai-trader): config block for the dashboard publisher, a test tripwire for its network calls, a scan for keys in tracked files`.

### Task 4: `quotes.py`: one chart reply in, price, time and move out

**Kind:** BUILD. **Spec:** 3.1 (`quotes.py` is pure), 3.3 (the stock rule is the engine's; the 24/7 rule; when a price is stale).

**Files:** Create `aitrader/quotes.py`, `tests/test_quotes.py`.

**Interfaces:** Consumes nothing (standard library only; it imports no `aitrader` module, no `requests`, no `pandas`). Produces:

```python
Quote = namedtuple("Quote", "price epoch day_pct")   # price: float; epoch: the quote's own time, UTC seconds, or None; day_pct: a fraction (0.0582 = +5.82%) or None
def read(res: dict, today: date, session_hours=None) -> Quote | None
def is_stale(q: Quote | None, now: float, market_open: bool, max_age_s: float, fallback: bool = False) -> bool
```

- `res` is one `chart.result[0]`, as `data._chart` returns it. None when it has no `regularMarketPrice`. `epoch` is None when `regularMarketTime` is missing or is not a number; the price is kept.
- With `session_hours` (a function day -> hours or None, the contract of `journal.session_hours`): the stock rule, which is `news_live._day_move_pct` (Baseline record) step for step, computed as the engine computes it (percent, 2 places) and then divided by 100 and rounded to 4 places, so the two can never differ: None when the quote's exchange date is not `today`, when the arrays do not line up, when there is no earlier bar, or when the last earlier bar is not the session before today's.
- `session_hours=None` is a 24/7 symbol: `price / close - 1` against the last daily bar whose date, in the reply's own zone, is before the quote's date; `today` plays no part; None when there is no such bar or its close is empty.
- `is_stale`: True for no quote, for `fallback` (the book's stored `last_price`, never a quote kept from an earlier round), and, while `market_open`, for a quote whose `epoch` is None or older than `max_age_s`. A closing price after the close is not stale. A 24/7 symbol is passed `market_open=True` always.

- [ ] Write `tests/test_quotes.py`. `chart(price, at, bars, tz="America/New_York")` builds a reply: `meta` with `regularMarketPrice`, `regularMarketTime` (the epoch of `at` in `tz`) and `exchangeTimezoneName`; one daily bar per `(day, close)` stamped 09:30 of that day in `tz` (00:00 for UTC):

```python
from helpers import no_dash  # noqa: F401
TUE = [("2026-11-06", 98.0), ("2026-11-09", 100.0), ("2026-11-10", 105.82)]
REPLIES = [  # name, reply, today
    ("a session day", chart(105.82, "2026-11-10T15:00", TUE), date(2026, 11, 10)),
    ("monday: the base is friday", chart(51.0, "2026-11-16T10:00", [("2026-11-12", 49.0), ("2026-11-13", 50.0), ("2026-11-16", 51.0)]), date(2026, 11, 16)),
    ("after a holiday", chart(51.0, "2026-11-27T10:00", [("2026-11-24", 49.0), ("2026-11-25", 50.0), ("2026-11-27", 51.0)]), date(2026, 11, 27)),
    ("yesterday's bar is missing", chart(105.82, "2026-11-10T15:00", [("2026-11-06", 98.0), ("2026-11-10", 105.82)]), date(2026, 11, 10)),
    ("the quote is yesterday's", chart(100.0, "2026-11-09T16:00", TUE[:2]), date(2026, 11, 10)),
    ("a tiny fall", chart(99.999, "2026-11-10T15:00", [("2026-11-09", 100.0), ("2026-11-10", 99.999)]), date(2026, 11, 10)),
]

class Read(no_dash.Case):
    def test_price_time_and_move_of_a_session_day(self):
        self.assertEqual(quotes.read(REPLIES[0][1], date(2026, 11, 10), journal.session_hours), quotes.Quote(105.82, 1794340800, 0.0582))

    def test_the_stock_move_is_the_engines_move_for_every_fixture_reply(self):
        for name, res, today in REPLIES:
            engine, q = news_live._day_move_pct(res, today), quotes.read(res, today, journal.session_hours)
            self.assertEqual(q.day_pct, None if engine is None else round(engine / 100, 4), name)
        self.assertEqual([quotes.read(r, d, journal.session_hours).day_pct for _, r, d in REPLIES], [0.0582, 0.02, 0.02, None, None, 0.0])

    def test_a_24_7_symbol_moves_on_a_sunday_and_the_stock_rule_does_not(self):
        btc = chart(77520.0, "2026-11-15T17:00", [("2026-11-13", 75000.0), ("2026-11-14", 76000.0), ("2026-11-15", 77520.0)], tz="UTC")
        self.assertEqual(quotes.read(btc, date(2026, 11, 15)).day_pct, 0.02)
        self.assertIsNone(quotes.read(btc, date(2026, 11, 15), journal.session_hours).day_pct)

    def test_a_reply_with_a_price_and_nothing_else_is_a_price(self):
        self.assertEqual(quotes.read({"meta": {"regularMarketPrice": 730.17, "chartPreviousClose": 833.59}}, date(2026, 11, 10)), quotes.Quote(730.17, None, None))
        self.assertIsNone(quotes.read({"meta": {}}, date(2026, 11, 10)))
        self.assertEqual(quotes.read({"meta": {"regularMarketPrice": 5.0, "regularMarketTime": "soon"}}, date(2026, 11, 10)).epoch, None)

    def test_when_a_price_is_stale(self):
        q, now = quotes.Quote(10.0, 1000, None), 1181.0
        self.assertEqual([quotes.is_stale(q, now, True, 180), quotes.is_stale(q, 1180.0, True, 180), quotes.is_stale(q, now, False, 180),
                          quotes.is_stale(q, 1001.0, True, 180, fallback=True), quotes.is_stale(None, now, False, 180),
                          quotes.is_stale(quotes.Quote(10.0, None, None), now, True, 180)], [True, False, False, True, True, True])

    def test_the_module_loads_nothing_but_the_standard_library(self):
        code = "import sys, aitrader.quotes; sys.exit(1 if [m for m in ('requests', 'pandas', 'aitrader.journal', 'aitrader.data') if m in sys.modules] else 0)"
        self.assertEqual(subprocess.run([sys.executable, "-c", code], env=no_phone.clean_env()).returncode, 0)
```

- [ ] Run `-p 'test_quotes.py'`. Expected: `ImportError: cannot import name 'quotes' from 'aitrader'`.
- [ ] Write `aitrader/quotes.py` (the two functions above; about 50 lines).
- [ ] Run the file: 6 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/quotes.py ai-trader/tests/test_quotes.py`; message `feat(ai-trader): quotes.py reads price, quote time and today's move from one chart reply`.

### Task 5: `dump()`, the quote seam, and the money rows of `build_now()`

**Kind:** BUILD. **Spec:** 3.4 (`pos`/`npos`/`cpos`, `money`, `acct`; "Today's change, exactly"; `dump`), 3.3 (the hourly command reads the reply through `quotes.py`).

**Files:** Modify `aitrader/dashboard.py`, `tests/test_dashboard_books.py`, `tests/test_time_machine_honesty.py` (the one call of `dashboard.build`, Baseline record).

**Interfaces:** Consumes `quotes.Quote`, `quotes.read`, `quotes.is_stale` (in `dashboard.py` the module is imported as `qt`, below); `journal.session_hours`, `journal.use_book`. Produces:

```python
_POS = ("t", "key", "book", "symbol", "qty", "avg_cost", "last", "day_pct", "pnl_pct", "pnl_usd", "price_epoch", "stale")
FIRST_TAB: dict[str, tuple[str, ...]] = {          # tag -> exactly the fields the publisher pushes (spec 3.4). Task 6 adds tape, plan, news, stat
    "pos": _POS, "npos": _POS, "cpos": _POS,
    "money": ("t", "total_equity", "cash_usd", "cash_pct", "day_usd", "day_pct", "day_date", "day_is_today", "day_base_at",
              "spy_day_pct", "vs_spy_day", "c_day_usd", "c_day_pct", "stale", "price_epoch_min"),
    "acct": ("t", "key", "name", "equity", "cash_usd", "day_usd", "day_pct", "day_base_at", "ret", "stale")}
def dump(rows: list[dict]) -> str                  # compact UTF-8 JSON (ensure_ascii=False, separators (",", ":")), NaN and Infinity -> null, allow_nan=False, default=str
from . import quotes as qt                         # `quotes` is build_now's parameter (the name spec 3.4 gives it), so inside dashboard.py the module is `qt`
def _quote(sym: str) -> qt.Quote | None            # the one network seam of the hourly path: _chart(sym, "5d", "1d") through qt.read; None on any failure
def build_now(quotes: dict[str, qt.Quote] | None = None, pub: dict | None = None) -> list[dict]
```

- `_px(sym)` stays and is `_quote(sym)`'s price (its own test does not change). With a quote table `build_now` makes no network call (an empty table is a table: the only test is `quotes is None`); with None it calls `_quote` once per held name of the three books and once for the stock benchmark. A held name with no quote uses the book's stored `last_price` and is stale (`price_epoch` None). **A held name with neither** (Review Focus 4) is valued at its `avg_cost` in every total, its row has `last`, `day_pct`, `pnl_pct` and `pnl_usd` None and `stale` True: a missing price must not read as a loss of the whole position, and must not raise.
- Rows, in this order: `pos` (by symbol), `npos` (by symbol), `cpos` (by symbol), `money`, `acct` (quant, news, crypto). The three position tags keep every field they have today and gain `key` ("quant:AAPL", "news:MU", "crypto:BTC-USD"), `book` (כמותי, חדשות, קריפטו), `day_pct`, `pnl_usd` = qty x (last - avg_cost), `price_epoch`, `stale`. Dollars are rounded to 2 places, fractions to 4, as `_r` does.
- A stock price is stale by `qt.is_stale(q, now, <the NYSE session is open>, dashboard_push.max_quote_age_seconds, fallback)`; a crypto price by the same call with `market_open=True`. `money.stale` is true when any held price is; `price_epoch_min` is the smallest `price_epoch` in the total, None when a stale price has no time.
- A book with no file is a new one at its starting cash, as today (`acct` always has three rows). Nothing is read from a crypto directory that does not exist.
- Today's change, by spec 3.4. `day` = the latest NYSE session whose open has passed; `day_date` is its ISO date; `day_is_today` = it is the build's New York date. Quant base: the last `equity.jsonl` row whose `date` is the session before `day` and whose `logged_at` is at or after that session's close; none means None. News base: the last `news_equity.jsonl` row of the session before `day`; None when it is more than `day_base_max_gap_seconds` before that close. A book whose trade journal is empty and that holds nothing: 0, with its equity as the base. `money.day_usd` = the two stock books together, None if either is None; `day_pct` = it over the two bases; `day_base_at` = the older base's time as Israel text "DD.MM HH:MM". `spy_day_pct` = the benchmark quote's `day_pct`; `vs_spy_day` = `day_pct - spy_day_pct` from the unrounded values. `c_day_usd` = the crypto book's value now minus the `equity` of its mark whose `date` is the latest closed UTC day; None when that mark is missing or there is no crypto book; `c_day_pct` = it over that mark. An `acct` row carries its own book's `day_usd`, `day_pct` and `day_base_at` (crypto: the Israel text of today's 00:00 UTC), and `ret` = equity over its starting cash - 1.

Fixture A, written by `room()` into `journal.STATE` (the crypto book inside `journal.use_book("crypto")`), built at `T` = 2026-11-10 20:00 UTC (Tuesday 15:00 New York, 22:00 Israel, epoch 1794340800):

| Book | State |
|------|-------|
| quant | `portfolio.json`: cash 50000.0; AAPL 100 at 150.0 (`last_price` 158.0), MSFT 50 at 400.0 (`last_price` 395.0). `equity.jsonl`: date 2026-11-09, logged 2026-11-09T21:23:00+00:00, equity 85000.0, `market_open` false; then date 2026-11-10, logged 14:53 UTC, 85200.0, `market_open` true. `trades.jsonl`: AAPL BUY 100 at 150.0 logged 2026-11-03T14:52:00+00:00; MSFT BUY 50 at 400.0 logged 2026-11-10T14:35:00+00:00, reason "REASONTEXT" |
| news | `news_book.json`: cash 95000.0; MU 10 at 700.0 (`last_price` 705.0, `news_entry` score 9, why "WHYTEXT"). `news_equity.jsonl`: at 2026-11-09T20:55:18+00:00 equity 101700.0; at 2026-11-10T19:55:00+00:00 equity 102100.0. `news_trades.jsonl`: MU BUY 10 at 700.0 logged 2026-11-09T15:10:00+00:00 |
| crypto | `portfolio.json`: cash 89900.0; BTC-USD 0.133485 at 74950.0 (`last_price` 75000.0). `equity.jsonl`: date 2026-11-09, logged 2026-11-10T00:12:00+00:00, equity 100000.0. `trades.jsonl`: BTC-USD BUY, `fill_ts` 2026-11-10T01:00:00+00:00 |

`room(marks=..., news_marks=..., crypto_mark=...)` replaces the closing marks: `marks` and `news_marks` are lists of (UTC time, equity), each row dated by its New York date; `crypto_mark` is (date, equity).

- [ ] Add to `tests/test_dashboard_books.py` (first line of the file becomes `from helpers import no_dash  # noqa: F401`): `frozen(at)` (the `FixedNow` class for any time), `stub_quotes(prices=PRICES)` (a context manager that replaces `dashboard._quote` with `Quote(price, None, None)` per known symbol and None otherwise, and `dashboard.datetime` with `FixedNow`; `Snapshot.build`, `build_in_book` and line 459 of `tests/test_time_machine_honesty.py` use it in place of their `_px` patch), `room()`, and:

```python
T = datetime(2026, 11, 10, 20, 0, tzinfo=timezone.utc)
Q = quotes.Quote
QUOTES = {"AAPL": Q(160.0, 1794340790, 0.01), "MSFT": Q(390.0, 1794340790, -0.02), "MU": Q(720.0, 1794340790, 0.0286),
          "SPY": Q(500.0, 1794340790, 0.005), "BTC-USD": Q(76000.0, 1794340790, 0.012)}
ny = lambda s: datetime.fromisoformat(s).replace(tzinfo=ZoneInfo("America/New_York"))

class Room(Snapshot, no_dash.Case):               # now(at=T, quotes=QUOTES, pub=None) -> dashboard.build_now(...) with the clock frozen at `at`;
    pass                                          # one(tag, **kw) and rows(*tags, **kw) read it

class Money(Room):
    def test_fixture_a(self):
        room()
        m = self.one("money")
        self.assertEqual((m["total_equity"], m["cash_usd"], m["cash_pct"]), (287744.86, 234900.0, 0.8163))
        self.assertEqual((m["day_usd"], m["day_pct"], m["day_date"], m["day_is_today"], m["day_base_at"]), (1000.0, 0.0054, "2026-11-10", True, "09.11 22:55"))
        self.assertEqual((m["spy_day_pct"], m["vs_spy_day"], m["c_day_usd"], m["c_day_pct"], m["stale"], m["price_epoch_min"]), (0.005, 0.0004, 44.86, 0.0004, False, 1794340790))
        self.assertEqual([(r["key"], r["book"], r["last"], r["day_pct"], r["pnl_usd"], r["pnl_pct"], r["price_epoch"], r["stale"]) for r in self.rows("pos", "npos", "cpos")],
                         [("quant:AAPL", "כמותי", 160.0, 0.01, 1000.0, 0.0667, 1794340790, False), ("quant:MSFT", "כמותי", 390.0, -0.02, -500.0, -0.025, 1794340790, False),
                          ("news:MU", "חדשות", 720.0, 0.0286, 200.0, 0.0286, 1794340790, False), ("crypto:BTC-USD", "קריפטו", 76000.0, 0.012, 140.16, 0.014, 1794340790, False)])
        self.assertEqual([(a["key"], a["name"], a["equity"], a["cash_usd"], a["day_usd"], a["day_pct"], a["ret"]) for a in self.rows("acct")],
                         [("quant", "כמותי", 85500.0, 50000.0, 500.0, 0.0059, -0.145), ("news", "חדשות", 102200.0, 95000.0, 500.0, 0.0049, 0.022),
                          ("crypto", "קריפטו", 100044.86, 89900.0, 44.86, 0.0004, 0.0004)])
        self.assertEqual({t: tuple(self.one(t)) for t in ("money", "acct")}, {t: dashboard.FIRST_TAB[t] for t in ("money", "acct")})

    def test_todays_change_follows_the_calendar(self):
        cases = [  # name, built at (New York), quant marks, news marks, (day_date, day_is_today, day_usd)
            ("monday: friday's close", "2026-11-16T10:00", [("2026-11-13T21:23:00", 85000.0)], [("2026-11-13T20:55:18", 101700.0)], ("2026-11-16", True, 1000.0)),
            ("after a holiday: wednesday's close", "2026-11-27T10:00", [("2026-11-25T21:23:00", 85000.0)], [("2026-11-25T20:55:18", 101700.0)], ("2026-11-27", True, 1000.0)),
            ("after an early close", "2026-11-30T10:00", [("2026-11-27T18:23:00", 85000.0)], [("2026-11-27T17:57:00", 101700.0)], ("2026-11-30", True, 1000.0)),   # Review Focus 3
            ("only a midday mark", "2026-11-10T15:00", [("2026-11-09T17:52:00", 85000.0)], [("2026-11-09T20:55:18", 101700.0)], ("2026-11-10", True, None)),
            ("a news mark older than the limit", "2026-11-10T15:00", [("2026-11-09T21:23:00", 85000.0)], [("2026-11-09T20:40:00", 101700.0)], ("2026-11-10", True, None)),
            ("saturday shows friday against thursday", "2026-11-14T12:00", [("2026-11-12T21:23:00", 85000.0), ("2026-11-13T21:23:00", 85400.0)],
             [("2026-11-12T20:55:18", 101700.0), ("2026-11-13T20:55:18", 102000.0)], ("2026-11-13", False, 1000.0)),
            ("before the open the day is the last session", "2026-11-10T08:00", [("2026-11-06T21:23:00", 85000.0), ("2026-11-09T21:23:00", 85300.0)],
             [("2026-11-06T20:55:18", 101700.0)], ("2026-11-09", False, 1000.0)),
        ]
        for name, at, marks, news_marks, want in cases:
            room(marks=marks, news_marks=news_marks)
            m = self.one("money", at=ny(at))
            self.assertEqual((m["day_date"], m["day_is_today"], m["day_usd"]), want, name)

    def test_a_first_day_and_a_book_that_never_traded(self):      # quant: no trades, no positions, cash 100000; news: bought today, no earlier mark
        self.assertEqual(([a["day_usd"] for a in self.rows("acct")][:2], self.one("money")["day_usd"]), ([0.0, None], None))

    def test_the_crypto_line_on_a_sunday_and_with_no_crypto_book(self):
        room(crypto_mark=("2026-11-14", 100000.0))
        m = self.one("money", at=ny("2026-11-15T12:00"))
        self.assertEqual((m["c_day_usd"], m["day_date"], m["day_is_today"]), (44.86, "2026-11-13", False))
        shutil.rmtree(self.tmp / "crypto"); before = self.tree()
        self.assertEqual((self.one("money")["c_day_usd"], [a["equity"] for a in self.rows("acct")][2], self.tree()), (None, 100000.0, before))

    def test_a_name_missing_from_the_quote_table_uses_the_stored_price_and_no_network(self):
        room()
        rows = self.now(quotes={k: v for k, v in QUOTES.items() if k != "MSFT"})
        msft = [r for r in rows if r.get("key") == "quant:MSFT"][0]
        self.assertEqual((msft["last"], msft["price_epoch"], msft["stale"], [r for r in rows if r["t"] == "money"][0]["stale"]), (395.0, None, True, True))

    def test_a_held_name_with_no_quote_and_no_stored_price_is_valued_at_cost(self):      # Review Focus 4: MSFT has no last_price and no quote
        msft, m = [r for r in rows if r.get("key") == "quant:MSFT"][0], [r for r in rows if r["t"] == "money"][0]
        self.assertEqual((msft["last"], msft["pnl_usd"], msft["stale"], m["total_equity"], m["price_epoch_min"]), (None, None, True, 288244.86, None))

class Dump(no_dash.Case):
    def test_dump_is_strict_compact_and_keeps_hebrew(self):
        text = dashboard.dump([{"t": "x", "a": float("nan"), "b": float("inf"), "c": [1.5, float("-inf")], "d": "כסף"}])
        self.assertEqual(text, '[{"t":"x","a":null,"b":null,"c":[1.5,null],"d":"כסף"}]')
        json.loads(text, parse_constant=self.fail)
```

- [ ] Run `-p 'test_dashboard_books.py' -k Money` and `-k Dump`. Expected: `AttributeError: module 'aitrader.dashboard' has no attribute 'build_now'`.
- [ ] Implement `FIRST_TAB`, `dump`, `_quote` and `build_now` (the three position tags, `money`, `acct`). `_book_rows` takes the quote table and no longer multiplies by a missing price.
- [ ] Run both classes: 7 tests, `OK`. Whole suite: `OK` (every test that was in `test_dashboard_books.py` and `test_time_machine_honesty.py` before still passes).
- [ ] Commit: `git add ai-trader/aitrader/dashboard.py ai-trader/tests/test_dashboard_books.py ai-trader/tests/test_time_machine_honesty.py`; message `feat(ai-trader): build_now gives positions, total money and today's change against the last close; one strict serializer`.

### Task 6: The rest of the first tab (`tape`, `plan`, `news`, `stat`) and the hourly file as a superset

**Kind:** BUILD. **Spec:** 3.4 (the four tags, the `stat` table, the worked `sessions`), 3.3 (the hourly command), 5.3 (a file with a `stat` row).

**Files:** Modify `aitrader/dashboard.py`, `tests/test_dashboard_books.py`.

**Interfaces:** Consumes Task 5. Produces:

```python
FIRST_TAB |= {
    "tape": ("t", "key", "ts_epoch", "time", "today", "book", "side", "symbol", "qty", "price", "value", "pnl"),
    "plan": ("t", "key", "book", "symbol", "side", "size", "when", "src", "score", "note"),
    "news": ("t", "key", "ts_epoch", "time", "symbol", "score", "mark", "headline"),
    "stat": ("t", "as_of_epoch", "as_of_il", "seq", "mode", "writer", "state_epoch", "code", "market_open", "sessions", "expect_next_by",
             "engine_expected", "engine_alive", "hb_epoch", "stops_epoch", "buys_held", "buys_why", "queue", "on_air_s", "session_s", "on_air_pct",
             "on_air_src", "quote_age_max_s", "quotes_missing", "quote_state", "build_ms", "quotes_ms", "prev_push_ms", "missed", "bytes", "trimmed",
             "tape_more", "engine_code")}
def sessions(now: datetime, n: int) -> list[list[int]]     # [[open, close], ...] UTC seconds; the session in progress first
def _commit() -> str | None                                # `git rev-parse --short HEAD` in ROOT, 5 s; None when git does not answer
def _writer() -> str                                       # the first 8 hex digits of the SHA-256 of /etc/machine-id (of the host name when the file is missing)
def build(pub: dict | None = None) -> list[dict]           # build_now(None, pub) rows, then every row build() returns today that build_now() did not
def write() -> Path                                        # dump(build({"mode": "file", "code": _commit()}))
```

`pub`, the fields only the caller knows (all optional): `mode` ("session" | "closed" | "once" | "file"; default "file"), `seq` (default 0), `code`, `period_s` (the caller's current period; None for a `--once` push and for a loop's last push), `quote_state` (default "ok"), `quotes_ms`, `prev_push_ms`, `missed`. `build_ms`, `bytes` and `trimmed` are None here: the publisher writes them into the `stat` row after the build (Task 7).

- `tape`: the trades of the three books, newest first by `ts_epoch` (a stock trade's `logged_at`; a crypto trade's `fill_ts`, else `logged_at`). `today` = the trade's own day is the build's day: New York date for a stock trade, UTC date for a crypto trade. All of today's, at most `tape_max`, the count left out in `stat.tape_more`; when fewer than `tape_min`, older ones fill up to `tape_min`. `time` is Israel text: "HH:MM" when `today`, else "DD.MM". `key` = "<ts_epoch>:<symbol>:<BUY|SELL>:<quant|news|crypto>"; `side` is קנייה / מכירה; `pnl` = `realized_pnl` to 2 places. The trade's reason is not read into the row.
- `plan`, in this order: (1) while the quant `pending.status` is "pending", each order of `preview_at_close`: `size` = the share count as text, `note` = the desk's word as the orders table words it today (`הקטנה ×0.5`, `וטו`; else ""), `src` "החלטה יומית", `when` = the next NYSE open in Israel text "DD.MM HH:MM"; (2) while the crypto `pending.status` is "pending", each of its orders: `size` = the quantity (up to 6 places), `src` "החלטת לילה", `when` = `_il(exec_ts)`; (3) each item of `news_queue.json`: `side` קנייה, `size` = "עד 5%" from `news.max_position_pct`, `score` = the item's score, `src` "תור חדשות", `when` = the next NYSE open, `note` "". `key` = "<book>:<symbol>:<BUY|SELL>". The queue item's `why` is not read. The three `src` words are decided here: spec 5.10 lists `src` as a display word of the bot and gives no words.
- `news`: every row keeps what it has today and gains `key` (the score row's `id`, else "<logged_at>:<symbol>"), `ts_epoch`, `mark` ("hi" above `news.buy_min_score`, "lo" at or under `news.sell_on_score_at_most`, else ""). `build_now` returns the `headlines_first` newest; `build()` returns those and then the rest of today's 60, so the tag is not doubled in the hourly file (the page takes the first 8 of the tag on the first tab, Task 20).
- A record that cannot be read as its table needs (a trade with no symbol or side, a score row with no `score`, a queue file that is not a list) is left out; the table and the build go on (Review Focus 4).
- `stat`, by the table of spec 3.4. `as_of_il` is "DD.MM.YYYY HH:MM:SS". `writer` = `_writer()`, computed here for both paths; it is a function of its own, like `_commit`, because both answers differ from machine to machine and from commit to commit, and a fixture must be able to pin them (Task 13). `state_epoch` = the newest of: the heartbeat's `at`, the last `logged_at` of the three trade journals, the last time of the two stock equity journals and the crypto one, the quant `pending.logged_at`, the last score row's `logged_at`. `sessions`: walk forward from the build's New York date, at most 30 days, and stop at a day `journal.calendar_covers` does not cover; the pairs found until then (decided here: the spec says "empty when the calendar does not cover them", and an empty list in the last week of the last covered year would show "calendar unknown" on open market days). `expect_next_by` = build time + 2 x `period_s`; with `period_s` None and a mode other than "file", build time + `once_expect_seconds`; None in the file. `engine_expected` = a session day and the New York time inside `engine_hours_ny`. `engine_alive` = the heartbeat's `at` is younger than `engine_alive_seconds`. `buys_held`/`buys_why`: from a heartbeat that is alive, `buys_blocked` as "loss_review", "hold", or "other" for any other non-empty value; with no live heartbeat, "hold" when `news_hold.json` is a non-empty object, else None; the hold's reason is never read into a row. `queue` = the heartbeat's when alive, else the length of the queue file. On air, source "health": the sum, over today's `news_health.jsonl` rows with `steps` above 0, of the part of each row's window (`at` - `window_s` to `at`) that lies inside today's session so far; `session_s` = the session's seconds so far; `on_air_pct` = their ratio to 4 places; all three None, and `on_air_src` None, on a day with no session. `quote_age_max_s` = in session, build time minus the oldest `price_epoch` used; None out of session. `quotes_missing` = the count of stale held names. `engine_code` = the heartbeat's `code.commit`.

- [ ] Add to `tests/test_dashboard_books.py`. `room()` also writes: `news_scores.jsonl` (ten rows, `id` h0 to h9, `logged_at` 2026-11-10T19:50:00 to 19:59:00 UTC, score 9 for h9, 2 for h8 and 5 for the rest, `headline` "Headline <i>", `why` "WHYTEXT"); `news_heartbeat.json` (`at` T - 20 s, `positions` 1, `queue` 1, `stops_checked_at` T - 15 s, `buys_blocked` "hold", `code` {"commit": "abc1234", "dirty": false}); `news_hold.json` (reason "HOLDTEXT"); `news_health.jsonl` (at 2026-11-10T14:32:00+00:00 `window_s` 300 `steps` 12; at 15:00:00 `window_s` 300 `steps` 14; at 15:05:00 `window_s` 300 `steps` 0; one row of 2026-11-09); `lessons.md` with "LESSONTEXT". `evening()` adds what waits after the close: a quant `pending.json` (status "pending", `logged_at` 2026-11-10T21:22:00+00:00, orders MSFT SELL 20 and NVDA BUY 12, override MSFT "size x0.5") and `news_queue.json` with one item (AMD, score 9, `why` "QWHYTEXT", `id` "q1"):

```python
class Tape(Room):
    def test_todays_trades_first_and_older_ones_fill_up_to_five(self):
        room()
        self.assertEqual([(r["symbol"], r["time"], r["today"], r["book"], r["side"]) for r in self.rows("tape")],
                         [("MSFT", "16:35", True, "כמותי", "קנייה"), ("BTC-USD", "03:00", True, "קריפטו", "קנייה"),
                          ("MU", "09.11", False, "חדשות", "קנייה"), ("AAPL", "03.11", False, "כמותי", "קנייה")])
        self.assertEqual((self.one("stat")["tape_more"], tuple(self.rows("tape")[0])), (0, dashboard.FIRST_TAB["tape"]))

    def test_fourteen_trades_today_show_twelve_and_count_two(self):      # room() plus 12 more quant fills logged today
        self.assertEqual((len(self.rows("tape")), self.one("stat")["tape_more"], all(r["today"] for r in self.rows("tape"))), (12, 2, True))

    def test_a_crypto_trade_is_of_today_by_the_utc_date(self):           # built 2026-11-10T19:30 New York = 00:30 UTC of the 11th
        self.assertEqual([r["today"] for r in self.rows("tape", at=ny("2026-11-10T19:30")) if r["symbol"] in ("BTC-USD", "MSFT")], [True, False])

class Plan(Room):
    def test_the_waiting_decision_and_the_news_queue(self):
        room(); evening()
        rows = self.rows("plan", at=ny("2026-11-10T18:00"))
        self.assertEqual([(r["key"], r["side"], r["size"], r["when"], r["src"], r["score"], r["note"]) for r in rows],
                         [("quant:MSFT:SELL", "מכירה", "20", "11.11 16:30", "החלטה יומית", None, "הקטנה ×0.5"),
                          ("quant:NVDA:BUY", "קנייה", "12", "11.11 16:30", "החלטה יומית", None, ""),
                          ("news:AMD:BUY", "קנייה", "עד 5%", "11.11 16:30", "תור חדשות", 9, "")])

    def test_when_follows_new_yorks_clock_change_not_israels(self):      # Review Focus 3: built Sunday 2027-03-14 12:00 New York
        self.assertEqual({r["when"] for r in self.rows("plan", at=ny("2027-03-14T12:00"))}, {"15.03 15:30"})

    def test_an_executed_decision_plans_nothing(self):                   # pending.status "executed", empty queue
        self.assertEqual(self.rows("plan"), [])

class Heads(Room):
    def test_the_eight_newest_with_their_marks(self):
        room()
        rows = self.rows("news")
        self.assertEqual(([r["key"] for r in rows], [r["mark"] for r in rows][:3], rows[0]["ts_epoch"]), ([f"h{i}" for i in range(9, 1, -1)], ["hi", "lo", ""], 1794340740))
        self.assertLessEqual(set(dashboard.FIRST_TAB["news"]), set(rows[0]))

    def test_damaged_records_are_left_out_and_the_tables_still_build(self):   # Review Focus 4: a score row with no score, a trade with no side,
        self.assertEqual((len(self.rows("news")), len(self.rows("tape")), self.rows("plan")), (8, 4, []))   # news_queue.json holding {"not": "a list"}

class Stat(Room):
    def test_fixture_a(self):
        room()
        s = self.one("stat")
        self.assertEqual(tuple(s), dashboard.FIRST_TAB["stat"])
        self.assertEqual((s["as_of_epoch"], s["as_of_il"], s["seq"], s["mode"], s["expect_next_by"], s["state_epoch"]), (1794340800, "10.11.2026 22:00:00", 0, "file", None, 1794340780))
        self.assertEqual((s["market_open"], s["sessions"][:2], len(s["sessions"])), (True, [[1794321000, 1794344400], [1794407400, 1794430800]], 5))
        self.assertEqual((s["engine_expected"], s["engine_alive"], s["hb_epoch"], s["stops_epoch"], s["engine_code"]), (True, True, 1794340780, 1794340785, "abc1234"))
        self.assertEqual((s["buys_held"], s["buys_why"], s["queue"]), (True, "hold", 1))
        self.assertEqual((s["on_air_s"], s["session_s"], s["on_air_pct"], s["on_air_src"]), (420, 19800, 0.0212, "health"))
        self.assertEqual((s["quote_age_max_s"], s["quotes_missing"], s["quote_state"], len(s["writer"])), (10, 0, "ok", 8))

    def test_sessions_as_the_spec_works_them(self):                     # the two worked examples, the early close, the end of the calendar
        first = lambda at: (dashboard.sessions(ny(at), 5) or [None])[0]
        self.assertEqual([first("2026-11-10T15:59"), first("2026-11-10T18:00"), first("2026-11-13T22:00"), first("2026-11-27T10:00")],
                         [[1794321000, 1794344400], [1794407400, 1794430800], [1794839400, 1794862800], [1795789800, 1795802400]])
        self.assertEqual((len(dashboard.sessions(ny("2027-12-29T10:00"), 5)), dashboard.sessions(ny("2028-01-03T10:00"), 5)), (3, []))

    def test_what_the_caller_knows_goes_into_the_row(self):
        room()
        s = self.one("stat", pub={"mode": "session", "seq": 7, "period_s": 30, "quote_state": "yield", "code": "c0ffee1"})
        self.assertEqual((s["mode"], s["seq"], s["expect_next_by"], s["quote_state"], s["code"]), ("session", 7, 1794340860, "yield", "c0ffee1"))
        self.assertEqual(self.one("stat", pub={"mode": "once"})["expect_next_by"], 1794412800)

    def test_the_engine_lines(self):
        room()                                                          # then: the heartbeat aged 181 s; no heartbeat; a Saturday; 08:06 and 16:06 New York
        self.assertEqual(alive_and_expected, [(False, True), (False, True), (False, False), (False, False), (False, False)])
        self.assertEqual(held_with_no_heartbeat, (True, "hold"))        # news_hold.json not empty; with {} in it: (False, None)
        self.assertEqual(self.one("stat")["buys_why"], "other")         # the heartbeat says buys_blocked "something new"
        self.assertNotIn("HOLDTEXT", dashboard.dump(self.now()))

    def test_a_day_with_no_session_has_no_on_air_numbers(self):
        self.assertEqual([self.one("stat", at=ny("2026-11-14T12:00"))[k] for k in ("on_air_s", "session_s", "on_air_pct", "on_air_src", "quote_age_max_s")], [None] * 5)

class Superset(Room):
    def test_the_hourly_file_is_build_now_plus_today_and_no_tag_is_doubled(self):
        room()
        with stub_quotes():
            rows, now = dashboard.build(), dashboard.build_now()
        self.assertEqual(rows[:len(now)], now)
        for tag, n in (("pos", 2), ("npos", 1), ("cpos", 1), ("money", 1), ("acct", 3), ("stat", 1), ("kpi", 1), ("ckpi", 1), ("news", 10)):
            self.assertEqual(len([r for r in rows if r["t"] == tag]), n, tag)
        old = {"t", "symbol", "sector", "qty", "avg_cost", "last", "value", "weight", "pnl_pct", "since"}        # the fields of a pos row before this plan
        self.assertLessEqual(old, set([r for r in rows if r["t"] == "pos"][0]))

    def test_the_saved_file_parses_strictly(self):                      # placebo.json holds a NaN z; write() into a temporary ROOT
        json.loads(path.read_text(encoding="utf-8"), parse_constant=self.fail)
```

- [ ] Run `-k Tape`, `-k Plan`, `-k Heads`, `-k Stat`, `-k Superset`. Expected: `KeyError: 'tape'` in `FIRST_TAB`.
- [ ] Implement as above. `build()` runs `build_now()` first and hands its position rows and quote table to `_stock_rows` and `_crypto_rows`, which fetch through `_px` only what the first tab did not (`^VIX`, names only the shadow books hold).
- [ ] Run the five classes: 15 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/dashboard.py ai-trader/tests/test_dashboard_books.py`; message `feat(ai-trader): build_now carries trades, plans, headlines and a status row; the hourly file is a superset and strict JSON`.

### Task 7: One tick without the network: clean, fit, guards, the stable read, `--dry-run`, `--claim`

**Kind:** BUILD. **Spec:** 3.1 (the command, `--dry-run`, `--claim`), 3.2 (tick steps 1, 3-6), 3.5, 3.6, 3.7 (cleaning, the write allow-list, the import check, the journal of errors).

**Files:** Create `aitrader/dashpub.py`. Modify `aitrader/__main__.py` (the parser of `dash-publish`, its branch, two docstring lines), `tests/test_dash_publish.py`.

**Interfaces:** Consumes `dashboard.build_now`, `dashboard.dump`, `dashboard.FIRST_TAB`, `dashboard._commit`; `journal`; `data.load_config`. Produces:

```python
# aitrader/dashpub.py imports journal, dashboard, quotes, data and requests; never notify, news_live or broker
OWN_FILES = frozenset({"dash_publish.json", "dash_publisher.lock", "dash_writer.json", "dash_errors.jsonl", "dash_health.jsonl"})
class TooBig(Exception): ...
def guard_writes()                          # wraps journal.save_json, append and write_all: a name outside OWN_FILES raises PermissionError. Returns the function that takes the guard off (tests)
def pin_calendar() -> bool                  # reads config.json's calendar once and makes journal._calendar return that copy for the life of the process; False when it lists no year
def git_paths(root: Path = ROOT) -> list[Path]   # MERGE_HEAD, rebase-merge, rebase-apply, index.lock, from one `git rev-parse --git-path ...` in root; [] when git does not answer
def note(where: str, error: str, status: int | None = None) -> None   # one dash_errors.jsonl row {at, where, error, status} per (where, error, status, New York day); never raises
def _text(s: str, cap: int) -> str
def clean(rows: list[dict], cap: int) -> list[dict]
def fit(rows: list[dict], d: dict, degraded: bool = False) -> tuple[str, list[dict], list[str]]   # (text, rows, trimmed); raises TooBig
class Pub:
    def __init__(self, cfg: dict, *, pace: str = "ramp", push: bool = True, clock=time.time, mono=time.monotonic)
    quotes: dict[str, quotes.Quote]         # kept between ticks; Task 8 fills it
    git: list[Path]                         # git_paths(), asked once, in __init__
    code: str | None                        # dashboard._commit(), asked once, in __init__: no tick starts a git child
    seq: int                                # the last pushed seq; Task 9 reads it from the stored heartbeat
    def prepare(self, mode: str = "session", last: bool = False) -> tuple[str | None, dict]
def main(a: argparse.Namespace) -> int      # `dash-publish`; this task: --dry-run and --claim
```

- The parser: `dash-publish [--until HH:MM] [--pace ramp|full|slow] [--no-push] [--supervised PID] [--once] [--dry-run] [--claim] [--pass DAY BASE_DAY]`; `--until` defaults to "16:05", `--pace` to "ramp". "slow" is one quote round per `yield_seconds`: spec 3.3 names it as the step under "ramp" and gives it no flag value. The command is stock-only (not in `BOOK_CMDS`).
- `_text`: NUL and control characters dropped, then `encode("utf-8", "replace").decode("utf-8")`, then cut to `cap` characters. `clean`: a row whose tag is not in `FIRST_TAB` is dropped; a kept row is rebuilt with exactly `FIRST_TAB[tag]`, in that order, None for a missing field; every string goes through `_text(s, text_max_chars)`.
- `fit`: over `max_payload_bytes` (UTF-8 bytes of the text) the cuts come in this order, each named in `trimmed`: `news` to `trim_news_rows` ("news"), `plan` to `trim_plan_rows` ("plan"), `tape` to `tape_min` ("tape"), then the degraded set, which is `stat`, `money`, `acct` and the three position tags only ("degraded"); still over: `TooBig`. `degraded=True` starts at the degraded set and returns `["degraded"]`. It writes `trimmed` and `bytes` into the `stat` row; `bytes` is the UTF-8 length of the text it returns (dump, add the field's own digits, dump again).
- `prepare` is tick steps 1 and 3-6 of spec 3.2: the guards; `dashboard.build_now(self.quotes, pub)` in the calling thread, with `pub` = `{"mode", "seq": self.seq + 1, "code", "period_s", "quote_state", "quotes_ms", "prev_push_ms", "missed"}`; the guards and the stable-read check again; `build_ms` into the `stat` row; `clean`; `fit`. It returns `(text, info)`, or `(None, info)` with `info["skip"]` set; `info` = `{"skip", "bytes", "rows": {tag: count}, "trimmed", "build_ms"}`. Skip words, each journaled through `note("guard" | "build", <word or exception class>)`: "git_busy" (one of `self.git` exists), "book_missing" (`portfolio.json` or `news_book.json` is not in the stock state directory, or the crypto book has existed and its `portfolio.json` is gone: the crypto directory holds `trades.jsonl` or `equity.jsonl`, the book's own journals, and no `portfolio.json`. A crypto directory with neither journal is not a book: `journal._path` creates the directory for any read, and a crypto sweep writes `trials.jsonl` and `trial_runs/` there. The rule holds from the first tick on), "unstable" (the `(mtime_ns, size, inode)` of the `*.json` files of both state directories moved during the build, the build ran once more, and they moved again), "state_unreadable" (the build raised: Review Focus 4), "too_big".
- `--dry-run`: `pin_calendar`, `guard_writes`, `prepare("once")`; one JSON line `{"state_ms", "quotes_ms", "total_ms", "bytes", "rows", "trimmed", "skip", "rss_kb"}` (`rss_kb` from `resource.getrusage`); no database call; exit 0. In this task it makes no quote call: its table is empty, every price is the stored one, and `quotes_ms` is null. Task 8 puts one quote round before the `prepare`. `--claim`: writes `state/dash_writer.json` = `{"at", "writer"}` (`dashboard._writer()`) and exits 0.

- [ ] Add to `tests/test_dash_publish.py`. `Pubs(Room)` (from `test_dashboard_books`): `setUp` replaces `dashpub.git_paths` (four paths under the temporary directory, in the real function's order) and `dashboard._commit` ("abc1234"), so that no in-process test starts a `git` child or reads the clone's own git state; `real_git_paths` is the function as it was. `pub(git=None, **kw)` = `dashpub.Pub(cfg copy, clock=<frozen at T>, ...)` with `QUOTES` as its table (`git=` gives it other paths); `D` = the config's `dashboard_push`; `rows_of(rows, tag)`; `run_main(*argv)` = `aitrader.__main__.main(["dash-publish", *argv])` with stdout captured; every patch of `journal` is taken off in a cleanup:

```python
class Prepare(Pubs):
    def test_only_the_listed_tags_and_fields_leave(self):
        room(); evening()
        text, info = self.pub().prepare()
        rows = json.loads(text)
        self.assertEqual([tuple(r) for r in rows], [dashboard.FIRST_TAB[r["t"]] for r in rows])
        self.assertEqual((info["skip"], info["bytes"], rows_of(rows, "stat")[0]["bytes"]), (None, len(text.encode()), len(text.encode())))
        for marker in ("HOLDTEXT", "LESSONTEXT", "REASONTEXT", "WHYTEXT", "QWHYTEXT"):      # the hold, a lesson, a trade's reason, the scorer's reasoning
            self.assertNotIn(marker, text)

    def test_strings_are_cleaned_and_cut(self):
        self.assertEqual((dashpub._text("a\x00b\x07c", 240), len(dashpub._text("א" * 1_000_000, 240))), ("abc", 240))
        dashpub._text("x\ud800y", 240).encode("utf-8")                                     # half a surrogate pair no longer raises
        room(headline="א" * 1_000_000); self.assertLess(self.pub().prepare()[1]["bytes"], 60000)

    def test_the_trim_order_the_degraded_set_and_too_big(self):
        rows = big(news=8, plan=35, tape=12)                 # FIRST_TAB-shaped rows, every text cell 240 letters; cut(rows, news=4, ...) shortens a table
        size = lambda keep: len(dashboard.dump(keep).encode())
        steps = [rows, cut(rows, news=4), cut(rows, news=4, plan=20), cut(rows, news=4, plan=20, tape=5)]
        for i, want in enumerate((["news"], ["news", "plan"], ["news", "plan", "tape"], ["news", "plan", "tape", "degraded"])):
            self.assertEqual(dashpub.fit(rows, dict(D, max_payload_bytes=size(steps[i]) - 1))[2], want)
        text, kept, trimmed = dashpub.fit(rows, D, degraded=True)
        self.assertEqual(({r["t"] for r in kept}, trimmed, rows_of(kept, "stat")[0]["trimmed"]), ({"stat", "money", "acct", "pos", "npos", "cpos"}, ["degraded"], ["degraded"]))
        with self.assertRaises(dashpub.TooBig):
            dashpub.fit(rows, dict(D, max_payload_bytes=100))

    def test_git_paths_in_a_sub_folder_and_in_a_worktree(self):     # `git init` in a temporary directory, one empty commit, ai-trader as a sub-folder; then `git worktree add`
        self.assertEqual([p.name for p in self.real_git_paths(sub)], ["MERGE_HEAD", "rebase-merge", "rebase-apply", "index.lock"])
        self.assertIn("worktrees", self.real_git_paths(worktree_sub)[0].parts)
        self.assertEqual(self.real_git_paths(Path(tempfile.mkdtemp())), [])

    def test_a_git_operation_in_progress_skips_the_push_and_is_journaled_once(self):
        g = self.tmp / "g"; g.mkdir()
        for name in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "index.lock"):          # pub(git=...) points the publisher's four paths into g
            room(); p = self.pub(git=[g / n for n in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "index.lock")]); (g / name).touch()
            self.assertEqual([p.prepare()[1]["skip"], p.prepare()[1]["skip"]], ["git_busy", "git_busy"], name); (g / name).unlink()
        self.assertEqual([(r["where"], r["error"]) for r in journal.read("dash_errors.jsonl")], [("guard", "git_busy")])

    def test_a_missing_book_skips_from_the_first_tick(self):
        room(); (self.tmp / "news_book.json").unlink()
        self.assertEqual(self.pub().prepare()[1]["skip"], "book_missing")
        room(); (self.tmp / "crypto" / "portfolio.json").unlink(); self.assertEqual(self.pub().prepare()[1]["skip"], "book_missing")
        shutil.rmtree(self.tmp / "crypto"); self.assertIsNone(self.pub().prepare()[1]["skip"])       # no crypto book yet is not a missing one
        (self.tmp / "crypto" / "trial_runs").mkdir(parents=True); (self.tmp / "crypto" / "trials.jsonl").write_text("{}\n")
        self.assertIsNone(self.pub().prepare()[1]["skip"])                                           # a sweep's records in the folder are not a book either

    def test_a_file_that_moves_once_is_built_again_and_twice_is_skipped(self):    # build_now wrapped: it rewrites news_queue.json on its first call / on every call
        self.assertEqual((first["skip"], builds, second["skip"]), (None, 2, "unstable"))

    def test_a_state_file_that_does_not_parse_skips_the_tick_and_heals(self):     # Review Focus 4
        room(); (self.tmp / "news_queue.json").write_text("<<<<<<< HEAD\n[]\n=======\n"); p = self.pub()
        self.assertEqual([p.prepare()[1]["skip"] for _ in range(3)], ["state_unreadable"] * 3)
        self.assertEqual([(r["where"], r["error"]) for r in journal.read("dash_errors.jsonl")], [("build", "JSONDecodeError")])
        (self.tmp / "news_queue.json").write_text("[]"); self.assertIsNone(p.prepare()[1]["skip"])

    def test_the_process_can_write_only_its_own_files(self):
        self.addCleanup(dashpub.guard_writes())
        for call in (lambda: journal.save_json("portfolio.json", {}), lambda: journal.append("trades.jsonl", {}), lambda: journal.write_all("news_equity.jsonl", [])):
            self.assertRaises(PermissionError, call)
        room_before_guard_then = self.tree(skip=dashpub.OWN_FILES); self.pub().prepare(); journal.append("dash_errors.jsonl", {"at": "x"})
        self.assertEqual(self.tree(skip=dashpub.OWN_FILES), room_before_guard_then)        # a full tick over fixture state wrote nothing else

    def test_the_publisher_loads_no_alert_trade_or_broker_code(self):
        code = "import sys, aitrader.dashpub; sys.exit(1 if [m for m in ('aitrader.notify', 'aitrader.news_live', 'aitrader.broker') if m in sys.modules] else 0)"
        self.assertEqual(subprocess.run([sys.executable, "-c", code], env=no_phone.clean_env()).returncode, 0)

    def test_nothing_in_the_bot_calls_the_publisher(self):                                 # a failure in it cannot reach the trading loop: nothing imports it
        users = {p.name for p in (ROOT / "aitrader").glob("*.py") if "dashpub" in p.read_text(encoding="utf-8")}
        self.assertEqual(users, {"dashpub.py", "__main__.py"})

    def test_a_tick_takes_no_engine_lock(self):                                            # another process holds news_engine.lock and news_exits.lock under flock
        room(); self.assertIsNone(self.pub().prepare()[1]["skip"])

    def test_the_calendar_is_read_once(self):
        with mock.patch.object(journal, "ROOT", self.tmp):                                 # no config.json there
            self.assertFalse(dashpub.pin_calendar())
        self.assertTrue(dashpub.pin_calendar())
        with mock.patch.object(journal, "ROOT", self.tmp):
            self.assertEqual(journal.session_hours(date(2026, 11, 27)), ((9, 30), (13, 0)))

class Cli(Pubs):
    def test_dry_run_prints_sizes_and_sends_nothing(self):
        room(); out = json.loads(self.run_main("--dry-run"))
        self.assertEqual((out["skip"], out["rows"]["pos"], out["bytes"] > 0), (None, 2, True))
        self.assertLessEqual({"state_ms", "quotes_ms", "total_ms", "rss_kb", "trimmed"}, set(out))

    def test_claim_writes_the_marker(self):
        self.run_main("--claim"); self.assertEqual(set(journal.load_json("dash_writer.json")), {"at", "writer"})
```

- [ ] Run `-p 'test_dash_publish.py' -k Prepare` and `-k Cli`. Expected: `ImportError: cannot import name 'dashpub' from 'aitrader'`.
- [ ] Write `aitrader/dashpub.py` as above and register the command.
- [ ] Run both classes: 15 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/dashpub.py ai-trader/aitrader/__main__.py ai-trader/tests/test_dash_publish.py`; message `feat(ai-trader): the dashboard publisher builds, cleans and fits one snapshot and can write only its own files`.

### Task 8: Quote rounds and the yield to the engine's stop quotes

**Kind:** BUILD. **Spec:** 3.3 (symbols, the call, a failed symbol, the yield), 3.2 (the pace's interval, the tick deadline).

**Files:** Modify `aitrader/dashpub.py`, `tests/helpers/no_dash.py` (one line: `dashpub._get`), `tests/test_dash_publish.py`.

**Interfaces:** Consumes Task 7, `quotes.read`, `data.CHART_URL`, `data.UA`. Produces:

```python
class QuoteFail(Exception): kind: str                  # "429" | "timeout" | "other"; it carries no text
def _get(sym: str, timeout: float) -> dict             # one requests.get of CHART_URL (range 5d, interval 1d), no retry; the reply's chart.result[0]; raises QuoteFail
def symbols() -> tuple[list[str], set[str]]            # (the held names of the three books and the stock benchmark, sorted; those of the crypto book)
Pub.quote_round(self, deadline: float | None = None) -> dict    # {"calls", "ok", "429", "timeouts", "cut"}; updates self.quotes
Pub.yield_reason(self) -> str | None                   # "stops_late" | "stops_missing" | "throttled" | None
Pub.quotes_due(self, mode: str, fresh: bool = False) -> bool
```

- `quote_round`: a pool of `quote_workers` threads that only call `_get(sym, quote_timeout_seconds)`; the replies are read in the calling thread with `quotes.read(res, <New York date>, journal.session_hours)` (no calendar for a crypto symbol). A symbol that fails keeps the quote it has, with that quote's own time; a name no longer held leaves the table. A call not started by `deadline` (a monotonic time) is not made and is counted in `cut`. `data._get_json` is not used (spec 3.3).
- `quotes_due(mode, fresh)`, in this order: false during a yield, whatever else holds (the engine's stop quotes come first); true for mode "once", and when `fresh` (the caller's word that this tick is the open push or the final push: spec 3.2 asks a new round for each, and a tick has no other way to know it is one of them); true when this process has made no round yet; else whether the last round started at least the interval minus `quote_slack_seconds` ago. The interval: `quote_seconds_ramp` (pace "ramp"), `quote_seconds` ("full"), `yield_seconds` ("slow") in session; `closed_quote_seconds` out of it.
- The yield, in session only (spec 3.3 item 3): (a) "stops_late": the heartbeat is younger than `engine_alive_seconds`, its `positions` is above 0, and its `stops_checked_at` is None or older than `yield_stops_age_seconds`; (b) "stops_missing": the newest `news_health.jsonl` row is younger than two `news.health_log_seconds` and its `stop_quotes_missing` is above 0; (c) "throttled": the publisher's last round had a 429, or timeouts on more than `yield_timeout_share` of its calls. A reason opens `yield_seconds` with no quote call; `pub["quote_state"]` is "yield" for as long, and pushes go on with the stored quotes.
- `--dry-run` (Task 7) gains its one quote round here, before the `prepare`, and reports the round's time as `quotes_ms`.

- [ ] Add to `Pubs`: `answers(**by_symbol)` installs a `dashpub._get` stand-in (per symbol a price, a `QuoteFail` kind, or seconds to sleep; every other symbol 100.0 stamped now) and keeps the symbols it was asked in `self.asked`; `refuse_quotes()` puts the refusing stand-in of `no_dash` back. From this task on `Pubs.setUp` calls `self.answers()`. The reason: code that is correct makes a quote round in `tick`, `once` and `--dry-run` (a new `Pub` has made no round, so one is due), and `no_dash.Case` fails every test in which a refused call was reached, also when the publisher's own try/except caught it. So the refusal is what a test asks for, not what it gets. Then class `Rounds(Pubs)`:

```python
    def test_the_symbols_are_the_held_names_and_the_benchmark_only(self):
        room(); self.assertEqual(dashpub.symbols(), (["AAPL", "BTC-USD", "MSFT", "MU", "SPY"], {"BTC-USD"}))     # no ^VIX, no shadow-only name, no coin that is not held

    def test_a_failed_symbol_keeps_its_last_quote_with_its_own_time(self):
        room(); p = self.pub(); self.answers(MSFT=390.0); p.quote_round(); first = p.quotes["MSFT"]
        self.answers(MSFT="timeout"); out = p.quote_round()
        self.assertEqual((p.quotes["MSFT"], out["timeouts"], out["ok"], out["calls"]), (first, 1, 4, 5))

    def test_a_round_is_cut_at_the_deadline(self):                 # quote_workers 1, every call sleeps 0.2 s, the deadline 0.3 s away
        self.assertEqual((out["cut"] >= 3, set(p.quotes)), (True, before))

    def test_when_a_round_is_due(self):                            # a fake monotonic clock; seconds since the last round started
        self.assertEqual([self.due("ramp", 54), self.due("ramp", 55), self.due("full", 25), self.due("slow", 294), self.due("slow", 295),
                          self.due("ramp", 594, mode="closed"), self.due("ramp", 595, mode="closed"), self.due("ramp", 1, mode="once"),
                          self.due("ramp", 1, fresh=True), self.pub().quotes_due("session")],            # the open or final push; a Pub that has made no round
                         [False, True, True, False, True, False, True, True, True, True])

    def test_each_cause_of_a_yield_stops_the_quote_calls_for_300_s_and_pushes_go_on(self):
        for cause, arrange in (("stops_late", self.stops_121_s_old), ("stops_missing", self.health_row_with_a_missing_stop_quote), ("throttled", self.a_round_with_a_429)):
            room(); p = self.pub(); arrange(p)
            self.assertEqual((p.yield_reason(), p.quotes_due("session"), p.quotes_due("session", fresh=True), p.quotes_due("once")), (cause, False, False, False), cause)
            self.assertEqual(rows_of(json.loads(p.prepare()[0]), "stat")[0]["quote_state"], "yield")
            self.mono += 301; self.assertTrue(p.quotes_due("session"), cause)
        self.assertEqual(self.timeouts_on(1, of=5), None); self.assertEqual(self.timeouts_on(2, of=5), "throttled")    # 0.2 is under the share of 0.25, 0.4 is over

    def test_no_yield_with_nothing_held_with_a_dead_engine_or_out_of_session(self):
        self.assertEqual([self.reason(positions=0), self.reason(heartbeat_age=181), self.reason(at=ny("2026-11-10T18:00"))], [None, None, None])

    def test_with_a_quote_table_a_build_makes_no_network_call(self):            # dashboard._chart and dashpub._get are the refusing stand-ins
        room(); self.refuse_quotes(); self.pub().prepare(); self.assertEqual(no_dash.TRIPPED, [])

    def test_dry_run_makes_one_quote_round_and_times_it(self):
        room(); out = json.loads(self.run_main("--dry-run"))
        self.assertEqual((sorted(self.asked), out["quotes_ms"] is not None, out["skip"]), (["AAPL", "BTC-USD", "MSFT", "MU", "SPY"], True, None))
```

- [ ] Run `-k Rounds`. Expected: `AttributeError: module 'aitrader.dashpub' has no attribute 'symbols'`.
- [ ] Implement (the round of `--dry-run` too); add `dashpub._get = refuse("dashpub._get")` to `no_dash.py` and `self.answers()` to `Pubs.setUp`.
- [ ] Run `-k Rounds`: 8 tests, `OK`. Whole suite: `OK` (Task 7's `Prepare` and `Cli` among them: they now run beside the default stand-in).
- [ ] Commit: `git add ai-trader/aitrader/dashpub.py ai-trader/tests/helpers/no_dash.py ai-trader/tests/test_dash_publish.py`; message `feat(ai-trader): the publisher's own quote rounds, with a deadline and a yield to the engine's stop quotes`.

### Task 9: The push: `--once`, what each answer means, who may publish

**Kind:** BUILD. **Spec:** 3.1 (`--once`, exit codes 0, 5, 78), 3.2 (tick steps 7-8), 3.7 (the POST, failures, the marker, the variable, the heartbeat file), 4 (the floor).

**Files:** Modify `aitrader/dashpub.py`, `tests/helpers/no_dash.py` (`dashpub._post`), `tests/helpers/engine_child.py` (only if its tripwire has no name yet), `tests/test_dash_publish.py`. Create `tests/helpers/dash_child.py`.

**Interfaces:** Consumes Tasks 7-8; `helpers.no_phone.clean_env`; the tripwire of `engine_child.py` (S-Task 3). Produces:

```python
PLACEHOLDER = "set-by-the-network-proxy"     # the apikey header as the machine sends it; the proxy puts the key in its place (spec 3.7, 6)
RPC = "/rest/v1/rpc/publish_snapshot"
class PushFail(Exception): kind: str          # "timeout" | "connect" | "other"; it carries no text
def _post(url: str, body: bytes, connect_s: float, read_s: float) -> tuple[int, str]   # (status, the reply's "message" when the body is a JSON object, else "")
Pub.tick(self, mode: str = "session", last: bool = False, fresh: bool = False) -> dict   # never raises: a quote round when quotes_due(mode, fresh), prepare, one POST, the heartbeat
Pub.period(self, in_session: bool) -> float   # session_seconds or closed_seconds; after backoff_after_fails failures in a row backoff_seconds[0], [1], then backoff_max_seconds
def once() -> int
```

- The request: POST `os.environ[<url_env>] + RPC`, body `{"p_id":"snapshot","p_payload":<the text>}`, headers `apikey: PLACEHOLDER` and `Content-Type: application/json`, timeouts (`connect_timeout_seconds`, `push_timeout_seconds`), no `Authorization` header, no retry. `tick` returns `{"pushed", "skip", "status", "fail", "seq", "bytes", "trimmed", "push_ms"}`.
- One round per push (spec 3.3), and the tick makes it: no caller makes a quote round before a tick. A tick's deadline is its start + `tick_deadline_seconds`, and for mode "once" its start + `once_deadline_seconds`: the quote round is cut there (`quote_round(deadline)`), and in mode "once" the POST's two timeouts are cut to what is left of it.
- What an answer means. 204: success; `seq` moves; the failure count and `missed` go to 0. A 400 whose message is exactly "too soon" (Review Focus 2): another writer was there first; in the loop `note("push", "foreign_writer", 400)`, `fail` "too soon", no back-off count and no degraded set; in `--once` it counts as done. Any other 400: the payload was refused (`note("push", "refused", 400)`); the next ticks send `fit(rows, d, degraded=True)`, and the full set is tried again when the text of its `news`, `plan` and `tape` rows differs from the refused one's (a hash kept in memory) or `degraded_retry_seconds` after the refusal. Everything else is a failure by its kind alone (`PushFail.kind`, or "http" with the status): one `note("push", kind, status)`, the count goes up, the next tick is the retry. No reply body is stored or printed; only the one fixed word is compared.
- `state/dash_publish.json`, written after every tick through `journal.save_json`: `{"at", "pid", "parent", "seq", "pace", "mode", "period_s", "last_ok", "fails", "last_error"}`. A new `Pub` takes `seq` from that file when it can be read, else 0 (Review Focus 1). Nothing takes the file's existence for a live loop: a loop is alive when the lock is held.
- Who may publish, checked by `once` and by the loop before anything else when they push: no variable: print `dash-publish: not configured (AITRADER_DASH_URL is not set)`, `note("start", "not_configured")`, return 78 (loop) or 0 (`--once`). No `state/dash_writer.json`: print `dash-publish: not the publishing checkout`, 78 or 0. `--no-push` and `--dry-run` ask for neither.
- `once()`: the two checks; then the lock is tried only to see whether a loop holds it, and let go at once (a slot's push must never keep a starting loop out). Held, and the stored heartbeat is younger than two of its `period_s`: print `dash-publish: the loop is publishing (seq <n>)`, return 0. Held and older: `note("once", "loop_stale")`, print `dash-publish: loop_stale pid <pid> age <n> s; kill allowed: <yes|no>` and return 5; "yes" when the age is over `hang_seconds` + `stale_term_extra_seconds` and `/proc/<pid>/cmdline` names `dash-publish` (the check is `dashpub._is_publisher(pid)`). Free: `pin_calendar`, `guard_writes`, then `tick("once")` and nothing else (the tick makes its one quote round and its one POST inside `once_deadline_seconds`); print `dash-publish: pushed seq <n>, <bytes> bytes, <ms> ms` or `dash-publish: not pushed (<skip or fail word>)`; return 0.
- `tests/helpers/dash_child.py --state-dir DIR --scenario FILE [dash-publish options]`, in this order: (1) puts `ai-trader/` and `ai-trader/tests/` at the front of `sys.path`, from its own `__file__` (it is also started from a plain shell, Tasks 16 and 18, where no `PYTHONPATH` is set and a script's own folder is all Python adds); (2) points `journal.STATE` at DIR; (3) replaces `dashpub._get` by the scenario, `dashpub.git_paths` by a function that returns `DIR/git/MERGE_HEAD`, `DIR/git/rebase-merge`, `DIR/git/rebase-apply` and `DIR/git/index.lock`, and `dashboard._commit` by one that returns "abc1234"; (4) installs the tripwire of `engine_child.py`, writing to `DIR/child.tripwire` (a call to a host other than 127.0.0.1, or a `git` or `claude` child, ends the process with 97; if S-Task 3 left the tripwire inline, this task gives it the name `tripwire(sent_file)` there, with no change of behaviour); (5) `sys.exit(aitrader.__main__.main(["dash-publish", *options]))`. Step 3 comes before step 4 for a reason: the publisher asks git twice at every start (the four paths and the commit), so behind the bare tripwire every child would leave with 97 where its test expects 0, 3, 4 or 78. With the two stand-ins the tripwire still catches any other `git` or `claude` child, and a child test never reads the clone's own git state (a test that wants "git_busy" creates one of the four files). Scenario keys, all optional: `prices` (`{sym: price | "429" | "timeout" | null}`; default 100.0, stamped now), `quote_delay_s` (0), `config` (keys merged over `dashboard_push`, so a test scales the seconds), `starts_at` (a New York time: the publisher's clock and `dashboard.datetime` run from there), `hang_build` (the n-th build never returns), `raise_in_build` (a text to raise from the build), `report` (print `os.nice(0)` and the oom score at the start).
- In the test module, `Row`: an `http.server` on 127.0.0.1 port 0, in a thread; `.answers` (a list of `(status, body)` played in order, the last repeats; "hang" never answers), `.seen` (`[(path, headers, body)]`), `.url` = `http://127.0.0.1:<port>/SECRETPATH`. `Procs`: a temporary state directory with fixture A, `child(*options, scenario=None, url=None) -> Popen` (`env=no_phone.clean_env(...)`, `AITRADER_DASH_URL=url` when given, text pipes), `beat()`, `wait_for(fn, timeout=5)`, `dead(pid)`, `files()` (every file under the state and cache directories); `tearDown` kills what is left and fails when a `.tripwire` file exists.

- [ ] Add the tests. `Push(Pubs)`: `posts([...])` installs a `dashpub._post` stand-in that plays answers (a pair, or a `PushFail`) and keeps `(url, body)` in `self.posted`; `go()` sets the variable for the test and writes the marker:

```python
class Push(Pubs):
    def test_a_204_is_a_push_and_the_heartbeat_says_so(self):
        room(); self.go(); self.posts([(204, "")])
        out = self.pub().tick(); hb = journal.load_json("dash_publish.json"); url, body = self.posted[0]
        self.assertEqual((out["pushed"], out["status"], out["seq"], hb["seq"], hb["fails"], hb["pid"]), (True, 204, 1, 1, 0, os.getpid()))
        self.assertEqual((url.endswith("/rest/v1/rpc/publish_snapshot"), json.loads(body)["p_id"], rows_of(json.loads(body)["p_payload"], "stat")[0]["seq"]), (True, "snapshot", 1))

    def test_seq_goes_on_from_the_stored_heartbeat(self):                # Review Focus 1
        room(); self.go(); self.posts([(204, "")])
        journal.save_json("dash_publish.json", {"at": "2026-11-09T21:00:00+00:00", "seq": 41, "pid": 1})
        self.assertEqual(self.pub().tick()["seq"], 42)
        (self.tmp / "dash_publish.json").write_text("{half"); self.assertEqual(self.pub().tick()["seq"], 1)

    def test_no_retry_inside_a_tick_and_the_back_off_after_five_failures(self):
        room(); self.go(); self.posts([(500, "")] * 7 + [(204, "")]); p = self.pub()
        self.assertEqual([(p.tick()["pushed"], p.period(True)) for _ in range(8)], [(False, 30)] * 4 + [(False, 60), (False, 120), (False, 300), (True, 30)])
        self.assertEqual((len(self.posted), [(r["where"], r["error"], r["status"]) for r in journal.read("dash_errors.jsonl")]), (8, [("push", "http", 500)]))

    def test_every_answer_that_is_not_a_204_is_a_failure_by_its_kind(self):      # Review Focus 2: a rotated key, a paused project, a gateway page
        for answer, fail in ((dashpub.PushFail("timeout"), "timeout"), (dashpub.PushFail("connect"), "connect"), ((429, ""), "http"), ((401, ""), "http"),
                             ((403, "x"), "http"), ((404, ""), "http"), ((503, ""), "http")):
            room(); self.go(); self.posts([answer]); out = self.pub().tick()
            self.assertEqual((out["pushed"], out["fail"]), (False, fail))

    def test_a_tick_never_raises(self):                                 # the build, the quote call and the POST each raise RuntimeError in turn
        for where in ("build", "get", "post"):
            room(); self.go(); self.breaks(where); out = self.pub().tick()
            self.assertEqual((out["pushed"], bool(out["skip"] or out["fail"])), (False, True), where)

    def test_a_refused_payload_is_followed_by_the_degraded_set(self):
        room(); self.go(); self.posts([(400, "invalid input syntax for type json"), (204, "")]); p = self.pub(); p.tick(); p.tick()
        self.assertEqual(({r["t"] for r in self.payload(1)}, rows_of(self.payload(1), "stat")[0]["trimmed"]), ({"stat", "money", "acct", "pos", "npos", "cpos"}, ["degraded"]))
        p.tick(); self.assertNotIn("news", {r["t"] for r in self.payload(2)})                 # nothing changed and 300 s have not passed: still degraded
        self.clock += 301; p.tick(); self.assertIn("news", {r["t"] for r in self.payload(3)})
        # and, in a second run: a new headline right after the refusal brings the full set back at the next tick

    def test_too_soon_is_a_foreign_writer_in_the_loop_and_done_in_once(self):      # Review Focus 2
        room(); self.go(); self.posts([(400, "too soon"), (204, "")]); p = self.pub(); out = p.tick(); p.tick()
        self.assertEqual((out["pushed"], out["fail"], p.period(True), [r["error"] for r in journal.read("dash_errors.jsonl")]), (False, "too soon", 30, ["foreign_writer"]))
        self.assertIn("news", {r["t"] for r in self.payload(1)})                              # not degraded
        self.posts([(400, "too soon")]); self.assertEqual((dashpub.once(), len(journal.read("dash_errors.jsonl"))), (0, 1))

    def test_who_may_publish(self):
        room(); self.posts([(204, "")])
        self.assertEqual((dashpub.once(), self.printed[-1], self.posted), (0, "dash-publish: not configured (AITRADER_DASH_URL is not set)", []))
        self.set_url(); self.assertEqual((dashpub.once(), self.printed[-1], self.posted), (0, "dash-publish: not the publishing checkout", []))
        self.assertEqual([r["error"] for r in journal.read("dash_errors.jsonl")], ["not_configured"])
        self.assertIsNone(json.loads(self.run_main("--dry-run"))["skip"])                     # needs neither

    def test_once_makes_one_quote_round_and_one_post(self):               # spec 3.3: one round per push, and the tick makes it
        room(); self.go(); self.posts([(204, "")])
        self.assertEqual((dashpub.once(), sorted(self.asked), len(self.posted)), (0, ["AAPL", "BTC-USD", "MSFT", "MU", "SPY"], 1))

    def test_once_beside_a_loop(self):                                   # the lock is held by a helper process whose command line names dash-publish
        room(); self.go(); self.posts([(204, "")])
        self.heartbeat(age=10, period_s=30); self.assertEqual((dashpub.once(), self.posted), (0, []))
        self.heartbeat(age=61, period_s=30); self.assertEqual((dashpub.once(), self.printed[-1].endswith("kill allowed: no")), (5, True))
        self.heartbeat(age=181, period_s=30); self.assertEqual((dashpub.once(), self.printed[-1].endswith("kill allowed: yes")), (5, True))
        self.assertEqual([r["error"] for r in journal.read("dash_errors.jsonl")], ["loop_stale"])
        self.free_lock(); self.heartbeat(age=86400, period_s=30); self.assertEqual((dashpub.once(), len(self.posted)), (0, 1))   # Review Focus 1: yesterday's file, no loop

    def test_an_unstubbed_push_raises(self):
        with self.assertRaises(AssertionError):
            dashpub._post("http://127.0.0.1:9", b"{}", 1, 1)
        self.assertEqual(no_dash.TRIPPED, ["dashpub._post"]); no_dash.TRIPPED.clear()

class Wire(Procs):
    def test_the_request_is_the_one_the_database_accepted(self):
        self.row.answers = [(204, "")]; p = self.child("--claim"); p.wait(timeout=20)
        rc = self.child("--once", url=self.row.url).wait(timeout=30); path, headers, body = self.row.seen[0]
        self.assertEqual((rc, path, headers["apikey"], [k for k in headers if k.lower() == "authorization"], set(json.loads(body))),
                         (0, "/SECRETPATH/rest/v1/rpc/publish_snapshot", "set-by-the-network-proxy", [], {"p_id", "p_payload"}))

    def test_the_address_reaches_no_file_and_no_output(self):            # Review Focus 5
        for case in ([(500, "<html>")], ["hang"], [(400, '{"message": "bad ' + self.row.url + '"}')], "closed port", "the build raises the address"):
            out, err = self.once_with(case)                              # --once, once_deadline_seconds 2; the last case sets raise_in_build to the address
            for text in (out, err, *(f.read_text(errors="replace") for f in self.files())):
                self.assertNotIn("SECRETPATH", text); self.assertNotIn("127.0.0.1", text)

    def test_once_gives_up_inside_its_deadline(self):                    # once_deadline_seconds 2, the row never answers
        self.assertEqual((rc, elapsed < 5), (0, True))
```

- [ ] Run `-k Push` and `-k Wire`. Expected: `AttributeError: type object 'Pub' has no attribute 'tick'`.
- [ ] Implement; write `dash_child.py`; add `dashpub._post = refuse("dashpub._post")` to `no_dash.py`.
- [ ] Run both: 14 tests, `OK`, and no `child.tripwire` file was left by a child. Whole suite: `OK` (the supervisor's `test_supervise.py` and `test_news_supervised.py` among them, if the tripwire got its name here).
- [ ] Commit: `git add ai-trader/aitrader/dashpub.py ai-trader/tests/helpers ai-trader/tests/test_dash_publish.py`; message `feat(ai-trader): dash-publish --once pushes one snapshot; every answer of the database has one meaning and the address never reaches a file`.

### Task 10: The loop: the grid, the day's one-off pushes, the lock, the watchdog, health rows

**Kind:** BUILD. **Spec:** 3.1 (the loop, `--pace`, `--no-push`, `--supervised`, exit codes 0, 3, 4), 3.2, 3.7 (the try/except, nice, the oom score, the health journal).

**Files:** Modify `aitrader/dashpub.py`, `tests/helpers/no_dash.py` (`launch_prefix`), `tests/test_dash_publish.py`.

**Interfaces:** Consumes Tasks 7-9. Produces:

```python
def due(prev_ny: datetime, now_ny: datetime, until: str, d: dict) -> list[str]   # the one-off pushes whose moment lies in (prev, now]: "open", "final", "last"
def loop(pub: Pub, until: str, supervised: int | None = None, *, sleep=time.sleep) -> int
def run(a: argparse.Namespace) -> int          # the checks of Task 9, the lock, nice, the oom score, the watchdog thread, loop(); returns 0, 3, 4 or 78
# tests/helpers/no_dash.py - the one shape of the publisher's start line: proven here, written into news-watch.md by Task 15
def launch_prefix(commands: str, guard: bool = False, folder: str = "ai-trader") -> str
#   "(" + ('[ -n "$AITRADER_DASH_URL" ] && ' if guard else "") + "cd " + folder + " && mkdir -p .cache"
#       + " && exec >> .cache/dash_publish.log 2>&1 < /dev/null && " + commands + " &); "
```

- Why the start line has this shape (Review Focus 1). `&` puts the whole AND list into a background subshell, and a redirection written on the last command binds to that command only. bash then keeps the background subshell, with the launcher's pipe still open in it, for as long as the loop lives (measured for this plan on bash 5.2 with `sleep` in the loop's place: the pipe closed after the child's 4 s, not after the launcher's 1 s; dash let go at once). So the list redirects itself first: `exec >> .cache/dash_publish.log 2>&1 < /dev/null` is a step of the list, before the command, and from that step on no process of the list has the launcher's pipe. Every step is joined by `&&`: a missing folder or an unset variable ends the list and starts nothing. `$$` inside the list is still the launching shell's pid.
- `due`: "open" at the session's open + `open_push_delay_seconds`, "final" at its close + `final_push_delay_seconds`, "last" at `until`; nothing on a day with no session but "last".
- The grid. The first tick runs at once. In every slice of `sleep_slice_seconds` the loop asks, in this order: is the parent gone (return 0, no last push); is a one-off due (run it; the next grid tick is one period after it); has the grid time come (run a tick, then move the grid time forward by whole periods until it is ahead of now: a tick that overran drops the ticks it missed, nothing queues). When the period gets shorter than the time left to the grid time (the open, the end of a back-off), the grid time becomes now + the period. No push of this process starts sooner than `min_push_gap_seconds` after the one before.
- The mode is "session" while the NYSE session is open, else "closed". The "open" push is `tick("session", fresh=True)` and the "final" push is `tick("closed", fresh=True)`: `fresh` is how a tick learns that it is one of the two and owes a new quote round (Task 8). "last" is `tick(mode, last=True)` (its `period_s` is None, so `expect_next_by` is that of a `--once` push), and the loop returns 0 after it. Every other tick is `tick(mode)`. A tick's quote round is cut at the tick's own deadline (Task 9).
- `--supervised PID`: the loop is gone within one slice of `/proc/<PID>` going. Without the flag it watches its own parent pid. A PID that is not alive at the start: one printed line, 0.
- The lock: `state/dash_publisher.lock` under `flock`, rewritten with `{"pid", "started_at"}`. When it is held the start tries again every slice for `lock_wait_seconds` (Review Focus 1: at a handover the earlier loop needs up to a slice to see that its parent is gone), then prints `dash-publish: another publisher holds the lock (pid <pid>)` and returns 3. No handler is installed for SIGTERM: the default ends the process at once and frees the lock, also while a tick hangs.
- The watchdog: a daemon thread; when no tick has finished for `hang_seconds` it prints `dash-publish: no tick finished for <n> s, leaving (exit 4)` and calls `os._exit(4)`.
- At the start of `run`: `os.nice(nice)`; `oom_score_adj` written to `/proc/self/oom_score_adj`, a refusal ignored; `pin_calendar()` false: print `dash-publish: the calendar in config.json cannot be read`, `note("start", "no_calendar")`, return 4; `guard_writes()`.
- `state/dash_health.jsonl`: one appended row per `health_log_seconds`: `{"at", "window_s", "pace", "push", "pushes_ok", "pushes_failed", "build_ms_median", "build_ms_max", "quotes_ms_median", "quotes_ms_max", "push_ms_median", "push_ms_max", "push_gap_max_s", "bytes_max", "quote_calls", "quote_429", "quote_timeouts", "quote_age_s_median", "quote_age_s_max", "yields", "skips": {word: count}}`. The two `quote_age_s` fields (each tick's `stat.quote_age_max_s`) are added to the spec's list so that the dry session itself measures the age of Yahoo's quotes (spec 3.8 b). With `--no-push` nothing is sent, every tick counts under `skips.no_push`, and the rows are written all the same.

- [ ] Add the tests. `Loop(Pubs)` runs `dashpub.loop` on a fake clock (`sleep` moves it; `Pub.tick` is replaced by a recorder that can be told how long a tick takes and keeps one dict per call in `self.ticks`: `mode`, `last`, `fresh`); times are New York. `Running(Procs)` adds: `QUICK` (a scenario config with `session_seconds` 0.2, `closed_seconds` 0.2, `sleep_slice_seconds` 0.05, `lock_wait_seconds` 1); `started(*options, scenario)` (a `child` whose first heartbeat has been waited for); `child_line(*options, scenario=QUICK)` (the shell text of the command `child` would start: `sys.executable`, the helper, the state directory, the scenario file and the options, every path absolute and quoted, `$$` left bare); `work` (a temporary folder that stands for `ai-trader/` in a start line); `env` (`no_phone.clean_env()`); `holders(popen)` (the pids, other than the launcher's and the test's own, that have the pipe behind `/proc/<popen.pid>/fd/1` among the links of their `/proc/<pid>/fd`):

```python
class Schedule(no_dash.Case):
    def test_the_one_off_pushes_of_a_day(self):
        at = lambda day, s: ny(f"{day}T{s}")
        tue = [dashpub.due(at("2026-11-10", a), at("2026-11-10", b), "16:05", D) for a, b in
               (("09:29:59", "09:30:02"), ("09:30:02", "09:30:03"), ("16:01:29", "16:01:30"), ("16:04:59", "16:05:00"), ("10:00:00", "10:00:30"))]
        self.assertEqual(tue, [[], ["open"], ["final"], ["last"], []])
        early = [dashpub.due(at("2026-11-27", a), at("2026-11-27", b), "16:05", D) for a, b in (("13:01:29", "13:01:30"), ("16:01:29", "16:01:30"))]
        self.assertEqual((early, dashpub.due(at("2026-11-14", "09:29:00"), at("2026-11-14", "09:31:00"), "16:05", D)), ([["final"], []], []))   # Review Focus 3; a Saturday

class Loop(Pubs):
    def test_ticks_sit_on_a_30_s_grid_and_an_overrun_drops_the_missed_ones(self):      # started 10:00:00; the third tick takes 70 s
        self.assertEqual(self.seconds[:6], [0, 30, 60, 150, 180, 210])

    def test_the_open_push_comes_three_seconds_after_the_open_and_the_grid_goes_on_from_it(self):   # started 09:29:40
        self.assertEqual((self.times[:4], [t["fresh"] for t in self.ticks[:4]]), (["09:29:40", "09:30:03", "09:30:33", "09:31:03"], [False, True, False, False]))

    def test_the_close_the_final_push_the_closed_pace_and_the_last_push(self):           # started 15:59:50, --until 16:05
        self.assertEqual((self.times, [t["last"] for t in self.ticks][-1], rc), (["15:59:50", "16:00:20", "16:01:30", "16:03:30", "16:05:00"], True, 0))
        self.assertEqual([(t["mode"], t["fresh"]) for t in self.ticks], [("session", False), ("closed", False), ("closed", True), ("closed", False), ("closed", False)])

    def test_an_early_close_day_is_on_the_closed_pace_from_13_00(self):                  # Review Focus 3: 2026-11-27, started 12:59:50, --until 16:05
        self.assertEqual((self.times[:4], set(self.gaps[3:-1]), self.times[-1]), (["12:59:50", "13:00:20", "13:01:30", "13:03:30"], {120}, "16:05:00"))

    def test_two_pushes_are_never_closer_than_6_s(self):                                 # started 09:59:30, --until 10:00:02
        self.assertEqual(self.times, ["09:59:30", "10:00:00", "10:00:06"])

    def test_the_back_off_pace_and_back(self):                                           # in session; ticks 1-7 fail, tick 8 succeeds
        self.assertEqual(self.gaps[:9], [30, 30, 30, 30, 60, 120, 300, 30, 30])

    def test_a_supervised_loop_follows_its_parent_within_a_slice_and_pushes_no_last_row(self):   # the watched pid is gone 45 s in
        self.assertEqual((rc, self.seconds, any(t["last"] for t in self.ticks)), (0, [0, 30], False))

    def test_a_health_row_every_300_s_with_no_push_too(self):                            # push=False, 11 minutes of session
        rows = journal.read("dash_health.jsonl")
        self.assertEqual((len(rows), rows[0]["push"], rows[0]["pushes_ok"], rows[0]["skips"]["no_push"] > 0, self.posted), (2, False, 0, True, []))
        self.assertLessEqual({"window_s", "pace", "build_ms_median", "quotes_ms_max", "push_gap_max_s", "bytes_max", "quote_calls", "quote_429",
                              "quote_timeouts", "quote_age_s_median", "quote_age_s_max", "yields"}, set(rows[0]))

class Running(Procs):
    def test_a_hung_tick_ends_the_process_with_4_and_frees_the_lock(self):               # hang_seconds 1, hang_build 2
        p = self.child("--no-push", "--until", "23:59", scenario={**QUICK, "hang_build": 2})
        self.assertEqual((p.wait(timeout=10), "leaving (exit 4)" in p.stdout.read()), (4, True))
        self.assertIsNone(self.started("--no-push", "--until", "23:59", scenario=QUICK).poll())      # a new loop takes the lock and beats

    def test_a_second_loop_leaves_with_3_and_names_the_holder(self):
        self.assertEqual((b.wait(timeout=5), f"pid {a.pid}" in b.stdout.read()), (3, True))

    def test_a_loop_started_while_the_earlier_one_is_ending_takes_over(self):            # Review Focus 1: A is supervised by a helper process; the helper is killed and B starts at once
        self.wait_for(lambda: self.beat().get("pid") == b.pid); self.assertTrue(self.dead(a.pid))

    def test_started_by_the_slot_files_line_only_the_launcher_has_the_launchers_pipe(self):   # Review Focus 1
        loop = self.child_line("--no-push", "--until", "23:59", "--supervised", "$$")
        for shell in [s for s in ("bash", "sh") if shutil.which(s)]:                     # the Bash tool's shell, and the system's
            for commands, guard in ((loop, False), (self.child_line("--claim") + " && " + loop, True)):   # the shapes of steps 1a and 1b
                line = no_dash.launch_prefix(commands, guard=guard, folder=str(self.work)) + "exec sleep 600"
                sh = subprocess.Popen([shell, "-c", line], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env={**self.env, "AITRADER_DASH_URL": self.row.url})
                self.wait_for(lambda: self.beat().get("parent") == sh.pid, timeout=15)    # the loop is up (two Python starts in the 1b shape) and follows the launching shell's pid
                self.assertEqual(self.holders(sh), [], (shell, guard))                    # while it lives, nothing but the launcher has that pipe
                sh.kill(); sh.wait(); self.wait_for(lambda: self.dead(self.beat()["pid"]), timeout=3)   # and it goes when the pid it watches goes
        self.assertEqual(self.row.seen, [])                                               # --no-push: the address in the environment was never called

    def test_a_loop_that_may_not_publish_leaves_with_78(self):                           # no variable; then the variable and no marker
        self.assertEqual([self.child("--until", "23:59").wait(timeout=10), self.child("--until", "23:59", url=self.row.url).wait(timeout=10)], [78, 78])
        self.assertEqual(self.row.seen, [])

    def test_nice_and_the_oom_score(self):                                               # scenario "report"
        self.assertEqual(reported["nice"], 10)                                           # the oom score is 500 where the file takes it, else what it was
```

- [ ] Run `-k Schedule`, `-k Loop`, `-k Running`. Expected: `AttributeError: module 'aitrader.dashpub' has no attribute 'due'`.
- [ ] Implement `due`, `loop` and `run`; add `launch_prefix` to `no_dash.py`.
- [ ] Run the three: 15 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/dashpub.py ai-trader/tests/helpers/no_dash.py ai-trader/tests/test_dash_publish.py`; message `feat(ai-trader): the dashboard publisher loop: a 30-second grid, the day's one-off pushes, a lock, a watchdog and health rows`.

### Task 11: The pass numbers of target 10 as a command

**Kind:** BUILD. **Spec:** 3.3 item 4 (the pass numbers), 1 (target 10: "measured, pass or fail"), 7 (checked in every session of step 1).

**Files:** Modify `aitrader/dashpub.py` (`pass_numbers`, the `--pass` form), `tests/test_dash_publish.py`.

**Interfaces:** Consumes the rows of `state/dash_health.jsonl` (Task 10) and `state/news_health.jsonl` (the engine's, Baseline record). Produces:

```python
def pass_numbers(day: str, base_day: str, cfg: dict) -> dict
# {"day", "base_day", "publisher": {"calls", "429", "timeouts", "timeout_share"},
#  "engine": {"stop_quotes_missing": [day, base], "stop_gap_max_s": [day, base], "step_s_median": [day, base]}, "fails": [...], "pass": bool}
```

- `python3 -m aitrader dash-publish --pass DAY BASE_DAY` prints that as JSON and exits 0 on a pass, 1 otherwise. It reads only; it is run in the room clone on pushed state.
- A day's rows are those whose `at` lies inside that day's NYSE session. Pass, all of: the publisher's 429s are 0; its timeouts are at most `pass_timeout_share` of its calls; the engine's sum of `stop_quotes_missing` is not above the base day's; its largest `stop_gap_max_s` is not above the base day's by more than `news.poll_seconds`; the median of its `step_s_median` is not above the base day's times `pass_step_ratio`. `fails` names each number that failed. A day with no rows in a file is a fail named `no_rows:<file>:<day>`: silence is not a pass.

- [ ] Add class `PassNumbers(Pubs)`; `health(day, **engine)` and `pub_health(day, **publisher)` write rows inside that day's session:

```python
    def test_a_clean_day_passes_and_each_number_can_fail_alone(self):
        base = dict(stop_quotes_missing=1, stop_gap_max_s=41.0, step_s_median=4.0)
        self.health("2026-11-09", **base); self.health("2026-11-10", stop_quotes_missing=1, stop_gap_max_s=61.0, step_s_median=4.8)
        self.pub_health("2026-11-10", quote_calls=1000, quote_429=0, quote_timeouts=10)
        self.assertEqual((self.report()["pass"], self.report()["fails"]), (True, []))
        for change, name in ((dict(quote_429=1), "quote_429"), (dict(quote_timeouts=11), "timeout_share")):
            self.assertEqual(self.report(pub=change)["fails"], [name])
        for change, name in ((dict(stop_quotes_missing=2), "stop_quotes_missing"), (dict(stop_gap_max_s=61.1), "stop_gap_max_s"), (dict(step_s_median=4.81), "step_s_median")):
            self.assertEqual(self.report(engine=change)["fails"], [name])

    def test_a_day_with_no_rows_is_a_fail_and_rows_outside_the_session_do_not_count(self):
        self.assertEqual((self.report()["pass"], self.report()["fails"]), (False, ["no_rows:dash_health.jsonl:2026-11-10", "no_rows:news_health.jsonl:2026-11-10", "no_rows:news_health.jsonl:2026-11-09"]))
        self.assertEqual(self.rc("--pass", "2026-11-10", "2026-11-09"), 1)
```

- [ ] Run `-k PassNumbers`. Expected: `AttributeError: module 'aitrader.dashpub' has no attribute 'pass_numbers'`.
- [ ] Implement.
- [ ] Run `-k PassNumbers`: 2 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/dashpub.py ai-trader/tests/test_dash_publish.py`; message `feat(ai-trader): dash-publish --pass compares a session's engine health with the last one before the publisher ran`.

### Task 12: Time on the air from the uptime log

**Kind:** BUILD. It waits for S-Task 16 (`aitrader/uptime.py`) to be on the live branch; until then `on_air_src` is "health" (Task 6) and nothing else waits for this task. **Spec:** 3.4 (`on_air_src` "uptime": "the function `uptime-report` uses, once `state/uptime.jsonl` exists").

**Files:** Modify `aitrader/dashboard.py`, `tests/test_dashboard_books.py`.

**Interfaces:** Consumes `uptime.day_report(rows, day, cfg, health=None) -> dict` (its `session_s` and `unprotected_s`) and `supervise.read_rows(path)` (S-Tasks 10, 16; both modules are standard library only). Produces no new name: whenever `uptime.jsonl` exists in the stock state directory, `on_air_src` is "uptime" and `stat.on_air_s` = the session's seconds so far minus the unprotected seconds so far, the latter being the report's `unprotected_s` minus the session's seconds still ahead (the report counts the time after the last row as unprotected), never below 0; else the "health" numbers as before.

- [ ] Add to class `Stat`:

```python
    def test_with_an_uptime_log_the_on_air_numbers_come_from_it(self):     # marks from 14:30 UTC to T, one exit at 16:00:00 and its `up` at 16:03:54
        s = self.one("stat")
        self.assertEqual((s["on_air_s"], s["session_s"], s["on_air_pct"], s["on_air_src"]), (19566, 19800, 0.9882, "uptime"))

    def test_the_engine_hours_end_where_the_parent_stops(self):
        cfg = dashboard.load_config(); self.assertEqual(cfg["dashboard_push"]["engine_hours_ny"][1], cfg["supervisor"]["until_ny"])
```

- [ ] Run `-k Stat`. Expected: `AssertionError`: the row says "health".
- [ ] Implement (the import of `uptime` sits inside the branch; `aitrader.dashboard` must still load no `notify`, `news_live` or `broker`: Task 7's import test covers it).
- [ ] Run `-k Stat`: `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/dashboard.py ai-trader/tests/test_dashboard_books.py`; message `feat(ai-trader): the dashboard's time on the air is read from the supervisor's uptime log when there is one`.
- [ ] Landing (OPS, the main session). This task has no rollout step of its own, and its commit must not ride unseen on a page landing. It reaches the live branch in the first evening landing after its commit: with that evening's task when one lands then (Task 16, 18, 19, 22 or 24), else alone. Either way that landing is at least a **code landing** (gate steps 1-3: the diff holds `aitrader/dashboard.py`), and the critic's written PASS names this commit. Files of the owner's list in the diff: none.

### Task 13: The page harness in the repository

**Kind:** BUILD. It needs Tasks 6 and 7 and nothing of Tasks 8-12. **Spec:** 7 ("Harness"; step 1a's check that the old page still draws the new file), 8 (builder B's files).

**Files:** Create `tests/page/run.js`, `tests/page/cases/old_page.js`, `tests/page/fixtures/pinned_live.json`, `tests/page/fixtures/pinned_file.json`, `tests/page/fixtures/headlines.json`, `tests/test_page.py`; `tests/page/vendor/d3.min.js` only if the harness has no local d3. Modify `THIRD_PARTY.md`.

**Interfaces:** Consumes `dashboard.build`, `dashboard.build_now`, `dashpub.clean`, `no_phone.clean_env`. Produces the harness that Tasks 20, 21 and 23 write their cases for:

```js
// node tests/page/run.js [--only <part of a name>] [--page <an index.html>]   (default page: dashboard/index.html)
//   one line per case, "PASS <name>" or "FAIL <name>: <why>"; then "OK <n> cases" (exit 0) or "FAILED <k> of <n>" (exit 1)
// a file under tests/page/cases/ exports a list of {name, width = 400, run: async (p) => {}}; p is a fresh page:
p.file(rows, status = "ok")        // dataset "snapshot": rows (or null) and status "ok" | "loading" | "error"
p.live(answer, status = "ok")      // dataset "live": the connector's raw answer (or null) and status "ok" | "loading" | "error" | "connect"; the page's own loader runs on it
p.answer({updated, now, payload})  // -> a raw answer in the saved real shape around one row: id "snapshot", updated_epoch, now_epoch, payload
p.open(hash = "")                  // loads the page; before it, p.at(epoch) sets the clock
p.at(epoch) / p.pass(seconds)      // set, or move, Date.now and performance.now together and fire the timers that came due
p.wall(seconds)                    // moves Date.now alone (a phone clock that is off, a clock set back)
p.css(seconds)                     // moves every CSS animation's currentTime; p.timers(false) makes setTimeout and setInterval dead
p.visible(bool)                    // document.visibilityState and its event
p.calls(id)                        // how many times the page has called dash.refresh(id)
p.text(sel) / p.texts(sel) / p.shown(sel) / p.cls(sel) / p.count(sel) / p.box(sel) / p.tap(sel) / p.remove(sel)
p.overflow()                       // [{sel, px}]: every table wrapper that is wider than its card
p.errors / p.outside / p.external  // console and page errors; writes of text or children outside a [data-draw] element; requests that were not file:
```

- The runner fails a case whose `p.errors`, `p.outside` or `p.external` is not empty. `p.outside` comes from a `MutationObserver`: the page type's own check sees only writes made while scripts, `onData` and drawings run (spec 7).
- The `dash` stand-in, with the page type's contract as its reference pages give it: `loader(id, {fn})` (called with `{answer, call, args, read}`; the answer taken out of a wrapper whose only key is `result`), `calc`, `draw(name, fn)` and `draw(name, {mount, update, unmount})` (`mount` once per element and again after a throw, `update` at every call, `unmount` when the element leaves or a call throws), `draw(name)`, `onData` (before the drawings), `data(id)` -> `{status, data}`, `refresh(id)` (counted; answered when the case calls `p.live` or `p.file` again), `setLink`, `colors`. Nothing under `hidden` loads or draws. One object `STUB` at the top holds what the probe will settle, pessimistic until then (spec 7): `{rerunUnmarked: false, drawOnUnhide: false}`.
- Fixtures are read with `JSON.parse`, so a `NaN` in a file fails as it does on the platform. Widths: 360, 400, 1280.
- If Task 1 handed over the scratch harness of 2026-11-10, start from it; the list above is what it must do either way. d3: the copy that harness used, else version 7 (the page uses `d3.pointer` and `selection.join`) placed once under `tests/page/vendor/`; which build the page type itself ships is not known. `THIRD_PARTY.md` gains "Page test tools": Node and Playwright from the machine image (not vendored; a test tool, not a dependency of the bot; the image finds Playwright through `NODE_PATH` and its browsers through `PLAYWRIGHT_BROWSERS_PATH`, and the harness needs both set), and the d3 copy with its licence (ISC) if one is added.
- The pinned state (spec 7): 15 positions, one of them BTC-USD at 104000.0 with a loss of 12000.0 dollars, 8 trades, 2 plans, and the 8 headlines of `headlines.json` (copied once from `state/news_scores.jsonl`: headline, symbol and score only; the longest stored one, 205 characters, among them). `tests/test_page.py` builds it in a temporary directory with the clock frozen at 2026-11-10 20:00 UTC (the `T` of Task 5, so `stat.sessions` starts with that Tuesday's session); `pinned()` returns the two texts, `dashboard.dump(dashpub.clean(build_now(...), text_max_chars))` and `dashboard.dump(build())`, built with `dashboard._writer` and `dashboard._commit` replaced by fixed answers ("00000000" and None): both fields differ from machine to machine and from commit to commit, and a fixture that held the real ones would match on the implementer's clone only. `--write` writes those two texts to `pinned_live.json` and `pinned_file.json` through the same `pinned()`. Run it from `ai-trader/` as `PYTHONPATH=. python3 tests/test_page.py --write`: started as a script the file has only `tests/` on its path, and `import aitrader` would fail.

- [ ] Write `tests/test_page.py`:

```python
from helpers import no_dash  # noqa: F401
class Fixtures(no_dash.Case):
    def test_the_pinned_fixtures_are_what_the_builder_makes_today(self):
        live, file = pinned()                                      # the two texts, built in a temporary state directory at a frozen time, writer and code pinned
        self.assertEqual((live, file), ((FIX / "pinned_live.json").read_text(encoding="utf-8"), (FIX / "pinned_file.json").read_text(encoding="utf-8")))

    def test_every_pinned_row_has_exactly_the_first_tab_fields(self):
        rows = json.loads((FIX / "pinned_live.json").read_text(encoding="utf-8"))
        self.assertEqual([tuple(r) for r in rows], [dashboard.FIRST_TAB[r["t"]] for r in rows])
        self.assertEqual([(r["writer"], r["code"]) for r in rows if r["t"] == "stat"], [("00000000", None)])   # nothing of this machine or this commit is in the file
        count = lambda tags: len([r for r in rows if r["t"] in tags])
        self.assertEqual((count(("pos", "npos", "cpos")), count(("tape",)), count(("plan",)), count(("news",)), max(len(r["headline"]) for r in rows if r["t"] == "news")), (15, 8, 2, 8, 205))

NODE_ENV = {k: os.environ[k] for k in ("NODE_PATH", "PLAYWRIGHT_BROWSERS_PATH") if k in os.environ}   # where the image keeps Playwright and its browsers; clean_env() alone drops both

class Harness(no_dash.Case):
    @unittest.skipUnless(shutil.which("node"), "node is not installed: run `node tests/page/run.js` where it is")
    def test_the_page_harness_passes(self):
        cp = subprocess.run(["node", "tests/page/run.js"], cwd=ROOT, capture_output=True, text=True, env=no_phone.clean_env(**NODE_ENV), timeout=600)
        self.assertEqual((cp.returncode, cp.stdout.strip().splitlines()[-1].split()[0]), (0, "OK"), cp.stdout[-2000:])
```

- [ ] Write `tests/page/cases/old_page.js`, against the page as it is before Task 20:

```js
// withoutNew(rows), in run.js: the rows without the tags money, acct, tape, plan and stat, and without the fields this plan adds
// (pos, npos, cpos: key, book, day_pct, pnl_usd, price_epoch, stale; news: key, ts_epoch, mark): the file as the builder wrote it before
module.exports = [1280, 400].map((width) => ({name: `today's page draws the new hourly file as it draws the old one (${width})`, width, run: async (p) => {
  const neu = fixture("pinned_file.json"), old = withoutNew(neu);
  p.file(old); await p.open(); const before = await p.texts("[data-draw]");
  p.file(neu); await p.open(); assert.deepEqual(await p.texts("[data-draw]"), before);
}}));
```

- [ ] Run `python3 -m unittest discover -s tests -p 'test_page.py' -v`. Expected: `FileNotFoundError` for `pinned_live.json`, and the harness test fails with `Cannot find module`.
- [ ] Write the harness, run `PYTHONPATH=. python3 tests/test_page.py --write`, and read the two written files once: they hold fixture numbers and public headlines only.
- [ ] Run `node tests/page/run.js`: `OK 2 cases`. Run the test file: 3 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/tests/page ai-trader/tests/test_page.py ai-trader/THIRD_PARTY.md`; message `test(ai-trader): the dashboard page harness moves into the repository, with fixtures the builder itself writes`.

### Task 14: Land the publisher's code, and measure it

**Kind:** OPS - the owner's main chat session. **Spec:** 7 step 1a (the landing), 3.8 (measurement a), 8.

- [ ] After 16:05 New York, in the room clone, with Tasks 3-11 and 13 committed: fetch and merge. This is a **config landing** (gate steps 1-4). Files of the owner's list in the diff: none of the seven modules; `config.json` only by the new block `dashboard_push`, outside `risk`, `signals` and `costs`. The critic is asked for exactly that statement and for the search that shows no trading path reads the block (`grep -rn dashboard_push aitrader/`: `dashpub.py` and `dashboard.py` only). The adversarial review reads `dashpub.py`, `quotes.py`, the diff of `dashboard.py` and `dash_child.py` against the second line of Global Constraints (what the publisher may touch). Proof: the suite's last line, the harness's `OK` line, the critic's PASS, the `differences` list of the two sweeps, kept in the session log.
- [ ] `git push origin HEAD:<branch>`. Nothing starts the publisher yet: the dashboard is as it was.
- [ ] Measurement (a) of spec 3.8, after the next close, once the trader session's checkout holds the landing: a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is to run `(cd ai-trader && for i in $(seq 20); do python3 -m aitrader dash-publish --dry-run; done)` and answer with its output only (one subshell, so that the trader session's shell is not left inside `ai-trader/` for its next turn); read it back with `list_events`. From the 20 lines, the medians of `state_ms`, `quotes_ms`, `total_ms`, and the largest `bytes` and `rss_kb`, go into "Baseline record". Pass: `state_ms` at most 1000 and `total_ms` at most 10,000 (target 7), `bytes` at most 60,000 (target 9).
- [ ] Only if the median `state_ms` is over 1000: Task 26 is built now and landed here, on the next evening: a code landing (gate steps 1-3; files of the owner's list in the diff: none), `git push origin HEAD:<branch>`. Then the 20 dry runs are made again on it, the same way: the median `state_ms` is at most 1000 before Task 16 starts.
- [ ] Undo: `git revert` the landing's commits in the room clone and land the revert.

### Task 15: The slot lines and the SKILL section

**Kind:** BUILD. It waits for S-Task 20 (the parent launches the engine; every scheduled prompt's text is its slot file at the pushed commit). **Spec:** 3.1 ("Who starts the loop", the push at the end of every slot), 3.7 (who may publish), 4 (the rule about `payload`), 5.1 (what the hourly task may write), 8 (prompts and SKILL change at steps 1a, 1b and 4).

**Files:** Modify `skills/trader/slots/news-watch.md`, `dashboard.md`, `open.md`, `midday.md`, `close.md`, `weekly.md` and each `crypto-*.md` that exists there (S-Task 18 made one only for a crypto task bound to the trader session), `skills/trader/SKILL.md` (a new section 3ג, and one sentence of 3ב), `tests/test_slot_files.py` (class `DashLines`).

**Interfaces:** Consumes `supervise --status`'s `launch.command` (S-Task 14), the slot files and their sync block (S-Tasks 18-19), `dash-publish` (Tasks 7-10), `no_dash.launch_prefix` (Task 10). Produces the prompt texts that Tasks 16, 18 and 19 put on the tasks.

- The spec's interim start line was written for the bare engine (`... & exec python3 -m aitrader news-live`). From S-Task 20 on the tracked command is the supervisor's parent, so the line becomes a prefix of that command and names the pid to follow: `$$` is the shell that `exec` turns into the parent. In `news-watch.md`, in the step for action `launch`: "the command to launch is this prefix followed by `launch.command` exactly as `--status` printed it, as ONE tracked background command". The prefix is `no_dash.launch_prefix(...)`, the shape Task 10 proved under bash and sh: its background list redirects its own three streams before it starts anything, so nothing of it has the launch command's pipe (Review Focus 1). It is never a second tracked command. Nothing restarts the publisher between launches: that is the supervisor's job after its spec is amended (Task 25).
- The slot files move through these steps; `STEP` in the test says where they are:

| Step | The prefix in `news-watch.md` | The last line of duty in every other slot file |
|------|-------------------------------|------------------------------------------------|
| 0 | none: the undo of step 1a, a forward edit (Global Constraints). No slot file starts the loop | none |
| 1a | `LAUNCH["1a"]` below: no guard, no claim, `--no-push` | none |
| 1b | `LAUNCH["1b"]`: the guard on the variable, `--claim`, pushes at the ramp pace | `END` below, and the sentence "whatever it prints the turn goes on; on exit 5 do what SKILL section 3ג says and nothing more" |
| 1c | as 1b with `--pace full` | as 1b |

- `END` sits after the slot's own duty, before the slot's `slot-done <slot>` line when S-Task 24 has added one, and before the closing sync block, so that the journal rows it may write travel with that turn's state commit. In `dashboard.md` it comes right after the upload. `news-watch.md` gets no `END`: beside a live loop it would only leave. `END` is one subshell: the Bash tool keeps the working directory from one call to the next, and the receipt and the sync block that follow are written from the repository root.
- `dashboard.md` also gains, at step 1a: "this task writes only the file of dataset `snapshot`: never `datasets/live`, never `index.html`".
- SKILL section 3ג, in Hebrew like the rest of the file, says: what `dash-publish` is (reads state, writes one row for the screen, cannot trade; paper money); no session ever selects `payload` or text out of it, and what may be read instead (`updated_at`, sizes, counts, `jsonb_typeof`, fields cast to numeric); no session runs `printenv` or `env` for the address; the publisher's output is in `.cache/dash_publish.log`; exit codes 0, 3, 4, 5 and 78 with what the session does: nothing for 0, 3 and 78; 4 is told at the next slot's summary; 5: when the printed line ends with `kill allowed: yes`, `kill <pid>` (the pid of that line) and nothing more; the hourly task writes only the snapshot file.
- The one `&`. Since S-Task 19, section 3ב tells the session to launch the parent "as a tracked background command; never `nohup`, `setsid` or `&`", and the prefix holds an `&`. Two orders that contradict each other would leave an unattended watchdog turn to choose, and a turn that drops the prefix publishes nothing. So the rule and its exception are written in one place. The sentence of 3ב keeps its ban and gains, in the same paragraph: the one exception is the `&` inside the dashboard publisher's prefix in `news-watch.md` (section 3ג, `dash-publish`); the parent itself is still never started with `&`. Section 3ג says the same from its side: the prefix is copied from `news-watch.md` character for character, in front of `launch.command`, and is never dropped, shortened or run by itself.

- [ ] Add to `tests/test_slot_files.py`:

```python
from helpers import no_dash                   # with the file's other imports
CFG = json.loads((SLOTS.parent.parent.parent / "config.json").read_text(encoding="utf-8"))
STEP = "1a"                                   # "0", "1a", "1b" or "1c"; Tasks 16, 18 and 19 move it in the same commit as the files
LOOP = "python3 -m aitrader dash-publish --until 16:05 --pace ramp --supervised $$"
LAUNCH = {"1a": no_dash.launch_prefix(LOOP.replace("--supervised", "--no-push --supervised")),
          "1b": no_dash.launch_prefix("python3 -m aitrader dash-publish --claim && " + LOOP, guard=True)}
LAUNCH["1c"] = LAUNCH["1b"].replace("--pace ramp", "--pace full")
END = "(cd ai-trader && python3 -m aitrader dash-publish --claim && python3 -m aitrader dash-publish --once)"

class DashLines(unittest.TestCase):
    def test_the_start_lines_as_the_trader_session_will_run_them(self):      # the whole text, for the reviewer; the shape is Task 10's (Review Focus 1)
        self.assertEqual(LAUNCH["1a"], "(cd ai-trader && mkdir -p .cache && exec >> .cache/dash_publish.log 2>&1 < /dev/null"
                                       " && python3 -m aitrader dash-publish --until 16:05 --pace ramp --no-push --supervised $$ &); ")
        self.assertEqual(LAUNCH["1b"], '([ -n "$AITRADER_DASH_URL" ] && cd ai-trader && mkdir -p .cache && exec >> .cache/dash_publish.log 2>&1 < /dev/null'
                                       " && python3 -m aitrader dash-publish --claim && python3 -m aitrader dash-publish --until 16:05 --pace ramp --supervised $$ &); ")
        for line in LAUNCH.values():
            self.assertIn(f'--until {CFG["supervisor"]["until_ny"]} ', line)

    def test_the_watchdog_starts_the_publisher_inside_the_parents_launch_and_nowhere_else(self):
        t = (SLOTS / "news-watch.md").read_text(encoding="utf-8")
        n = 0 if STEP == "0" else 1                                           # step "0": no slot file starts the loop
        self.assertEqual((t.count(LAUNCH.get(STEP, "dash-publish --until")), t.count("dash-publish --until")), (n, n))
        for f in SLOTS.glob("*.md"):
            if f.name != "news-watch.md":
                self.assertNotIn("dash-publish --until", f.read_text(encoding="utf-8"), f.name)

    def test_from_step_1b_on_every_other_slot_ends_with_one_push_before_its_receipt_and_its_sync(self):
        for f in SLOTS.glob("*.md"):
            if f.name in ("news-watch.md", "watcher.md"):
                continue
            t = f.read_text(encoding="utf-8")
            self.assertEqual(t.count(END), 0 if STEP in ("0", "1a") else 1, f.name)
            self.assertEqual(t.count("dash-publish --once"), t.count(END), f.name)      # never the bare form, which would leave the turn inside ai-trader/
            for later in ("slot-done " + f.stem, "git merge --no-edit origin/"):
                if END in t and later in t:
                    self.assertLess(t.index(END), t.rindex(later), f.name)

    def test_the_hourly_task_knows_what_it_may_write_and_the_skill_has_the_rules(self):
        self.assertIn("datasets/live", (SLOTS / "dashboard.md").read_text(encoding="utf-8"))
        skill = (SLOTS.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual([m for m in ("payload", "printenv", "kill allowed: yes", "dash-publish --once", ".cache/dash_publish.log") if m not in skill], [])
        ban = [p for p in skill.split("\n\n") if "setsid" in p]              # the paragraph of 3ב that bans nohup, setsid and &
        self.assertTrue(ban and all("dash-publish" in p and "3ג" in p for p in ban))   # names its one exception where the rule is
```

- [ ] Run `-p 'test_slot_files.py' -k DashLines`. Expected: `test_the_watchdog_starts_the_publisher_inside_the_parents_launch_and_nowhere_else` fails with `(0, 0) != (1, 1)`, and the SKILL test fails on its markers.
- [ ] Edit the files for step 1a.
- [ ] Run the file: the supervisor's tests and these 4, `OK` (its leak test reads the new lines too). Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/skills/trader/slots ai-trader/skills/trader/SKILL.md ai-trader/tests/test_slot_files.py`; message `docs(ai-trader): the watchdog prompt starts the dashboard publisher inside the parent's launch, without a push; SKILL rules for the row`.

### Task 16: Rollout step 1a: one dry session

**Kind:** OPS - the owner's main chat session; the owner answers one question. **Spec:** 7 step 1a, 3.3 (items 1 and 4), 3.8 (measurement b).

- [ ] Preconditions: Task 14 has landed and passed its measurement (with Task 26 landed too, when Task 14 called for it); S-Task 20 has landed and its prompts are on the tasks; Task 15 is committed at `STEP` "1a".
- [ ] The launch-line drill, after the close, in this session, on a scratch directory `<dir>` (an absolute path) with `s.json` = `{"config": {"session_seconds": 5, "closed_seconds": 5}}`. The line is `launch_prefix` with the child helper in the publisher's place, so it is the 1a line's own shape. Launch as a tracked background command: `(cd ai-trader && mkdir -p .cache && exec >> .cache/dash_publish.log 2>&1 < /dev/null && python3 tests/helpers/dash_child.py --state-dir <dir> --scenario <dir>/s.json --no-push --until 23:59 --supervised $$ &); exec sleep 600`. Twenty seconds later `<dir>/dash_publish.json` exists, its `pid` is alive, and its `parent` is a pid whose `/proc/<pid>/cmdline` holds `sleep`. Then `TaskStop`: the publisher's pid is gone within 5 s. Second run, the one that shows who holds the pipe: `s.json` also sets `"sleep_slice_seconds": 30` (the publisher now notices its parent's end up to 30 s late), the line ends with `exec sleep 20`, and nothing is stopped: the task is reported ended within 5 s of the 20 while the publisher's pid is still alive, and that pid is gone within 35 s more. A task that is reported ended only when the publisher goes: the line holds the pipe under this harness. A fail stops this task and goes back to Tasks 10 and 15.
- [ ] Land Task 15: a code landing (gate steps 1-3). Files of the owner's list in the diff: none.
- [ ] Ask the owner, one message: "להפעיל את משדר לוח המחוונים ליום מסחר אחד של ניסיון? הוא רק קורא ומודד: לא כותב למסד הנתונים ולא נוגע במסחר. א: כן (המלצה). ב: לא עכשיו. כסף נייר." On yes: `list_triggers`; the prompts of the two `news-watch` tasks and of the dashboard task must equal their files at the commit before this landing, else stop (someone changed one). `update_trigger` the three from their files at the pushed commit; `list_triggers` again and `diff` each prompt against its file: no difference (once S-Task 23 has landed: `python3 -m aitrader slots-check <the saved reply>` prints `"differences": []`).
- [ ] One full dry session. Proofs that evening, in the room clone after fetch and merge:
  - `state/dash_health.jsonl` holds at least 70 rows of that session, each with `push` false and `pushes_ok` 0.
  - `python3 -m aitrader dash-publish --pass <that day> <the last full session before it>` prints `"pass": true` (target 10).
  - `python3 -m aitrader uptime-report --day <that day>`: every `handover_s` is under 60 (Review Focus 1).
  - From the health rows: the median of `build_ms_median` at most 1000 and of build plus quotes at most 10,000 (target 7); the session's median and largest `quote_age_s_max` go into "Baseline record" (spec 3.8 b: the age of Yahoo's quotes, measured for the first time), and with them the `yields` of the first two rows after 09:30 (item 7 of "Where the plan decides": whether the open push met a yield).
  - `node tests/page/run.js --only "today's page"`: both cases `PASS`.
- [ ] A pass number that fails: the pace goes back one step. `--pace ramp` becomes `--pace slow` in `LOOP` (the test) and in `news-watch.md` (a BUILD edit with its test, landed and put on the tasks as above), one more dry session, and open question 3 is asked.
- [ ] Undo (spec: "the old prompt line"), as a forward edit: a BUILD edit sets `STEP` to "0" (the prefix leaves `news-watch.md` as that file stands on the day; nothing else in any slot file moves), `-k DashLines` red, edit, green; a code landing; then `update_trigger` the `news-watch` tasks from their files at that pushed commit. Never the files of an older commit, and no `git revert` of Task 15's commit (Global Constraints: the supervisor may have landed lines in the same files since).

### Task 17: The probe on the owner's phone, rollout step 1.5

**Kind:** OPS - the owner's main chat session, with the owner for two minutes. It can run any time after Task 1; Tasks 20, 21 and 23 wait for it. **Spec:** 7 (step 1.5, "Probe"), 6 item 4, 10.1.

- [ ] Extend the probe page that already ran a connector call on the owner's phone to print P1-P10 exactly as spec 7 lists them. The probe page is its own artifact and its source stays in this session's scratch folder: its dataset names the project, so it never enters the repository.
- [ ] The owner's part, one message, the spec's sentence: "פתח את הקישור, חכה שתי דקות, נעל את המסך לחצי דקה, חזור לדף ושלח לי צילום מסך".
- [ ] Write the ten answers into the spec (a new last section "Probe answers, step 1.5") and into "Probe record" below. Save P10's answer byte for byte as `tests/page/fixtures/live_answer.txt` after reading it for anything that names the project (the scan of Task 3 reads it too). `git add` the spec, this plan and the fixture; message `trader: the phone probe's answers for the live trading room`; fetch, merge, push. Spec 5.3-5.7 are frozen from here.
- [ ] What each answer decides:

| Probe | The answer the design hopes for | Any other answer |
|-------|---------------------------------|------------------|
| P1: the 1-second tick and the 30-second timer fire unattended, also after a screen lock | at least 100 ticks and 3 timers in the two minutes | the page is built as written all the same: the button, the absolute times and the CSS alarm are the design's own fallback (spec 10.1), and at step 2 the owner is told in plain words that the counter does not run by itself |
| P2: a CSS animation changes a stored element with no script | yes | the two animations are still built; if P1 failed too, nothing on the page turns red by itself, and the owner is told so in plain words (spec 10.1) |
| P3: every `dash.refresh` under `updates: "viewed"` makes a new database read | distinct `now()` values | stop before Task 20: spec 5.6 no longer holds and goes back to its author. This plan designs no other way |
| P4, P5: drawings run when `hidden` comes off; a drawing reruns for a dataset its element is not marked with | recorded | `STUB.drawOnUnhide` and `STUB.rerunUnmarked` in the harness take the answers (Task 20's first step); the page calls `dash.draw(name)` itself under either |
| P6: a calc with a failed input | recorded | nothing: the page has no such calc (spec 5.3) |
| P7: the platform covers a marked element whose source failed, or asks to connect when nothing is marked | no | the first tab's elements are stored unmarked and only the badge is marked `now_stat` (spec 5.3); Task 20 builds that form |
| P8: answers of 60,000 and 200,000 bytes are read | both | `max_payload_bytes` goes under the largest size that was read: a config landing before Task 18 |
| P9: a file holding `NaN` | recorded | nothing: `dump` writes none (Task 5) |
| P10: the type and whole text of `answer` | the fixture | - |

### Task 18: Rollout step 1b: the form, the card, pushes at the ramp pace

**Kind:** OPS - the owner's main chat session; the owner fills one form, approves one card and answers one question. **Spec:** 6 (items 1-3), 7 step 1b, 3.5 (the size ratio), 4 (retention, traffic).

- [ ] Preconditions: Task 2 and Task 16 passed.
- [ ] Where the key and the variable will land, before any form or card is shown. `request_credential` saves on the environment of the session that calls it, and `update_environment` edits only the calling session's own environment; spec 6.3 wants both on the environment the trader session runs in. So: `get_session` on the trader session for its environment, then `get_environment` with that environment: the answer must say that it is the environment this session runs in. (No id is written anywhere.) If it says so, go on. If it does not, or `get_session` names no environment: stop, and ask the owner, one message: "המפתח והכתובת נשמרים רק בסביבה של הסשן שמבקש אותם, והצ'אט הזה רץ בסביבה אחרת מזו של הסוחר. א: להעביר את הצ'אט הזה לסביבה של הסוחר, באישור שלך, ואז להמשיך (המלצה). ב: לעצור כאן; לוח המחוונים נשאר שעתי. כסף נייר." On א: `switch_environment` to that environment (the tool's own approval card), the check again, and only then the form. A refused switch: stop, and tell him what the tool said. Saved anywhere else, the key and the variable would never reach the publisher, and the key would sit where it was not meant to.
- [ ] The write key, through the secure form, never through chat. In the message before the call: which secret (the project's key called "publishable"), for which host (the database project's own address), why, and the exact taps to find it on the project's API settings page as that page reads that day. Then `request_credential` with `host` = the project's host as the connector gives it in that turn (it is written nowhere), `header_name` "apikey", no prefix, `display_name` "dashboard write key (paper data)", and the form's sentence: "זה מאפשר לבוט לכתוב את השורה האחת של לוח המחוונים. זה למסך בלבד ולא יכול לסחור. כסף נייר." The environment is the one the step above confirmed: this session's own, which is the trader session's (the owner's answer to the supervisor's question 11 decides which one that is).
- [ ] One approval card for one variable: `get_environment`; one sentence in the message (the card adds the address of the dashboard's database to the trader's environment and nothing else); then `update_environment` with `set_environment_variables` `{"AITRADER_DASH_URL": <the project's address, from the connector in that turn>}`, `environment_name` and `applies_to` copied from `get_environment`. If he declines the form or the card, everything stays as it is and no second prompt is shown.
- [ ] The next trading morning the variable has reached the trader session: a one-time scheduled task bound to it, created on the owner's word, whose prompt is to run `[ -n "$AITRADER_DASH_URL" ] && echo set || echo missing` and answer with the word only. "missing": the machine has not been restored since the card; wait for the next morning.
- [ ] BUILD edit (an implementer subagent, the `git stash` ban in its prompt): `STEP` becomes "1b"; `news-watch.md` takes `LAUNCH["1b"]`; every other slot file bound to the trader session takes `END` and its sentence. Run `-k DashLines` red, edit, green; commit `git add ai-trader/skills/trader/slots ai-trader/tests/test_slot_files.py`, message `docs(ai-trader): the publisher pushes at the ramp pace and every slot ends with one push`. A crypto task bound to another session has no slot file and gets no line: its night decision reaches the screen with the trader session's next push, the owner gets one line about it, and `state/backlog.md` gets the item.
- [ ] The launch-line drill of Task 16 once more, now for the 1b line, before that line goes on a task: the same two runs with the guard and the claim in the line, and the variable given to that one command as a dead local address (`--no-push`: nothing is sent, and the helper's tripwire refuses every other host): `export AITRADER_DASH_URL=http://127.0.0.1:9; ([ -n "$AITRADER_DASH_URL" ] && cd ai-trader && mkdir -p .cache && exec >> .cache/dash_publish.log 2>&1 < /dev/null && python3 tests/helpers/dash_child.py --state-dir <dir> --scenario <dir>/s.json --claim && python3 tests/helpers/dash_child.py --state-dir <dir> --scenario <dir>/s.json --no-push --until 23:59 --supervised $$ &); exec sleep 600`. Same proofs as in Task 16, and `<dir>/dash_writer.json` exists. A third run on a new, empty `<dir>` with `unset AITRADER_DASH_URL; ` in place of the `export`: after 20 s that directory holds no `dash_publish.json` and no `dash_writer.json`. A fail goes back to Tasks 10 and 15, and nothing is put on a task.
- [ ] Land it: a code landing (gate steps 1-3; files of the owner's list in the diff: none). The owner's yes, one message: "להתחיל לשדר ללוח המחוונים? מהרגע הזה השורה במסד הנתונים מתעדכנת, והדף עדיין לא קורא אותה. א: כן (המלצה). ב: לא עכשיו. כסף נייר." Then `update_trigger` every changed task from its file, and `list_triggers` with no difference.
- [ ] The first real push, read from the trader session's transcript after its next slot: the line `dash-publish: pushed seq 1, <n> bytes, <ms> ms`. Then through the connector, numbers only: the two time expressions of the page's own query (`select extract(epoch from updated_at)::float8, extract(epoch from now())::float8 from public.trader_live where id = 'snapshot'`: two numbers, the second not below the first; spec 5.1), and `select updated_at, pg_column_size(payload) as stored, octet_length(payload::text) as text_len, jsonb_array_length(payload) as n from public.trader_live where id = 'snapshot'`. A `not pushed (http)` with status 401 or 403 in `dash_errors.jsonl`: the key did not reach the request; read the `environment.secrets` documentation page and the form's result before anything is changed, and if the placeholder header turns out to stand in the proxy's way, that is a BUILD edit of `_post` with its test, through a code landing.
- [ ] One full pushed session, and the five reads of spec 7 ("at five times of day"). Only this session holds the connector and nothing wakes it, so a read is made when the owner writes to it. That morning, one message: "היום הבוט משדר ללוח המחוונים בפעם הראשונה. אני יכול לבדוק את השורה במסד רק כשאתה כותב לי. א: אכתוב לך מילה חמש פעמים היום, בערך ב-<the Israel times of 09:35, 11:00, 13:00, 15:00 and 16:10 New York on that day> (המלצה). ב: לא היום; נבדוק ביום המסחר הבא. כסף נייר." At each word of his: the second query above with `extract(epoch from now() - updated_at)::float8 as age_s` added (numbers only), written into the log with the read's own time. Pass: five reads, at least three of them inside the session and one after 16:02 New York, and `age_s` at most 60 at every read inside the session (the database's clock on both sides, not this machine's). The exact minutes do not matter: the time between two reads is covered by `push_gap_max_s`, below. Fewer reads, or ב: that evening's proofs from the files are still made, the reads move to the next trading day he can, and Task 19 waits for them.
- [ ] Proofs that evening from `dash_health.jsonl`: build and quote times as in Task 16 (target 7), 95% of `push_ms_max` under 3000 (target 8), `bytes_max` at most 60,000 (target 9), `push_gap_max_s` under 75 outside the back-off; `dash-publish --pass` again: `"pass": true`; `dash_errors.jsonl` has no `foreign_writer` row. The next morning, at this session's first turn, the same query once more: `updated_at` is later than the night's last hourly rebuild and the crypto slots that ran in the trader session (target 2). A `foreign_writer` row, then or on any later day: the upgrade path of spec 4 (the public right revoked, a secret key in the same form) is put to the owner in one message.
- [ ] The size limits, from the measured ratio `stored / text_len` (spec 3.5 leaves the rule open): `max_payload_bytes` stays 60,000; the database's limit becomes 60,000 x the ratio x 1.25, rounded up to the next 10,000, and no migration is made when that is 100,000. A changed limit is one migration by this session, with rows 2 and 6 of Task 2's table again.
- [ ] After the first full day: `select pg_total_relation_size('public.trader_live')` into the log, next to the traffic spec 4 computes (about 830 pushes and 6 MB a day), and the project's usage as the connector shows it; a quota the free plan would pass within a month is told to the owner in one line.
- [ ] Undo (spec: "`--no-push` back, or the old prompt lines"), as a forward edit: `STEP` back to "1a" (the `--no-push` line; `END` leaves the other slot files), or to "0", on the files as they stand; landed; `update_trigger` from the pushed files. Never the prompts of an older commit (Global Constraints).

### Task 19: Rollout step 1c: the many-symbols form, then the full pace

**Kind:** OPS - the owner's main chat session; one BUILD edit inside, and one conditional BUILD task. **Spec:** 7 step 1c, 3.3 (item 2, the form "one request for many symbols"), 9 question 3.

- [ ] Precondition: one clean pushed session at the ramp pace (Task 18's proofs).
- [ ] Try the form once: a one-time scheduled task bound to the trader session, created on the owner's word, after the close, whose prompt is one `python3 -c` line that sends a single GET for the held symbols to the same host's quote address that takes a `symbols` list, with the bot's own `UA` header and a 5-second timeout, and prints the status code, the reply's length and, when it is JSON, its top-level keys and the keys of the first quote; nothing else. No sign-in is attempted.
- [ ] If the status is 200 and each quote carries a price, the quote's own time and the previous close: a conditional BUILD task, written into this plan then with the saved reply as its fixture (prices only): `quotes.read_many(reply: dict, today: date, session_hours) -> dict[str, Quote]` with the same rules and the same tests as `read`, `dashpub._get_many(symbols, timeout) -> dict`, and one round = one call when `dashboard_push.quote_form` is "many" (a new key, default "single"); it lands as a config landing. Any other answer: the per-symbol calls stay, and the answer goes into "Baseline record".
- [ ] BUILD edit: `STEP` becomes "1c" and `news-watch.md` takes `LAUNCH["1c"]`; `-k DashLines` red, edit, green; commit message `docs(ai-trader): the publisher's quotes at the full pace`. Land it (a code landing; files of the owner's list in the diff: none), the owner's yes in one message ("להעביר את מחירי לוח המחוונים לקצב המלא, כל 30 שניות? עבר יום נקי בקצב האיטי. א: כן (המלצה). ב: להישאר בדקה. כסף נייר."), `update_trigger` the two `news-watch` tasks.
- [ ] One full session at the full pace; `dash-publish --pass <that day> <the base day of Task 16>`: `"pass": true`.
- [ ] A fail: `STEP` back to "1b" through the same landing, and open question 3 is asked, one message, the spec's sentence with its two options and the recommendation (א).
- [ ] Undo (spec): `--pace ramp`: `STEP` back to "1b", the same forward way (Global Constraints).

### Task 20: The page: the `live` loader, the one pick, the money block

**Kind:** BUILD. It waits for Task 17 (the probe's answers). **Spec:** 5.1 (the dataset the page expects), 5.2, 5.3, 5.8 (block 1), 5.9, 5.10 (rows "Money", "Loader errors"), 5.11, 9 question 1 (default א: the accounts table is built).

**Files:** Modify `dashboard/index.html`, `tests/page/run.js` (`STUB` takes P4, P5 and P7 from "Probe record"; `p.answer` wraps its row in `fixtures/live_answer.txt`; `p.loadError(id)` returns the message the page's loader threw). Create `tests/page/cases/loader.js`, `tests/page/cases/pick.js`.

**Interfaces:** Consumes the harness (Task 13), the row fields of `FIRST_TAB` (Tasks 5-6), "Probe record". Produces, in the page's second script (the one closure, as today):

```js
const K = {STALE_S: 120, PRICE_OLD_S: 180, BEAT_S: 180, P_IN: 30, P_OUT: 300, OPEN_EXTRA: 5, FILE_BAD: 300, FILE_OK: 1800, WAIT: 20, OPEN_GRACE: 120, LEAD: 60,
           TAIL: 120, LATE: 600, SKEW: 60, DEADMAN: 5, REQ: 20, FAIL_CAP: 300, ROWS: 100, CELL: 300, SEC_MAX: 120, MIN_MAX: 7200, HEADS: 8};   // spec 5.11, one place
const TABLES = {money: ['money'], accounts: ['acct'], book: ['pos', 'npos', 'cpos'], tape: ['tape'], plan: ['plan'], heads: ['news'], stat: ['stat']};
let current;                    // {source: 'live' | 'file' | null, rows, stat, seq, id}: chosen once per data change, in dash.onData, and nowhere else
function nowData(table)         // -> {status: 'ok' | 'loading' | 'error', data, known}, the two tables of spec 5.9; 'heads' is the first K.HEADS rows of its tag
// drawings: nkv (one value of a table's first row), nrows (a table body; a cell may hold two fields), npick (a stored sentence by a code or a flag)
```

and, in the first script, `dash.loader('live', ...)` and the seven calcs `now_stat`, `now_money`, `now_accounts`, `now_book`, `now_tape`, `now_plan`, `now_heads` over `live`, each the filter of its `TABLES` entry, titled with its block's heading from spec 5.10.

- The loader is the six steps of spec 5.2, using nothing outside itself; its four sentences are those of spec 5.10 ("Loader errors"): step 2 throws "אין בלוק נתונים בתשובה" followed by the first 200 characters of the answer, step 3 "התשובה אינה שורה אחת", step 4 "התוכן אינו רשימה" (not a list, over 2,000 rows, a row with no string `t`) or "חסרה שורת המצב או שהיא לא תקינה".
- The pick is spec 5.3, with `K.STALE_S` for its two "120 s". The page keeps the last good live rows in memory. When `current` changes identity (source, `seq`, or the file's time), `onData` calls `dash.draw(name)` for every first-tab drawing. `onData` also puts one of the classes `src-live`, `src-file`, `src-none` on the page's root element: a class is what a script may set outside a drawing, and the harness reads the choice there.
- `K.HEADS` (8) is added to the spec's constants: the tag `news` is both the 8 headlines of the first tab and the 60 of the hourly table, so when the file is shown the first tab takes the first 8. A harness case holds it equal to `dashboard_push.headlines_first`, as spec 5.11 does for the two 180s.
- The money block: `<section class="card now" id="money">`, stored right after `<header id="top">`, above the page as it is (spec 7 step 2). Its words are row "Money" of spec 5.10, character for character; the total is the big figure; the label is "היום (מניות)" when `day_is_today`, else the stored sentence with `day_date`; "שינוי יומי: אין בסיס להשוואה" when `day_usd` is null; the crypto line is hidden when `c_day_usd` is null; the stale line shows when `money.stale`. Under it the accounts table, three rows from `acct`: columns `name`, `equity`, `day_usd` with `day_pct`; its three headings are תיק · שווי · היום (words spec 5.10 already has; decided here). Every element is marked with its calc and, for a row, its `key`; if "Probe record" P7 says the platform covers a marked element whose source failed, they are stored unmarked (spec 5.3).
- `known` (spec 5.9) is false for a table that `stat.trimmed` names: "news" names `heads`, "plan" `plan`, "tape" `tape`, and "degraded" all three, so a degraded snapshot never reads as "no trades".
- States, by spec 5.9: loading = a skeleton on each figure; not known = "—" and the stored line "אין נתון בתמונת המצב הזו"; error = "—" and "הטעינה נכשלה". A number that arrives as text shows "—" (spec 5.11).

- [ ] Write the cases. `LIVE` and `FILE` are the two pinned fixtures; `T` = 1794340800; `A(over)` = `p.answer({updated: T - 10, now: T, payload: LIVE, ...over})`; `rows({stat: {...}, money: {...}})` returns `LIVE` with fields of the named rows replaced, and `stat(over)`, `money(over)` are its two short forms; `file(at, over)` returns `FILE` with its `stat.as_of_epoch` (and more) replaced:

```js
// cases/loader.js: load(name, answer, want) opens the page with FILE loaded and this answer for `live`
load("the saved real answer", A(), {src: "src-live", total: usd(LIVE.find((r) => r.t === "money").total_equity)});
load("a list of text items", items(A()), {src: "src-live"});
load("rows that arrive as objects", [{id: "snapshot", updated_epoch: T - 10, now_epoch: T, payload: LIVE}], {src: "src-live"});
load("the payload as a string", A({payload: JSON.stringify(LIVE)}), {src: "src-live"});
load("a headline that holds a closing tag of another id", A({payload: heads("</untrusted-data-0000>")}), {src: "src-live"});
load("no data block: a paused project", "The project is paused.", {src: "src-file", error: /^אין בלוק נתונים בתשובה.*The project is paused\./});
load("two rows", rowsOf([row(), row()]), {src: "src-file", error: /^התשובה אינה שורה אחת/});
for (const [why, bad] of [["another id", {id: "x"}], ["now 6 s before updated", {now: T - 16}], ["the year 2025", {updated: 1750000000, now: 1750000010}], ["a time that is text", {updated: "now"}]])
  load("not one good row: " + why, A(bad), {src: "src-file", error: /^התשובה אינה שורה אחת/});
for (const [why, payload] of [["an object", {}], ["2,001 rows", many(2001)], ["a row with no t", [...LIVE, {}]]])
  load("not a list of rows: " + why, A({payload}), {src: "src-file", error: /^התוכן אינו רשימה/});
for (const [why, over] of [["no stat row", null], ["two stat rows", "twice"], ["a falling session pair", {sessions: [[T, T - 1]]}], ["11 session pairs", {sessions: pairs(11)}],
                           ["an unknown mode", {mode: "x"}], ["seq 1.5", {seq: 1.5}], ["a negative quote age", {quote_age_max_s: -1}], ["market_open as text", {market_open: "yes"}]])
  load("a bad status row: " + why, A({payload: stat(over)}), {src: "src-file", error: /^חסרה שורת המצב או שהיא לא תקינה/});

// cases/pick.js: pick(name, steps, want) plays steps and reads the root's class and the money block
pick("live alone", [{live: A()}], {src: "src-live"});
pick("the file while live still loads, then live", [{file: FILE, live: "loading"}, "src-file", {live: A()}, "src-live"]);
pick("neither", [{file: "error", live: "error"}], {src: "src-none", money: "הטעינה נכשלה"});
pick("loading shows skeletons", [{file: "loading", live: "loading"}], {src: "src-none", skeleton: true});
pick("a file built 120 s after the row was written does not win", [{file: file(T + 110), live: A()}], {src: "src-live"});
pick("121 s does", [{file: file(T + 111), live: A()}], {src: "src-file"});
pick("a file whose state is 121 s newer wins", [{file: file(T - 600, {state_epoch: T + 111}), live: A({payload: stat({state_epoch: T - 10})})}], {src: "src-file"});
pick("a row cannot pin itself by claiming the future", [{file: file(T + 111), live: A({payload: stat({as_of_epoch: T + 99999})})}], {src: "src-file"});
pick("one failed refresh keeps the last good live rows", [{file: FILE, live: A()}, {live: "error"}, "src-live"]);
pick("a file from before this change has no known first tab", [{file: withoutNew(FILE), live: "error"}], {src: "src-file", money: "אין נתון בתמונת המצב הזו"});
pick("a new seq changes a first-tab value under the pessimistic stub", [{live: A()}, {live: A({now: T + 30, updated: T + 20, payload: rows({money: {total_equity: 1}, stat: {seq: 2}})})}], {total: "$1"});   // LIVE's seq is 0: a real push moves seq, and identity (source, seq, the file's time) is what makes the page redraw, also when its elements are stored unmarked
pick("a number sent as text shows a dash", [{live: A({payload: money({total_equity: "<b>1</b>"})})}], {total: "—"});
pick("no basis for today", [{live: A({payload: money({day_usd: null, day_pct: null})})}], {shown: '[data-when="no_base"]'});
pick("the seven calcs take every first-tab row exactly once and leave a row of an unknown tag out", [{live: A({payload: [...LIVE, {t: "zz"}]})}], {calcRows: LIVE.length});
pick("the accounts table draws the three rows of its calc, keyed", [{live: A()}], {keys: ["#money tbody tr", ["quant", "news", "crypto"]]});
```

- [ ] Run `node tests/page/run.js --only loader` and `--only pick`. Expected: every case `FAIL` (the root has no `src-` class).
- [ ] Set `STUB` from "Probe record"; write the loader, the calcs, the pick, `nowData`, the three drawings and the money block.
- [ ] Run `node tests/page/run.js`: `OK`, the two cases of Task 13 among them (the page still draws both files as before under the new block). Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/dashboard/index.html ai-trader/tests/page`; message `feat(ai-trader): the dashboard reads the live row, picks once between it and the hourly file, and shows the money block`.

### Task 21: The page: the clock, the badge, the reason line, the refresh

**Kind:** BUILD. **Spec:** 5.4, 5.5, 5.6, 5.10 (rows "Tabs, button", "Reason line"), 5.11 (the `st-` repair, the constants), 7 (harness: badge, no timers, refresh, a person's edit).

**Files:** Modify `dashboard/index.html`. Create `tests/page/cases/badge.js`, `tests/page/cases/refresh.js`.

**Interfaces:** Consumes Task 20 (`current`, `K`, `nowData`). Produces:

```js
function clock()              // -> {now, age, from}: "now" on the database's clock, the age of what is shown, and the epoch the age is counted from (spec 5.4)
function badge()              // -> {state, tone, why}: the first row of spec 5.5's table that holds; tone 'muted' | 'ok' | 'warn' | 'bad'; why = a reason code or null
// drawings: fresh ({mount, update, unmount}: the chooser and the timers), age (kinds s, m, hms, t, pm), why
```

- Stored HTML, in `<header id="top">` under the title row: `<p id="fresh">` holding the chooser `<span data-draw="fresh" data-source="now_stat">`, one `<span data-s="<state>">` per sentence of spec 5.5 (all but `wait` stored `hidden`) with each drawn part as `<b class="num" data-draw="age" data-age="<kind>">—</b>`, and the two timer-less sentences "הספירה נעצרה · לחץ רענן" and "לא מתעדכן · לחץ רענן"; `<p id="why">` holding `<span data-draw="why">` and the nine sentences of spec 5.10 ("Reason line"), each `data-when="<code>"`; `<button id="refresh" type="button">רענן</button>`. The chooser sets `hidden` on sentences and the classes `s-<state>` and `t-<tone>` on `#fresh`; it writes no text. Today's header line stays where it is until Task 23.
- A time in the badge (kinds `t` and `hms`) is the moment the age is counted from: for a live snapshot `db_updated_epoch`, or `as_of_epoch` when that is more than `K.STALE_S` older (spec 5.4); for the file its build time. It is formatted by the page in Israel time.
- The reason line shows the first of these that holds, and only in the states spec 5.5 names or when a clock differs (the order is decided here; the spec lists the sentences and not their rank): `connect` (the status of `live` is "connect"), `timeout` (a refresh the page started is unanswered after `K.REQ`), `failed` (the status is "error"), `file_newer` (the file is shown although live rows exist), `db_still` (state `slow`, `not_final` or `late`), `yield` (state `prices_old` and `quote_state` "yield"), `yahoo` (state `prices_old` otherwise), `phone_clock` (the skew is beyond `K.SKEW`), `bot_clock` (`as_of_epoch` and `db_updated_epoch` differ by more than `K.STALE_S`).
- The refresh is spec 5.6, timers in `fresh`'s `mount` and cleared in its `unmount`. How the `setTimeout` chain moves into and out of the 30-second window, which spec 5.6 leaves open and the cases below count on: the window of a session is from open - `K.LEAD` up to, and not including, close + `K.TAIL`. The chain picks its period at the moment it schedules: the next call is at now + the period that holds now (`K.P_IN` inside a window and before any row has loaded, `K.P_OUT` outside), or at the next window's start when that comes sooner; the call at a window's start is made. The extra call at open + `K.OPEN_EXTRA` is one more call and does not move the chain. Only a refresh that is answered with an error doubles the period; one that is never answered is passed over once it is `K.REQ` old. The file's own limit (`K.FILE_BAD`, `K.FILE_OK`) is counted from the file's last load or refresh. The two CSS animations (the 5-second dead-man of the tick, the alarm armed with the seconds left to `K.STALE_S`) are single steps; their CSS is the builder's and the cases below are the contract.
- `.at .now [data-dash-source-state=refreshing] { opacity: 1; }` is added after the rule of line 58: the first tab must not dim every 30 seconds (Task 23 narrows the old rule to the second tab and takes this one out). `td.className += ' st-' + v` (line 607) becomes a lookup in the fixed list ok, warn, bad.

- [ ] Write the cases. `OPEN` = 1794321000 and `CLOSE` = 1794344400 (Tuesday 2026-11-10, 09:30 and 16:00 New York); Israel is 7 hours ahead that day; `A`, `stat`, `money`, `file` as in Task 20; `closedRow` is a row written out of session 10 minutes before the case's `at` and read at `at` (`A({updated: at - 600, now: at, payload: stat({market_open: false, mode: "closed", expect_next_by: at + 72000})})`). How a `calls` case answers the page's refreshes: a refresh of a source whose status is "ok" is answered at once with the same rows (for `live`, with a new `now` and `updated`), so the 20-second rule never holds back the next call; `hold` leaves it unanswered; `thenFail` answers it with an error; a source the case set to "error", "connect" or "loading" stays as it is, and its refreshes stay unanswered:

```js
// cases/badge.js: badge(name, setup, want); setup = {file, live, at, after}; want = {state, text, tone, why}
badge("wait", {file: "loading", live: "loading", after: 0}, {state: "wait", text: "מתחבר לנתונים", tone: "muted"});
badge("none after both loads failed", {file: "error", live: "error"}, {state: "none", text: "אין נתונים", tone: "bad"});
badge("none after 20 s", {file: "loading", live: "loading", after: 20}, {state: "none"});
badge("file_wait", {file: file(T - 600), live: "loading", at: T, after: 5}, {state: "file_wait", text: "תמונת מצב שעתית מ-21:50 · מתחבר לנתונים החיים", tone: "muted"});
badge("the file in session is red", {file: file(T - 600), live: "error", at: T}, {state: "file", text: "לא חי · תמונת מצב שעתית מ-21:50", tone: "bad", why: "failed"});
badge("the file out of session is a warning", {file: file(CLOSE + 3000), live: "error", at: CLOSE + 3600}, {state: "file", tone: "warn"});
badge("the file because it is newer says so", {file: file(T + 111), live: A(), at: T + 120}, {state: "file", why: "file_newer"});
badge("waiting for his approval", {file: file(T - 600), live: "connect", at: T}, {state: "file", why: "connect"});
badge("nocal", {live: A({payload: stat({sessions: []})}), at: T}, {state: "nocal", tone: "warn"});
badge("ok", {live: A({updated: T - 12}), at: T}, {state: "ok", text: "חי · נכון ל-21:59:48 · לפני 12 שניות", tone: "ok", why: null});
badge("120 s is still ok", {live: A({updated: T - 120}), at: T}, {state: "ok"});
badge("the tick turns ok to slow within a second of 120 s", {live: A({updated: T - 119}), at: T, pass: 2}, {state: "slow", tone: "bad"});
badge("121 s is slow, in minutes", {live: A({updated: T - 121}), at: T}, {state: "slow", text: "לא מתעדכן · עודכן לפני 2 דקות", tone: "bad", why: "db_still"});
badge("slow beyond 120 minutes names the time", {live: A({updated: T - 7201}), at: T}, {state: "slow", text: "לא מתעדכן · מאז 19:59"});
badge("a row from 08:00 at 09:30:01 waits for the open", {live: A({updated: OPEN - 5400, now: OPEN + 1, payload: stat({market_open: false})}), at: OPEN + 1},
      {state: "wait_open", text: "השוק נפתח · ממתין לעדכון ראשון", tone: "muted"});
badge("and at 09:32:01 it is slow", {live: A({updated: OPEN - 5400, now: OPEN + 121, payload: stat({market_open: false})}), at: OPEN + 121}, {state: "slow"});
badge("friday's row on monday at 09:31", {live: A({updated: 1794603540, now: 1794839460, payload: stat({sessions: [[1794839400, 1794862800]]})}), at: 1794839460}, {state: "wait_open"});
badge("prices_old: a stale held name", {live: A({payload: rows({money: {price_epoch_min: T - 600}, stat: {quotes_missing: 1}})}), at: T}, {state: "prices_old", text: "חי · המחירים מלפני 10 דקות", tone: "warn", why: "yahoo"});
badge("prices_old: the publisher yields", {live: A({payload: stat({quote_state: "yield"})}), at: T}, {state: "prices_old", why: "yield"});
badge("prices_old: the quote age passes 180 s on the screen", {live: A({updated: T - 11, payload: stat({quote_age_max_s: 170, as_of_epoch: T - 11})}), at: T}, {state: "prices_old"});
badge("died at 15:59, seen at 18:00", {live: A({updated: CLOSE - 60, now: CLOSE + 7200, payload: stat({market_open: true})}), at: CLOSE + 7200},
      {state: "not_final", text: "שוק סגור · העדכון האחרון מ-10.11 22:59, לפני הסגירה", tone: "warn"});
badge("late", {live: A({updated: 1794625200, now: 1794697801, payload: stat({market_open: false, mode: "once", expect_next_by: 1794697200, sessions: [[1794839400, 1794862800]]})}), at: 1794697801},
      {state: "late", tone: "warn"});                                                    // written Friday 22:00, due 20 h later, seen 601 s after that
badge("closed, the same evening", {live: A({updated: CLOSE + 90, now: CLOSE + 1800, payload: stat({market_open: false, expect_next_by: CLOSE + 72090})}), at: CLOSE + 1800},
      {state: "closed", text: "שוק סגור · נכון ל-23:01", tone: "muted"});
badge("closed, the next israel day carries the date", {live: A({updated: CLOSE + 90, now: CLOSE + 7200, payload: stat({market_open: false, expect_next_by: CLOSE + 72090})}), at: CLOSE + 7200},
      {state: "closed", text: "שוק סגור · נכון ל-10.11 23:01"});
badge("israel summer time", {live: A({updated: 1806328788, now: 1806328800, payload: stat({sessions: [[1806327000, 1806350400]]})}), at: 1806328800}, {state: "ok", text: "חי · נכון ל-16:59:48 · לפני 12 שניות"});   // Review Focus 3
badge("a kept answer counts from when it was got", {live: A({updated: T - 40}), at: T + 300}, {state: "slow"});                // the first answer, the phone 300 s past now_epoch
badge("a phone clock 10 minutes fast, after a refresh the page started", {live: A({updated: T - 12}), at: T, wall: 600, refresh: A({updated: T + 18, now: T + 30})}, {state: "ok", why: "phone_clock"});
badge("a phone clock 10 minutes slow", {live: A({updated: T - 12}), at: T, wall: -600, refresh: A({updated: T + 18, now: T + 30})}, {state: "ok", why: "phone_clock"});
badge("a replay records nothing and the age goes on", {live: A({updated: T - 12}), at: T, pass: 30, refresh: A({updated: T - 12})}, {state: "ok", text: /לפני 42 שניות$/});   // the same now_epoch again
badge("an old build written late counts from the build", {live: A({updated: T - 10, payload: stat({as_of_epoch: T - 200})}), at: T}, {state: "slow", why: "db_still"});
badge("with every timer dead an answer aged 100 s turns to the alarm sentence 20 to 21 s later", {live: A({updated: T - 100}), at: T, timers: false, css: [19, 21]}, {shownAfter: ["לא מתעדכן · לחץ רענן", false, true], tone: "bad"});
badge("with every timer dead the counting part is gone within 6 s", {live: A(), at: T, timers: false, css: [6]}, {shownAfter: ["הספירה נעצרה · לחץ רענן", true]});
badge("the alarm is not armed out of session", {live: closedRow, at: CLOSE + 3600, timers: false, css: [600]}, {state: "closed", tone: "muted"});
badge("the button and one sentence deleted by a person: no error, the rest still chooses", {live: A(), at: T, remove: ["#refresh", '[data-s="closed"]']}, {state: "ok"});

// cases/refresh.js: calls(name, script, want) counts dash.refresh
calls("every 30 s in session", {live: A(), at: T, pass: 95}, {live: 3});
calls("every 300 s out of it", {live: closedRow, at: CLOSE + 3600, pass: 650}, {live: 2});
calls("30 s from 60 s before the open, and one extra call 5 s after it", {live: closedRow, at: OPEN - 61, pass: 100}, {live: 5});   // the window's start pulls the first call to OPEN - 60; then OPEN - 30, OPEN, the extra one at OPEN + 5, OPEN + 30
calls("30 s until 120 s after the close, then 300", {live: A({updated: CLOSE - 5, now: CLOSE}), at: CLOSE, pass: 700}, {live: 5});   // +30, +60, +90, +120 (scheduled at +90, still inside the window), then +420: at +120 the window has ended
calls("every 30 s before any row has loaded", {live: "loading", file: "loading", pass: 65}, {live: 2});
calls("none while hidden, one at once on return", {live: A(), at: T, hideAt: 5, pass: 200, show: true}, {live: 1});
calls("none while a call is unanswered and younger than 20 s", {live: A(), at: T, hold: true, pass: 35, tap: "#refresh"}, {live: 1});
calls("the period doubles after each failure up to 300 s", {live: A(), at: T, thenFail: true, pass: 1100}, {gaps: [30, 60, 120, 240, 300, 300]});
calls("none while the status is connect; the button still asks", {file: FILE, live: "connect", at: T, pass: 100, tap: "#refresh"}, {live: 1});
calls("the button works with every timer dead and asks for both sources", {timers: false, tap: "#refresh"}, {live: 1, snapshot: 1});
calls("unmount clears the timers", {live: A(), at: T, remove: ["#fresh"], pass: 100}, {live: 0});
calls("the file is asked again at most once in 300 s while not live", {file: file(T - 600), live: "error", at: T, pass: 650}, {snapshot: 2});
calls("and once in 1,800 s while live", {file: FILE, live: A(), at: T, pass: 3700}, {snapshot: 2});
calls("a live refresh does not dim the money block", {live: A(), at: T, refreshing: "live"}, {opacity: ["#money .big", "1"]});
calls("a status that is not ok, warn or bad adds no class", {file: health("ok x")}, {count: ['#health td[class*="st-"]', 0]});
calls("the page's two 180s are the bot's", {}, {equal: [K.PRICE_OLD_S, cfg.dashboard_push.max_quote_age_seconds, K.BEAT_S, cfg.dashboard_push.engine_alive_seconds]});
```

- [ ] Run `node tests/page/run.js --only badge` and `--only refresh`. Expected: every case `FAIL` (`#fresh` does not exist).
- [ ] Implement.
- [ ] Run `node tests/page/run.js`: `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/dashboard/index.html ai-trader/tests/page`; message `feat(ai-trader): a freshness badge on the database's clock, a reason line, a refresh button and the page's own 30-second refresh`.

### Task 22: Rollout step 2: the badge and the money block on the owner's page

**Kind:** OPS - the owner's main chat session (it holds the Artifact tools); the owner answers five short questions. **Spec:** 5 (the store), 5.1, 6 (items 5-6), 7 step 2 and "Phone checks", 10.1.

- [ ] Preconditions: Task 18 passed (the row moves), Tasks 20-21 are committed.
- [ ] Land them: a **page landing** (gate steps 1-2) when `git diff --stat origin/<branch>..HEAD` shows `dashboard/index.html` and `tests/page/` only. If it shows more (Task 12, or an edit committed since the last landing), the landing is the kind that diff asks for (Global Constraints), quant-critic included. Files of the owner's list in the diff: none.
- [ ] Publish, in this order. (1) Read the store's `dash/settings` and write its `updates` value into the session log: it is the undo. `update` (never `set`: the same document holds `shared`, which only the page writes) it to `updates: "viewed"`. The database connector stays unshared. (2) Write the dataset document `live` exactly as spec 5.1 gives it: `connector` copied from the probe dataset that worked on the phone, `project_id` from the connector in that turn, the query character for character. (3) Publish `dashboard/index.html` at the landed commit. (4) Read the `live` source back from the store and compare it with spec 5.1: the stored query runs with the owner's whole database access.
- [ ] Proof: the page's check report shows no one-writer fault; its runs report shows `live` ok with rows. A run that fails with a limit of the connector: the in-session period `K.P_IN` becomes 60 through a page landing (spec 10.2).
- [ ] Tell the owner what changed (spec 6.6): a badge at the top and the money block under it; if the platform asks him once to let the page use the database, that prompt is the platform's. If P1 or P2 of Task 17 failed, the plain sentence that Task 17's table gives for it.
- [ ] The phone checks, in session, each one question in its own message, each answer written down by itself: the five sentences of spec 7 ("Phone checks", step 2), in its order. Check 2 or 5 answered "לא": the page's own refresh does not run unattended on his phone; the button is the way, he is told so in one plain line, and nothing later in this plan depends on the timer.
- [ ] Undo (spec, in this order): the previous `index.html` from git; then delete the dataset `live`; `updates` back to the recorded value with `update`.

### Task 23: The page: two tabs and the rest of the first tab

**Kind:** BUILD. **Spec:** 5.7, 5.8 (blocks 2-6), 5.9, 5.10, 5.11, 7 (harness: layout targets 3 and 4, hostile payload, tabs).

**Files:** Modify `dashboard/index.html`. Create `tests/page/cases/tabs.js`, `tests/page/cases/first_tab.js`, `tests/page/cases/hostile.js`.

**Interfaces:** Consumes Tasks 20-21. Produces the drawings `heads` (the headline list) and `seen` (what the page itself measured), and this stored structure:

```html
<header id="top">   title · כסף נייר · #fresh · #why · #refresh · <button id="tab-now" role="tab">עכשיו</button> <button id="tab-more" role="tab">עוד</button>
<section id="now">  #money · #book · #tape · #plan · #heads · #status          (every card has class "now")
<section id="more" hidden>  #more-nav · the line "תמונת מצב שעתית ·" + today's header line · #takeaway · every section of today, in today's order · <footer>
```

- The header is above both tabs and is never hidden (spec 5.7). The tab listener sets `hidden` and `aria-selected`, calls `dash.setLink(id)` and then `dash.draw(name)` for every drawing of the shown tab. On opening, `location.hash` picks the tab; a hash that is an id inside `#more` (`#crypto`) opens `#more` and scrolls there. Nothing of today's page is deleted and no existing id changes.
- Blocks 2-6 are spec 5.8, their words rows "Book" to "Status" of spec 5.10, their states spec 5.9. For the cases: the headlines are a `<ul>` with one `<li>` each, the headline's text in `.hl`; a price cell has the class `px`, and `stale` when its price is; a sentence chosen by a code is `data-when="<code>"`. Columns change at a card width of 480 px by a container query. The headline list does not use `.long`. A stale price is muted and carries a hollow dot, a trade of today a filled dot: CSS shapes, never a written character.
- The engine sentence is chosen by the page as spec 5.8 writes it, with `K.BEAT_S`; the on-air sentence by `on_air_src` ("uptime": the sentence with the percent; "health": the "לפחות" sentence; null: "אין היום מסחר במניות").
- `#more-nav`: plain links to the sections of `#more`. The spec asks for the row and gives no words; decided here, and told to the owner at step 3: מדדים · תשואה · פוזיציות · פקודות · דסק · חדשות · ציונים · עסקאות · למידה · מכונת הזמן · חוקים · בריאות · לוח זמנים · חסימת דוחות · לקחים · קריפטו, to the ids `kpis`, `equity-card`, `positions`, `orders`, `desk`, `news`, `scorecard`, `trades`, `learning`, `timemachine`, `rules`, `health`, `schedule`, `blackout`, `lessons`, `crypto`; one listener scrolls to the section and calls `dash.setLink` with its id.
- In `#health`, a block `#livepath` headed "הנתיב החי", drawn from `current`: `seq`, `bytes`, `build_ms`, `prev_push_ms`, `quotes_missing`, `quote_age_max_s`, `code`, `engine_code`, the next open (the first pair of `sessions` that is ahead), and `seen` (when the page last got an answer; how long the first file rows and the first live rows took, in seconds). Its labels, decided here (the spec lists the numbers and no words): מספר שידור · גודל (בייטים) · זמן בנייה · זמן השידור הקודם · מחירים חסרים · גיל המחיר הישן ביותר · גרסת המשדר · גרסת המנוע · הפתיחה הבאה · נמדד בדף: תשובה אחרונה, שורות הקובץ אחרי, השורות החיות אחרי. One more stored line there, shown while the first tab shows the file: "המסך הראשון מציג עכשיו את התמונה השעתית, לא את השורה החיה."
- The rule of line 58 becomes `#more [data-dash-source-state=refreshing] { opacity: .5; }` and Task 21's override goes.
- Safety, spec 5.11: payload text reaches the page through `textContent` only; a cell is cut to `K.CELL` characters, a table to `K.ROWS` rows; `mark`, `buys_why` and every status pass through fixed lists.

- [ ] Write the cases:

```js
// cases/tabs.js
tab("the page opens on the first tab and #more is hidden", {}, {shown: "#now", hidden: "#more", selected: "#tab-now"});
tab("opening עוד draws its tables under the pessimistic stub", {tap: "#tab-more"}, {rows: ["#positions tbody tr", ">0"], link: "more"});
tab("an old link opens the second tab at its section", {hash: "#crypto"}, {shown: "#more", inView: "#crypto"});
tab("the badge and its timers live through a tab change", {tap: "#tab-more", pass: 65}, {calls: {live: 2}, shown: "#fresh"});
tab("every button is at least 44 by 44", {}, {minBox: [["#tab-now", "#tab-more", "#refresh"], 44, 44]});
tab("the second tab says its own time", {tap: "#tab-more"}, {text: ["#more", /^[\s\S]*תמונת מצב שעתית ·/]});
tab("the path block shows the row's numbers and what the page measured", {tap: "#tab-more"}, {text: ["#livepath", /מספר שידור/]});
tab("while the file is shown the health card says where the first tab comes from", {live: "error", tap: "#tab-more"}, {shown: '#livepath [data-when="file"]'});
// cases/first_tab.js, with the pinned fixture
for (const [width, tall] of [[400, 2400], [360, 2600]])
  layout(`the first tab at ${width}`, {width}, {height: ["#now", "<=", tall], bottom: ["#money", "<=", 700], overflow: []});       // targets 3 and 4
layout("at 1280 the book has its own columns for both profit numbers", {width: 1280}, {columns: ["#book", 7], overflow: []});
for (const state of ["loading", "no rows, known", "not known", "error"])
  block("every block in the state: " + state, state, SENTENCES[state]);                  // the two tables of spec 5.9, sentence for sentence
block("older trades but none today", tape({today: false}), {shown: "היום לא היו עסקאות. האחרונות:"});                 // tape(over), pos(over): every row of that table
block("with the hourly file the first tab still lists 8 headlines", {file: withNews(FILE, 20), live: "error"}, {count: ["#heads li", cfg.dashboard_push.headlines_first]});
block("a table the publisher trimmed is not known, never empty", rows({stat: {trimmed: ["degraded"]}}, {drop: ["tape", "plan", "news"]}), {shownIn: [["#tape", "#plan", "#heads"], "אין נתון בתמונת המצב הזו"]});
block("more of today's trades are in the second tab", stat({tape_more: 2}), {text: /ועוד 2 עסקאות היום בלשונית "עוד"/});
for (const code of ["loss_review", "hold", "something new"])                             // the three sentences of spec 5.10, the last for any other code
  block("buys on hold: " + code, stat({buys_held: true, buys_why: code}), {shown: `#plan [data-when="${code === "something new" ? "other" : code}"]`});
for (const [name, over, want] of ENGINE)                                                 // active; not answering; off outside its hours; not known when the badge is not ok, prices_old or closed
  block("the engine sentence: " + name, stat(over), want);
block("a stale price is muted and the legend line shows", pos({stale: true}), {cls: ["#book td.px", /stale/], shown: "מחיר מעומעם = מחיר ישן"});
for (const [src, want] of [["uptime", /באוויר היום 5:26 מתוך 5:30 \(99%\)/], ["health", /באוויר היום לפחות 0:07 מתוך 5:30/], [null, /אין היום מסחר במניות/]])
  block("on the air: " + src, stat(src === "uptime" ? {on_air_src: src, on_air_s: 19566, session_s: 19800, on_air_pct: 0.9882}
                                 : src ? {on_air_src: src, on_air_s: 420, session_s: 19800, on_air_pct: 0.0212} : {on_air_src: null, on_air_s: null, session_s: null, on_air_pct: null}), {text: ["#status", want]});
// cases/hostile.js
hostile("markup in a headline stays text", heads("<img src=x onerror=alert(1)>"), {count: ["#heads img", 0]});
hostile("class names in mark and in a code add no class", rows({news: {mark: "zz-evil"}, stat: {buys_held: true, buys_why: "zz-evil x"}}), {count: ["#now .zz-evil", 0]});
hostile("150 rows of one table draw 100", many("pos", 150), {count: ["#book tbody tr", 100]});
hostile("a 2,000-character cell is cut to 300 and no table widens", heads("x".repeat(2000)), {textLen: ["#heads .hl", 300], overflow: []});
hostile("numbers as text show dashes", pos({last: "1e9", pnl_usd: "<b>9</b>"}), {text: ["#book td.px", "—"], count: ["#book b", 0]});
hostile("no payload text becomes a link", heads("https://example.test/x"), {count: ["#now a", 0]});
```

- [ ] Run `node tests/page/run.js --only tab`, `--only "first tab"`, `--only block`, `--only hostile`. Expected: `FAIL` (`#now` does not exist).
- [ ] Implement.
- [ ] Run `node tests/page/run.js`: `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/dashboard/index.html ai-trader/tests/page`; message `feat(ai-trader): a short live first tab and everything else under a second, hourly tab`.

### Task 24: Rollout step 3: the two tabs on the owner's page

**Kind:** OPS - the owner's main chat session; the owner answers two short questions. **Spec:** 6 (items 6-7), 7 step 3, 1 (targets 3-5).

- [ ] Land Task 23: a page landing (gate steps 1-2) when the diff is the page and its cases only, else the kind its diff asks for; files of the owner's list in the diff: none. Publish `dashboard/index.html` at the landed commit; the check report shows no fault and the runs report shows `live` and `snapshot` ok; the `live` source is read back from the store and compared with spec 5.1 again (spec 10.8: after every page change).
- [ ] Phone checks 6 and 7 of spec 7, one question per message. Then one request: "פתח 'עוד', גלול ל'בריאות', ושלח לי צילום של 'הנתיב החי'": the two measured times there are target 5 (file rows within 2 s, live rows within 5 s); they go into "Baseline record" as measured by the page.
- [ ] Tell him, a line each (spec 6.7): "אפשר לבקש ממני כל טבלה, גרף או כפתור בשמו." · "ב-Sources אפשר להוריד את השורות של כל מקור כ-CSV." · "כעורך אתה יכול לערוך שם את השאילתה החיה, לבדוק אותה, לשמור, לשחזר גרסה קודמת, ולהחליף את הקובץ המצורף." · "השאילתה החיה רצה כשפותחים את הדף, כשלוחצים 'רענן', וכל 30 שניות בשעות המסחר כשהדף פתוח, עם הגישה שלך למסד הנתונים." · "כל מי שיכול לפתוח את הדשבורד יכול לקרוא את הקובץ השעתי המצורף." · "'עכשיו' חי. 'עוד' מתעדכן פעם בשעה ונפתח בשורת קישורים לחלקים שלו." · "'היום' הוא תיקי המניות מול הסגירה האחרונה. לקריפטו יש שורה משלו." And one line that the link row, the labels of "הנתיב החי" and the accounts table's headings are words he has not seen before and can change by asking.
- [ ] Undo (spec): the previous `index.html`.

### Task 25: Rollout step 4: the drill, the hand-over to the supervisor, closing

**Kind:** OPS - the owner's main chat session, with the owner at his phone once. **Spec:** 7 step 4, 3.1 (the final form), 8 (backlog), 10.

- [ ] The drill, in session, right after Task 24, with the owner in the chat. This session cannot write to him 150 s after the kill (nothing wakes it), so the kill gets a clock time and he is told when to look before it happens. Pick K: a whole minute at least 3 minutes ahead and, while the parent hands over by the clock (`supervisor.handover_times_ny`), 6 minutes before a hand-over time. On his word, a one-time scheduled task bound to the trader session, set for K, whose prompt is to run `pid=$(python3 -c "import json; print(json.load(open('ai-trader/state/dash_publish.json'))['pid'])") && grep -q dash-publish /proc/$pid/cmdline && kill $pid` and answer with the pid only. In the same turn, before the kill, phone check 8 of spec 7 with the two clock times (Israel time) in place of its "now": "ב-<K> אני עוצר את השידור בכוונה. ב-<K ועוד 4 דקות>: השורה למעלה אדומה?" (Four minutes: 150 s to red, and up to a minute and a half for a task that starts late.) Pass: he answers that the line was red at K + 4; the trader session's transcript (`list_events`) shows that the kill ran at least 150 s before that minute (a kill that ran later, behind another turn: the drill is repeated before another hand-over); after the hand-over the next launch starts the publisher and the line is green again; `dash_health.jsonl` shows the gap and nothing in `uptime.jsonl` moved because of it. When the parent runs with no hand-overs (S-Task 27 has landed), K is any minute at least 3 minutes ahead and the same command goes on after the kill: `sleep 300`, then it starts the publisher again with the body of `LAUNCH[STEP]` in which `$$` is the parent's pid from `python3 -m aitrader.supervise --status`.
- [ ] The final form is not built here. Hand to the supervisor's author, in one message and one backlog item: the amendment spec 3.1 asks of the supervisor spec (the parent starts `dash-publish` as a second child beside the engine, restarts it with back-off, never counts it in uptime, never restarts or stops the engine because of it, and never restarts it after exit 78). When that has landed through its own spec and plan, the prefix leaves `news-watch.md` (a BUILD edit: `STEP` "parent", `LAUNCH` gone, the test asserts no slot file starts the loop) and this drill is repeated.
- [ ] After 14 sessions of `dash_health.jsonl`: one short Hebrew page for the owner with the numbers behind targets 1, 7, 8, 9 and 10 (each with its file), the count of `dash_errors.jsonl` rows by kind, and one question: whether the hourly rebuild stays hourly (spec 7: decided after two weeks). The recommendation is written from those numbers, then.
- [ ] Append to `state/backlog.md`: the five items of spec 8's last paragraph; a phone line when live has been down for some minutes (spec 10.9; it belongs to the supervisor's lines); the crypto slots' push if those tasks run in another session (Task 18); the amendment above. Land them with the state.
- [ ] Move the claim in `BUILD_CLAIMS.md` to "Done" in that push, and write the session log.

### Task 26: Journals read once and then by their tail (only if Task 14 measured over 1 s)

**Kind:** BUILD, conditional: it runs right after Task 14 when the median `state_ms` there is over 1000, and not otherwise. **Spec:** 3.8 ("re-read a journal only when its size or mtime changed, then read only appended bytes").

**Files:** Modify `aitrader/dashboard.py`, `tests/test_dashboard_books.py`.

**Interfaces:** Consumes `journal.read`, `journal._path`. Produces `dashboard._rows(name: str) -> list[dict]`: what `journal.read(name)` returns, kept per path with the file's `(inode, size, mtime_ns)` and the byte offset of the last full line. The same three numbers: the kept rows. The same inode and a larger size: only the bytes after the offset are read and their full lines added. Anything else (a new inode after `write_all`, a smaller file): read whole. `build_now` uses it for the score, trade, equity and health journals of both books; `build()` and every other caller keep `journal.read`.

- [ ] Add class `Tail(Room)`:

```python
    def test_an_appended_line_is_read_without_reading_the_file_again(self):
        room(); self.now()
        with mock.patch.object(journal, "read", side_effect=AssertionError("read whole")):
            journal.append("news_scores.jsonl", {"id": "h10", "symbol": "AAPL", "score": 9, "headline": "Headline 10", "logged_at": "2026-11-10T19:59:30+00:00"})
            self.assertEqual(self.rows("news")[0]["key"], "h10")

    def test_a_rewritten_file_and_a_torn_last_line(self):
        room(); self.now()
        journal.write_all("news_equity.jsonl", [{"at": "2026-11-09T20:55:18+00:00", "equity": 101000.0}])      # a new inode
        self.assertEqual([a["day_usd"] for a in self.rows("acct") if a["key"] == "news"], [1200.0])
        with open(self.tmp / "trades.jsonl", "a") as f: f.write('{"symbol": "NV')                               # half a line
        self.assertEqual(len(self.rows("tape")), 4)
        with open(self.tmp / "trades.jsonl", "a") as f: f.write('DA", "side": "BUY", "qty": 1, "price": 1.0, "value": 1.0, "logged_at": "2026-11-10T19:00:00+00:00"}\n')
        self.assertEqual(len(self.rows("tape")), 5)
```

- [ ] Run `-k Tail`. Expected: `AssertionError: read whole`.
- [ ] Implement `_rows` and use it in `build_now`.
- [ ] Run `-k Tail`: 2 tests, `OK`. Whole suite: `OK`. Its landing is a step of Task 14 (a code landing, gate steps 1-3; files of the owner's list in the diff: none), before Task 16 starts; Task 16's dry session then shows the median `build_ms_median` at most 1000.
- [ ] Commit: `git add ai-trader/aitrader/dashboard.py ai-trader/tests/test_dashboard_books.py`; message `perf(ai-trader): the dashboard builder reads a journal's new lines only`.

## Open owner decisions

The owner approved the spec as written on 2026-11-11, so its three questions stand at the spec's own defaults. The plan builds the last column and designs no alternative.

| # | Question | Asked in | Built until he says otherwise |
|---|----------|----------|-------------------------------|
| 1 | Spec 9.1: the accounts table on the first tab | not asked again | א: the three-row table under the money block (Task 20). ב would take out its HTML and nothing else |
| 2 | Spec 9.2: the tab "עוד", hourly or live | not asked again | א: hourly, with its own time at its top (Task 23); the row holds the first tab only. ב redoes spec 3.4, 3.5, 4 and 5.3 and is not planned |
| 3 | Spec 9.3: Yahoo cannot keep the planned quote pace without disturbing the engine's stop quotes | Task 16 or Task 19, only when a pass number fails; the spec's sentence, recommendation א | the pace one step back (`--pace slow`, or `ramp`); a second quote source is not built |
| 4 | Not in spec 9; found by this plan. Spec 8 sends every change of `config.json` through the whole gate, sweep included. The owner's ruling of 2026-11-11 leaves the sweep out for a change to how the news engine is run, supervised or measured, because each registered sweep makes every later Deflated Sharpe stricter. Does the ruling cover this publisher's config block as well? | by the controller, before Task 14, if it chooses to ask; one message with the number: two registered sweeps for each config landing (Task 14 for certain; one more only if probe P8 or the many-symbols form changes the block) | the spec's letter: the sweep before and after at every config landing (gate step 4) |

Only he can also: fill the secure form and approve the card (Task 18), after saying where this chat should run if it and the trader session turn out to be on two environments (Task 18); write a word to the main chat five times on the first pushed day, so that the row can be read (Task 18); be in the chat for the drill (Task 25); open the probe page for two minutes (Task 17); answer the eight phone checks (Tasks 22, 24, 25); say yes to each change of a scheduled prompt (Tasks 16, 18, 19) and to each one-time task in the trader session (Tasks 14, 18, 19, 25); look at the project's sign-up setting if the connector does not show it (Task 2); restore the database project if the free plan pauses it.

## Where the plan decides what the spec leaves open

For the reviewer of each task; every item is repeated in its task.

1. The start of the loop. The spec's interim line starts the bare engine; from S-Task 20 the tracked command is the supervisor's parent, so the line is a prefix of `launch.command`, names the pid to follow (`--supervised $$`), and its background list redirects its own three streams to `.cache/dash_publish.log` with an `exec` step before it starts anything, so that no process of it has the launch command's pipe (a redirection on the last command alone leaves the list's subshell holding it under bash). One function, `no_dash.launch_prefix`, is both the shape that is tested and the shape that is written into the slot file. The slots' closing push is one subshell, so that it leaves the turn's working directory alone. In section 3ב of the SKILL the ban on `&` names this prefix as its one exception. Rollout step 1a therefore waits for S-Task 20. A supervised loop ends when `/proc/<pid>` is gone; no SIGTERM handler is installed. Tasks 10, 15, 16, 18.
2. A slot's prompt is a file in git since S-Tasks 18-20, so each switch of the start line (no push, ramp, full) is a small gated landing and an `update_trigger` on the owner's word; the spec's "needs no second gate" was written for a prompt that lived only on the task. Three landing kinds (config, code, page), and a landing's kind follows its diff: Task 12 lands with the first evening landing after its commit, as a code landing at the least, and Task 26, when it runs, lands inside Task 14. For the same reason an undo of a slot line is a forward edit of the files as they stand (`STEP` one step back; "0" is the undo of 1a), never a restore from an older commit: the supervisor lands lines in the same files. Global Constraints, Tasks 12, 14, 15, 16, 18, 19, 22.
3. A third pace word, `slow` (one round per `yield_seconds`), for the step the spec names under "ramp". Tasks 7, 16.
4. Config keys the spec does not name: `trim_news_rows`, `trim_plan_rows`, `backoff_seconds`, `nice`, `quote_slack_seconds`, `lock_wait_seconds`, `sleep_slice_seconds`, `stale_term_extra_seconds`, `pass_timeout_share`, `pass_step_ratio`; `quote_form` only if the many-symbols form answers. Tasks 3, 19.
5. The lock is waited for (`lock_wait_seconds`) before exit 3; `--once` tries the lock only to see whether a loop holds it. `seq` goes on from the stored heartbeat, which also carries `parent`, `mode` and `period_s`. One quote round per push, and the tick makes it: `--once` makes none of its own, and the tick's deadline is `once_deadline_seconds` in mode "once". Tasks 9, 10.
6. A 400 whose message is "too soon" is told from a refused payload by that one word; it is no back-off count and no degraded set. A forced degraded set says `trimmed` = ["degraded"]. `stat.bytes` is exact (two dumps). Tasks 7, 9.
7. The grid: a one-off push (open, final, last) re-bases it; a period that got shorter re-times the next tick; no two pushes inside `min_push_gap_seconds`. The open push and the final push tell the tick that they are one by `fresh=True`; a yield comes before `fresh` and before mode "once" (the stops first; spec 3.3 says "every tick"). A consequence the spec does not name: the engine looks at stops only in session, so at 09:30:03 its heartbeat can still say `stops_checked_at` null, and on a day the news book holds a name the open push can then meet yield (a) and go out with the stored prices for `yield_seconds`. The dry session's first health rows after the open show how often (`yields`); changing rule (a) is the spec's business, not this plan's. Tasks 8, 10, 16.
8. Health rows also carry `pace`, `push`, `quote_age_s_median` and `quote_age_s_max`, so the dry session measures the age of Yahoo's quotes (spec 3.8 b) without a second tool: the oldest quote of each tick over a whole session, where the spec says per symbol for one hour. The pass numbers are a command, and a day with no rows fails. Tasks 10, 11.
9. The tick's skip words; a state file that does not parse skips the tick; the crypto book "has existed" (spec 3.6 b) when its directory holds `trades.jsonl` or `equity.jsonl`, and is missing when it has existed and has no `portfolio.json`; the directory alone proves nothing, because any read and every crypto sweep create it (no memory of its own is kept). An unreadable calendar at the start ends the loop with 4. Tasks 7, 10.
10. `sessions` gives the pairs found before the first day the calendar does not cover (the spec: empty). `state_epoch` is the newest of a fixed list of record stamps. `writer` and `code` are worked out by the builder for both paths (`_writer()`, `_commit()`), and so is the session list (spec 3.4 has the publisher pass it): the builder reads the calendar the publisher pinned at its start. The publisher asks git once, when it starts, for the four paths and the commit. The pinned page fixtures are built with `_writer` and `_commit` replaced by fixed answers, so that they are the same on every machine and at every commit. Tasks 6, 7, 13.
11. The tag `news` is the first tab's 8 headlines and the hourly table's 60: `build()` returns each row once, and the page takes the first `K.HEADS` on the first tab. Tasks 6, 20.
12. A held name with neither a quote nor a stored price is valued at its cost and shows no price. `price_epoch_min` is None when a stale price has no time. "Never traded" = an empty trade journal and no position. The crypto account row's base time is today's 00:00 UTC. Task 5.
13. `buys_why` is "other" for a code the page does not know. On the air from the health journal counts each window only inside the session; from the uptime log it is the session so far minus the unprotected seconds so far. Tasks 6, 12.
14. Words the spec does not give: the plan table's `src` (החלטה יומית, החלטת לילה, תור חדשות) and `size` forms; the accounts table's headings; the link row of "עוד"; the labels and the one sentence of "הנתיב החי"; the secure form's sentence; the owner's yes questions; the questions this plan adds for him (the sign-up switch, Task 2; the two environments and the five reads, Task 18); the two clock times in phone check 8, which the spec words as "now" (Task 25: the main session cannot write to him after the kill). Tasks 2, 6, 16, 18, 19, 20, 23, 25. The owner is told of the page's new words at step 3 (Task 24).
15. The page: the class `src-live` / `src-file` / `src-none` on its root; the rank of the nine reason sentences and their codes; a badge time is the moment the age is counted from; a trimmed table is "not known", and "degraded" names all three text tables; an override keeps the first tab from dimming until the tabs exist; the refresh chain picks its period when it schedules, a window's start pulls the next call forward, the window's end is not part of it, and only an answered error doubles the period. Tasks 20, 21, 23.
16. Tests: `tests/helpers/no_dash.py` on top of the supervisor's `no_phone`; the child helper uses the engine child's tripwire, which gets a name, and first stands in for the publisher's two git calls (behind the bare tripwire every child would leave with 97) and puts its own folders on `sys.path`; in-process tests get the same two stand-ins from `Pubs.setUp`, and from Task 8 on a quote stand-in by default, so that a test meets the refusal only when it asks for it; the page fixtures are written by the Python builder and compared at every run; d3 from a local copy; the Python wrapper skips only where Node is missing, hands the harness the image's `NODE_PATH` and `PLAYWRIGHT_BROWSERS_PATH`, and the gate runs the harness itself. Tasks 3, 7, 8, 9, 13.
17. The database's step 0 is proven as the role itself in SQL, with no key, and applies only what the applied function lacks. The database's size limit follows the measured ratio by one stated rule. Tasks 2, 18.
18. The many-symbols form is tried by one request from the trader session; if it answers, its task is written then, around the saved reply. Task 19.
19. The starter's TERM (spec 3.1) is the session's act on exit 5, when the printed line allows it; the code only says whether it is allowed. Tasks 9, 15.
20. The drill restarts the publisher through the next launch of the parent; the supervisor's second child is handed over, not built. The kill has a clock time, 6 minutes before a hand-over, and the owner looks 4 minutes after it. Task 25.
21. What only the main session can do, and when. It acts only when the owner writes to it: the five connector reads of step 1b are made at his words, at any five moments spread over the day, and the drill's question goes out before the kill. The form and the card act on the calling session's own environment, so the two sessions' environment is compared before either is shown; if they differ the owner chooses between moving the chat and stopping, and no third way is designed. Tasks 18, 25.

## Baseline record

Checked by the plan's author on commit `4ef409be` (2026-11-11, before S-Tasks 2-8 were on the branch). Task 1 checks every row again on the merged tip and writes "was -> is" where something moved. No id of a session, a task, an environment or a database project is ever written here.

| What | Where on `4ef409be` |
|------|---------------------|
| `aitrader/dashboard.py` | `_px` 63-68; `_book_rows` 71-88 (`qty * last` at 77 and 82 raises when there is neither a price nor a `last_price`); the heartbeat read and the 3-minute rule 124-125, 141; the orders table 147-153; trades 181-186; the 60 headlines 188-194 (`id` is the row's index); the schedule row "08:07–16:05" 255; the engine's health row 268; `_crypto_rows` 308-392 (no crypto directory: 313-315; orders 349-357; equity marks 367-373); `build` 395-402; `write` 405-410 (`json.dumps` with `default=str`: a NaN passes). Importing the module loads `data`, `journal`, `signals`, `strategy` and no `notify`, `news_live` or `broker` |
| `aitrader/journal.py` | `_path` 26-28 (it creates the directory it is asked about); `use_book` 31-51; `_calendar` 64-68; `calendar_covers` 71-73; `session_hours` 76-84; `append` 142-164; `read` 208-220; `write_all` 223-227; `load_json` 230-232; `save_json` 235-239 |
| `aitrader/data.py` | `CHART_URL` 30; `UA` 32; `_get_json` 43-56 (20 s, three tries); `_chart` 59-73; `load_config` 337 |
| `aitrader/news_live.py` | imports 45-47 (`notify`, `postmortem`, `PaperBroker`); `error_once` 78; `_clean` 93; `_day_move_pct` 339 (percent, 2 places); `live_price` 372; `buy_hold` 487; the health row 654 (`at`, `window_s`, `steps`, `step_s_median`, `stop_gap_max_s`, `stop_quotes_missing`); `_buys_blocked` 692 (codes "loss_review", "hold"); the heartbeat write 1382 (`at`, `headlines_seen`, `positions`, `queue`, `stops_checked_at`, `buys_blocked`, `code`); the news equity mark, every 300 s in session, 1389 |
| `aitrader/cycle.py` | the quant equity mark 601-603 (`date`, `logged_at`, `equity`, `market_open`); the crypto mark 608-611 |
| `aitrader/__main__.py` | `BOOK_CMDS` 47; the `dashboard` parser 101 and branch 326-329 |
| `aitrader/notify.py` | `send` 28-58; the quiet-hours write to `alert_queue.json` 29-34 |
| `config.json` | `calendar` 9-15; `alerts` 234-238; `news.poll_seconds` 243, `buy_min_score` 245, `max_position_pct` 246, `sell_on_score_at_most` 248, `max_quote_age_minutes` 256 (3 minutes: the spec's 180 s), `health_log_seconds` 279 |
| `dashboard/index.html` (801 lines) | the meta line 1; `.num` 16; `.long` 28; the refreshing rule 58; the header line 71-77; the since-start sentence 78-83; the `snapshot` loader 527-535; the 25 calcs 536-560; the formats 565-569; `td.className += ' st-' + v` 607; the drawings 624-799 |
| Tests that build the snapshot | `tests/test_dashboard_books.py` (`Snapshot.build` 83-88, `build_in_book` 175-178, both patch `_px`); `tests/test_time_machine_honesty.py` 459 |
| Not in the repository | the prototype `_measure_first_tab.js` the spec cites as [P], and the page harness `harness/run.js` (a session's scratch folder) |
| Not in the checkout that was read | `state/news_health.jsonl`, `state/uptime.jsonl`, `tests/helpers/`, `skills/trader/slots/` (they come with the supervisor's tasks) |
| Scheduled tasks: slot -> task name, cron, "trader session" or "another session" (from the supervisor plan's record) | |
| The room clone's path; whether the scratch harness was handed over | |
| Task 14: medians of `state_ms`, `quotes_ms`, `total_ms`; largest `bytes`, `rss_kb` | |
| Task 16: the base day; the session's median and largest `quote_age_s_max`; `yields` in the first two health rows after the open | |
| Task 18: the ratio `stored / text_len`; `pg_total_relation_size` after one day | |
| Task 19: what the many-symbols request answered | |
| Task 24: seconds to the first file rows and to the first live rows, as the page measured | |

## Probe record

Filled by Task 17, from the owner's screenshot. Until then the harness stays on the pessimistic model.

| Probe | Answer on the owner's phone |
|-------|-----------------------------|
| P1 ticks and timers in two minutes; again after a screen lock | |
| P2 a CSS animation with a delay changes a stored element with no script | |
| P3 what `dash.refresh` returns; a new database read at each call under `viewed`; `status` and `data` during a re-run and after a failure | |
| P4 drawings run when `hidden` comes off | |
| P5 a drawing reruns for a dataset its element is not marked with | |
| P6 what a calc does with a failed input | |
| P7 what the platform draws on an element whose source is in "connect" or "error"; the connect prompt with nothing marked | |
| P8 answers of 60,000 and 200,000 bytes | |
| P9 a file holding `NaN` | |
| P10 the type and the whole text of `answer` (saved as `tests/page/fixtures/live_answer.txt`) | |

