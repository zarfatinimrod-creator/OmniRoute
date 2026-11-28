# SEC Filings Feed (log-only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A separate, log-only process asks the SEC once a minute for the filing list of each of the bot's 74 companies and writes what was new, the SEC's own acceptance stamp and the second the bot first saw it, so that the lead over Yahoo becomes a number in a journal; it never trades, never changes a score, and nothing calls the SEC until the owner's contact is in `AITRADER_SEC_CONTACT` (paper money only).

**Architecture:** Two new modules. `aitrader/sec.py` holds the pure parts (the contact rule, the copied 8-K and keyword tables, the reply parser, the form classes, the ticker map, the pacer) and the one network seam `_get`. `aitrader/secfeed.py` holds the process: `sec-feed` (the loop and its one-shot forms), the lock taken with the supervisor's `supervise.take_lock`, the heartbeat, three journals and `sec-report`. The feed builds no launcher: it is one background list in the watchdog's launch prefix, beside the dashboard publisher's, produced by `no_dash.launch_prefix`, and later a side child of the supervisor's parent. Rollout follows spec section 10: the address (step 0), the code (step 1), first contact and the measurements (step 2) with one config commit, the loop in the prefix (step 3), ten sessions and a report (step 4), the parent's child (step 5).

**Tech Stack:** Python standard library; `requests` (already a dependency: streamed, redirects off); `defusedxml` (already a dependency: the one Atom reply of step 2); unittest; the supervisor's test helpers (`tests/helpers/no_phone.py`, `install_tripwire` of `tests/helpers/engine_child.py`, `Procs` of `tests/test_supervise.py`).

**Spec:** `ai-trader/research/specs/2026-11-11-sec-filings-feed-design.md` (rev 2; approved by the owner as written on 2026-11-11, answer "א"). The plan argues from the spec; executors read both. "Spec 2.7" means section 2.7 of that file. Two other plans are built first in the same queue: `ai-trader/research/plans/2026-11-10-supervisor.md` ("S-Task 9" is its Task 9) and `ai-trader/research/plans/2026-11-11-live-trading-room.md` ("TP-Task 15" is its Task 15). Each task is BUILD (code and tests, by an implementer subagent in the feed clone, one task at a time, gated by a fresh reviewer) or OPS (only the named session or the owner can do it).

## Global Constraints

- Paper money only (כסף נייר). The feed never places, changes or cancels a trade, never changes a score, and no trading code reads `sec.*` or `state/sec_*`. Hard rules 1 and 3 of `ai-trader/CLAUDE.md` stand.
- What the feed may touch (spec 3.4, 8.2, 9): it writes only `state/sec_filings.jsonl`, `sec_health.jsonl`, `sec_errors.jsonl` (tracked, append-only, not hash-chained, through `journal.append`), `state/sec_ciks.json` (`--map`), `state/sec_history.json` (`--once --history`), `state/sec_feed.json` and `state/sec_feed.lock` (git-ignored). It never imports `aitrader.news_live`, `broker`, `notify`, `strategy`, `backtest`, `data` or `signals`; it takes no engine lock, reads no engine file while it loops, never calls Yahoo and runs no git but the two read-only listings of `--leak-check`. Not edited: `backtest.py`, `strategy.py`, `signals.py`, `learn.py`, `metrics.py`, `broker.py`, `data.py`, `news_live.py`, `journal.py`, `notify.py`, `supervise.py`. Pinned by tests: Task 6 (imports, readers), Task 10 (files written, the engine's lock free, `nice` and `oom_score_adj`, no engine file opened by the loop), Task 13 (the engine's numbers on the feed's first day, target 6).
- Every SEC request of the bot goes through `sec._get`, on the one `requests.Session` and the one `Pacer` of its process (spec 2.4, 3.4: one connection): hosts of `sec.allowed_hosts` only, no redirect followed, never two requests at once, never a gap under `min_request_gap_seconds`. On a refusal the feed slows down or stops; it never changes its User-Agent, its address, its host or its route (spec 2.7).
- The contact lives only in the environment variable `AITRADER_SEC_CONTACT`. It is never written to a file, a log, a journal, an error text, a command-line argument, a URL, a config value, a commit or this plan; where it is meant, the text says "the value of AITRADER_SEC_CONTACT". No session prints the environment (spec 8.4); the only check is `[ -n "$AITRADER_SEC_CONTACT" ] && echo set || echo missing`. The repository is public: no address or address-shaped text, key, token, session id, task id, environment id or scratch path that carries a session's folder name, in any file.
- Every number lives in `config.json` block `sec` (rule 5; Task 3 holds the whole table). Keys this plan adds: `contact_max_chars` (100, spec 2.3), `edgar_hours_ny` (["06:00", "22:00"], spec 4.4), `heartbeat_wait_seconds` (60, spec 3.3 "once a minute during any wait"), `report.quartile_min_n` (4) and `report.projection_sessions` (10, spec 5.3 "per 10 sessions"); the projection's target is `report.min_events`. The launch window is read from the supervisor's keys (`supervisor.watcher.engine_window_ny[0]` to `supervisor.until_ny`); the feed has no hour of its own.
- Tests never reach the network, the SEC, the model, the live `state/` or the owner's phone (spec 7). Every test module of this plan starts with `from helpers import no_sec  # noqa: F401` (Task 3: it imports `helpers.no_phone` first and drops `AITRADER_SEC_CONTACT`; from Task 9 it refuses `sec._get`). State lives in a temporary directory (`journal.STATE`). Every config a test uses points every `sec` URL at 127.0.0.1 and sets `allowed_hosts` to `["127.0.0.1"]`. Every process that runs `sec-feed` in a test runs through `tests/helpers/sec_child.py` (Task 9: the tripwire of `engine_child.py`) with `no_phone.clean_env()` plus a sentinel contact (the import test of Task 6 and the shell lines of Task 18 run no `sec-feed`). A loop a test starts gets `--until 24:00`, which `sec-feed` accepts and never reaches (Task 9). The only real HTTP is the test module's own stub on the literal host 127.0.0.1. The contact in tests is `no_sec.sentinel()`, made at run time. No test depends on the real date or hour: in-process feeds take an injected wall clock and monotonic clock.
- Two lines go verbatim into the prompt of every subagent of this plan (implementers, reviewers, the adversarial lens, the quant-critic): from step 0 on, the main session runs in the trader's environment, so every subagent it starts holds the real value in its environment, and a transcript becomes a session log. (1) `git stash` / `git stash pop` are banned ANYWHERE in this repository, including inside an isolated worktree and inside any subagent. (2) Never print the environment or AITRADER_SEC_CONTACT (no env, printenv, set, export -p, ps e or ps eww, /proc/*/environ); the only check is [ -n "$AITRADER_SEC_CONTACT" ] && echo set || echo missing. "The two lines" below means these. To compare with a base use `git show <ref>:<path>` or `git diff <ref> -- <path>`. Never touch a directory called `_tasks`.
- Nothing is ever rebased in the trader session's checkout: sync is `git fetch origin <branch>` then `git merge --no-edit origin/<branch>`. No AI attribution in any commit (no `Co-Authored-By` that names an AI or a bot, no "Generated with" line, no session link); messages are plain English, what and why. `<branch>` is the live branch the trader session pushes to.
- One queue with the two other plans (spec 11). BUILD tasks are dispatched one at a time, never beside a builder of the supervisor's or the trading room's plan, and only once their imports are on the live branch: Tasks 3-5 after S-Task 9's landing (`no_phone`, `install_tripwire`, `Procs`); Tasks 6-14 after S-Task 20's landing (`supervise.take_lock`, `supervise.read_rows`); Task 18 after TP-Tasks 15-16 and Task 17. They commit on a work branch `secfeed-build` in a clone of its own, "the feed clone", cut from the live branch in Task 1; the work branch is local to that clone and never pushed. Before each dispatch the controller runs `git fetch origin <branch>` and `git merge --no-edit origin/<branch>` on `secfeed-build` and names the tip in the brief; a conflict in a shared file is settled there by keeping every plan's lines, and the whole suite runs again; a conflict under `state/` is reported, never settled by hand. An implementer never fetches, pulls or merges.
- A landing is: after 16:05 New York, in the feed clone, the controller cuts a landing branch (local) at the landing's cut point (the last commit of its step on `secfeed-build`); on it `git fetch origin <branch>` and `git merge --no-edit origin/<branch>`; the gate on it; `git push origin HEAD:<branch>` from it, never from the work branch; then the live branch is merged back into `secfeed-build`. On a rejected push: fetch and merge again, the suite again, push, up to 5 tries.
- The gate (spec 9 and the owner's three rulings of 2026-11-11 in rule 4), at every landing: (1) `python3 -m unittest discover -s tests` prints `OK` (`tests/test_golden_stock.py` among them, unchanged); (2) one independent adversarial review of the unit that ships (a subagent with the two lines verbatim in its prompt), the privacy test of spec 7.3 as its first target; (3) the `quant-critic` agent (the two lines verbatim in its prompt) on `git diff origin/<branch>..HEAD`: a written PASS that says in words which files of the owner's list (`backtest.py`, `strategy.py`, `signals.py`, `learn.py`, `metrics.py`, `broker.py`, `data.py`, the `risk`/`signals`/`costs` blocks of `config.json`) the diff touches, with the searches showing that no trading path reads `sec.*` or `state/sec_*` and that nothing read `sec_user_agent`. No time machine sweep: no landing of this plan is expected to touch the list. The statement is made on `git diff --stat origin/<branch>..HEAD` of that landing. A task that finds it must touch a listed file stops and takes the sweep before and after (spec 9). Every must-fix goes back to the task that owns the code and the gate starts again.
- Nothing lands in market hours. Each rollout step passes its proof before the next starts and keeps the undo the spec gives it. An undo of a slot line is a forward BUILD edit of the files as they stand, landed, then `update_trigger` from the pushed files; never a restore of an older commit (both other plans land lines in the same files).
- Who can do what. The "main session" is the owner's main chat: it holds the environment tools (the approval card), creates scheduled tasks and changes a scheduled prompt only on the owner's word, has no shell in the trader session's machine, and cannot be woken by a scheduled task (its only clock is a chain of tracked background waits, each under 2 hours). The "trader session" runs the engine, the slots and, from step 3, the feed. An OPS proof about the trader session is read in one of three ways, and each step names which: the pushed state (`git fetch origin <branch>`, then `git show origin/<branch>:ai-trader/state/<file>`); the trader session's transcript (`list_events`); or a one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is one exact command, read back with `list_events`.
- The owner: short plain Hebrew, one question per message with options (א / ב / ג) and a recommendation; every line he gets ends with "כסף נייר". Models are the controller's business: this plan names none.
- Every session that works on this plan ends with `logs/YYYY-MM-DD-<slug>.md` under the eight Hebrew headings.
- How a BUILD task runs: from `ai-trader/`. One test class: `python3 -m unittest discover -s tests -p 'test_sec_feed.py' -k <class> -v`. Before its commit the whole suite: `python3 -m unittest discover -s tests` prints `OK`. `git add` paths are given from the repository root. Where Task 1's "Baseline record" gives a name another spelling on the merged tip, the recorded one is used.

## Review Focus

Input classes and failure modes the spec implies and none of its named tests exercises, most likely first. Each has its test in the task that owns the code.

1. **What an earlier process left in the heartbeat** (four handovers a day, every morning): the spec's tests carry `blocked_until` across a restart, but not the day's counts. A new feed that drops today's `megabytes_today`, `blocks_today`, `host_blocked` and `fails_in_a_row` resets the daily guard and allows a third block at every handover; one that adopts yesterday's stays off a whole new day. Task 8 (`test_todays_heartbeat_is_carried_over_and_yesterdays_counts_are_not`).
2. **The first days and the empty days of the report**: `sec-report` before any row exists, on a day the feed did not run, with one matched lead, with a window of 0 requests. Every line prints its n and "no data", nothing divides by zero, one value has no quartile range, the command exits 0. Task 13 (`test_an_empty_state_and_a_day_without_the_feed_print_n_0`), Task 14 (`test_one_and_three_leads_have_no_quartile_range`).
3. **Slow replies** (a 1,000-row body through the outbound proxy, a busy SEC hour): every request takes longer than its gap. Each company is still asked once a sweep, none skipped and none twice, the sweep stretches on the grid, rows turn "catchup" only when a company's own gap passes `fresh_gap_seconds`, and the health row's `sweep_s_max` and `poll_gap_max_s` show it. Task 7 (`test_slow_replies_stretch_the_sweep_and_every_company_is_still_asked_once`).
4. **Days when NYSE and EDGAR disagree, and short days**: Good Friday 2027-03-26 (EDGAR open, no session) is asked from the nightly index at the next start; on 2026-11-27 (13:00 close) the engine pass counts only rows inside 09:30-13:00; on dates either side of 2027-03-14 the history's outside-hours count uses each date's own offset. Task 12 (`test_good_friday_is_an_edgar_day`, `test_each_date_has_its_own_offset`), Task 13 (`test_on_the_early_close_day_rows_after_13_00_do_not_count`).
5. **Damaged or foreign input**: a torn last line in `sec_filings.jsonl`, a heartbeat that does not parse, a reply whose `filingDate`, `acceptanceDateTime` or `form` is null, a 500-letter company name with markup and control characters, a wall clock that went back between two polls, an acceptance stamp the report cannot read. No crash; the filing is logged once and never again after a restart; text is cleaned and cut; the clock jump gives "catchup", never "fresh"; the stamp is "unreadable" and counted apart. Task 6 (`test_damaged_state_and_odd_fields_cost_nothing_and_log_once`, `test_a_wall_clock_that_went_back_is_catchup`), Task 13 (`test_a_stamp_that_cannot_be_read_is_counted_apart`).

---

### Task 1: Preconditions, the SEC's own words, the baseline, the claim, the feed clone

**Kind:** OPS - the owner's main chat session. **Spec:** evidence tags ([W1]-[W5]), 2.2, 5.2 ("missed"), 6, 7.1 (fixtures), 8.1 (`index_url`, `edgar_closed`), 11, 13 (facts 12, 13, 14, 16).

**Files:** Modify `ai-trader/BUILD_CLAIMS.md`, `ai-trader/state/backlog.md` (one item), this plan ("Baseline record"). Create, on `secfeed-build` only: `ai-trader/tests/fixtures/sec/submissions-CIK0000320193.json`, `submissions-CIK0000021344.json`, `company_tickers.json`.

- [ ] `git fetch origin <branch>`. S-Task 9 has landed when all three hold: `git show origin/<branch>:ai-trader/tests/helpers/no_phone.py` prints the file; `git grep -n "def install_tripwire" origin/<branch> -- ai-trader/tests/helpers/engine_child.py` gives one line; `git grep -n "class Procs" origin/<branch> -- ai-trader/tests/test_supervise.py` gives one line. If not, no BUILD task of this plan is dispatched. Before Task 6 the controller runs `git grep -n "def take_lock" origin/<branch> -- ai-trader/aitrader/supervise.py` (S-Task 20's landing); before Task 18, `git grep -n "def launch_prefix" origin/<branch> -- ai-trader/tests/helpers/no_dash.py` and `git grep -n "class DashLines" origin/<branch> -- ai-trader/tests/test_slot_files.py` (TP-Tasks 15-16), and the spelling of the state commit in `close.md`'s closing block (S-Task 19) into "Baseline record".
- [ ] The SEC's own words. From this session only, with the fetch tool, read the five documentation pages of spec section 6 ([W1]-[W5]) and the SEC's documentation of the daily index under `/Archives/edgar/daily-index`. Nothing else on `www.sec.gov` and nothing on `data.sec.gov`: never `company_tickers.json`, an index file, the Atom feed or a submissions file (those are step 2's, from the trader session, with the declared agent). For each quoted sentence ask the tool for that sentence verbatim and compare. Write into "Baseline record" each quote as "same" or "was -> is". A difference that changes a number or a rule the design uses (10 requests a second; 06:00-22:00 ET; 5:30 p.m. next business day; the 10:00 p.m. nightly index; "at least one year ... or 1,000"; "less than a second"; the User-Agent sample and `Accept-Encoding`) stops the plan and goes to the spec's author. Any other difference is a one-line fix of the spec's quote in this task's commit.
- [ ] `index_url`: from that documentation, the name and path of one day's index file as a template with the fields `{year}`, `{qtr}` (1-4) and `{ymd}` (YYYYMMDD), and the file's documented layout (delimiter, the header lines by their names, columns, how the CIK and the accession are written), with the page's address and the date read. A header line that holds an address is recorded as "a line holding an address (not copied)": its value never enters this plan, the spec or a fixture (the repository is public, and Task 3's scan and S-Task 19's fixture scan would fail on it). If no SEC page names the file: `index_url` is null (spec 8.1), and Task 12 builds no parser.
- [ ] `edgar_closed`: the dates of 2026 and 2027 on which EDGAR takes no filings, from an SEC page (its address and date into "Baseline record"). If no SEC page lists them, the list is the federal holidays of those two years with their observed dates (5 U.S.C. 6103), and the record says that it is that and not an SEC statement (spec fact 16 stays open).
- [ ] Names on the merged tip, file and line into "Baseline record" (`git grep -n`), "was -> is" where a spelling moved: `journal`: `STATE`, `append`, `read`, `save_json`, `load_json`, `now_utc`, `session_hours`, `calendar_covers`; `news_live._clean` (its regex is copied, never imported), the `news_health.jsonl` row (`at`, `window_s`, `steps`, `step_s_median`, `stop_gap_max_s`, `stop_quotes_missing`), the seen row (`key`, `symbol`, `published`, `first_seen`, `outcome`), the scores row (`id`, `symbol`, `headline`, `score`, `logged_at`); `config.json`: `universe`, `market.etf_groups`, `news.poll_seconds`, `news.fresh_minutes`, `news.health_log_seconds`, `news.buy_min_score`, `news.sell_on_score_at_most`, the top-level `sec_user_agent`; `data.sec_recent_form4` (no caller); `__main__.main(argv)`; from S-Task 9: `no_phone.clean_env`, `engine_child.install_tripwire(path)`, `test_supervise.Procs` (`tmp`, `state`, `sent_file`, `_started`, `scenario`, `wait_for`, `dead`; its `tearDown` closes every started process's stdout and stderr); from S-Task 20: `supervise.take_lock(path, now)`, `supervise.read_rows(path)`, `supervise.load_cfg(path)`, the keys `supervisor.until_ny`, `handover_target_seconds`, `up_hb_max_seconds`, `watcher.engine_window_ny`, and the uptime rows `exit` (`why`), `up`, `hang`, `mark` (`hb`); `tests/helpers/http_stub.py` (`NtfyStub`: it plays ntfy and cannot script a redirect, a gzip body or a slow body, so the wire stub is this plan's own, Task 9; spec fact 14).
- [ ] Add under "Open" in `BUILD_CLAIMS.md`: session (main), purpose ("SEC filings feed, log-only: spec 2026-11-11-sec-filings-feed-design, plan 2026-11-11-sec-filings-feed; BUILD tasks run in the one queue of the supervisor's and the trading room's plans, one at a time"), UTC time, files. New: `aitrader/sec.py`, `aitrader/secfeed.py`, `tests/test_sec_feed.py`, `tests/helpers/no_sec.py`, `tests/helpers/sec_child.py`, `tests/fixtures/sec/`. Shared, with the supervisor's claim of 2026-11-11 10:09 and the trading room's claim: `aitrader/__main__.py` (two commands), `config.json` (the `sec` block in, the top-level `sec_user_agent` out), `.gitignore` (two lines), `THIRD_PARTY.md` (one line), `tests/helpers/no_dash.py` (`launch_prefix` only, Task 18), `skills/trader/SKILL.md` (section 3ד and one sentence of 3ב), `skills/trader/slots/news-watch.md` (the feed's list) and `close.md` (two lines), `tests/test_slot_files.py` (class `SecLines` and its constants). The claim's time is refreshed on every working day.
- [ ] One item in `state/backlog.md`, for the supervisor's author (spec 11, collision 3): the side-children amendment that TP-Task 25 hands over is written for a LIST of side children (the dashboard publisher and this feed): started with the engine, restarted with back-off, never counted in uptime, never a reason to stop or restart the engine, never restarted after exit 78.
- [ ] `git add ai-trader/BUILD_CLAIMS.md ai-trader/state/backlog.md ai-trader/research/plans/2026-11-11-sec-filings-feed.md` (and the spec, when a quote was fixed); message `trader: build claim and plan for the SEC filings feed (spec 2026-11-11)`; fetch, merge, push. Proof: `git show origin/<branch>:ai-trader/BUILD_CLAIMS.md` shows the claim.
- [ ] The feed clone: a clone of its own, `git fetch origin <branch>`, `git switch -c secfeed-build origin/<branch>`. Record its path as "clones/feed/ai-trader under the main session's scratch folder", never with the scratch directory's name.
- [ ] Fixtures, in the feed clone: from the upstream repository at the pinned commit of `THIRD_PARTY.md` (`3d0f4ef6`), `git -C <upstream checkout> show 3d0f4ef6:tests/fixtures/trader-analyst/submissions-CIK0000320193.json` (5,105 bytes, 29 rows), `...:tests/fixtures/trader-analyst/submissions-CIK0000021344.json` (19 rows) and `...:tests/fixtures/trader-news/company_tickers.json` (7 rows, `BRK-B` among them), each written unchanged under `ai-trader/tests/fixtures/sec/`. Run the address pattern of S-Task 19 over the three: no hit (none on 2026-11-11). `git add ai-trader/tests/fixtures/sec`; message `test(ai-trader): SEC reply fixtures copied unchanged from the pinned trader pack (MIT)`, on `secfeed-build`.

### Task 2: Rollout step 0: the contact address

**Kind:** OPS - the owner's main chat session; the owner answers question 6 (and the network question when it applies), gives the address once, approves one card and says yes to two one-time tasks. Independent of every BUILD task: it can run while they are built. **Spec:** 2.3 ("How the value gets there"), 2.7 (a 403 the proxy made), 10 step 0, 12 question 6.

- [ ] Question 6 first. If the owner has answered the supervisor's question 11, that answer is this one (one environment for the trader). Otherwise one message, the spec's two options (א: the environment of the ntfy topic; ב: an environment for the trader session only), each to be personal and the one the trader session runs in, recommendation "the same as your answer to the supervisor's question 11". No card is shown before he answers.
- [ ] The environment check (spec step 0.1): `get_session` on the trader session for its environment, then `get_environment` on that environment. Go on only when the answer says it is the environment this session runs in AND that it is personal. Otherwise stop and ask one question: "הכתובת נשמרת רק בסביבה של הסשן שמבקש אותה, והצ'אט הזה רץ בסביבה אחרת מזו של הסוחר (או בסביבה משותפת לארגון). א: להעביר את הצ'אט לסביבה של הסוחר ולהמשיך (המלצה). ב: לעצור כאן. כסף נייר." On א: `switch_environment` (its own approval card), then the check again. A refused switch (the tool refuses an environment with unrestricted network access or a wildcard host): stop, and one message that gives what the tool said, in its words and without any id: "הצ'אט לא יכול לעבור לבד לסביבה של הסוחר. א: לפתוח צ'אט ראשי חדש בסביבה של הסוחר ולהמשיך משם (המלצה). ב: לעצור כאן. כסף נייר." No card is shown until the check passes. No environment id is written anywhere.
- [ ] The network, from the same `get_environment` answer (spec 2.7: a 403 can come from the proxy). When the access is limited and `data.sec.gov` or `www.sec.gov` is not among its allowed hosts, one question before the card: "כדי שהבוט יגיע ל-SEC צריך להוסיף לסביבה של הסוחר את הכתובות data.sec.gov ו-www.sec.gov. א: להוסיף באותו כרטיס (המלצה). ב: לעצור כאן. כסף נייר." On ב nothing is shown and steps 2 onward wait. Unrestricted access, or both hosts allowed: no question.
- [ ] He opens the address himself and gives it once, in chat. This session never repeats it in a message.
- [ ] `get_environment`; one sentence ("הכרטיס מוסיף משתנה אחד, AITRADER_SEC_CONTACT, לסביבה של הסוחר, ושום דבר אחר. כסף נייר.", or, after an א to the network question, "הכרטיס מוסיף לסביבה של הסוחר משתנה אחד, AITRADER_SEC_CONTACT, ואת הכתובות data.sec.gov ו-www.sec.gov, ושום דבר אחר. כסף נייר."); `update_environment` with `set_environment_variables` `{"AITRADER_SEC_CONTACT": <the value he gave>}` (and `add_allowed_hosts` with the missing ones after that א), `environment_name` and `applies_to` copied from `get_environment`. Declined: nothing else is shown, and steps 2 onward wait.
- [ ] The session log of this turn names the variable only. Before the push of that turn: `git diff --cached`; push only when no line holds an "@" that is not expected.
- [ ] The next trading morning: a one-time scheduled task bound to the trader session, on the owner's word, whose prompt is to run `[ -n "$AITRADER_SEC_CONTACT" ] && echo set || echo missing` and answer with the word only; read back with `list_events`. "missing": the machine has not been restored since the card; wait a morning.
- [ ] Once Task 15 has landed, and the trader session's checkout holds the landing (the command does not exist before it, and a landing pushed after 16:05 usually reaches that checkout only the next morning): its next pushed state commit descends from the landing (`git fetch origin <branch>`, then `git merge-base --is-ancestor <landing> <that commit>` exits 0), or the prompt below begins with `git fetch origin <branch> && git merge --no-edit origin/<branch> && ` (TP-Task 14). Then a one-time task the same way, `(cd ai-trader && python3 -m aitrader sec-feed --leak-check)`. Proof: `leak-check: 0 files hold the contact`.
- [ ] Undo (spec): he removes the variable; the feed then exits 78.

### Task 3: The `sec` block, the contact rule, the copied tables, the address scan

**Kind:** BUILD. Dispatched after S-Task 9's landing. **Spec:** 2.3, 4.2 (the tables), 6 (licence), 7.1 (`no_sec.py`, the sentinel), 7.2 (the config rows, the tables), 7.3 (the repository check), 8.1.

**Files:** Modify `config.json` (the top-level `sec_user_agent` removed; a top-level block `sec` where it stood), `.gitignore` (`state/sec_feed.json`, `state/sec_feed.lock`), `THIRD_PARTY.md` (one line under the v2 entry). Create `aitrader/sec.py`, `tests/helpers/no_sec.py`, `tests/test_sec_feed.py`.

**Interfaces:** Consumes `helpers.no_phone` (S-Task 2). Produces:

```python
# aitrader/sec.py (standard library only in this task)
ITEMS_8K: dict[str, str]; IMPORTANT_ITEMS: set[str]; KEYWORDS: list[tuple[str, str]]   # copied; header: MIT notice, (c) 2026 Jake Schincariol, commit 3d0f4ef6
DEFAULTS: dict          # the keys of the block the code may fall back on, nested as in the block
REQUIRED = ("accept_clock", "index_url", "index_enabled", "edgar_closed", "max_wire_bytes", "max_body_bytes", "max_daily_megabytes")
class NotConfigured(Exception): key: str          # carries the key's name only
def settings(cfg: dict) -> dict                   # DEFAULTS merged under cfg["sec"] (one level into forms, match, report); NotConfigured when a REQUIRED key is absent
def user_agent(env: Mapping[str, str], s: dict) -> tuple[str | None, str]   # (s["agent_name"] + " " + value, "ok") | (None, "missing") | (None, "malformed")
def norm_ticker(t: str) -> str                    # upper case; "." and "-" removed
def clean(text: object, cap: int) -> str          # the engine's _clean rule, copied: control, markup and surrogate characters to spaces, white space folded, cut to cap

# tests/helpers/no_sec.py - imports helpers.no_phone first; at import: os.environ.pop("AITRADER_SEC_CONTACT", None)
TRIPPED: list[str]
def refuse(name: str)          # -> a function that appends name to TRIPPED and raises AssertionError("a test reached " + name)
class Case(unittest.TestCase)  # tearDown, in try/finally around super().tearDown(): fails the test when TRIPPED is not empty, then empties it
def sentinel() -> str          # ten random lower-case letters, "@", ten random lower-case letters, ".invalid"; no fixed address in any file
```

- The value is `env[s["contact_env"]]`. Empty or absent: "missing". "malformed" unless it is one token of at most `contact_max_chars` characters, `isascii() and isprintable()`, exactly one "@", no white space, and "example" not in it (any case). The reason is a word; the value is never in a return, an exception or a print.
- `settings` raises for an absent key only: `index_url` present and null is configured.

- [ ] Write `tests/test_sec_feed.py`:

```python
from helpers import no_sec  # noqa: F401  (first: it imports no_phone and drops AITRADER_SEC_CONTACT)
ROOT = Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
FORMS = {"event": ["8-K", "6-K"], "report": ["10-Q", "10-K", "20-F", "40-F"],
         "ownership": ["3", "4", "5", "144", "SC 13D", "SC 13G", "SCHEDULE 13D", "SCHEDULE 13G"], "offering": ["S-1", "S-3", "F-1", "F-3", "424B*", "FWP"]}
CLASSES = {"2.02": "earnings", "5.02": "people", "1.01": "deal", "2.01": "deal", "5.01": "deal", "1.03": "risk", "1.05": "risk", "2.04": "risk",
           "2.06": "risk", "3.01": "risk", "4.02": "risk", "3.02": "capital", "3.03": "capital"}
SEC = {"contact_env": "AITRADER_SEC_CONTACT", "agent_name": "ai-trader-research-bot", "contact_max_chars": 100,
       "submissions_url": "https://data.sec.gov/submissions/CIK{cik}.json", "tickers_url": "https://www.sec.gov/files/company_tickers.json",
       "allowed_hosts": ["data.sec.gov", "www.sec.gov"],
       "atom_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&owner=include&count=100&output=atom",
       "edgar_hours_ny": ["06:00", "22:00"], "sweep_seconds": 60, "min_request_gap_seconds": 0.5, "connect_timeout_seconds": 5,
       "read_timeout_seconds": 10, "request_deadline_seconds": 20, "lock_wait_seconds": 25, "clock_tolerance_seconds": 120,
       "backoff_after_fails": 5, "backoff_max_seconds": 600, "bad_body_block_after": 3, "block_429_seconds": 600, "block_403_seconds": 3600,
       "blocks_per_day_max": 2, "slow_factor_after_block": 2, "seen_keep_days": 14, "fresh_gap_seconds": 150, "publish_slack_seconds": 120,
       "cik_map_refresh_days": 7, "text_max_chars": 120, "health_log_seconds": 300, "hang_seconds": 180, "sleep_slice_seconds": 1,
       "heartbeat_wait_seconds": 60, "nice": 10, "oom_score_adj": 500, "forms": FORMS,
       "match": {"before_seconds": 3600, "after_seconds": 14400, "engine_gap_seconds": 120, "item_classes": CLASSES},
       "report": {"min_events": 30, "max_error_rate": 0.01, "min_delay_ok_share": 0.9, "days": 14, "sign_alpha": 0.05,
                  "boot_level": 0.95, "boot_draws": 2000, "boot_seed": 0, "pass_step_ratio": 1.2, "quartile_min_n": 4, "projection_sessions": 10}}
SET_LATER = ("accept_clock", "index_url", "index_enabled", "edgar_closed", "max_wire_bytes", "max_body_bytes", "max_daily_megabytes")
ADDRESS = re.compile(r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[a-z]{2,}")

class Block(no_sec.Case):
    def test_the_block_is_the_spec_table_and_the_seven_are_there(self):        # the seven by presence and type: Task 17 changes them without this test
        b = CFG["sec"]
        self.assertEqual({k: v for k, v in b.items() if k not in (*SET_LATER, "_note")}, SEC)
        self.assertEqual((b["accept_clock"] in ("unknown", "utc", "et"), type(b["index_enabled"]), {type(b[k]) for k in SET_LATER[4:]}), (True, bool, {int}))
        self.assertTrue(b["index_url"] is None or b["index_url"].startswith("https://www.sec.gov/Archives/edgar/daily-index/"))
        self.assertTrue(b["edgar_closed"] == sorted(set(b["edgar_closed"])) and all(d[:4] in ("2026", "2027") for d in b["edgar_closed"]))
        self.assertNotIn("sec_user_agent", CFG)

    def test_every_fallback_says_what_config_says_and_the_seven_have_none(self):   # flat(d): dotted keys
        self.assertEqual(flat(sec.DEFAULTS), {k: v for k, v in flat(CFG["sec"]).items() if k in flat(sec.DEFAULTS)})
        self.assertLessEqual(set(flat(sec.DEFAULTS)), set(flat(CFG["sec"])))
        self.assertEqual(set(sec.REQUIRED) & set(sec.DEFAULTS), set())
        for key in sec.REQUIRED:
            with self.assertRaises(sec.NotConfigured) as e:
                sec.settings({"sec": {k: v for k, v in CFG["sec"].items() if k != key}})
            self.assertEqual(e.exception.key, key)

    def test_the_waits_fit_together(self):
        s = CFG["sec"]
        self.assertGreaterEqual(s["lock_wait_seconds"], s["request_deadline_seconds"] + 2 * s["sleep_slice_seconds"])
        self.assertGreater(s["hang_seconds"], s["request_deadline_seconds"])

    def test_the_two_machine_local_files_are_ignored(self):
        self.assertLessEqual({"state/sec_feed.json", "state/sec_feed.lock"}, set((ROOT / ".gitignore").read_text().split()))

class Contact(no_sec.Case):
    def test_one_well_formed_value_makes_the_header_and_nothing_else_is_accepted(self):
        s, v = sec.settings(CFG), no_sec.sentinel()
        self.assertEqual(sec.user_agent({"AITRADER_SEC_CONTACT": v}, s), ("ai-trader-research-bot " + v, "ok"))
        self.assertEqual([sec.user_agent(e, s) for e in ({}, {"AITRADER_SEC_CONTACT": ""})], [(None, "missing")] * 2)
        for bad in (v.replace("@", " @"), v + "\n", v + "@x", "EXAMPLE" + v, v + "é", "a" * 100 + v):
            self.assertEqual(sec.user_agent({"AITRADER_SEC_CONTACT": bad}, s), (None, "malformed"))
        self.assertNotIn("AITRADER_SEC_CONTACT", os.environ)

class Tables(no_sec.Case):
    def test_the_copied_tables_equal_the_vendored_file(self):              # read with ast, never imported
        tree = ast.parse((ROOT / "vendor/jake-trader-skill-v2/trader-news/news.py").read_text(encoding="utf-8"))
        got = {t.id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
               if getattr(t, "id", "") in ("ITEMS_8K", "IMPORTANT_ITEMS", "KEYWORDS")}
        self.assertEqual(got, {"ITEMS_8K": sec.ITEMS_8K, "IMPORTANT_ITEMS": sec.IMPORTANT_ITEMS, "KEYWORDS": sec.KEYWORDS})
        head = (ROOT / "aitrader/sec.py").read_text(encoding="utf-8")[:1500]
        self.assertTrue(all(w in head for w in ("MIT", "Jake Schincariol", "3d0f4ef6")))
        self.assertIn("aitrader/sec.py", (ROOT / "THIRD_PARTY.md").read_text(encoding="utf-8"))

class NoAddress(no_sec.Case):
    def test_no_code_instruction_or_feed_output_holds_an_address(self):      # spec 7.3, narrowed; text files only
        paths = [p for r in ("aitrader", "tests", "scripts", "skills", "agents", "dashboard") for p in (ROOT / r).rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts] + [ROOT / "config.json", *(ROOT / "state").glob("sec_*")]
        self.assertEqual([str(p.relative_to(ROOT)) for p in paths if ADDRESS.search(text_or_empty(p))], [])

    def test_nothing_calls_the_old_form4_reader(self):
        self.assertEqual([p.name for p in (ROOT / "aitrader").glob("*.py") if "sec_recent_form4(" in p.read_text(encoding="utf-8")], ["data.py"])
        self.assertEqual((ROOT / "aitrader/data.py").read_text(encoding="utf-8").count("sec_recent_form4("), 1)   # its def only
```

`text_or_empty(p)` is the file decoded as strict UTF-8, or "" when it does not decode: a binary fixture is not code or an instruction (`tests/fixtures/stock_panel.pkl` holds an address-shaped run of bytes by chance and does not decode). `flat(d)` gives a nested dict as dotted keys.

- [ ] Run `python3 -m unittest discover -s tests -p 'test_sec_feed.py' -v`. Expected: `ModuleNotFoundError: No module named 'helpers.no_sec'`.
- [ ] Create `no_sec.py` and `sec.py`; the block (`_note`: read only by `aitrader/sec.py` and `aitrader/secfeed.py`; log-only; changes no trade; the contact is never written here; the page and date `edgar_closed` was read from), with `accept_clock` "unknown", `index_enabled` false, `max_wire_bytes` 5000000, `max_body_bytes` 50000000, `max_daily_megabytes` 1500, and `index_url` and `edgar_closed` from "Baseline record"; the `.gitignore` lines; the `THIRD_PARTY.md` line (the two 8-K tables and the keyword table copied into `aitrader/sec.py`; the three SEC fixtures under `tests/fixtures/sec/`).
- [ ] Run the file: 8 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/config.json ai-trader/.gitignore ai-trader/THIRD_PARTY.md ai-trader/aitrader/sec.py ai-trader/tests/helpers/no_sec.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): config block for the SEC feed, the contact rule, the 8-K tables copied with their licence; the dummy contact address leaves config.json`.

### Task 4: Reading a reply: filings, form classes, the ticker map

**Kind:** BUILD. Dispatched after S-Task 9's landing. **Spec:** 2.1 (shape), 2.2 (matching), 4.2, 7.2 (rows "the two pack fixtures", "arrays of different lengths", "a ticker spelled with -").

**Files:** Modify `aitrader/sec.py`, `tests/test_sec_feed.py` (class `Reply`).

**Interfaces:** Consumes Task 3. Produces:

```python
class BadBody(Exception)                          # no text
def items_of(text: object) -> list[str]           # "2.02,9.01" -> ["2.02", "9.01"]; None or "" -> []
def classify(form: object, forms: dict[str, list[str]]) -> str   # a trailing "/A" dropped first; an entry ending in "*" matches as a prefix; else "other"
def parse_submissions(body: object) -> dict
    # {"cik": str | None, "name": str | None, "tickers": list[str], "filings": [{"accession", "form", "items", "accepted_raw", "filed", "report_date", "doc"}]}
    # BadBody unless body is a dict whose filings.recent.accessionNumber is a list
def cik_map(reply: object, tickers: list[str], at: str) -> dict
    # {"built_at": at, "tried_at": at, "tickers": {t: {"cik": "<10 digits>", "name", "checked": at}}}; BadBody on another shape
```

- `parse_submissions` reads only `cik`, `name`, `tickers` and `filings.recent`; it walks the length of `accessionNumber`, and a parallel array that is shorter or missing gives None (`items` gives []). Values are returned raw: rows clean them (Task 6). It is written new, on the model of the pack's `latest_filings`, which indexes `items` directly.
- `cik_map` matches `norm_ticker` on both sides.

- [ ] Add a module-level `fixture(name)` (the JSON of `tests/fixtures/sec/<name>`) and class `Reply(no_sec.Case)`:

```python
    def test_the_two_pack_fixtures(self):
        a, k = sec.parse_submissions(fixture("submissions-CIK0000320193.json")), sec.parse_submissions(fixture("submissions-CIK0000021344.json"))
        self.assertEqual((len(a["filings"]), len(k["filings"]), a["tickers"], a["name"]), (29, 19, ["AAPL"], "Apple Inc."))
        eights = sorted((f["form"], f["items"], bool(set(f["items"]) & sec.IMPORTANT_ITEMS)) for f in a["filings"] + k["filings"] if f["form"].startswith("8-K"))
        self.assertEqual(eights, [("8-K", ["2.02", "9.01"], True), ("8-K", ["2.02", "9.01"], True), ("8-K/A", ["5.02"], True)])
        self.assertEqual({f["form"]: sec.classify(f["form"], FORMS) for f in a["filings"] + k["filings"]},
                         {"10-Q": "report", "144": "ownership", "3": "ownership", "4": "ownership", "8-K": "event", "8-K/A": "event", "25-NSE": "other"})
        self.assertEqual([f["accepted_raw"] for f in a["filings"] if f["form"] == "8-K/A"], ["2026-09-02T00:30:35.000Z"])

    def test_arrays_of_different_lengths_no_items_a_6k_and_an_unknown_form(self):
        body = {"name": "X", "tickers": ["X"], "filings": {"recent": {"accessionNumber": ["a1", "a2", "a3"], "form": ["6-K", "SD"], "filingDate": ["2026-12-01"]}}}
        got = sec.parse_submissions(body)["filings"]
        self.assertEqual([(f["accession"], f["form"], f["items"], f["filed"]) for f in got], [("a1", "6-K", [], "2026-12-01"), ("a2", "SD", [], None), ("a3", None, [], None)])
        self.assertEqual([sec.classify(f, FORMS) for f in ("6-K", "SD", None, "424B2", "424B5/A", "SCHEDULE 13G/A", "10-K/A", "FWP")],
                         ["event", "other", "other", "offering", "offering", "ownership", "report", "offering"])

    def test_a_body_that_is_not_the_object_is_bad_body(self):
        for body in ("<html>", [], {}, {"filings": {}}, {"filings": {"recent": {"accessionNumber": "x"}}}, None):
            with self.assertRaises(sec.BadBody):
                sec.parse_submissions(body)

    def test_the_ticker_map_meets_dashes_and_dots_and_leaves_out_what_the_sec_lacks(self):
        at = "2026-12-01T21:10:00+00:00"
        m = sec.cik_map(fixture("company_tickers.json"), ["AAPL", "BRK-B", "ZZZZ"], at)
        self.assertEqual(({t: v["cik"] for t, v in m["tickers"].items()}, m["built_at"], m["tried_at"]), ({"AAPL": "0000320193", "BRK-B": "0001067983"}, at, at))
        dotted = {"0": {"cik_str": 1067983, "ticker": "BRK.B", "title": "BERKSHIRE HATHAWAY INC"}}
        self.assertEqual(sec.cik_map(dotted, ["BRK-B"], at)["tickers"]["BRK-B"]["cik"], "0001067983")
```

- [ ] Run `-k Reply`. Expected: `AttributeError: module 'aitrader.sec' has no attribute 'parse_submissions'`.
- [ ] Implement.
- [ ] Run `-k Reply`: 4 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/sec.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): parse the SEC's per-company filing list, sort forms into classes, map tickers to CIKs`.

### Task 5: The pacer

**Kind:** BUILD. Dispatched after S-Task 9's landing. **Spec:** 2.4 (the grid, the ceiling), 7.2 (row "the pacer on a fake clock").

**Files:** Modify `aitrader/sec.py`, `tests/test_sec_feed.py` (class `Pace`).

**Interfaces:** Consumes nothing. Produces:

```python
def gap_for(period: float, n: int, min_gap: float) -> float   # max(min_gap, period / max(n, 1))
class Pacer:
    def __init__(self, min_gap: float) -> None
    def next_at(self, now: float, gap: float) -> float   # monotonic: the first grid point origin + k * gap at or after now and at or after last start + min_gap;
                                                         # the first call sets origin = now; a changed gap sets origin = max(now, last start + gap)
    def started(self, t: float) -> None                  # a request began at t
```

One pacer per process carries every SEC request (the map, the index and the Atom request included, Tasks 8 and 12). A late request skips to the next free grid point; nothing is caught up. A changed gap (a back-off doubling, the half pace after a block) starts one whole new gap after the last start: with one company the gap is the period, and a re-base at `last start + min_gap` would send the first request after a doubling 0.5 s after the last one.

- [ ] Add class `Pace(no_sec.Case)`; `starts(n, period, stall_at=None, stall_s=0)` drives a `Pacer` on a fake monotonic clock for n requests that take no time (request number `stall_at` takes `stall_s`) and returns the start times:

```python
    def test_74_companies_in_a_60_s_sweep(self):
        t = self.starts(74, 60)
        self.assertEqual({round(b - a, 6) for a, b in zip(t, t[1:])}, {round(60 / 74, 6)})            # 0.81 s
        self.assertAlmostEqual(t[-1] - t[0] + 60 / 74, 60, places=6)

    def test_500_companies_keep_the_floor_and_the_sweep_grows_to_250_s(self):
        t = self.starts(500, 60)
        self.assertEqual({round(b - a, 6) for a, b in zip(t, t[1:])}, {0.5})
        self.assertAlmostEqual(t[-1] - t[0] + 0.5, 250, places=6)

    def test_after_a_30_s_stall_there_is_no_burst(self):
        t = self.starts(74, 60, stall_at=10, stall_s=30)
        self.assertGreaterEqual(min(b - a for a, b in zip(t, t[1:])), 60 / 74 - 1e-9)
        self.assertGreaterEqual(t[11] - t[10], 30)

    def test_the_floor_holds_whatever_the_period_says(self):
        self.assertEqual((sec.gap_for(10, 74, 0.5), sec.gap_for(120, 74, 0.5), sec.gap_for(600, 1, 0.5)), (0.5, 120 / 74, 600))

    def test_a_changed_gap_starts_one_whole_gap_after_the_last_start(self):          # one company, its period doubled by the back-off
        p = sec.Pacer(0.5)
        for now in (0, 1):
            p.started(p.next_at(now, 60))                                              # starts at 0 and 60
        self.assertEqual(p.next_at(61, 120), 180)
```

- [ ] Run `-k Pace`. Expected: `AttributeError: module 'aitrader.sec' has no attribute 'Pacer'`.
- [ ] Implement.
- [ ] Run `-k Pace`: 5 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/sec.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): one pacer for every SEC request, on a monotonic grid with a 0.5 s floor`.

### Task 6: What is new: one company's poll and its rows

**Kind:** BUILD. Dispatched after S-Task 20's landing (`secfeed.py` imports `supervise`). **Spec:** 2.2 (b), 2.5 (`Age`, `Date`), 2.6 (conditional requests, the unchanged body), 3.4 (imports), 4.1, 4.3, 7.2 (rows "first sight" to "a filing older than", "the reply's tickers", "ETag", "import").

**Files:** Modify `aitrader/sec.py` (`Reply`). Create `aitrader/secfeed.py`. Test: `tests/test_sec_feed.py` (base `Feeds`, classes `New`, `Bounds`).

**Interfaces:** Consumes Tasks 3-5; `journal.append`, `read`, `load_json`, `save_json`, `now_utc`. Produces:

```python
# aitrader/sec.py
@dataclass
class Reply:
    status: int; body: bytes | None; wire: int; decoded: int; headers: dict[str, str]; fail: str | None
    # fail: None | "timeout" | "connect" | "redirect" | "too_big" | "other"; headers: only ETag, Last-Modified, Date, Age, Cache-Control, Retry-After, Content-Encoding, Content-Length

# aitrader/secfeed.py - standard library, aitrader.journal, aitrader.sec, aitrader.supervise; nothing else of the package
def universe(cfg: dict) -> list[str]        # tickers of cfg["universe"] whose group is not in cfg["market"]["etf_groups"], config order (strategy.etf_groups is not imported)
def rebuild(rows: list[dict], today: date, keep_days: int) -> tuple[dict[str, set[str]], set[str]]
    # accessions by CIK from filing and prime rows whose `filed` is within keep_days of today or cannot be read; and every CIK that has any row
def kind_of(prev_poll: datetime | None, at: datetime, fresh_gap: float) -> str   # "fresh" only when 0 <= at - prev_poll <= fresh_gap, else "catchup"
class Feed:
    def __init__(self, cfg: dict, env: Mapping[str, str], *, now=lambda: datetime.now(timezone.utc), mono=time.monotonic,
                 sleep=time.sleep, dry: bool = False, offline: Path | None = None) -> None
    def start(self) -> None                 # the map file, the heartbeat's `polls`, the seen set; `cold` when no heartbeat file was found; never raises on a damaged file
    def request(self, url: str, cik: str | None = None) -> sec.Reply   # sec._get(url, session=self.session, ua=..., s=..., etag=..., modified=...) as a module attribute
                                                                       # (Task 9's signature); sends that CIK's remembered ETag / Last-Modified
    session: requests.Session | None        # None in this task; Task 9 builds one per process
    def poll(self, ticker: str, cik: str) -> str   # "primed" | "new" | "nothing" | "unchanged" | "not_modified"; Task 8 adds the failure words
```

- A filing row is spec 4.3's table, field for field: `v` 1; `at` = the moment the reply was parsed, `isoformat(timespec="milliseconds")` in UTC; `company` and `doc` through `sec.clean(..., text_max_chars)`; `important` from `IMPORTANT_ITEMS`; `accepted_raw` character for character; `prev_poll` the company's previous good poll, from this process or the heartbeat's `polls`; `skew_s` = the `Date` header minus the local clock, whole seconds, null when missing or unreadable; `age_s` from `Age`, null when absent; `map_mismatch` true only when the reply's `tickers` lack the universe ticker (then also one error row, `place` = ticker, `error` = "map_mismatch").
- First sight of a CIK = no row of any kind for it in the whole journal: one row `{"v": 1, "outcome": "primed", "cik", "ticker", "at", "filings": [{"accession", "filed"}, ...]}` for its filings inside `seen_keep_days`, an empty list when none. A body with the same SHA-256 as that CIK's last is not parsed again. A 304 is "answered, nothing new".
- `secfeed` reaches the seam only as `sec._get(...)`, never through a name imported from `sec`: the tests replace the module attribute. Until Task 9 defines `_get`, the tests patch it with `create=True`.

- [ ] Write the base `Feeds(no_sec.Case)`: a temporary state directory (`journal.STATE`, restored at `tearDown`); `self.clock` (a fake wall clock and monotonic clock moved together by its own `sleep`); `self.cfg = cfg_for(self.tmp, ["AAPL", "KO"])`; `cfg_for` pins `sweep_seconds` and `index_enabled` (false) in the `sec` block it writes, whatever `config.json` says, so that Task 17's config-only commit cannot change what the loop tests do (a test that needs the index sets it itself, Task 12); `write_map(self.tmp, {"AAPL": "0000320193", "KO": "0000021344"}, <the clock's time>)`. Both are module-level, so that Task 9's children and Task 19's drill write the same fence: `cfg_for(dir, universe, base=None, **over) -> dict` is config.json with that universe, every `sec` URL keeping its path with scheme and host replaced (`submissions_url` at `http://127.0.0.1:9`, the three `www.sec.gov` URLs at `http://127.0.0.1:8`, two netlocs standing for the two hosts of spec 2.7's per-host row; all four at `base` when given), `allowed_hosts` `["127.0.0.1"]`, `sweep_seconds` 60 whatever config.json holds (the tests' periods and counts rest on it, and question 2 may change the real value, Task 17), then the keyword overrides of the `sec` block; also written to `dir/config.json`; `write_map(dir, tickers, at)` writes `dir/sec_ciks.json` with `built_at` and `tried_at` = `at`; `self.env = {"AITRADER_SEC_CONTACT": no_sec.sentinel()}`; `serve(cik, *replies)` scripts what the seam answers for that CIK (the last repeats), keeps every call in `self.asked` as `{"url", "cik", "etag", "modified"}`, and moves the clock by `took` seconds when a reply is given as `(reply, took)`; `self.parsed` counts `sec.parse_submissions` calls; `ok(body, wire=None, decoded=None, **headers)` makes a 200 `Reply` of the body's JSON bytes (both sizes its length unless given); `feed()` builds and starts a `Feed` on the fake clocks; `rows(name)`. Then the classes:

```python
class New(Feeds):                                  # the clock at 2026-10-20 15:00:00 UTC unless a test says otherwise
    def test_first_sight_primes_once_and_writes_no_filing_row(self):
        self.serve("0000320193", self.ok(fixture("submissions-CIK0000320193.json"))); self.serve("0000021344", self.ok(fixture("submissions-CIK0000021344.json")))
        f = self.feed(); f.poll("AAPL", "0000320193"); f.poll("KO", "0000021344")
        rows = self.rows("sec_filings.jsonl")
        self.assertEqual([(r["outcome"], r["ticker"]) for r in rows], [("primed", "AAPL"), ("primed", "KO")])
        self.assertEqual(sorted(x["accession"] for x in rows[0]["filings"]),
                         sorted(f["accession"] for f in sec.parse_submissions(fixture("submissions-CIK0000320193.json"))["filings"] if f["filed"] >= "2026-10-06"))
        self.assertEqual(rows[1]["filings"], [])                                      # KO's newest filing is 22 days old

    def test_the_same_file_again_writes_nothing_and_is_parsed_once(self):            # two polls, the same bytes; parse_submissions wrapped
        self.assertEqual((len(self.rows("sec_filings.jsonl")), self.parsed), (1, 1))

    def test_one_added_accession_60_s_after_the_last_good_poll_is_fresh(self):       # AAPL_PLUS: the fixture with 0000320193-26-000099 first,
        r = self.rows("sec_filings.jsonl")[-1]                                         # an 8-K "2.02,9.01" filed 2026-10-20 accepted 2026-10-20T14:59:30.000Z;
        self.assertEqual({k: r[k] for k in ("v", "cik", "ticker", "company", "accession", "form", "class", "items", "important", "accepted_raw", "filed", "kind")},
                         {"v": 1, "cik": "0000320193", "ticker": "AAPL", "company": "Apple Inc.", "accession": "0000320193-26-000099", "form": "8-K",
                          "class": "event", "items": ["2.02", "9.01"], "important": True, "accepted_raw": "2026-10-20T14:59:30.000Z", "filed": "2026-10-20", "kind": "fresh"})
        self.assertEqual((r["prev_poll"], r["at"], r["skew_s"], r["age_s"]), ("2026-10-20T15:00:00.000+00:00", "2026-10-20T15:01:00.000+00:00", 2, 7))
        # the second reply carries Date "Tue, 20 Oct 2026 15:01:02 GMT" and Age "7"

    def test_ten_minutes_after_or_no_earlier_poll_in_this_process_or_the_heartbeat_is_catchup(self):
        self.assertEqual([r["kind"] for r in self.rows("sec_filings.jsonl") if "kind" in r], ["catchup", "catchup"])

    def test_a_restart_over_the_journal_logs_nothing_twice_and_reads_the_heartbeats_polls(self):
        # process 1 primes AAPL at 15:00; the test writes the heartbeat a sweep leaves (polls: AAPL at 15:00); process 2 starts at 15:01 and gets AAPL_PLUS
        self.assertEqual([r.get("kind", r.get("outcome")) for r in self.rows("sec_filings.jsonl")], ["primed", "fresh"])

    def test_a_company_whose_only_row_is_a_prime_30_days_old_is_not_primed_again(self):   # prime row with an empty list; a filing filed 3 days ago
        self.assertEqual([(r.get("outcome"), r.get("kind")) for r in self.rows("sec_filings.jsonl")][1:], [(None, "catchup")])

    def test_a_filing_older_than_seen_keep_days_writes_no_row(self):                 # a new accession filed 15 days before the clock
        self.assertEqual(len(self.rows("sec_filings.jsonl")), 1)

    def test_an_etag_is_sent_back_and_a_304_is_answered_nothing_new(self):
        self.serve("0000320193", self.ok(fixture("submissions-CIK0000320193.json"), ETag='"v1"'), sec.Reply(304, b"", 0, 0, {}, None))
        f = self.feed(); f.poll("AAPL", "0000320193")
        self.assertEqual((f.poll("AAPL", "0000320193"), self.asked[-1]["etag"]), ("not_modified", '"v1"'))

    def test_a_reply_whose_tickers_lack_the_universe_ticker_is_marked_and_said_once(self):   # KO's file answered for "AAPL"
        self.assertEqual(([r.get("map_mismatch") for r in self.rows("sec_filings.jsonl")], [e["error"] for e in self.rows("sec_errors.jsonl")]), ([True], ["map_mismatch"]))

    def test_damaged_state_and_odd_fields_cost_nothing_and_log_once(self):           # Review Focus 5
        (self.tmp / "sec_filings.jsonl").write_text('{"v": 1, "outcome": "primed", "cik": "0000320193", "ticker": "AAPL", "at": "2026-10-19T15:00:00.000+00:00", "filings": []}\n{"v": 1, "acc')
        (self.tmp / "sec_feed.json").write_text("{half")
        odd = {"cik": "320193", "name": "<b>\x07" + "x" * 500, "tickers": ["AAPL"], "filings": {"recent": {"accessionNumber": ["0000320193-26-000123"],
               "form": [None], "filingDate": [None], "acceptanceDateTime": [None]}}}
        for _ in range(2):                                                             # two processes, the same reply
            self.serve("0000320193", self.ok(odd)); self.feed().poll("AAPL", "0000320193")
        new = [r for r in self.rows("sec_filings.jsonl") if r.get("accession") == "0000320193-26-000123"]
        self.assertEqual([(r["class"], r["filed"], r["accepted_raw"], len(r["company"]), "<" in r["company"]) for r in new], [("other", None, None, 120, False)])

    def test_a_wall_clock_that_went_back_is_catchup(self):                           # Review Focus 5: the second poll is stamped 3,600 s before the first
        self.assertEqual(self.rows("sec_filings.jsonl")[-1]["kind"], "catchup")

class Bounds(no_sec.Case):
    def test_the_feed_loads_no_trading_module(self):                                 # a fresh interpreter
        code = ("import sys, aitrader.secfeed; bad = [m for m in ('aitrader.news_live', 'aitrader.broker', 'aitrader.notify', 'aitrader.strategy',"
                " 'aitrader.backtest', 'aitrader.data', 'aitrader.signals') if m in sys.modules]; print(bad); sys.exit(1 if bad else 0)")
        self.assertEqual(subprocess.run([sys.executable, "-c", code], env=no_phone.clean_env(), capture_output=True, text=True).returncode, 0)
        for name in ("sec.py", "secfeed.py"):
            text = (ROOT / "aitrader" / name).read_text(encoding="utf-8")
            self.assertEqual([w for w in ("ownerlines", "deadman", "Sender") if w in text], [], name)

    def test_only_the_feed_reads_its_block_and_its_files(self):                      # the critic's search, kept as a test
        marks = ('["sec"]', "sec_filings", "sec_health", "sec_errors", "sec_ciks", "sec_history", "sec_feed")
        hits = {p.name for p in (ROOT / "aitrader").glob("*.py") if any(m in p.read_text(encoding="utf-8") for m in marks)}
        self.assertLessEqual(hits, {"sec.py", "secfeed.py"})
```

- [ ] Run `-k New` and `-k Bounds`. Expected: `ModuleNotFoundError: No module named 'aitrader.secfeed'`.
- [ ] Implement `Reply`, `universe`, `rebuild`, `kind_of` and the `Feed` methods above.
- [ ] Run both: 13 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/sec.py ai-trader/aitrader/secfeed.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): the SEC feed primes a company once, then writes one row per new filing with the bot's own first-seen time`.

### Task 7: The sweep, the health row, the heartbeat

**Kind:** BUILD. **Spec:** 2.2 (c), 2.4 (one request at a time), 2.6 (one request per company), 3.3 (the heartbeat), 8.2 (the health row).

**Files:** Modify `aitrader/secfeed.py`, `tests/test_sec_feed.py` (class `Sweeps`).

**Interfaces:** Consumes Task 6. Produces:

```python
Feed.sweep(self) -> dict            # every universe ticker with a CIK (and not left out after a 404) once, in config order, through the pacer, with the gap
                                    # taken once at the sweep's start: gap_for(period(), the companies it asks, min_request_gap_seconds);
                                    # {"seq", "companies", "mapped", "answered", "sweep_s"}
Feed.wait_until(self, t: float) -> bool   # sleeps in slices of sleep_slice_seconds to monotonic t; True (Task 10 adds the --until and parent checks)
Feed.beat(self) -> None             # state/sec_feed.json via journal.save_json (a temporary file, then a rename)
Feed.health_if_due(self) -> None    # one sec_health.jsonl row per health_log_seconds
```

- The heartbeat holds exactly spec 3.3's fields: `at`, `pid`, `parent`, `seq`, `last_ok`, `answered`, `fails_in_a_row`, `blocked_until`, `blocks_today`, `host_blocked`, `megabytes_today`, `last_error` (a class name), `configured`, `polls` ({cik: last good poll}). `host_blocked` is a list of netlocs, `[]` when none. It is written after every sweep (Tasks 8 and 10 add the other moments).
- The health row holds exactly spec 8.2's fields, sums over all companies for the window: `at`, `window_s`, `sweeps`, `sweep_s_median`, `sweep_s_max`, `requests`, `ok`, `not_modified`, `failed` (by kind: `timeout`, `http_5xx`, `http_403`, `http_429`, `map_403`, `bad_body`, `too_big`, `redirect`, `other`), `request_s_median`, `request_s_max`, `bytes` (wire), `decoded_bytes`, `megabytes_today` (wire), `companies`, `mapped`, `answered_min`, `poll_gap_max_s`, `new` (by class), `fresh`, `catchup`, `map_mismatch`, `too_big` (tickers), `skew_s_max`, `age_s_max`, `backoff_s`, `blocked` (null, "429", "403" or "day"). A ticker with no CIK is not polled and is counted in `companies`, not in `mapped`.
- Rows written in the first sweep of a process whose start found no heartbeat file carry `cold` true (a new machine: the report counts them apart, spec 4.1 last bullet).

- [ ] Add class `Sweeps(Feeds)`:

```python
    def test_a_sweep_asks_every_mapped_company_once_and_never_two_at_once(self):   # universe AAPL, KO, BRK-B; BRK-B has no CIK in the map
        out = self.feed().sweep()                                                    # the seam fails the test if it is entered while a call is open
        self.assertEqual(([a["cik"] for a in self.asked], out["companies"], out["mapped"], out["answered"]), (["0000320193", "0000021344"], 3, 2, 2))

    def test_the_heartbeat_after_a_sweep(self):
        b = journal.load_json("sec_feed.json")
        self.assertEqual(set(b), {"at", "pid", "parent", "seq", "last_ok", "answered", "fails_in_a_row", "blocked_until", "blocks_today", "host_blocked",
                                  "megabytes_today", "last_error", "configured", "polls"})
        self.assertEqual((b["seq"], b["answered"], sorted(b["polls"])), (1, 2, ["0000021344", "0000320193"]))

    def test_one_health_row_per_300_s_with_every_field(self):                       # 11 minutes of sweeps, every reply 1,000 wire and 9,000 decoded bytes
        rows = self.rows("sec_health.jsonl")
        self.assertEqual((len(rows), rows[0]["requests"], rows[0]["bytes"], rows[0]["decoded_bytes"], rows[0]["answered_min"], rows[0]["blocked"]),
                         (2, 10, 10000, 90000, 2, None))
        self.assertEqual(set(rows[0]["failed"]), {"timeout", "http_5xx", "http_403", "http_429", "map_403", "bad_body", "too_big", "redirect", "other"})

    def test_rows_of_a_start_without_a_heartbeat_are_marked_cold(self):             # first process: no sec_feed.json; second: one
        self.assertEqual([r.get("cold") for r in self.rows("sec_filings.jsonl")], [True, True, None])

    def test_slow_replies_stretch_the_sweep_and_every_company_is_still_asked_once(self):   # Review Focus 3
        # 74 mapped companies (self.ciks); three sweeps whose replies take 1.5 s each, then three whose replies take 2.5 s; AAPL gains a filing in every sweep from the second
        self.assertEqual(Counter(a["cik"] for a in self.asked), {cik: 6 for cik in self.ciks})
        h = self.rows("sec_health.jsonl")
        self.assertAlmostEqual(h[0]["sweep_s_max"], 120, delta=1)                     # each request on the next grid point after 1.5 s: 1.62 s apart
        self.assertEqual([r["kind"] for r in self.rows("sec_filings.jsonl") if "kind" in r], ["fresh", "fresh", "fresh", "catchup", "catchup"])
        self.assertGreaterEqual(h[-1]["poll_gap_max_s"], 239)                          # 3.24 s apart: a 240 s sweep, past fresh_gap_seconds
```

- [ ] Run `-k Sweeps`. Expected: `AttributeError: 'Feed' object has no attribute 'sweep'`.
- [ ] Implement.
- [ ] Run `-k Sweeps`: 5 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/secfeed.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): the SEC feed sweeps its companies one paced request at a time and records its health every five minutes`.

### Task 8: Failures, blocks and caps

**Kind:** BUILD. **Spec:** 2.2 (a: the map at a start; one map request a New York day), 2.4 (the daily guard), 2.7 (the whole table and its four bullets), 7.2 (rows "the reply's tickers ...; a 404" to "429 ...", "a 302 to another host (the seam)", "`max_daily_megabytes` crossed").

**Files:** Modify `aitrader/secfeed.py`, `tests/test_sec_feed.py` (class `Refusals`).

**Interfaces:** Consumes Tasks 6-7. Produces:

```python
def retry_after(value: str | None, now: datetime) -> float | None   # seconds, from either form; None when absent, negative or unreadable
def block_until(now: datetime, seconds: float) -> datetime            # now + seconds, never past the next New York midnight
def body_class(body: bytes | None) -> str                             # "json" | "html" | "empty" | "other"
Feed.note(self, place: str, error: str, status: int | None, body: bytes | None = None) -> None
    # one sec_errors.jsonl row per place, error and New York day: {"at", "place", "error", "status"}, and for a block "body_class" and "body_sha" (12 hex)
Feed.block(self, kind: str, netloc: str, seconds: float) -> None   # kind "429" | "403" | "day"; the heartbeat first, atomically; then the error row, the counts, the wait
Feed.may_ask(self, netloc: str) -> bool                            # False while blocked_until holds, that netloc is shut for the day, polling is stopped for the day, or the megabytes are over
Feed.period(self) -> float                                         # the sweep period now: sweep_seconds x slow_factor_after_block (after a block today) x 2^k, capped at backoff_max_seconds;
                                                                   # k = the sweeps in a row that ended with fails_in_a_row >= backoff_after_fails (spec 2.7: "doubles each sweep")
# Feed attributes blocks_today, megabytes_today, fails_in_a_row and host_blocked mirror the heartbeat's fields
Feed.map_due(self) -> bool                                         # tried_at older than cik_map_refresh_days, or a 404 row after built_at and tried_at older than one New York day
Feed.refresh_map(self) -> bool                                     # one request to tickers_url through request(); writes sec_ciks.json; tried_at moves even on a refusal
```

- What each answer does is spec 2.7's table. Plan rules where the table leaves a choice: a status with no row of its own (400, 401, 410, ...) and a 200 whose body is not the object are `bad_body`; a connection error is error class `connect` in the error row and `other` in the health row; after a block of either kind the pace is halved for the rest of the day (`slow_factor_after_block`); after a 403 wait one company is asked first and the sweep goes on only if it answers. A 404 leaves that CIK out for the rest of the process and, at a start, while a 404 row is newer than the map's `built_at`.
- `megabytes_today` sums `Reply.wire`, never `decoded`. The error row never holds an exception's text, a header or a URL.
- The heartbeat carries the day: a start adopts `blocked_until`, `blocks_today`, `host_blocked`, `megabytes_today` and `fails_in_a_row` only from a heartbeat whose `at` is of today's New York date (Review Focus 1).

- [ ] Add class `Refusals(Feeds)`. Its helpers drive the fake clock and the scripted seam as their names say: `periods()` (seconds between sweep starts), `beat()` (the heartbeat file), `map_requests_after(n)` (map requests made once start n has run), `map_requests_after_404(tried_days_ago)`, `seconds_without_a_request()`, `quiet_after_429(value)` (seconds with no request after a 429 with that `Retry-After`, or "midnight"), `period_after_429()`, `quiet_after_second_block()`, `writes_after_429` (the ordered list of writes), `feed_over(heartbeat)` (a feed started over that heartbeat file):

```python
    def test_retry_after_both_forms_and_the_cap_at_the_next_new_york_midnight(self):
        now = datetime(2026, 12, 1, 15, 0, tzinfo=timezone.utc)
        self.assertEqual([secfeed.retry_after(v, now) for v in (None, "120", "Tue, 01 Dec 2026 15:30:00 GMT", "soon", "-5")], [None, 120, 1800, None, None])
        self.assertEqual(secfeed.block_until(now, 10 * 86400), datetime(2026, 12, 2, 5, 0, tzinfo=timezone.utc))

    def test_timeouts_and_500s_skip_the_company_and_five_in_a_row_double_the_period_to_600(self):   # one company: 8 failures, then 200s
        self.assertEqual(self.periods(), [60, 60, 60, 60, 120, 240, 480, 600, 60])

    def test_three_html_200s_in_a_row_are_a_429_and_cut_json_is_bad_body(self):     # 200 "<html>" for AAPL, KO, MSFT; then 200 '{"filings": {'
        self.assertEqual(([e["error"] for e in self.rows("sec_errors.jsonl")][:4], self.beat()["blocked_until"] is not None), (["bad_body"] * 3 + ["http_429"], True))

    def test_too_big_never_blocks_and_nothing_oversized_is_parsed(self):            # 4 of 74 companies answer fail "too_big" (three on the decoded cap, one on the wire cap)
        self.assertEqual((self.beat()["blocked_until"], len(self.asked), self.parsed, self.rows("sec_health.jsonl")[0]["failed"]["too_big"]), (None, 74, 70, 4))

    def test_megabytes_today_are_wire_bytes_and_crossing_the_cap_stops_until_tomorrow(self):   # 74 companies; wire 1,100,000 and decoded 9,000,000 a reply; cap 3 (1 MB = 1,000,000 bytes)
        self.assertEqual((round(self.beat()["megabytes_today"], 3), len(self.asked)), (3.3, 3))
        self.assertEqual(self.rows("sec_health.jsonl")[-1]["blocked"], "day")
        self.clock.to("2026-12-02T13:10:00+00:00"); self.feed().sweep(); self.assertEqual(len(self.asked), 6)   # a new New York day: three more, then the cap again

    def test_a_404_leaves_the_company_out(self):
        self.assertEqual(([e["error"] for e in self.rows("sec_errors.jsonl")], [a["cik"] for a in self.asked]), (["map_mismatch"], ["0000320193", "0000021344", "0000021344"]))

    def test_one_map_request_a_new_york_day_at_most(self):                          # five starts in a day, the map lacking BRK-B; then a 404 and tried_at two days old
        self.assertEqual([self.map_requests_after(start) for start in range(5)], [1, 1, 1, 1, 1])     # the first start only, tried_at 8 days old
        self.assertEqual(self.map_requests_after_404(tried_days_ago=2), 1)

    def test_a_403_on_the_map_shuts_that_host_for_the_day_and_polling_goes_on_then_a_403_on_a_company_blocks_3600_s(self):
        self.assertEqual(([e["error"] for e in self.rows("sec_errors.jsonl")], self.beat()["host_blocked"], len([a for a in self.asked if "submissions" in a["url"]])),
                         (["map_403", "http_403"], ["127.0.0.1:8"], 3))
        self.assertEqual(self.seconds_without_a_request(), 3600)

    def test_429_with_each_retry_after_then_half_pace_and_a_second_block_ends_the_day(self):
        for value, quiet in ((None, 600), ("120", 600), ("Tue, 01 Dec 2026 15:30:00 GMT", 1800), ("864000", "midnight"), ("rubbish", 600)):
            self.assertEqual(self.quiet_after_429(value), quiet)                      # "midnight": until the next New York midnight
        self.assertEqual((self.period_after_429(), self.quiet_after_second_block()), (120, "midnight"))

    def test_the_block_is_in_the_heartbeat_before_anything_else(self):              # save_json, append and print wrapped in one ordered list
        self.assertEqual(self.writes_after_429[0], ("save_json", "sec_feed.json", True))   # (call, file, blocked_until set)

    def test_a_302_from_the_seam_is_not_followed(self):
        self.serve("0000320193", sec.Reply(302, None, 0, 0, {}, "redirect"))
        self.assertEqual((self.feed().poll("AAPL", "0000320193"), len(self.asked), self.rows("sec_errors.jsonl")[0]["error"]), ("redirect", 1, "redirect"))

    def test_a_block_row_keeps_the_body_class_and_12_hex_and_nothing_else(self):    # a 429 with an HTML body
        e = self.rows("sec_errors.jsonl")[0]
        self.assertEqual((set(e), e["body_class"], len(e["body_sha"])), ({"at", "place", "error", "status", "body_class", "body_sha"}, "html", 12))

    def test_todays_heartbeat_is_carried_over_and_yesterdays_counts_are_not(self):  # Review Focus 1
        today = {"at": "2026-12-01T16:00:00+00:00", "blocks_today": 1, "megabytes_today": 2.5, "host_blocked": ["127.0.0.1:8"], "fails_in_a_row": 2, "polls": {}}
        f = self.feed_over(today)                                                     # a new process at 16:01 UTC the same New York day; cap 3
        self.assertEqual((f.blocks_today, f.megabytes_today, f.fails_in_a_row, f.may_ask("127.0.0.1:8"), f.period()), (1, 2.5, 2, False, 120))
        f = self.feed_over({**today, "at": "2026-11-30T20:00:00+00:00", "blocked_until": "2026-12-01T04:59:00+00:00"})
        self.assertEqual((f.blocks_today, f.megabytes_today, f.fails_in_a_row, f.may_ask("127.0.0.1:8"), f.period()), (0, 0.0, 0, True, 60))
```

The key of the per-host rule is the URL's netloc (host and port): with the real config that is `data.sec.gov` or `www.sec.gov`; in these tests the two ports stand for them.

- [ ] Run `-k Refusals`. Expected: `AttributeError: module 'aitrader.secfeed' has no attribute 'retry_after'`.
- [ ] Implement.
- [ ] Run `-k Refusals`: 13 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/secfeed.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): the SEC feed slows down or stops on every refusal, writes a block before anything else and keeps the day's counts across a restart`.

### Task 9: The wire: the real `_get`, the child helper, the forms that ask once

**Kind:** BUILD. **Spec:** 2.3 (hosts, no redirects, the header), 2.6 (`Accept-Encoding`), 2.7 (the deadline, caps while streaming), 3.1 (the forms, the lock for forms that ask once, exit 78), 7.1 (`sec_child.py`, the wire class, the stub), 7.2 (the WIRE rows but the echo; "no contact ..."; the config row's exit 78).

**Files:** Modify `aitrader/sec.py` (`_get`), `aitrader/secfeed.py` (`run`, `git_lines`), `aitrader/__main__.py` (`sec-feed`), `tests/helpers/no_sec.py` (`sec._get` refused at import), `tests/test_sec_feed.py` (`SecStub`, `SecProcs`, class `WireCases`). Create `tests/helpers/sec_child.py`.

**Interfaces:** Consumes Tasks 6-8; `supervise.take_lock`, `supervise.load_cfg`; `engine_child.install_tripwire`; `test_supervise.Procs`. Produces:

```python
def _get(url: str, *, session: requests.Session, ua: str, s: dict, etag: str | None = None, modified: str | None = None) -> Reply   # never raises
Feed.session                                 # one requests.Session per process, built in Feed.__init__; None under --offline (no network object)
def run(a: argparse.Namespace) -> int        # every sec-feed form; returns 0, 3, 4 or 78
def git_lines(args: list[str]) -> list[str] | None   # the only git call of the feed (read-only); None when git fails; Task 11 uses it
# __main__: sec-feed --until HH:MM (default supervisor.until_ny; "24:00" is accepted and never reached) --supervised PID --once --map --dry-run
#                    --offline DIR --state-dir DIR --config FILE        (Task 10 adds --status, Task 11 --leak-check, Task 12 --history)
```

- `_get`: a host not in `s["allowed_hosts"]` gives `fail` "other" and opens no connection. Headers: `User-Agent` = `ua`, `Accept-Encoding: gzip, deflate`, and `If-None-Match` / `If-Modified-Since` when given. `session.get(url, headers=..., stream=True, allow_redirects=False, timeout=(connect, read))`, so that the polls share one connection (spec 2.4, 3.4: one connection; about 35,400 requests a day must not each open a TCP and TLS connection and a proxy tunnel); a body read to its end gives the connection back to the session (`r.raw.release_conn()`), and a cut, a deadline or a 3xx closes it. The tripwire guards `Session.request`, which `session.get` calls. A 3xx is `fail` "redirect" and its body is not read. The body is read with `r.raw.read1(65536, decode_content=False)`: wire bytes counted and cut past `max_wire_bytes`; decoded with `zlib` by `Content-Encoding` (gzip; deflate, falling back to raw deflate), decoded bytes counted and cut past `max_body_bytes` ("too_big"; the body is never held whole). A `threading.Timer` armed at `request_deadline_seconds` closes the response, so a slow body ends there ("timeout"). `requests` timeouts: "timeout"; connection errors: "connect"; anything else: "other". No exception's text is kept.
- `--until`: `HH:MM` New York time; "24:00" is accepted and means never (`strptime("%H:%M")` refuses it, so it is read before that), the value every loop a test starts gets.
- `run`: the contact (`sec.user_agent`) and `sec.settings` come first for every form that can send a request (the loop, `--once` with or without `--history`, `--map`, `--dry-run`): no usable contact prints `SEC feed: no contact configured, nothing is polled (<missing|malformed>)`, writes one `not_configured` error row per New York day and returns 78; an absent key of `REQUIRED` prints `SEC feed: the sec block lacks <key>, nothing is polled` and returns 78. Then the lock: `--once`, `--map` and `--dry-run` that find it held print `sec-feed: a feed holds the lock (pid <pid>); nothing sent` and return 0. `--once`: one sweep, one health row, the heartbeat, exit 0. `--map`: one request, `sec_ciks.json`. `--dry-run`: one sweep, no journal row, one JSON line of counts (the heartbeat is still written: a block must be kept). `--offline DIR`: replies from `DIR/submissions-CIK##########.json` and `DIR/company_tickers.json`, no lock, no network object built. With no map file nothing is polled and one line says so. `--state-dir` points `journal.STATE` there; `--config` reads that file with `supervise.load_cfg`.
- `tests/helpers/sec_child.py --state-dir DIR --config FILE [sec-feed options]`, in this order: (1) `ai-trader/` and `ai-trader/tests/` at the front of `sys.path`, from its own `__file__`; (2) `secfeed.git_lines` replaced by a function that lists the files under DIR for `ls-files` and gives [] for `log`; (3) `engine_child.install_tripwire(DIR + "/child.tripwire")`; (4) `sys.exit(aitrader.__main__.main(["sec-feed", "--state-dir", DIR, "--config", FILE, *options]))`.
- In the test module: `SecStub`, an `http.server.ThreadingHTTPServer` (daemon threads) on 127.0.0.1 port 0 in a thread, so that a request it holds never delays the next child's: `.answers` maps a path prefix to a list played in order, the last repeating, and a path takes the longest key that prefixes it (no key: 404). An answer is `(status, headers, body)`, a function of the request's headers that returns one (the echo scripts of Tasks 11-12), "slow" (the body one byte a second), "hang" (no answer until `.stop()`) or "reset" (the connection closed mid-body); `.seen` holds `(path, headers, body)` of every request; `.url`; `.stop()`. Module-level scripts: `DEFAULT_ANSWERS` = `{"/submissions/CIK0000320193": [(200, {}, AAPL_BYTES)], "/submissions/CIK0000021344": [(200, {}, KO_BYTES)], "/files/": [(200, {}, TICKERS_BYTES)]}`; `SLOW` = `{"/submissions/": ["slow", (200, {}, KO_BYTES)]}` (only the first request, AAPL's, is slow); `HANG` = `{"/submissions/": ["hang"]}`; `BOMB` = `{"/submissions/": [(200, {"Content-Encoding": "gzip"}, <gzip of 400,000,000 zero bytes, made once, in chunks, when the gzip test first needs it>)]}`; `QUICK` = `{"request_deadline_seconds": 3, "read_timeout_seconds": 2, "hang_seconds": 10}`. `class SecProcs(ts.Procs)` (`import test_supervise as ts`: the module, never the class by name): `setUp` starts `self.stub`, writes `cfg_for(self.tmp, ["AAPL", "KO"], base=self.stub.url, sweep_seconds=1)` (Task 6; the gap falls to its 0.5 s floor, so a two-company `--once` takes about half a second and not 30 s) and `write_map(self.state, {"AAPL": "0000320193", "KO": "0000021344"}, <now>)` (a fresh `tried_at`: no child makes a map request unless the test asks); `child(*options, contact="sentinel", answers=None, conf=None, config_without=None) -> Popen` (`sec_child.py`; first sets `self.stub.answers` to `answers`, or to `DEFAULT_ANSWERS` when it is None, so a child never meets the script an earlier child left; `conf=` keys merged over the `sec` block and `config_without=` a key left out, each in a config file of its own in `self.tmp`, never in the state directory; `env=no_phone.clean_env()` plus `AITRADER_SEC_CONTACT` unless `contact` is None; text pipes for stdout and stderr; appended to `self._started`); `sec_beat()` (the heartbeat file, `{}` when absent or unreadable); `files()` (every file under the state directory and its `.cache`); `tearDown` reads `self.state / "child.tripwire"` first, then `super().tearDown()` in try/finally, then asserts the file held no line.

- [ ] Add class `WireCases(SecProcs)` and one in-process test. `SecProcs` also gives `self.sentinel` (the contact the children get), `rows_of(name)` (a journal of the child's state directory) and `map_file()`; `AAPL_BYTES`, `KO_BYTES` and `TICKERS_BYTES` are the fixture files' bytes, `FIX` their folder:

```python
    def test_the_header_reaches_the_stub_and_only_there(self):
        self.assertEqual(self.child("--once").wait(timeout=30), 0)
        path, headers, _ = self.stub.seen[0]
        self.assertEqual((headers["User-Agent"], headers["Accept-Encoding"], self.sentinel in path), ("ai-trader-research-bot " + self.sentinel, "gzip, deflate", False))
        self.assertEqual([k for k, v in headers.items() if self.sentinel in v], ["User-Agent"])

    def test_a_302_to_a_second_stub_is_never_followed(self):
        other = SecStub(); p = self.child("--once", answers={"/submissions/": [(302, {"Location": other.url + "/x"}, b"")]})
        self.assertEqual((p.wait(timeout=30), other.seen, self.rows_of("sec_errors.jsonl")[0]["error"]), (0, [], "redirect"))

    def test_a_host_not_in_allowed_hosts_gets_no_connection(self):
        self.assertEqual((self.child("--once", conf={"allowed_hosts": ["127.0.0.2"]}).wait(timeout=30), self.stub.seen), (0, []))

    def test_a_gzip_body_that_decodes_past_the_cap_is_cut_while_streaming(self):    # BOMB: about 400 KB of gzip that decodes to 400,000,000 bytes
        p = self.child("--once", answers=BOMB, conf={"max_body_bytes": 1000000}); _, status, use = os.wait4(p.pid, 0); p.returncode = os.waitstatus_to_exitcode(status)
        self.assertEqual((p.returncode, self.rows_of("sec_errors.jsonl")[0]["error"]), (0, "too_big"))
        self.assertLess(use.ru_maxrss, 250000)                                         # KB: a whole decode would need 400 MB on top of the interpreter

    def test_a_body_sent_one_byte_a_second_ends_at_the_deadline(self):              # QUICK: deadline 3, read 2, hang 10; the KO request after it answers at once
        t0 = time.monotonic(); self.assertEqual(self.child("--once", answers=SLOW, conf=QUICK).wait(timeout=30), 0)
        self.assertEqual(([e["error"] for e in self.rows_of("sec_errors.jsonl")][:1], time.monotonic() - t0 < 9), (["timeout"], True))

    def test_without_a_usable_contact_nothing_is_asked_and_the_exit_is_78(self):
        for contact, word in ((None, "missing"), ("x y", "malformed"), ("café" + self.sentinel, "malformed")):
            p = self.child("--once", contact=contact); out, err = p.communicate(timeout=30)
            self.assertEqual((p.returncode, out.strip().endswith(f"({word})"), self.stub.seen), (78, True, []))
        self.assertEqual([e["error"] for e in self.rows_of("sec_errors.jsonl")], ["not_configured"])        # one row a New York day

    def test_a_config_without_one_of_the_seven_ends_every_asking_form_with_78(self):
        for key in ("accept_clock", "max_body_bytes"):
            for form in (("--once",), ("--map",), ("--dry-run",), ("--until", "24:00")):
                self.assertEqual(self.child(*form, config_without=key).wait(timeout=30), 78, (key, form))
        self.assertEqual(self.stub.seen, [])

    def test_once_takes_the_lock_and_lets_it_go_and_offline_builds_no_network_object(self):
        self.assertEqual([self.child("--once").wait(timeout=30) for _ in range(2)], [0, 0])
        before = len(self.stub.seen); self.assertEqual(self.child("--once", "--offline", str(FIX)).wait(timeout=30), 0)
        self.assertEqual(len(self.stub.seen), before)

    def test_map_writes_the_tickers_it_finds_with_one_request(self):
        self.assertEqual((self.child("--map").wait(timeout=30), len(self.stub.seen), sorted(self.map_file()["tickers"])), (0, 1, ["AAPL", "KO"]))

class Seam(no_sec.Case):
    def test_an_unstubbed_seam_raises(self):
        with self.assertRaises(AssertionError):
            sec._get("http://127.0.0.1:9/x", session=None, ua="x", s={})
        self.assertEqual(no_sec.TRIPPED, ["sec._get"]); no_sec.TRIPPED.clear()
```

- [ ] Run `-k WireCases` and `-k Seam`. Expected: `AttributeError: module 'aitrader.sec' has no attribute '_get'` (in the in-process test) and a `FileNotFoundError` for `sec_child.py`.
- [ ] Implement `_get`, `Feed.session`, `run`, `git_lines`, the `sec-feed` parser (the options above) and branch in `__main__.py` (`from .secfeed import run; return run(a)`), `sec_child.py`, and `aitrader.sec._get = refuse("sec._get")` in `no_sec.py`.
- [ ] Run both: 10 tests, `OK`, and no `child.tripwire` was left. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/sec.py ai-trader/aitrader/secfeed.py ai-trader/aitrader/__main__.py ai-trader/tests/helpers/no_sec.py ai-trader/tests/helpers/sec_child.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): sec-feed --once, --map and --dry-run over one guarded request function: allowed hosts only, no redirect, caps while streaming, a hard deadline`.

### Task 10: The loop: the lock wait, sliced waits, the parent, the watchdog, `--status`

**Kind:** BUILD. **Spec:** 3.1 (exit codes), 3.3 (the whole section), 3.4 (`nice`, `oom_score_adj`, no engine lock, no engine file read), 8.2 (the files), 8.3 (the daily lines), 7.2 (rows "a 429, and the process is killed at once", "a second feed ...", "`--once`, `--map`, `--dry-run` beside a live loop", "one request the seam holds open ...", "a 600 s back-off ...", "`--supervised` ...", "WIRE: `--supervised` ...").

**Files:** Modify `aitrader/secfeed.py`, `aitrader/__main__.py` (`--status`), `tests/test_sec_feed.py` (classes `Loops`, `Running`, `Status`).

**Interfaces:** Consumes Tasks 6-9. Produces:

```python
def loop(feed: Feed, until: str, supervised: int | None) -> int   # sweeps until --until, the parent's end or a signal; every sweep inside one try/except; 0
Feed.in_flight: float | None                                      # monotonic start of the request in progress, None between requests
def hung(feed: Feed, mono_now: float, hang_s: float) -> bool       # the watchdog's one test, run by its daemon thread every slice
def launch_window(day: date, cfg: dict) -> tuple[datetime, datetime]   # UTC: supervisor.watcher.engine_window_ny[0] to supervisor.until_ny on that New York date (zoneinfo)
def up_stretches(rows: list[dict], gap_s: float, ok=lambda r: True) -> list[tuple[datetime, datetime]]   # [at - window_s, at] of rows passing ok, joined over holes <= gap_s
def coverage(day: date, health: list[dict], cfg: dict) -> float   # the covered share (0-1) of launch_window(day): up_stretches(health rows with sweeps > 0 and
                                                                  # poll_gap_max_s <= fresh_gap_seconds, gap 0), cut to the window, over the window's length
def status(cfg: dict, env: Mapping[str, str], now: datetime) -> dict
    # read-only, no network, no lock: {"configured", "hb_age_s", "alive", "blocked", "blocked_until", "blocks_today", "megabytes_today", "new_today",
    #  "events_today", "ran_pct", "no_cik", "too_big", "map_mismatch", "missed", "lines"}; "configured" from sec.user_agent(env, ...)
LINES: dict[str, str]   # "base", "blocked", "day_cap", "not_configured", "no_cik", "too_big", "missed": spec 8.3's six sentences, character for character,
                        # and "day_cap", the plan's (Where the plan decides, 9): "מקור SEC עצר היום: הגיע לתקרת ההורדה היומית ({mb} MB). לא נוגע למסחר. כסף נייר"
# the nightly-index row of sec_filings.jsonl, written by Task 12 and read here:
#   {"v": 1, "at", "outcome": "index_check", "day", "listed", "in_journal", "missing": [accessions]}
```

- `Feed.wait_until` now tests, in every slice of every wait (the pacing gap, a back-off, a block, the megabytes stop, the day-long idle, a map with no company), `--until` and, under `--supervised`, whether `/proc/<PID>` is there, and returns False when either says so; `loop` then returns 0. A `--supervised` PID that is not alive at the start: one line, 0.
- The lock: `supervise.take_lock(state/sec_feed.lock, now)`; while it is held the loop tries again every `sleep_slice_seconds` for `lock_wait_seconds`, then prints `sec-feed: another feed holds the lock (pid <pid>): this one does not start (exit 3)` and returns 3.
- The watchdog fires only while one request has run for more than `hang_seconds`: it prints `sec-feed: one request ran for <n> s, leaving (exit 4)` and calls `os._exit(4)`. At the start of `run`: `os.nice(nice)`; `oom_score_adj` written to `/proc/self/oom_score_adj`, a refusal ignored. No SIGTERM handler: the default ends the process and frees the lock. An uncaught exception prints its class name only.
- The heartbeat: right after it takes the lock, `loop` reads today's heartbeat AGAIN (a feed that held the lock may have written `blocked_until` during the lock wait of up to `lock_wait_seconds`; spec 2.7 and 3.3), carries that over (a block is kept and honoured), and only then writes it once, before its first request, so that a loop that waits or idles from its first second still shows its pid; then after every sweep, every `heartbeat_wait_seconds` during any wait, and at once when a block starts.
- `status`: `ran_pct` = `coverage(today, today's health rows, cfg)`, and `{p}` in the base sentence is it x 100 rounded to a whole number. `lines` holds the base sentence, then every other sentence that applies, in this order: blocked, day_cap, no_cik, too_big, missed; with no usable contact in `env` the not-configured sentence alone. The blocked sentence applies when blocks stopped polling for the day (`blocks_today` reached `blocks_per_day_max`, or a second 403); `{status}` is the status of today's last block row in `sec_errors.jsonl`. The day_cap sentence applies when today's `megabytes_today` reached `max_daily_megabytes`; `{mb}` is `max_daily_megabytes`. Spec 2.4 asks that this stop be said in the daily line, and spec 8.3 gives it no sentence; the blocked one would name a status that does not exist and say "not known whether it was us" of the feed's own cap. `missed` is the newest `index_check` row with `missing`. `run` passes `os.environ`.
- `--status` joins the parser: it prints `status(...)` as one JSON object (`ensure_ascii=False`, so the Hebrew lines are copied as they are).

- [ ] Add the classes. `Loops(Feeds)` runs `loop` in-process on the fake clock with `alive(pid)` scripted (`hung_seen`, `loop_alive_at_the_end`, `ends_after_parent_goes()`, `opened` are what it records). `Running(SecProcs)` runs children: `started_loop(**child_kw)` (a supervised loop child; returns once the heartbeat names its pid, `wait_for(..., timeout=15)`), `supervised_loop(**child_kw)` (the same, and returns once the stub has seen its first request, so that the test acts while the first body is arriving), `end_parent_of(p)` and `kill_parent(p)` (the helper process its `--supervised` names is killed), `niceness(p)` (from `/proc/<pid>/stat`). `Status(Feeds)` writes fixture state (`self.now`; `self.health(at, **fields)`, a health row with `window_s` 300, `sweeps` 5 and `poll_gap_max_s` 60 unless given):

```python
class Loops(Feeds):
    def test_waits_longer_than_hang_seconds_never_look_hung(self):                  # a 600 s back-off, a 3,600 s block, the megabytes stop, a day-long idle
        self.assertEqual((self.hung_seen, self.loop_alive_at_the_end), ([], True))     # hung() asked at every slice of every wait

    def test_a_parent_that_is_gone_ends_the_loop_within_a_slice(self):              # in the pacing gap; during a 403 block; during the day-long idle
        self.assertEqual(self.ends_after_parent_goes(), [(0, 1.0)] * 3)                # (code, seconds after the parent went)

    def test_the_loop_opens_no_engine_file(self):                                   # builtins.open wrapped for two sweeps
        self.assertEqual([p for p in self.opened if Path(p).name.startswith(("news_", "uptime", "dash_", "portfolio"))], [])

class Running(SecProcs):
    def test_a_block_written_while_the_lock_is_held_is_kept_by_the_feed_that_takes_the_lock(self):
        # a helper holds sec_feed.lock and, while a second feed waits for it, writes blocked_until = now + 600 into
        # today's heartbeat, then lets go; the second feed takes the lock: its first heartbeat still carries that
        # blocked_until, and the seam records no request before it (the block is honoured)

    def test_a_second_feed_leaves_with_3_naming_the_holder_and_one_started_while_the_first_ends_takes_over(self):
        a = self.started_loop(); b = self.child("--until", "24:00")
        self.assertEqual((b.wait(timeout=40), f"pid {a.pid}" in b.stdout.read()), (3, True))
        self.end_parent_of(a); c = self.child("--until", "24:00")                      # a leaves within a slice of its parent; c is started at once
        self.wait_for(lambda: self.sec_beat().get("pid") == c.pid, timeout=30)

    def test_once_map_and_dry_run_beside_a_live_loop_send_nothing(self):
        self.started_loop(); n = len(self.stub.seen)
        for form in ("--once", "--map", "--dry-run"):
            p = self.child(form); out, _ = p.communicate(timeout=30)
            self.assertEqual((p.returncode, "a feed holds the lock" in out), (0, True), form)
        self.assertEqual([s for s in self.stub.seen[n:] if s[0].startswith("/files/")], [])     # the loop's map is fresh: any map request here came from --map

    def test_a_request_held_past_hang_seconds_ends_with_4_and_frees_the_lock(self):  # the deadline itself failed: deadline 60, read 50, hang 2; the stub hangs
        p = self.child("--until", "24:00", answers=HANG, conf={"request_deadline_seconds": 60, "read_timeout_seconds": 50, "hang_seconds": 2, "lock_wait_seconds": 62})
        self.assertEqual((p.wait(timeout=20), "leaving (exit 4)" in p.stdout.read()), (4, True))
        self.assertEqual(self.child("--once").wait(timeout=30), 0)

    def test_a_parent_that_goes_during_a_slow_body_ends_the_loop_after_the_deadline(self):   # SLOW and QUICK: deadline 3, read 2, hang 10
        loop = self.supervised_loop(answers=SLOW, conf=QUICK); self.kill_parent(loop)
        self.assertEqual((loop.wait(timeout=10), "exit 4" in loop.stdout.read()), (0, False)); self.assertEqual(self.child("--once").wait(timeout=30), 0)

    def test_a_429_then_kill_9_and_no_new_process_asks_before_blocked_until(self):  # killed as soon as the heartbeat holds the block, before the 600 s end
        loop = self.started_loop(answers={"/submissions/": [(429, {}, b"<html>")]})
        self.wait_for(lambda: self.sec_beat().get("blocked_until"), timeout=15); os.kill(loop.pid, signal.SIGKILL); loop.wait(timeout=10)
        n = len(self.stub.seen)
        self.assertEqual([self.child(f).wait(timeout=30) for f in ("--once", "--map", "--dry-run")], [0, 0, 0])
        self.started_loop(); time.sleep(3); self.assertEqual(len(self.stub.seen), n)

    def test_the_feed_writes_only_its_own_files_and_leaves_the_engines_lock_free(self):   # the state directory seeded with the engine's files
        seeded = {p.name: p.read_bytes() for p in self.state.iterdir()}
        loop = self.started_loop()
        with open(self.state / "news_engine.lock", "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)                              # would raise if the feed held it
        self.child("--map").wait(timeout=30); self.end_parent_of(loop)
        self.assertEqual({n: (self.state / n).read_bytes() for n in seeded}, seeded)
        self.assertLessEqual({p.name for p in self.state.iterdir()} - set(seeded) - {"child.tripwire"},
                             {"sec_filings.jsonl", "sec_health.jsonl", "sec_errors.jsonl", "sec_ciks.json", "sec_feed.json", "sec_feed.lock"})

    def test_nice_and_the_oom_score(self):                                          # read from /proc/<pid> of the running loop
        loop = self.started_loop()
        self.assertEqual(self.niceness(loop), min(19, os.nice(0) + 10))               # the oom score is 500 where the file takes it, else what it was

class Status(Feeds):
    def test_the_days_lines_as_the_close_slot_copies_them(self):                    # 12 new rows today, 3 of them event; health rows over the launch window
        self.assertEqual(secfeed.status(self.cfg, self.env, self.now)["lines"][0],     # but one 750 s hole: coverage 97.4%
                         "מקור SEC (רישום בלבד): 12 דיווחים חדשים היום, מהם 3 אירועים (8-K/6-K). רץ 97% מהשעות. כסף נייר")

    def test_each_other_sentence_when_it_applies(self):                             # a day-long stop after a 403; BRK-B unmapped; JPM too big; 2 missed on 2026-12-01
        self.assertEqual(secfeed.status(self.cfg, self.env, self.now)["lines"][1:], [
            "מקור SEC נחסם היום (403) ונעצר עד מחר. לא ידוע אם בגללנו. לא נוגע למסחר. כסף נייר",
            "מקור SEC: ל-BRK-B אין מספר חברה ב-SEC. כסף נייר", "מקור SEC: הקובץ של JPM גדול מהתקרה ולא נקרא. כסף נייר",
            "מקור SEC: 2 דיווחים מיום 2026-12-01 לא הופיעו אצלנו בכלל. כסף נייר"])
        self.assertEqual(secfeed.status(self.cfg, {}, self.now)["lines"], ["מקור SEC לא רץ היום: אין כתובת קשר בסביבה. כסף נייר"])

    def test_the_megabytes_stop_has_its_own_sentence(self):                         # today's heartbeat: megabytes_today 1500.4, no block
        cfg = cfg_for(self.tmp, ["AAPL", "KO"], max_daily_megabytes=1500)            # pinned: Task 17 sets the real cap
        self.assertEqual(secfeed.status(cfg, self.env, self.now)["lines"][1:],
                         ["מקור SEC עצר היום: הגיע לתקרת ההורדה היומית (1500 MB). לא נוגע למסחר. כסף נייר"])

    def test_the_launch_window_and_coverage(self):                                  # 2026-12-01 is in New York winter time
        day = date(2026, 12, 1)
        self.assertEqual(secfeed.launch_window(day, self.cfg), (datetime(2026, 12, 1, 13, 7, tzinfo=timezone.utc), datetime(2026, 12, 1, 21, 5, tzinfo=timezone.utc)))
        rows = [self.health("2026-12-01T13:12:00+00:00"), self.health("2026-12-01T13:17:00+00:00", poll_gap_max_s=151), self.health("2026-12-01T13:22:00+00:00", sweeps=0)]
        self.assertAlmostEqual(secfeed.coverage(day, rows, self.cfg), 300 / 28680)     # the launch window is 478 minutes
```

- [ ] Run `-k Loops`, `-k Running`, `-k Status`. Expected: `AttributeError: module 'aitrader.secfeed' has no attribute 'loop'`.
- [ ] Implement.
- [ ] Run the three: 14 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/secfeed.py ai-trader/aitrader/__main__.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): the sec-feed loop waits for the lock, follows its parent within a second, times only the request in progress and says its day in one Hebrew line`.

### Task 11: The contact never leaves memory: the privacy test and `--leak-check`

**Kind:** BUILD. **Spec:** 7.3 (the whole section), 7.2 (row "WIRE: a reply that echoes the request's User-Agent").

**Files:** Modify `aitrader/secfeed.py` (`leak_check`), `aitrader/__main__.py` (`--leak-check`), `tests/test_sec_feed.py` (class `Privacy`).

**Interfaces:** Consumes Tasks 6-10 (`git_lines`, `SecProcs`, `SecStub`). Produces:

```python
def leak_check(cfg: dict, env: Mapping[str, str]) -> int
    # the WHOLE value, case-insensitive, in: git_lines(["ls-files", "--cached", "--others", "--exclude-standard"]), every file under logs/ and .cache/,
    # state/sec_feed.json, git_lines(["log", "--format=%B", "@{u}..HEAD"]) (the last commit's message when there is no upstream);
    # prints "leak-check: {n} files hold the contact" and the file names only; 0 when n is 0, 1 otherwise, 78 with no variable
```

The parts of the real value (before and after "@") are never searched (spec 7.3: a common mail domain is in tracked files already).

- [ ] Add class `Privacy(SecProcs)`; `clean_of(texts)` asserts that none of three strings (the sentinel, its part before "@", its domain) is in any of the texts; `state_texts()` and `texts(paths)` read files as text; `captured` is the in-process stdout; `ECHO_BODY`, `ECHO_MALFORMED_HEADER`, `REDIRECT`, `OVERSIZED`, `RESET` are stub scripts (the first two put the request's User-Agent into the reply), `SLOW` and `QUICK` are Task 9's; `BROKEN` is a folder whose submissions file makes `--offline` raise:

```python
    def test_in_process_every_failure_of_the_table_leaves_no_trace(self):           # the seam raises an exception whose text holds the sentinel, answers 5xx, 403, 429,
        # a body and headers that echo the User-Agent, a redirect, too_big; stdout captured; every file under the state directory read
        self.clean_of([self.captured, *self.state_texts()])

    def test_over_the_wire_in_a_child_nothing_holds_the_contact(self):               # the real _get against the stub, the sentinel in the child's environment
        for answers in (ECHO_BODY, ECHO_MALFORMED_HEADER, REDIRECT, OVERSIZED, SLOW, RESET):
            p = self.child("--once", answers=answers, conf=QUICK); out, err = p.communicate(timeout=60)
            self.clean_of([out, err, *self.texts(self.files())])

    def test_the_forms_without_network_and_a_crashing_offline_run(self):
        for form in (("--once", "--offline", FIX), ("--once", "--offline", BROKEN), ("--status",), ("--map", "--offline", FIX), ("--leak-check",)):
            p = self.child(*map(str, form)); out, err = p.communicate(timeout=60)
            self.clean_of([out, err, *self.texts(self.files())])

    def test_the_sentinel_is_in_the_user_agent_header_and_nowhere_else_and_never_in_argv(self):
        p = self.child("--until", "24:00"); self.wait_for(lambda: self.stub.seen, timeout=30)
        self.assertNotIn(self.sentinel.encode(), Path(f"/proc/{p.pid}/cmdline").read_bytes())
        self.assertEqual({k for path, h, body in self.stub.seen for k, v in h.items() if self.sentinel in v} | {"path" for path, h, b in self.stub.seen if self.sentinel in path}, {"User-Agent"})

    def test_the_code_prints_no_exception_text_and_no_headers(self):                # a static search of sec.py and secfeed.py
        for name in ("sec.py", "secfeed.py"):
            text = (ROOT / "aitrader" / name).read_text(encoding="utf-8")
            self.assertEqual([m for m in (r"str\(e\)", r"repr\(e\)", r"%s.*\be\b\)", r"traceback", r"print\([^)]*headers") if re.search(m, text)], [], name)

    def test_leak_check_finds_the_whole_value_in_a_listed_file_and_prints_names_only(self):
        (self.state / "notes.txt").write_text("x " + self.sentinel.upper() + " y")     # git_lines replaced: the files under the state directory
        p = self.child("--leak-check"); out, _ = p.communicate(timeout=30)
        self.assertEqual((p.returncode, out.splitlines()[0], self.sentinel.lower() in out.lower()), (1, "leak-check: 1 files hold the contact", False))
        (self.state / "notes.txt").unlink(); self.assertEqual(self.child("--leak-check").wait(timeout=30), 0)
        self.assertEqual(self.child("--leak-check", contact=None).wait(timeout=30), 78)
```

- [ ] Run `-k Privacy`. Expected: `test_leak_check_finds_the_whole_value_in_a_listed_file_and_prints_names_only` fails with `IndexError` (the parser has no `--leak-check` before this task: the child exits 2 with `unrecognized arguments: --leak-check` on stderr and nothing on stdout). The forms test's `--leak-check` child exits the same way and is only scanned, so it passes until the form exists and is scanned again after. Any other failure is a leak in Tasks 6-10 and goes back to the task that owns that code.
- [ ] Implement `leak_check`, and `--leak-check` in the parser and in `run`.
- [ ] Run `-k Privacy`: 6 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/secfeed.py ai-trader/aitrader/__main__.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): sec-feed --leak-check, and a privacy test that follows the SEC contact through every failure and every output`.

### Task 12: The one-off history file and the nightly index

**Kind:** BUILD. **Spec:** 2.1 (the Atom request of step 2), 3.1 (`--once --history`), 4.4 (the two readings), 4.5, 5.2 ("missed"), 5.3 (the projection's inputs), 7.2 (rows "a year of made-up stamps", "the nightly index", "the index days").

**Files:** Modify `aitrader/sec.py` (`parse_index`), `aitrader/secfeed.py`, `aitrader/__main__.py` (`--history`), `tests/test_sec_feed.py` (class `Histories`, one test in `Privacy`). Create `tests/fixtures/sec/index-hand.idx` (written by hand in the layout of Task 1's record; no real file: it keeps the header's shape but not a header line that holds an address, which Task 1 recorded as such).

**Interfaces:** Consumes Tasks 6-11; `launch_window`, the `index_check` row (Task 10); `journal.session_hours`, `journal.calendar_covers`. Produces:

```python
def stamp_utc(raw: object, reading: str) -> datetime | None     # "utc": the stamp as true UTC; "et": its digits as New York wall time ("Z" dropped), zoneinfo date by date; None when unreadable
def outside_hours(stamps: list[str], reading: str, hours: list[str]) -> int   # weekday stamps (New York date) outside edgar_hours_ny under that reading
def edgar_days(after: date, through: date, closed: set[str]) -> list[date]   # weekdays in (after, through] not in closed
def index_day(rows: list[dict], today: date, s: dict) -> date | None
    # the oldest EDGAR business day with no index_check row, from the day after the last such row (with none: from today - seen_keep_days days, that day
    # included) to the previous EDGAR business day, never before today - seen_keep_days; None when index_enabled is false, index_url is null or none is left
def parse_index(text: str) -> list[dict]                         # sec.py: [{"cik": int, "form", "accession"}] in Task 1's recorded layout; the header lines and
                                                                 # any line that does not fit the layout are skipped
class History:                                                   # counts only; nothing a filing row or a prime row does not already make public
    def __init__(self, contact: str) -> None                     # the value of AITRADER_SEC_CONTACT, in memory, only to withhold an echo of it
    def add(self, ticker: str, cik: str, reply: Reply, parsed: dict, parse_s: float) -> None
    def write(self, extra: dict) -> None                         # state/sec_history.json, spec 4.5's items; extra: the index and Atom requests, ru_maxrss, CPU seconds
Feed.index_check(self) -> None                                   # at most one request a start, after the first full sweep, only when index_enabled and index_url
```

- `--once --history`: the sweep with a `History` fed per reply while it is in memory (no body is kept after its poll); then one request to the index of the previous EDGAR business day at `index_url` whatever `index_enabled` says ("not made" when it is null); then one request to `atom_url` (status, wire bytes, entries and the age of the newest entry, read with `defusedxml`), whose 403 is recorded and does not shut the host; then `write`. The only header text the file keeps, the `Cache-Control` text of spec 4.5, goes through `sec.clean(..., text_max_chars)` and is written as "withheld" when it holds the contact (case-insensitive): a reply that echoes the User-Agent there would otherwise put the address in a tracked file. `--history` joins the parser.
- Counts by session use only dates `journal.calendar_covers` holds; the rest go to an `uncovered` bucket. The span where a match is possible starts `match.before_seconds` after the start of `launch_window` (Task 10) and ends `news.health_log_seconds` before its end (09:07-16:00 today).
- The index row is Task 10's shape: `listed` the index's rows of the polled CIKs, `in_journal` those whose accession is in any filing or prime row. A refused or unreadable index answer writes no row: that day stays unchecked.
- `loop` calls `feed.index_check()` once, right after its first full sweep.
- If Task 1's record says `index_url` null: `parse_index` and `index_check` are not built, `History` records the index as "not made", and the four index tests below are left out; in `test_the_history_file_holds_every_item_of_spec_4_5` the expected `h["index"]["status"]` is then `"not made"` instead of 200.
- The `Feeds` helpers this task's tests use and no earlier task defined are added here: `self.beat()` (the same reader as Task 8's, moved up into `Feeds`) and `self.feed(**overrides)` (Task 6's `feed()` with keyword overrides merged into `self.cfg["sec"]`).

- [ ] Add class `Histories(Feeds)`; `made_up_year(written_as)` gives 2,000 weekday stamps inside 06:00-22:00 New York written in that clock; `history(**over)` runs `--once --history` in-process and returns the file; `asked_day(last, today, **over)` is the day `index_day` gives with that last `index_check` row (`None`: no such row), `index_enabled` true unless `over` says otherwise; `index_requests` counts index requests; the seam serves `index-hand.idx` for the index URL; `seed_journal(checked)` writes filing rows for four of `index-hand.idx`'s accessions and an `index_check` row for the day `checked`; `FIFTH` is the one accession of `index-hand.idx` the journal lacks:

```python
    def test_a_year_of_stamps_decides_the_clock_either_way(self):                    # 2,000 made-up weekday stamps, all inside 06:00-22:00 New York
        for written_as in ("utc", "et"):
            stamps = made_up_year(written_as)
            right, wrong = written_as, {"utc": "et", "et": "utc"}[written_as]
            self.assertEqual((secfeed.outside_hours(stamps, right, ["06:00", "22:00"]), secfeed.outside_hours(stamps, wrong, ["06:00", "22:00"]) > 500), (0, True))

    def test_each_date_has_its_own_offset(self):                                    # Review Focus 4: 2027-03-14 is the change
        self.assertEqual(secfeed.outside_hours(["2027-03-12T02:30:00.000Z", "2027-03-16T02:30:00.000Z"], "utc", ["06:00", "22:00"]), 1)   # 21:30 EST in, 22:30 EDT out

    def test_the_history_file_holds_every_item_of_spec_4_5(self):                   # --once --history over AAPL and KO; the stub answers index and Atom
        h = self.history()
        self.assertLessEqual({"built_at", "answered", "companies", "by_class_month", "by_item", "strict_mappable", "hour_histogram", "outside_hours",
                              "per_day", "headers", "skew_s_max", "atom", "index", "ru_maxrss_kb", "cpu_s"}, set(h))
        self.assertEqual(set(h["companies"]["AAPL"]), {"rows", "oldest_filed", "wire", "decoded", "parse_s", "forms"})
        self.assertEqual((set(h["outside_hours"]), h["index"]["status"], h["atom"]["status"]), ({"utc", "et"}, 200, 200))

    def test_index_null_is_not_made_and_an_atom_403_shuts_nothing(self):
        h = self.history(index_url=None, atom=403)
        self.assertEqual((h["index"], h["atom"]["status"], self.beat()["host_blocked"]), ("not made", 403, []))

    def test_the_nightly_index_names_the_one_filing_the_journal_lacks(self):        # the clock's day 2026-10-20; index-hand.idx: 5 rows of AAPL's and KO's CIKs
        self.seed_journal(checked="2026-10-16")                                        # 2026-10-19, the previous EDGAR day, is then the one day unchecked
        f = self.feed(index_enabled=True); f.sweep(); f.index_check()
        r = [x for x in self.rows("sec_filings.jsonl") if x.get("outcome") == "index_check"]
        self.assertEqual([(x["day"], x["listed"], x["in_journal"], x["missing"]) for x in r], [("2026-10-19", 5, 4, [FIFTH])])
        g = self.feed(index_enabled=True); g.sweep(); g.index_check(); self.assertEqual(self.index_requests, 1)   # a second start the same day

    def test_which_day_is_asked(self):                                              # edgar_closed of this config holds 2026-11-11
        self.assertEqual([self.asked_day(last, today) for last, today in (("2026-11-10", "2026-11-12"), ("2026-11-13", "2026-11-18"))], [None, "2026-11-16"])
        self.assertEqual(self.asked_day("2026-11-16", "2026-11-18"), "2026-11-17")   # the second start that day, after the first wrote its row
        self.assertEqual(self.asked_day(None, "2026-11-18"), "2026-11-04")            # no index_check row yet: the oldest day of the last seen_keep_days (14)
        self.assertEqual((self.asked_day("2026-11-13", "2026-11-18", index_enabled=False), self.asked_day("2026-11-13", "2026-11-18", index_url=None)), (None, None))

    def test_good_friday_is_an_edgar_day(self):                                     # Review Focus 4: no session on 2027-03-26, EDGAR open
        self.assertEqual(self.asked_day("2027-03-25", "2027-03-29"), "2027-03-26")

    def test_the_loop_asks_the_index_once_after_its_first_full_sweep(self):          # index_enabled; the loop runs on the fake clock to 11:05 New York
        secfeed.loop(self.feed(index_enabled=True), "11:05", None)
        self.assertEqual((self.index_requests, [a["cik"] for a in self.asked[:3]]), (1, ["0000320193", "0000021344", None]))
```

Add to class `Privacy` (Task 11) one case; `ECHO_HISTORY` is a stub script whose submissions replies carry the request's User-Agent as their `Cache-Control` and whose index and Atom replies carry it in their bodies:

```python
    def test_once_history_keeps_no_echoed_contact(self):
        p = self.child("--once", "--history", answers=ECHO_HISTORY); out, err = p.communicate(timeout=60)
        self.assertEqual((p.returncode, "sec_history.json" in {f.name for f in self.files()}), (0, True))
        self.clean_of([out, err, *self.texts(self.files())])
```

- [ ] Run `-k Histories` and `-k test_once_history_keeps_no_echoed_contact`. Expected: `AttributeError: module 'aitrader.secfeed' has no attribute 'outside_hours'`, and the child exits 2 (`unrecognized arguments: --history`).
- [ ] Implement; write `index-hand.idx` in the recorded layout (its header lines as Task 1 recorded them, the line that holds an address left out; 5 rows of the test universe's CIKs, invented accessions).
- [ ] Run `-k Histories`: 8 tests (4 when `index_url` is null), `OK`; `-k Privacy`: 7 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/sec.py ai-trader/aitrader/secfeed.py ai-trader/aitrader/__main__.py ai-trader/tests/test_sec_feed.py ai-trader/tests/fixtures/sec/index-hand.idx`; message `feat(ai-trader): sec-feed --once --history keeps a year of counts under both clock readings; the SEC's nightly index counts the filings the feed missed`.

### Task 13: `sec-report` I: the clock, coverage, errors, fresh share, missed, the engine beside it

**Kind:** BUILD. **Spec:** 3.4 (target 6, the pass), 4.4 (the four causes, the share rule), 5.2 (rows `delay_s`, fresh share, late, missed, coverage, error rate, the engine beside it), 5.3 (the projection), 7.2 (rows "the report, clock utc", "`accept_clock` unknown", "the engine pass", "fresh share").

**Files:** Modify `aitrader/secfeed.py`, `aitrader/__main__.py` (`sec-report`), `tests/test_sec_feed.py` (class `Numbers`).

**Interfaces:** Consumes Tasks 6-12 (`launch_window`, `up_stretches` and `coverage` of Task 10); `journal.read`, `journal.session_hours`. Produces:

```python
def delay_why(row: dict, clock: str, s: dict) -> tuple[float | None, str]   # "ok" | "et_clock" | "late_publish" | "negative" | "unreadable"
def engine_pass(day: str, base_day: str, rows: list[dict], cfg: dict) -> dict
    # {"engine": {"stop_quotes_missing": [d, b], "stop_gap_max_s": [d, b], "step_s_median": [d, b]}, "fails": [...], "notes": [...], "pass": bool}
def numbers(days: list[str], cfg: dict, base: str | None = None) -> dict   # every row of spec 5.2 but the match (Task 14), each with its n and its file
def render(nums: dict) -> str
def report(a: argparse.Namespace) -> int            # sec-report [--days N | --day YYYY-MM-DD | --history] [--base YYYY-MM-DD] [--state-dir DIR] [--config FILE];
                                                    # reads only; 0. --base: target 6's base day, the last full session before the feed's loop first ran
```

- `delay_why`: `t` = `stamp_utc(accepted_raw, clock)`, `delay` = `at` - `t`, `bound` = (`at` - `prev_poll`) + `publish_slack_seconds`; "ok" when 0 <= delay <= bound; "et_clock" when delay minus or plus that date's New York offset lies in [-`clock_tolerance_seconds`, bound + tolerance]; else "late_publish" above the range, "negative" under 0; "unreadable" when the stamp does not parse. With `accept_clock` "unknown", `delay_s`, late and the fresh share print "not calibrated". Always printed, whatever the clock (spec 1 target 1, 5.2 `delay_s`): the stamp-free bound over fresh rows with a `prev_poll`, `numbers()["bound"]` = `{"median", "max", "n", "file"}` of `at` - `prev_poll` in seconds, on the page as `bound at - prev_poll: median {m:g} s, largest {x:g} s, n {n}` (`no data, n 0` when there is none).
- Fresh share: fresh rows / filing rows whose stamp under `accept_clock` falls inside a stretch of the feed's own health rows (rows with `sweeps` > 0), always with numerator and denominator. Coverage (spec 5.2): `numbers()["coverage"]` = `{"mapped", "of", "answered_min", "days": [{"day", "pct"}], "file"}`: the last health row's `mapped` and `companies` (companies with a CIK out of 74), the smallest `answered_min` of the span's health rows with `sweeps` > 0, and each day's `coverage()` (Task 10); None where there is no row. Error rate: failed / requests by kind (`too_big` apart); blocks seen with their length (consecutive health rows with `blocked` set) and `body_class`; `map_mismatch`, `map_403`; wire megabytes a day. Missed: "missed filings: not measured" while no `index_check` row exists, never 0 on no data. `cold` rows are counted apart as "possibly re-logged after a new machine (an upper bound)".
- Engine pass: TP-Task 11's rule, computed here (not `dashpub.pass_numbers`): a day's rows are those of `news_health.jsonl` whose `at` lies inside that day's NYSE session (`journal.session_hours`); the sum of `stop_quotes_missing` not above the base day's; the largest non-null `stop_gap_max_s` not above the base day's plus `news.poll_seconds`; the median of `step_s_median` not above the base day's times `report.pass_step_ratio`; a null stop gap on either side is "not compared" in `notes`; a day with no rows fails as `no_rows:<day>`. Computed for each day of the report against `--base`; with no `--base` the engine line reads `the engine beside it: no base day (--base)`.
- `--history`: "history not measured" with no file; else spec 4.5's numbers and 5.3's projection: strict candidates in the covered span (event filings x inside the possible span on a session day x items that map to a strict class), per `report.projection_sessions` sessions (x `projection_sessions` / the span's sessions), and the months to `report.min_events` (`min_events` / (candidates / the span's months)): `{"per_sessions", "months_to_min_events"}`.

- [ ] Add class `Numbers(Feeds)`. Its helpers: `self.s` (the test's settings), `fresh(day, raw)` (a fresh row of that day with that stamp, `prev_poll` 15:00:00Z and `at` 15:01:00Z), `numbers(**fixture)` and `page(**fixture)` (`numbers` and `render` over a state written from the keywords: `clock`, `ok`/`of`, `health` (consecutive health rows inside 2026-12-01's launch window, each given as `(companies, mapped, answered_min)`)), `engine(day, missing, gap, step)` and `pass_for(day, ...)` (health rows inside that day's session, then `engine_pass` against 2026-11-30; keywords add rows outside the session or at a New York time), `nothing()` and `engine_only()` (an empty state; engine rows only), `rc(*argv)` (`__main__.main` on the test's state), `page_history(file)` and `projection()`:

```python
    def test_the_four_causes_under_utc(self):                                       # prev_poll 15:00:00Z, at 15:01:00Z: the bound is 180 s
        why = lambda raw, day="2026-12-01": secfeed.delay_why(self.fresh(day, raw), "utc", self.s)[1]
        self.assertEqual([why("2026-12-01T15:00:30.000Z"), why("2026-12-01T10:00:30.000Z"), why("2026-07-15T11:00:30.000Z", "2026-07-15"),
                          why("2026-12-01T13:00:00.000Z"), why("2026-12-01T15:02:00.000Z")], ["ok", "et_clock", "et_clock", "late_publish", "negative"])
        self.assertIn("2026-12-01T13:00:00.000Z", [r["accepted_raw"] for r in self.numbers(clock="utc")["late"]["rows"]])

    def test_an_unknown_clock_prints_not_calibrated_and_the_stamp_free_bound(self):  # ten fresh rows, each prev_poll 15:00:00Z and at 15:01:00Z
        page = self.page(clock="unknown", ok=9, of=10)
        for name in ("delay_s", "late", "fresh share"):
            self.assertIn(f"{name}: not calibrated", page)
        self.assertIn("bound at - prev_poll: median 60 s, largest 60 s, n 10", page)

    def test_coverage_names_the_mapped_companies_and_the_smallest_answered_min(self):   # three health rows of 2026-12-01: (companies, mapped, answered_min)
        c = self.numbers(clock="utc", health=[(74, 73, 73), (74, 73, 70), (74, 73, 73)])["coverage"]
        self.assertEqual((c["mapped"], c["of"], c["answered_min"], c["file"]), (73, 74, 70, "sec_health.jsonl"))

    def test_the_median_only_with_90_percent_ok(self):                              # 9 ok of 10; then 8 of 10
        self.assertIsNotNone(self.numbers(ok=9, of=10)["delay_s"]["median"])
        self.assertEqual((self.numbers(ok=8, of=10)["delay_s"]["median"], "the SEC's acceptance stamp is not calibrated" in self.page(ok=8, of=10)), (None, True))

    def test_a_stamp_that_cannot_be_read_is_counted_apart(self):                    # Review Focus 5
        self.assertEqual(secfeed.delay_why(self.fresh("2026-12-01", "2026-12-01 nonsense"), "utc", self.s), (None, "unreadable"))

    def test_the_fresh_share_counts_only_stamps_inside_an_up_stretch(self):         # feed health rows 14:00-15:00Z; stamps 13:30 catchup, 14:30 fresh, 14:40 catchup, 15:30 catchup
        self.assertEqual(self.numbers(clock="utc")["fresh_share"], {"fresh": 1, "of": 2, "share": 0.5, "file": "sec_filings.jsonl"})

    def test_the_engine_pass(self):                                                 # base 2026-11-30: 1, 41.0, 4.0
        self.engine("2026-11-30", 1, 41.0, 4.0)
        for day_numbers, fails in (((1, 61.0, 4.8), []), ((2, 61.0, 4.8), ["stop_quotes_missing"]), ((1, 61.1, 4.8), ["stop_gap_max_s"]), ((1, 61.0, 4.81), ["step_s_median"])):
            self.assertEqual(self.pass_for("2026-12-01", *day_numbers)["fails"], fails)
        self.assertEqual(self.pass_for("2026-12-01", None)["fails"], ["no_rows:2026-12-01"])
        r = self.pass_for("2026-12-01", 0, None, 4.0)
        self.assertEqual((r["pass"], r["notes"], r["engine"]["stop_gap_max_s"]), (True, ["not_compared:stop_gap_max_s"], [None, None]))
        self.assertEqual(self.pass_for("2026-12-01", 1, 61.0, 4.8, extra_outside_session=(9, 999.0, 99.0))["pass"], True)

    def test_on_the_early_close_day_rows_after_13_00_do_not_count(self):            # Review Focus 4: 2026-11-27; a row at 14:00 New York with stop_quotes_missing 5
        self.assertEqual(self.pass_for("2026-11-27", 1, 41.0, 4.0, extra_at_ny=("14:00", 5))["engine"]["stop_quotes_missing"][0], 1)

    def test_an_empty_state_and_a_day_without_the_feed_print_n_0(self):             # Review Focus 2
        for setup in (self.nothing, self.engine_only):
            setup(); page = self.page(clock="utc"); nums = self.numbers(clock="utc")
            self.assertEqual((nums["fresh_share"]["of"], nums["errors"]["requests"], nums["coverage"]["days"][0]["pct"]), (0, 0, 0.0))
            self.assertIn("missed filings: not measured", page); self.assertNotIn("Traceback", page)
        self.assertEqual(self.rc("sec-report", "--days", "14"), 0)

    def test_history_not_measured_and_the_projection(self):                         # a hand-made history: 120 strict candidates over 220 sessions and 11 months
        self.assertIn("history not measured", self.page_history(None))
        self.assertEqual((self.projection()["per_sessions"], self.projection()["months_to_min_events"]), (5.45, 2.75))   # per 10 sessions; months to 30
```

- [ ] Run `-k Numbers`. Expected: `AttributeError: module 'aitrader.secfeed' has no attribute 'delay_why'`.
- [ ] Implement; register `sec-report` in `__main__.py` (`from .secfeed import report; return report(a)`).
- [ ] Run `-k Numbers`: 10 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/secfeed.py ai-trader/aitrader/__main__.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): sec-report prints the feed's coverage, errors, fresh share, missed filings and the engine's numbers beside it; the SEC's stamp only once its clock is known`.

### Task 14: `sec-report` II: the match with Yahoo and the test of the lead

**Kind:** BUILD. **Spec:** 5.1 (the whole section), 5.2 (rows `lead_s`, the test of the lead, censored, unmatched, headlines explained), 5.3 (the registered test), 7.2 (rows "`sec-report` on a fixture set", "one handover at 10:48", "the test of the lead").

**Files:** Modify `aitrader/secfeed.py`, `tests/test_sec_feed.py` (class `Match`).

**Interfaces:** Consumes Task 13; `supervise.read_rows` (the uptime log); `journal.read` (`news_seen_log.jsonl`, `news_scores.jsonl`, `news_health.jsonl`). Produces:

```python
def yahoo_rows(seen: list[dict], scores: list[dict]) -> tuple[list[dict], list[dict], int]
    # (seen rows; scored rows with "first_seen" taken from their seen row, joined by scores.id = seen.key; the count of scores rows with no seen row)
def bridged(hole: tuple[datetime, datetime], uptime: list[dict], cfg: dict) -> tuple[bool, float | None]   # spec 5.1's five parts; (bridged, seconds exit -> up)
def engine_stretches(health: list[dict], uptime: list[dict], cfg: dict) -> list[dict]   # {"start", "end", "handovers": [{"exit", "up", "s"}]}; holes bridged where bridged() says so
def match(filing: dict, yahoo: tuple, stretches: list[dict], first_start: datetime | None, cfg: dict) -> dict
    # {"strict": {"outcome", "lead_s", "t", "why", "across_handover"}, "loose": {...}, "stale_in_window": int}
    # outcome: "matched" | "unmatched" | "censored" | "no_class" (strict only: no item maps to a class); why: "first_hour" | "after_last_row" | "break"
def lead_test(leads: list[tuple[str, float]], rep: dict) -> dict
    # leads = (New York day, lead_s); {"n", "no_test": True} under min_events; else {"n", "p", "lo", "hi", "sign_pass", "boot_pass", "pass"}
```

- One Yahoo clock: the seen row's `first_seen`, for the strict match as for the loose one. Candidates: the same ticker, `published` no earlier than `at` - `match.before_seconds`, `first_seen` no later than `at` + `match.after_seconds`. Strict: the earliest scored candidate whose headline matches the `KEYWORDS` class of one of the filing's items through `match.item_classes`. Loose: the earliest candidate of any outcome.
- Censoring before matching, by spec 5.1: "matched" needs one engine stretch (bridged holes included) from `at` - `before_seconds` to the candidate's `first_seen`; "unmatched" needs one from that start to `at` + `after_seconds`; everything else is "censored", with `why` and `t` (New York time) by spec 5.2's three categories, in this order: "first_hour" when `at` is within `before_seconds` after the day's first engine start (the start of its first stretch), `t` None; "after_last_row" when the stretch the window falls out of is the day's last (the earliest candidate, or with none the window's end, comes after the day's last health row), `t` = that row's `at`; "break" for every other, a window that crosses a hole that is not bridged, which takes in every filing in the hour after a restart that is not a bridged handover, `t` = the end of the stretch before that hole. A matched candidate first seen within `engine_gap_seconds` after a bridged `up` is `across_handover`.
- `lead_test`: (a) the exact two-sided sign test of `lead_s` > 0 against one half, leads of 0 dropped, `p` = min(1, 2 x P(X >= max(pos, neg))) with `math.comb`, passed at `p` < `sign_alpha`; (b) `boot_draws` resamples of whole New York days with `random.Random(boot_seed)`, the median of each draw's pooled leads, `lo` and `hi` the k-th smallest with k = floor(q x (draws - 1)) for q = (1 - `boot_level`) / 2 and 1 - q; passed when `lo` > 0. Both must pass.
- The page adds: per filing kind of match, `lead_s` median, quartiles (only from n >= `report.quartile_min_n`), the share above 0 and n, split by item class and by "regular session / before the open"; the test of the lead, below `report.min_events` as `the test of the lead: n = {n}, under {min_events}: no test` (spec 5.2); the censored count with the sentence that it biases the median down and its three categories; each day's handovers, bridged or not, with the seconds from `exit` to `up`; the count of `across_handover` leads and the median without them; the poll handicap, `poll handicap: {x:g} s in Yahoo's favour, not subtracted` with x = (`sweep_seconds` - `news.poll_seconds`) / 2 (20 s today), printed and not subtracted; the stale rows in each window; headlines explained (scored headlines with a score above `buy_min_score` or at or under `sell_on_score_at_most` that had an event filing of the same ticker with `at` in [`first_seen` - `after_seconds`, `first_seen` + `before_seconds`]).

- [ ] Add class `Match(Feeds)`. Fixture day D = 2026-12-01 (EST), New York times; engine health rows every 300 s from 08:12:00 to 16:02:00 with `steps` 15, none with `at` in (14:00:00, 14:25:00) (a break: the last row before it is 13:57:00, the first after it 14:27:00, which covers 14:22:00 on); no uptime log unless a test says so. Helpers: `matches(day)` (`match` for every fresh event filing of that day, by ticker), `page_line(name)`, `outcomes(**variant)` (the two filings of the handover test: outcome, `lead_s`, `across_handover`), `numbers()`, `page(clock)`, `lead_numbers(n)` (the strict lead line over n matched filings), `self.seen` and `self.scores` (the fixture's Yahoo rows). Fresh event filings:

| ticker | `at` | items | Yahoo (seen row: `published`, `first_seen`, `outcome`; scores row: headline, `score`, `logged_at`) |
|--------|------|-------|-------------------------------------------------------------------------------------------|
| AAPL | 10:00:00 | 2.02 | 09:59:00, 10:03:00, scored; "Apple results top estimates", 9, 10:09:00 |
| MSFT | 11:00:00 | 5.02 | 10:50:00, 10:51:00, scored; "Microsoft CFO steps down", 5, 10:52:00 |
| NVDA | 09:30:00 | 1.01 | none |
| TSLA | 09:50:00 | 2.02 | 09:25:00, 10:00:00, stale; no scores row |
| GOOGL | 15:55:00 | 2.02 | none |
| META | 14:50:00 | 5.02 | 15:20:00, 15:30:00, scored; "Meta CEO to step down", 5, 15:31:00 |
| AMZN | 08:30:00 | 2.02 | none |
| WMT | 09:45:00 | 8.01 | none |

Two Yahoo rows whose ticker files nothing that day: KO, 11:30:00, 11:31:00, scored; "Coca-Cola raises dividend", 10, 11:32:00; and JPM, 12:00:00, 12:01:00, scored; "JPMorgan faces probe", 1, 12:02:00. With `buy_min_score` 8 and `sell_on_score_at_most` 2, the headlines at or beyond the action lines are AAPL's (9), KO's (10) and JPM's (1); only AAPL has an event filing in its window.

```python
    def test_the_fixture_day(self):
        got = self.matches("2026-12-01")
        self.assertEqual({t: (m["strict"]["outcome"], m["strict"].get("lead_s"), m["loose"]["outcome"], m["loose"].get("lead_s")) for t, m in got.items()}, {
            "AAPL": ("matched", 180, "matched", 180), "MSFT": ("matched", -540, "matched", -540), "NVDA": ("unmatched", None, "unmatched", None),
            "TSLA": ("unmatched", None, "matched", 600), "GOOGL": ("censored", None, "censored", None), "META": ("censored", None, "censored", None),
            "AMZN": ("censored", None, "censored", None), "WMT": ("no_class", None, "unmatched", None)})
        self.assertEqual([(got[t]["strict"]["why"], got[t]["strict"]["t"]) for t in ("GOOGL", "META", "AMZN")],
                         [("after_last_row", "16:02:00"), ("break", "13:57:00"), ("first_hour", None)])
        x = (self.cfg["sec"]["sweep_seconds"] - self.cfg["news"]["poll_seconds"]) / 2
        self.assertEqual((got["TSLA"]["stale_in_window"], self.page_line("handicap")), (1, f"poll handicap: {x:g} s in Yahoo's favour, not subtracted"))
        self.assertEqual(self.page_line("no test"), "the test of the lead: n = 2, under 30: no test")   # AAPL and MSFT, the strict matches

    def test_a_handover_bridged_only_by_its_uptime_rows(self):                       # rows to 10:45:00, the next at 10:53:50 (window 300); marks every minute with hb 5; exit "planned" at 10:48:00
        # a 10:30 AAPL filing whose candidate is first seen at 11:00; a 10:47 MSFT filing whose candidate is first seen 20 s after the up row
        self.assertEqual(self.outcomes(up_after_s=50), [("matched", 1800, False), ("matched", 130, True)])
        for variant in ({"up_after_s": 200}, {"no_uptime_log": True}, {"up_after_s": 50, "hang_in_hole": True}):
            self.assertEqual([o[0] for o in self.outcomes(**variant)], ["censored", "censored"], variant)

    def test_the_test_of_the_lead(self):
        rep = self.cfg["sec"]["report"]
        self.assertEqual(secfeed.lead_test([("2026-12-01", 5.0)] * 29, rep), {"n": 29, "no_test": True})
        days = [f"2026-12-{d:02d}" for d in range(1, 13)]
        up = secfeed.lead_test([(days[i % 12], 10.0 + i) for i in range(30)], rep)
        self.assertEqual((up["sign_pass"], up["boot_pass"], up["pass"]), (True, True, True))
        half = secfeed.lead_test([(days[i % 12], (10.0 + i) * (-1) ** i) for i in range(30)], rep)
        self.assertEqual((half["sign_pass"], half["boot_pass"]), (False, False))
        self.assertEqual(secfeed.lead_test([(days[i % 12], (10.0 + i) * (-1) ** i) for i in range(30)], rep), half)

    def test_scores_rows_join_by_id_and_keep_the_seen_clock(self):                  # the AAPL scores row's logged_at is 6 minutes after first_seen
        seen, scored, orphans = secfeed.yahoo_rows(self.seen, self.scores + [{"id": "nokey", "symbol": "AAPL", "headline": "x", "logged_at": "2026-12-01T16:00:00+00:00"}])
        self.assertEqual(([s["first_seen"] for s in scored if s["symbol"] == "AAPL"], orphans), (["2026-12-01T15:03:00+00:00"], 1))

    def test_headlines_explained(self):                                             # AAPL 9, KO 10, JPM 1 are at or beyond the lines; only AAPL has an event filing in its window
        self.assertEqual(self.numbers()["explained"], {"with_filing": 1, "of": 3, "file": "news_scores.jsonl"})

    def test_lead_numbers_print_under_an_unknown_clock(self):
        self.assertIn("lead_s strict: median", self.page(clock="unknown"))

    def test_one_and_three_leads_have_no_quartile_range(self):                      # Review Focus 2
        for n in (1, 3):
            self.assertEqual((self.lead_numbers(n)["n"], self.lead_numbers(n)["quartiles"]), (n, None))
```

- [ ] Run `-k Match`. Expected: `AttributeError: module 'aitrader.secfeed' has no attribute 'yahoo_rows'`.
- [ ] Implement.
- [ ] Run `-k Match`: 7 tests, `OK`. Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/aitrader/secfeed.py ai-trader/tests/test_sec_feed.py`; message `feat(ai-trader): sec-report matches each 8-K and 6-K with Yahoo inside the engine's uptime, bridges planned handovers from the uptime log and registers the test of the lead`.

### Task 15: Land rollout step 1 (the code)

**Kind:** OPS - the owner's main chat session. **Spec:** 9, 10 step 1, 11 ("Step 1 of section 10 lands when ...").

- [ ] Preconditions: Tasks 3-14 committed on `secfeed-build`; S-Task 20's landing on the live branch (Task 1's `take_lock` grep).
- [ ] After 16:05 New York, in the feed clone: cut the landing branch at Task 14's commit (the cut point), fetch and merge the live branch into it. A code and config landing: gate steps 1-3 of Global Constraints, no sweep. `git diff --stat origin/<branch>..HEAD` names the files; expected and to be stated by the critic: files of the owner's list in the diff: none (`config.json` only by the new `sec` block and the removal of the top-level `sec_user_agent`; no key of `risk`, `signals` or `costs`). The critic also runs `grep -rn "sec_user_agent\|\[\"sec\"\]\|state/sec_\|sec_filings" aitrader/` and says that only `sec.py` and `secfeed.py` hit. The adversarial review starts with the privacy test (Task 11) and the wire cases (Task 9). Proof, kept in the session log: the suite's last line, the review's verdict, the critic's PASS with its sentence about the list.
- [ ] `git push origin HEAD:<branch>` from the landing branch; then the live branch is merged back into `secfeed-build`. Nothing starts the feed.
- [ ] If step 0 is done: the `--leak-check` one-time task of Task 2.
- [ ] Undo (spec): `git revert` the landing's commits in the feed clone and land the revert.

### Task 16: Rollout step 2: first contact with the SEC, and the measurements

**Kind:** OPS - the owner's main chat session; the owner says yes to two one-time tasks in the trader session. **Spec:** 2.1 (the Atom request), 2.2, 4.4, 4.5, 10 step 2, 13 (facts 1-9, 13, 15).

- [ ] Preconditions: Task 15 has landed; step 0 answered "set"; a close has passed since the landing.
- [ ] The trader session's checkout holds the landing: its next pushed state commit descends from it (`git merge-base --is-ancestor <landing> <that commit>` exits 0), or each task's prompt begins with `git fetch origin <branch> && git merge --no-edit origin/<branch> && ` (TP-Task 14).
- [ ] Task one, after the close, on the owner's word: `(cd ai-trader && python3 -m aitrader sec-feed --map; python3 -m aitrader sec-feed --once --history; python3 -m aitrader sec-feed --leak-check; grep MemTotal /proc/meminfo)`, one subshell, as ONE Bash call with timeout 300000 ms, answering with the output only.
- [ ] Task two, set at least 10 minutes after task one: `(cd ai-trader && python3 -m aitrader sec-feed --once; python3 -m aitrader sec-report --history; python3 -m aitrader sec-feed --leak-check)`, the same way. Two tasks, never one call that sleeps.
- [ ] Read both back with `list_events`; the files (`state/sec_ciks.json`, `sec_history.json`, `sec_filings.jsonl`, `sec_health.jsonl`, `sec_errors.jsonl`) from the trader session's next pushed state commit. Proof (spec step 2): 74 of 74 tickers mapped or the missing ones named; 74 answered; no 403 and no 429; `sec_history.json` with every item of spec 4.5; prime rows only on the first run and only new filings on the second; `--leak-check` 0 both times.
- [ ] If the map is refused, or any company answers 403 or 429: the step stops there, and nothing is tried under another identity or route. First `get_environment` on the trader's environment: when its network access is limited and the refused host is not among its allowed hosts, the 403 is the outbound proxy's, not the SEC's (spec 2.7); the owner is asked Task 2's network question, and on his א the hosts are added by a card and this task runs again on a later day; question 5 is not asked for it. Otherwise the owner is told in one message, with the error row's `status` and `body_class`, and asked question 5 (Open owner decisions). A 403 on the one Atom request does not stop the step: it is recorded, and option ד of question 2 is off the table.
- [ ] Into "Baseline record" and into the spec as a last section "Step 2 measurements" (counts only): the largest wire size, decoded size and row count and whose they are; the four banks' sizes against the rest; peak `ru_maxrss` and `MemTotal`; CPU seconds for the sweep; the two outside-hours counts; the headers sent (`ETag`, `Last-Modified`, `Age`, `Cache-Control`, `Content-Length`, `Content-Encoding`) and the largest `skew_s`; the Atom result; the index result; filings a day by class (the `offering` share) and by company; the share of last year's filings outside 08:07-16:05; the projection of spec 5.3. `git add` the spec and this plan; message `trader: SEC feed step 2 - first contact measurements`; fetch, merge, push.
- [ ] Undo (spec): nothing runs afterwards; the files stay.

### Task 17: Step 2's config commit, and questions 1-3

**Kind:** OPS - the owner's main chat session, with one BUILD edit; the owner answers up to three questions. **Spec:** 2.4 (the caps), 4.4 (the clock), 5.2 ("missed"), 8.1 (the config-only commit), 12 questions 1-3.

- [ ] Question 2 first, one message, with step 2's numbers (requests a day, wire megabytes a day, the largest reply, the Atom answer): the spec's four options and its recommendation (ד when the Atom request was accepted and fresh, else א). On ב or ג: `sweep_seconds` becomes 30 or 120 in the edit below. On ד: this plan stops after this task; the Atom trigger becomes a backlog item for a new spec section, and Tasks 18-21 wait for it. Then question 3, with the `offering` share (recommendation א, or ג when offering rows are most of the journal; ב or ג means a conditional BUILD task written into this plan then). Then question 1, with the share of last year's filings outside the launch window (recommendation א).
- [ ] The values, by these rules, each cited in the commit message: `accept_clock` = the reading whose outside-hours count is at most 1% of the weekday stamps while the other's is at least ten times as large, else "unknown"; `max_wire_bytes` = twice the largest measured wire size, rounded up to the next 1,000,000; `max_body_bytes` = twice the largest decoded size, rounded up to the next 10,000,000, provided the peak `ru_maxrss` is under 10% of `MemTotal` (otherwise stop and tell the owner: the feed would press on the engine's memory); `max_daily_megabytes` = 1.5 x one sweep's measured wire megabytes x the sweeps of the launch window at `sweep_seconds`, rounded up to the next 100; `index_enabled` true only when the index request answered 200 with a file whose rows were read and whose rows of the 74 CIKs were counted.
- [ ] BUILD edit (an implementer subagent, the two lines of Global Constraints verbatim in its prompt): those keys of `config.json` `sec` and nothing else; no code changes (the seven have no fallback, Task 3). On answer ב or ג, `sweep_seconds` is not one of the seven: the same edit also sets `SEC["sweep_seconds"]` in `tests/test_sec_feed.py` (the `Block` test pins the table) and the `sweep_seconds` fallback in `sec.DEFAULTS` when `DEFAULTS` holds it (the fallback test); the tests' own configs pin 60 (`cfg_for`, Task 6), so nothing else moves. Whole suite: `OK`. Commit `git add ai-trader/config.json` (with `ai-trader/tests/test_sec_feed.py` and `ai-trader/aitrader/sec.py` on ב or ג); message `trader(config): SEC feed caps, acceptance clock and index switch from the step-2 measurement` with the two clock counts and the measured maxima in its body (and the owner's answer to question 2 on ב or ג).
- [ ] Land it: the cut point is that commit; a config landing, gate steps 1-3 (a code and config landing on ב or ג); files of the owner's list in the diff: none (`config.json` only inside `sec`).
- [ ] Undo: `git revert` that commit and land the revert.

### Task 18: The slot lines: the feed's list, the close slot's two lines, the SKILL paragraph

**Kind:** BUILD. Dispatched after TP-Tasks 15-16 have landed, Task 17 has landed and question 2 was answered א, ב or ג. **Spec:** 3.2 (the line, its shape, `launch_prefix`), 8.3 (the close slot), 8.4 (the paragraph), 11 (collisions 1, 2 and 9).

**Files:** Modify `tests/helpers/no_dash.py` (`launch_prefix`), `skills/trader/slots/news-watch.md`, `skills/trader/slots/close.md`, `skills/trader/SKILL.md` (a new section 3ד; one sentence of 3ב), `tests/test_slot_files.py` (constants and class `SecLines`), `tests/test_sec_feed.py` (class `LaunchLine`).

**Interfaces:** Consumes `no_dash.launch_prefix` (TP-Task 10), `LAUNCH`, `STEP`, `END` and `CFG` of `tests/test_slot_files.py` (TP-Task 15), `sec-feed --status` and `--leak-check` (Tasks 10-11). Produces:

```python
def launch_prefix(commands: str, guard: bool = False, folder: str = "ai-trader", guard_var: str = "AITRADER_DASH_URL", log: str = ".cache/dash_publish.log") -> str
# tests/test_slot_files.py
SEC_LOOP = "python3 -u -m aitrader sec-feed --until 16:05 --supervised $$"
SEC_LAUNCH = no_dash.launch_prefix(SEC_LOOP, guard=True, guard_var="AITRADER_SEC_CONTACT", log=".cache/sec_feed.log")
SEC_STEP = "3"            # "0": no slot file starts the feed (the undo, and step 5); "3": the feed's list right after the publisher's
SEC_STATUS = "(cd ai-trader && python3 -m aitrader sec-feed --status)"
SEC_LEAK = "(cd ai-trader && python3 -m aitrader sec-feed --leak-check)"
```

- `news-watch.md`, in the step for action `launch`: the prefix is the publisher's list, then `SEC_LAUNCH`, then `launch.command` exactly as `--status` printed it, as ONE tracked background command; when the publisher's `STEP` is "0", `SEC_LAUNCH` alone.
- `close.md`: `SEC_STATUS` where the daily summary is written, with "copy each text of `lines` into the daily summary unchanged"; `SEC_LEAK` before `END` (when present), before `slot-done close` and before the sync block and its state commit (`git add` / `git commit`), with "exit 1: do not commit the state, tell the owner in chat; 0 or 78: go on". If the closing block spells the state commit otherwise than `git commit` (Task 1's record), the test anchors on that spelling.
- SKILL 3ד, in Hebrew, says every point of spec 8.4 (what `sec-feed` is; the address is never shown, and the forbidden commands by name; the only check; never copied, `SEC_USER_AGENT` named; no session calls the SEC by hand; the log and `--status`; exit codes 0, 3, 78 nothing and 4 told at the next slot's summary; a block: nothing tried around it, two days in a row to the owner in chat; `--leak-check` in the close slot). The ban paragraph of 3ב names both side processes of the launch prefix as its one exception (`dash-publish`, 3ג; `sec-feed`, 3ד); the parent itself is never started with `&`.

- [ ] Add class `SecLines` to `tests/test_slot_files.py` and class `LaunchLine` to `tests/test_sec_feed.py`:

```python
class SecLines(unittest.TestCase):
    def test_the_feeds_start_line_as_the_trader_session_will_run_it(self):
        self.assertEqual(SEC_LAUNCH, '([ -n "$AITRADER_SEC_CONTACT" ] && cd ai-trader && mkdir -p .cache && exec >> .cache/sec_feed.log 2>&1 < /dev/null'
                                     " && python3 -u -m aitrader sec-feed --until 16:05 --supervised $$ &); ")
        self.assertIn(f'--until {CFG["supervisor"]["until_ny"]} ', SEC_LAUNCH)
        self.assertEqual(no_dash.launch_prefix("x", guard=True), '([ -n "$AITRADER_DASH_URL" ] && cd ai-trader && mkdir -p .cache && exec >> .cache/dash_publish.log 2>&1 < /dev/null && x &); ')

    def test_the_watchdog_starts_the_feed_right_after_the_publisher_and_nowhere_else(self):
        t = (SLOTS / "news-watch.md").read_text(encoding="utf-8"); n = 0 if SEC_STEP == "0" else 1
        self.assertEqual((t.count(SEC_LAUNCH), t.count("sec-feed --until")), (n, n))
        if n and STEP != "0":
            self.assertEqual(t.count(LAUNCH[STEP] + SEC_LAUNCH), 1)
        self.assertEqual([f.name for f in SLOTS.glob("*.md") if f.name != "news-watch.md" and "sec-feed --until" in f.read_text(encoding="utf-8")], [])

    def test_the_close_slot_says_the_day_and_checks_for_a_leak_before_its_state_commit(self):
        c = (SLOTS / "close.md").read_text(encoding="utf-8")
        self.assertEqual((c.count(SEC_STATUS), c.count(SEC_LEAK)), (1, 1))
        self.assertLess(c.index(SEC_STATUS), c.index(SEC_LEAK))
        self.assertIn("git commit", c)                                                 # the closing block's state commit (S-Task 19; spelling in "Baseline record")
        for later in (END, "slot-done close", "git add", "git commit", "git merge --no-edit origin/"):
            if later in c:                                                             # rindex: the closing block is the last git work of the file
                self.assertLess(c.index(SEC_LEAK), c.rindex(later), later)

    def test_the_skill_has_the_feeds_rules_and_the_one_ban_names_both_side_processes(self):
        skill = (SLOTS.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual([m for m in ("3ד", "sec-feed --status", "sec-feed --leak-check", ".cache/sec_feed.log", "echo set || echo missing", "printenv",
                                      "/proc/<pid>/environ", "export -p", "SEC_USER_AGENT", "curl") if m not in skill], [])
        ban = [p for p in skill.split("\n\n") if "setsid" in p]
        self.assertTrue(ban and all(all(w in p for w in ("dash-publish", "3ג", "sec-feed", "3ד")) for p in ban))

class LaunchLine(no_sec.Case):                                                       # spec 3.2's three faults, under bash and sh
    def test_the_line_returns_with_its_launcher_and_the_parent_starts_in_ai_trader(self):
        for shell in [s for s in ("bash", "sh") if shutil.which(s)]:
            for front in ("", no_dash.launch_prefix("exec sleep 3", folder=str(self.work))):         # alone, and after the publisher's list
                line = front + self.feed_list("pwd > side.cwd && exec sleep 3") + f"cd {self.work} && pwd > {self.tmp}/parent.cwd && exec sleep 0.5"
                t0 = time.monotonic(); subprocess.run([shell, "-c", line], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=self.tmp, env=self.env, timeout=10)
                self.assertLess(time.monotonic() - t0, 2.0, (shell, bool(front)))        # with the launcher (0.5 s), not with a side process (3 s)
                self.assertEqual(((self.work / "side.cwd").read_text().strip(), (self.tmp / "parent.cwd").read_text().strip()), (str(self.work), str(self.work)))

    def test_with_the_variable_unset_nothing_starts_and_the_parent_still_starts(self):
        subprocess.run(["bash", "-c", self.feed_list("pwd > side.cwd") + f"cd {self.work} && pwd > {self.tmp}/parent.cwd"], cwd=self.tmp, env=self.env_without_contact, timeout=10)
        self.assertEqual(((self.work / "side.cwd").exists(), (self.work / ".cache").exists(), (self.tmp / "parent.cwd").exists()), (False, False, True))
```

`feed_list(cmd)` = `no_dash.launch_prefix(cmd, guard=True, folder=str(self.work), guard_var="AITRADER_SEC_CONTACT", log=".cache/sec_feed.log")`; `self.env` = `no_phone.clean_env()` plus a sentinel contact.

- [ ] Run `-p 'test_slot_files.py' -k SecLines`. Expected: `TypeError: launch_prefix() got an unexpected keyword argument 'guard_var'` (the module cannot load).
- [ ] Change `launch_prefix`; edit `news-watch.md`, `close.md` and `SKILL.md`.
- [ ] Run `-p 'test_slot_files.py'` (the supervisor's, the trading room's and these 4: `OK`; `DashLines` unchanged) and `-k LaunchLine` (2 tests, `OK`). Whole suite: `OK`.
- [ ] Commit: `git add ai-trader/tests/helpers/no_dash.py ai-trader/skills/trader/slots ai-trader/skills/trader/SKILL.md ai-trader/tests/test_slot_files.py ai-trader/tests/test_sec_feed.py`; message `docs(ai-trader): the watchdog starts the SEC feed beside the publisher, the close slot says its day and checks for a leak; SKILL rules for the contact`.

### Task 19: Rollout step 3: the feed in the launch prefix

**Kind:** OPS - the owner's main chat session; the owner says yes once. **Spec:** 3.2, 3.4 (target 6), 10 step 3.

- [ ] Preconditions: Task 18 committed; S-Task 20's prompts on the tasks; TP-Tasks 15-16 landed; Task 17 landed; question 2 answered and not ד.
- [ ] The launch-line drill, after the close, in this session, in the feed clone after `git fetch origin <branch>` and `git merge --no-edit origin/<branch>` on `secfeed-build` (it holds Tasks 9, 10 and 18); every command below runs with the clone's repository root as its working folder. `<dir>` is a new scratch directory (an absolute path). Its config and map, written by the test module's own helpers (Task 6), so they are the test fence: `(cd ai-trader && PYTHONPATH=.:tests python3 -c "from datetime import datetime, timezone; from pathlib import Path; import test_sec_feed as t; d = Path('<dir>'); t.cfg_for(d, ['AAPL', 'KO'], sweep_seconds=1); t.write_map(d, {'AAPL': '0000320193', 'KO': '0000021344'}, datetime.now(timezone.utc).isoformat(timespec='seconds'))")`. `<dir>/config.json` has every `sec` URL at 127.0.0.1 on a closed port and `allowed_hosts` `["127.0.0.1"]`, so nothing can reach the SEC and the helper's tripwire refuses every other host; the map's fresh `tried_at` means no map request. The value of `AITRADER_SEC_CONTACT` in this session's environment is replaced for that one command by a sentinel made then (random letters, "@", random letters, ".invalid"). The publisher's list keeps its shape with `exec sleep 30` in its loop's place (`(cd ai-trader && mkdir -p .cache && exec >> .cache/dash_publish.log 2>&1 < /dev/null && exec sleep 30 &); `), so no real publisher starts and nothing reaches the database. Run 1, as a tracked background command: `export AITRADER_SEC_CONTACT=<sentinel>; (cd ai-trader && mkdir -p .cache && exec >> .cache/dash_publish.log 2>&1 < /dev/null && exec sleep 30 &); ([ -n "$AITRADER_SEC_CONTACT" ] && cd ai-trader && mkdir -p .cache && exec >> .cache/sec_feed.log 2>&1 < /dev/null && python3 tests/helpers/sec_child.py --state-dir <dir> --config <dir>/config.json --until 24:00 --supervised $$ &); exec sleep 600`. Twenty seconds later `<dir>/sec_feed.json` exists (the loop writes it when it takes the lock, Task 10), its `pid` is alive and its `parent` is a pid whose `/proc/<pid>/cmdline` holds `sleep`; then `TaskStop`: the feed's pid is gone within 5 s. Run 2: the same helpers with `sweep_seconds=1, sleep_slice_seconds=30, lock_wait_seconds=82`, the line ends with `exec sleep 20`, nothing is stopped: the task is reported ended within 5 s of the 20 while the feed's pid is alive, and that pid is gone within 35 s more. Run 3, on a new `<dir>` with its config and map written the same way, with `unset AITRADER_SEC_CONTACT; ` in place of the `export`: after 20 s no `sec_feed.json` exists and the `sleep` ran. A fail stops this task and goes back to Task 18.
- [ ] Land Task 18: the cut point is its commit. A code landing (gate steps 1-3); files of the owner's list in the diff: none.
- [ ] The owner's yes, one message: "להפעיל את מקור ה-SEC מיום המסחר הבא? הוא רק רושם דיווחים של 74 החברות, לא קונה, לא מוכר ולא משנה ציון. א: כן (המלצה). ב: לא עכשיו. כסף נייר." On yes: `list_triggers`; the prompts of the two `news-watch` tasks and the close task must equal their files at the commit before this landing, else stop; `update_trigger` the three from their files at the pushed commit; `list_triggers` again and diff each prompt against its file: no difference.
- [ ] One full session. Proofs that evening, in the feed clone after fetch and merge, from the pushed state: `answered_min` 74 in every health row outside handovers; failed requests under 1% of requests; no block seen; no `too_big`; `poll_gap_max_s` at most 150 outside handovers; a health row within `health_log_seconds` + `lock_wait_seconds` + 60 s (385 s) after each handover's `up` row (a new feed writes its first health row one `health_log_seconds` after it starts, and may first wait for the lock; so a feed ran in every leg; no exit 3); megabytes as Task 17 measured; the base day (the last full session before the feed's loop first ran, spec 3.4) into "Baseline record", then `python3 -m aitrader sec-report --day <that day> --base <the base day>` prints the engine line as a pass; one `fresh` row checked by hand against the SEC's own filing index page for that accession, read once from this session.
- [ ] Undo (spec), as a forward edit: a BUILD edit sets `SEC_STEP` to "0" and removes the feed's list from `news-watch.md` as that file stands (the publisher's list untouched); `-k SecLines` red, edit, green; a code landing; `update_trigger` from the files at that pushed commit.
- [ ] Move the claim in `BUILD_CLAIMS.md` to "Done" in the push of this landing (Task 21 opens its own line).

### Task 20: Rollout step 4: ten sessions, then the report

**Kind:** OPS - the owner's main chat session; the owner reads five lines and answers one question, and question 4. **Spec:** 5.1 (the hand reading), 5.3, 5.4, 6 (the table), 12 question 4, 13 (backlog).

- [ ] After 10 sessions with the loop running: in the feed clone after fetch and merge, `python3 -m aitrader sec-report --days 14 --base <the base day of "Baseline record">`.
- [ ] The hand reading: every strict match and every unmatched or censored event filing, read against its seen and scores rows; the count of automatic matches it overturned goes into the report.
- [ ] Write `reports/YYYY-MM-DD-sec-feed.md`: its first line says that the lead cannot be tested (n far under `report.min_events`); then the table of spec 5.2 with each number's n and file; the facts of section 6 as they now stand (cost, the measured delay, the error rate), written into the spec's table too; what was not measured; the projection of 5.3 (strict matches so far, strict candidates per 10 sessions, months to 30); a recommendation among: keep logging as is, widen the hours, switch to the Atom feed, stop. Run it through `data:validate-data` before the owner sees it.
- [ ] The owner gets five short Hebrew lines (each ending "כסף נייר") and one question: the recommendation, with options. Then question 4, one message, with the count of stale Yahoo rows inside event windows (recommendation ב).
- [ ] Append to `state/backlog.md`: the items of spec 13's last paragraph; a block on two days in a row or a feed that did not run for two sessions is a defect, said to the owner in chat by the session that sees it. Commit the report, the spec's table and the backlog with the state; fetch, merge, push.

### Task 21: Rollout step 5: the supervisor's side child

**Kind:** OPS - the owner's main chat session, with one BUILD edit. Waits for the supervisor's side-children amendment (Task 1's backlog item) to land through its own spec and plan. **Spec:** 3.2 (last table row), 10 step 5, 11 (collision 3).

- [ ] A new claim line for the two files below; then a BUILD edit: `SEC_STEP` becomes "0" and the feed's list leaves `news-watch.md` as that file stands (the test then asserts that no slot file starts the feed). `-k SecLines` red, edit, green; commit `git add ai-trader/skills/trader/slots/news-watch.md ai-trader/tests/test_slot_files.py`; message `docs(ai-trader): the supervisor's parent starts the SEC feed; the launch prefix no longer does`.
- [ ] Land it (cut point: that commit; gate steps 1-3; files of the owner's list in the diff: none). `update_trigger` the two `news-watch` tasks on the owner's word, from their files at the pushed commit.
- [ ] One session as in Task 19's proofs. Then a one-time task bound to the trader session, on the owner's word: `pid=$(python3 -c "import json; print(json.load(open('ai-trader/state/sec_feed.json'))['pid'])") && grep -q sec-feed /proc/$pid/cmdline && kill $pid`, answering with the pid only. `state/sec_feed.json` is git-ignored and this session has no shell there, so the new pid is read by a second one-time task the same way, set for the amendment's restart back-off plus 2 minutes after the first: `python3 -c "import json; b = json.load(open('ai-trader/state/sec_feed.json')); print(b['pid'], b['at'])"`, answering with its output only; both read back with `list_events`. Pass: a pid other than the killed one, with an `at` after the kill; and from the pushed state (`git show origin/<branch>:ai-trader/state/...`) a `sec_health.jsonl` row whose window starts after the kill, and no engine `exit` row in `state/uptime.jsonl` at that minute.
- [ ] Undo: the prefix part back (`SEC_STEP` "3"), the same forward way. Close the claim line.

## Open owner decisions

The owner approved the spec as written on 2026-11-11, so its six questions stand at the spec's defaults; the plan builds the last column and designs no alternative.

| # | Question (spec 12) | Asked in | Built until he says otherwise |
|---|--------------------|----------|-------------------------------|
| 1 | Widen the feed's hours beyond 08:07-16:05? | Task 17, third, with the share of last year's filings outside the window | א: session hours only |
| 2 | How to ask the SEC (each file every 60 s, 30 s, 2 minutes, or the Atom feed as the trigger)? | Task 17, first, with step 2's sizes and the Atom answer | א: each company's file once a minute; nothing loops before he answers; ד stops this plan after Task 17 and becomes a backlog design |
| 3 | What to log (every filing, 8-K/6-K only, or offering documents as one count a day)? | Task 17, second, with the `offering` share | א: every filing; ב or ג would be a conditional BUILD task written then |
| 4 | Keep the title of stale Yahoo headlines in the engine's journal? | Task 20, with the count of stale rows in event windows | ב: not added; the report counts them |
| 5 | If the SEC refuses the declared client | Task 16 or later, only when a refusal is seen with both SEC hosts allowed by the environment's network (a 403 for a host the network does not allow is the proxy's: Task 2's network question instead) | א: the feed stops and he is told |
| 6 | Where the variable lives | Task 2, before any card (his answer to the supervisor's question 11 answers it) | no card is shown |

Only he can also: open the contact address and give it once (Task 2); approve the card (Task 2) and, if the two sessions turn out to be on two environments, say whether the chat moves or, when the tool refuses the move, whether a new main chat starts in the trader's environment (Task 2); say whether the two SEC hosts join a limited network (Tasks 2, 16); say yes to each one-time task in the trader session (Tasks 2, 16, 21) and to each change of a scheduled prompt (Tasks 19, 21).

## Where the plan decides what the spec leaves open

For the reviewer of each task; every item is repeated in its task.

1. The tripwire is `install_tripwire(path)` in `engine_child.py`: S-Task 3 named it (gate clone commit 25d18a4b), so TP-Task 9's rename to `tripwire(sent_file)` ("if S-Task 3 left the tripwire inline") never happens. `sec_child.py` calls `install_tripwire`, and the tripwire's wait ends with S-Task 9's landing, before S-Task 20's (spec 11, collision 8). Tasks 1, 9.
2. The supervisor's `http_stub.py` plays ntfy only, so the wire stub is the feed's own `SecStub` in the test module (no third helper file). The fixture `company_tickers.json` is the pack's `trader-news` copy (7 rows, `BRK-B`). Tasks 1, 4, 9.
3. Config keys the spec writes as prose or leaves to the code: `contact_max_chars` (100), `edgar_hours_ny` (["06:00", "22:00"]), `heartbeat_wait_seconds` (60), `report.quartile_min_n` (4) and `report.projection_sessions` (10) (rule 5: no number in the logic); the projection runs to `report.min_events`. The launch window is `supervisor.watcher.engine_window_ny[0]` to `supervisor.until_ny` (`launch_window`, Task 10), and the span where a match is possible ends `news.health_log_seconds` before `until_ny`. The `Block` test pins the seven measured or dated keys by presence and type only, so Task 17's commit stays config-only; `sweep_seconds` is pinned by value, so an answer ב or ג to question 2 also edits the test's table and the fallback, while every test config pins 60 (`cfg_for`). Tasks 3, 6, 10, 12, 13, 17.
4. The repository scan reads text files only (strict UTF-8): `tests/fixtures/stock_panel.pkl` carries an address-shaped run of bytes by chance. Task 3.
5. The map file is `{"built_at", "tried_at", "tickers": {...}}`; "a company answered 404 since the last build" is read from `sec_errors.jsonl` rows newer than `built_at`. Forms: the config lists base forms; "/A" is always accepted; a trailing "*" is a prefix. Tasks 4, 8.
6. Failures: a status with no row of its own in spec 2.7 is `bad_body`; a connection error is error class `connect` and health kind `other`; the pace is halved after a block of either kind; after a 403 wait one company is asked first; the back-off doubles once per sweep that ends with `fails_in_a_row` at or above `backoff_after_fails` ("doubles each sweep"), not once per failed request. A start carries over the day's counts only from a heartbeat of today's New York date (Review Focus 1); `host_blocked` is `[]` when empty. Tasks 7, 8.
7. The pacer's grid re-bases when the gap changes, one whole new gap after the last start (never `last start + min_gap`: with one company that would turn a back-off into back-to-back requests); a sweep takes its gap once, at its start. Every request of a process rides one `requests.Session` (spec 3.4: one connection). The deadline is a timer that closes the response, so a slow body cannot outlast it by a read timeout. `--once` writes one health row; `--dry-run` writes the heartbeat (a block must be kept) and no journal row; plain `--once` makes no index request. Each `sec-feed` option enters the parser with the task that builds it (`--status` 10, `--leak-check` 11, `--history` 12), so an earlier child meets an argparse error, never a half-built form. Tasks 5, 7, 9-12.
8. Rows of a start that found no heartbeat file carry `cold` true; the report counts them as an upper bound of rows re-logged after a new machine (spec 4.1 gives no rule to find them). A filing whose `filed` cannot be read stays in the seen set; a poll stamped before the previous one is "catchup". Tasks 6, 7, 13.
9. `--status` prints the day's Hebrew lines already filled: the base line, then every other that applies in spec 8.3's order (the spec says "one of"); the not-configured line alone when there is no contact (read from the `env` it is given, never from a config); the blocked line only for a day-long stop by blocks; and one sentence the spec does not write, for the megabytes stop that spec 2.4 says the daily line names: "מקור SEC עצר היום: הגיע לתקרת ההורדה היומית ({mb} MB). לא נוגע למסחר. כסף נייר". `coverage`, `up_stretches`, `launch_window` and the `index_check` row's shape are defined in Task 10, the first task that needs them, and Tasks 12-13 reuse them. The loop writes its heartbeat once when it takes the lock, besides spec 3.3's moments. Task 10.
10. The import test adds `aitrader.data` and `aitrader.signals` to the spec's list (the feed never reaches Yahoo). The loop is checked to open no engine file. Tasks 6, 10.
11. Strict matching has a fourth outcome, `no_class`, for a filing whose items map to no class (7.01, 8.01, 9.01 alone, every 6-K), so that "unmatched" counts only filings that could have matched. Headlines explained uses the mirror window [`first_seen` - `after_seconds`, `first_seen` + `before_seconds`]. Quartiles print from n >= `report.quartile_min_n`. The bootstrap's range is the k-th smallest median, k = floor(q x (draws - 1)). Censored filings take spec 5.2's three categories: the hour after a restart that is not a bridged handover is "break", with `t` the end of the stretch before it; "first_hour" is the day's first start only. Tasks 13, 14.
12. Coverage is read from the feed's health rows (`sweeps` > 0 and `poll_gap_max_s` <= `fresh_gap_seconds`); history counts by session use only dates the calendar covers (2025 is not in `calendar.years`), and the projection's sessions and months come from that span. Target 6's base day is given to `sec-report` by `--base` (Task 19 records it). `sec_history.json` keeps the `Cache-Control` text only cleaned, and as "withheld" when it holds the contact. With no `index_check` row yet, the first day asked is the oldest of the last `seen_keep_days`. Tasks 10, 12, 13, 19.
13. The launch-line case lives in `tests/test_sec_feed.py` (spec 7: "all in `tests/test_sec_feed.py`"), with `sleep` in both side processes' places; TP-Task 10's pipe test in `tests/test_dash_publish.py` is not edited (spec 3.2 asks to extend it, but spec 11's claim list does not name that file). The prefix order is the publisher's list, then the feed's. The SKILL paragraph is section 3ד; the 3ב sentence names both side processes and keeps TP-Task 15's markers. In `close.md` the `--status` line comes before `--leak-check`, and `--leak-check` before `END`, the receipt and the sync block (collision 9). Task 18.
14. Task 1 reads the SEC's documentation pages from the main session with the fetch tool (the spec asks the plan's first task to re-read every quote and to copy the index file's name); that is never the bot calling the SEC, and nothing on `data.sec.gov`, no index file and no ticker file is read before step 2. The index template's fields are `{year}`, `{qtr}`, `{ymd}`. With no SEC page for the holidays, `edgar_closed` is the federal list, marked as such. Task 1.
15. Step 2's command adds `grep MemTotal /proc/meminfo`, so that `max_body_bytes` is set "with peak memory in view" by a stated rule (peak under 10% of the machine's memory). The clock rule (at most 1% outside under one reading, ten times as many under the other) and the cap rules are written in Task 17, not left to that day. Tasks 16, 17.
16. The supervisor amendment is asked for a list of side children from the start (a backlog item in Task 1), before TP-Task 25 hands over its one-child amendment. The feed's claim closes with step 3; step 5 opens its own line. Tasks 1, 19, 21.
17. Step 0 also reads the network of the trader's environment: a limited network without the two SEC hosts gets them in the same card, on the owner's word, and a 403 for a host the network does not allow is the proxy's, never a reason for question 5. A switch of environment the tool refuses (unrestricted network, a wildcard host) ends in one question: a new main chat in the trader's environment, or stop. Tasks 2, 16.
18. Every subagent of this plan gets two lines verbatim (Global Constraints): the `git stash` ban and the ban on printing the environment, since from step 0 on every subagent of the main session holds the real value. Every task.

## Baseline record

Filled by Task 1 on the merged tip after S-Task 9's landing, and completed after S-Task 20's. No id of a session, a task or an environment, and no address, is ever written here.

| What | Where / value |
|------|---------------|
| The SEC quotes [W1]-[W5], re-read: same / was -> is, with the page and date | |
| `index_url` template, the index file's layout (delimiter, header lines by name, a line holding an address named as such and never copied, columns, CIK and accession), the page and date | |
| `edgar_closed` for 2026 and 2027, and its source (an SEC page, or "federal list, not an SEC statement") | |
| `journal` names (file:line) | |
| `news_live._clean` regex, the health, seen and scores rows (file:line) | |
| `config.json` keys used (line numbers), and the `sec_user_agent` line | |
| `data.sec_recent_form4` (its def only) | |
| From S-Task 9: `no_phone.clean_env`, `engine_child.install_tripwire`, `test_supervise.Procs` (file:line, commit) | |
| From S-Task 20: `supervise.take_lock`, `read_rows`, `load_cfg`; the `supervisor` keys; the uptime rows (file:line, commit) | |
| From TP-Tasks 10, 15: `no_dash.launch_prefix`, `LAUNCH`, `STEP`, `END`, `DashLines`; SKILL 3ב and 3ג (file:line, commit); from S-Task 19: how `close.md`'s closing block spells its state commit | |
| The feed clone, written as "clones/feed/ai-trader under the main session's scratch folder" | |
| The three fixtures: sizes, and the commit on `secfeed-build` | |
| Scheduled tasks: slot -> task name, cron, "trader session" or "another session" (copied from the supervisor plan's record) | |
| Task 16: per-company maxima (wire, decoded, rows, whose), peak `ru_maxrss`, `MemTotal`, CPU s, the two outside-hours counts, headers, largest `skew_s`, Atom, index, `offering` share, share outside the window, the projection | |
| Task 17: the owner's answers to questions 1-3, the values set and the rule each came from | |
| Task 19: the base day; the first session's numbers; the hand-checked `fresh` row | |
