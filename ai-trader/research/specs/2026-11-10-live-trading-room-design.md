# Live trading room - design spec (2026-11-10, rev 2)

Status: the design was approved by the owner in chat on 2026-11-10; this spec stays inside it. Rev 2 answers two reviews. Three
things need the owner's word and are listed in section 9; nothing else is left open for him. Paper money only. Reader: a
programmer who was not in the conversation. Every number is a measured fact with its source, or is marked **dt** (design target or
design value: a test or a rollout check must prove it) or **?** (not verified by anyone yet). This file never holds a key, a
project name or ref, a topic or an address; it names environment variables instead.

Evidence tags: [F] verified by the main session on 2026-11-10 (database, write test, connector read, phone probe). [C file:line]
code read on 2026-11-10 under `ai-trader/`; `news_live.py` was mid-merge that day and is cited by function name. [M] measured for
this spec from a file on disk, named each time. [P] reviewer 2's rough prototype of the first tab (`_measure_first_tab.js` beside
this spec; harness stub fonts, so a proxy, not the phone). [R] the dashboard page type's own reference pages (`sources.md`,
`one-writer.md`, `design-defaults.md`). [S] the supervisor spec, `2026-11-10-supervisor-design.md` rev 2.

What rev 2 changed, in short: the database row holds the first tab only, and the tab "עוד" reads the hourly file; the bot-side
names say "dashboard", not "live"; the write key goes through the credential form, not a variable; the publisher starts slower,
yields to the engine's stop quotes and cannot be run by another checkout or a test; the page picks its source once per data
change, measures age on the database's clock, and has a badge whose every state, order and sentence is written down; a probe on
the owner's phone comes before the page is built.

## 1. Goal, non-goals, targets

Goal: the dashboard becomes a live trading room. While the market is open the owner sees on the first tab money, positions,
trades, plans and headlines, and one badge that says how old they are and never claims more than was measured. The money block
shows without scrolling; the whole first tab is about three phone screens. When any hop of the live path is dead the page still
works and says "not live".

Non-goals: anything that changes a trade; history in the database (it stays in `state/` and git); reading the database from the
bot; real-time ticks (prices are polled Yahoo quotes); live crypto marks at night (the machine is up only for the scheduled
slots); alerts to the phone ([S] section 8 owns them); retiring the hourly file; a live second tab (open question 2); a cap on
how many positions the first tab lists (the approved design says each position).

| # | Measure | Today (source) | Target | Kind |
|---|---------|----------------|--------|------|
| 1 | Age of what the owner sees, market open | 0-60 min by schedule: one rebuild an hour at minute 57 [F]; never measured | at the full pace (prices every 30 s): usually under 45 s, at most about 75 s while every hop is up (10 s quote-to-row + 30 s row age at the read + 30 s on screen + the read); at the starting pace (prices every 60 s): at most about 105 s. Yahoo's own delay is on top and is not measured (3.8). The badge is red after 120 s | dt; proven by `dash_health.jsonl` and the phone check |
| 2 | Age, market closed | until the next weekday rebuild; a crypto night decision is not shown before it | one push within 60 s of the end of every scheduled slot and of every hourly rebuild; the badge says "market closed, as of HH:MM" with the date when it is not today, is never red, and warns when the last row was not the closing one or is overdue (5.5) | dt |
| 3 | Length of the first tab | 13,273 px, one scroll [M `harness/shot-now-400.png`, 400 x 13273, 2026-11-10 04:31] | with the pinned fixture (7, harness): at most 2,400 px at 400 px wide and 2,600 px at 360 px; the money block ends inside the first 700 px at both. Not bounded above: each further position adds about 27 px [P], so 37 positions (the most the three books can hold: 15 + 20 + 2 [C config.json `risk.max_positions`, `news.max_position_pct`]) add about 600 px | dt, harness; [P] reached 2,062-2,393 px with a rougher layout |
| 4 | Sideways scroll on the first tab | long cells force 240 px [C dashboard/index.html:28] | none at 360 and 400 px: no table wrapper is wider than its card | dt, harness; [P] measured 3-92 px of overflow with today's CSS, so 5.8 changes the layout |
| 5 | Time to first numbers on screen | not measured | file rows within 2 s of opening, live rows within 5 s, on the owner's phone | dt; the page times itself (5.11) |
| 6 | Live told from not live | one text "עודכן HH:MM" [C index.html:72] | one badge, 12 states, each a stored sentence (5.5); red within 1 s of crossing 120 s while the page's tick runs, and by a CSS alarm with no script when it does not | dt, harness with a fake clock; on the phone: the probe (7, step 1.5) |
| 7 | Snapshot build time | not measured | state part at most 1 s, whole tick at most 10 s (median, trader machine, real state) | the build must measure it before step 1 (3.8) |
| 8 | Push time | 1.19 s for one push from the cloud container [F] | 95% under 3 s | measured in `dash_health.jsonl` |
| 9 | Payload size | whole snapshot: 45,804 bytes, 245 rows, 42,449 bytes compact; the first tab's share of it (summary row, 15 positions, 8 headlines, 12 trades): 7,329 bytes compact [M `dashbuild/ai-trader/.cache/dashboard/snapshot.json`, 2026-11-09 22:40] | at most 60,000 bytes of text; the database refuses above 100,000 after step 0 | dt + test; computed worst case about 21,000 bytes (3.5) |
| 10 | Effect on the engine | - | the pass numbers of 3.3, checked in every session of step 1 | measured, pass or fail |

"Live" when the market is closed means: the last scheduled event is in. Nothing moves but the scheduled slots (close, crypto
decision, crypto fill, morning summary, the hourly rebuild), each of which ends with one push. Prices are the last ones Yahoo
gave at that push. The badge is grey, shows the time of the snapshot and makes no claim of seconds.

## 2. Data path
One way only: no part of the bot reads the database.
```
 TRADER SESSION (cloud VM)                    DATABASE (the owner's Supabase project) [F]      OWNER'S PHONE
 engine, cycles --write--> state/*.json(l)
                             | read only
 dash-publish (new) ---------+
   every 30 s: quotes for held names and SPY, build_now(), clean
   POST /rest/v1/rpc/publish_snapshot ------> publish_snapshot() -> trader_live['snapshot']
     address: $AITRADER_DASH_URL                one row (first tab only), overwritten,
     write key: added by the network proxy      updated_at = now(), at most one write per 5 s
                                                     ^  execute_sql, one fixed SELECT,          dashboard page: header,
                                                     +--- the owner's own Supabase connector <-- tab "עכשיו" (dataset "live")
 hourly task, minute 57
   python3 -m aitrader dashboard -> snapshot.json -> uploaded into the artifact -------------> dataset "snapshot" (file):
   then dash-publish --once                                                                     tab "עוד", fallback of "עכשיו"
```

| Hop | Writer, cadence, credential | When the hop before it is dead |
|-----|-----------------------------|--------------------------------|
| state files | engine and cycles, as today | - |
| publisher | new process; 30 s in session; address from the environment, key from the proxy | engine dead: under the supervisor it still pushes, and the status block says "engine not answering" in red; in the interim start (3.1) it dies with the engine and the badge goes red within 120 s. Yahoo dead or throttled: it pushes the last known prices, each marked stale, and the badge says the prices are old |
| database row | the function, on each push | publisher, network or database down, project paused: the row stops moving and its write time ages |
| page, dataset `live` | the reader's browser, with his connector, every 30 s in session while open | row old: the badge counts up, red after 120 s in session; once the hourly file is clearly newer the page shows the file. Read fails (not connected, declined, error, malformed): the file, marked "not live", with the reason |
| page, dataset `snapshot` | the hourly task uploads a file | task dead: the file ages; its own time is printed wherever it is shown |

## 3. The publisher
### 3.1 Files and command
- New `aitrader/dashpub.py` (loop, guards, clean, push) and `aitrader/quotes.py` (pure: one chart reply in, price, quote time and
  today's move out; the calendar is an argument; no state, no network). `aitrader/__main__.py` registers `dash-publish`.
  `aitrader/dashboard.py` gains `build_now()` and `dump()` (3.4). `config.json` gains a block `dashboard_push` (3.8).
  `.gitignore` gains three lines (3.7). `data.py`, `news_live.py`, `journal.py` and `notify.py` are not edited.
- The names say "dashboard" on purpose. In a trading bot "live" beside "key" reads as real-money trading, hard rule 1 is paper
  money only, and the owner sees these names on approval screens.
- `python3 -m aitrader dash-publish --until 16:05 [--pace ramp|full] [--no-push] [--supervised PID]` is the loop (New York time,
  like the engine). `--pace` picks the quote interval (3.3; default `ramp`). `--no-push` does everything but the POST and still
  writes the health rows. `--once` builds and pushes once, within `once_deadline_seconds` (20). `--dry-run` builds, cleans and
  prints bytes and rows per table, with no database call. `--claim` writes the marker of 3.7 and exits.
- Exit codes: 0 end of the run, and `--once` always (a failed or refused push is one printed line: a slot's turn must not start
  repairing things), except 5 below; 3 another publisher holds `state/dash_publisher.lock` (loop mode); 4 a tick hung and the
  process ended itself (3.2); 5 `--once` found the lock held by a loop whose heartbeat is older than two periods (it journals
  `loop_stale` and prints it); 78 not configured or not the publishing checkout (3.7), which a parent must not restart.
- Who starts the loop. Final form: the supervisor, as a second child beside the engine. [S] rev 2 has one child and lists "a
  dashboard row" as a non-goal, so [S] needs an amendment: start it with the engine, restart it with back-off, never count it in
  uptime, never restart or stop the engine because of it. Until then: the two engine watchdog prompts start it inside the
  engine's own tracked command, `[ -n "$AITRADER_DASH_URL" ] && python3 -m aitrader dash-publish --claim && python3 -m aitrader
  dash-publish --until 16:05 --pace ramp & exec python3 -m aitrader news-live ...`. No second tracked command exists, so no
  extra model turn is added. In step 1a the line has no guard and no claim, and carries `--no-push`. The publisher ends when its
  parent is gone, so in the interim it lives and dies with the engine (gaps of up to about 30 minutes, and the 2-hour cap [S
  4.5]). A starter may send TERM to the pid named in a heartbeat older than `hang_seconds` + 60 s, after checking that the pid's
  command line is this command.
- Every scheduled slot ends with one push, `dash-publish --claim && dash-publish --once` (3.7): open, midday, close, Saturday
  review, the three crypto slots, and the hourly dashboard task after its upload. With the loop up, `--once` sees the lock,
  checks the heartbeat and leaves.

### 3.2 Loop and cadence
| When | Build and push | Quotes |
|------|----------------|--------|
| Regular session (`journal.session_hours` [C journal.py:76-84]) | every `session_seconds` (30) | every tick whose last quote round is at least the pace's interval minus 5 s old: `quote_seconds_ramp` (60) or `quote_seconds` (30) |
| At the open | one extra tick `open_push_delay_seconds` (3) after it, so the first in-session row lands within about 10 s | fresh |
| Loop up, market closed (before the open; from the close to `--until`) | every `closed_seconds` (120) | every `closed_quote_seconds` (600) |
| At the close | one push `final_push_delay_seconds` (90) after it, with `market_open` false | once, for that push |
| At `--until` | one last push, marked as the loop's last: its `expect_next_by` is that of mode "once" (3.4) | stored |
| Loop not running | one push per scheduled slot and per hourly rebuild (`--once`) | once per push |

Ticks sit on a fixed grid on the monotonic clock. A tick that overruns skips the ticks it missed; nothing queues. The publisher
keeps at least `min_push_gap_seconds` (6) between its own pushes, so it never meets the database's 5-second floor (4). One tick:
(1) the guards of 3.6; (2) the yield check and the quotes (3.3); (3) `dashboard.build_now(quotes, pub)` in the main thread; (4)
the guards and the stable-read check of 3.6 again; (5) keep only the listed fields of 3.4, clean every string (3.7), then
`dashboard.dump()`; (6) the size check (3.5); (7) POST; (8) heartbeat and counters. A tick has a deadline,
`tick_deadline_seconds` (25): a quote round that would pass it is cut, and the names it did not reach keep their stored quotes.
A watchdog thread ends the process with `os._exit(4)` and one printed line when no tick has finished for `hang_seconds` (120);
that frees the lock, which a hung process would hold for ever.

### 3.3 Quotes and the load on Yahoo
- Symbols: every name held by the quant, news and crypto books, and SPY for the comparison: 16 on the snapshot of 2026-11-09 (14
  + 1 + SPY) [M]. The shadow books, `^VIX` and the crypto benchmark are not on the first tab and are not fetched. One GET per
  symbol to the chart address the bot already uses (`data.CHART_URL`, range 5d, interval 1d [C data.py:30, 59-73]), sent by
  `dashpub.py` itself with timeout `quote_timeout_seconds` (5) and no retry, through a pool of `quote_workers` (4).
  `data._get_json` is not used: its 20 s timeout and 3 tries [C data.py:43-56] can hold one quote 66 s [S target 4].
- From the reply, `quotes.py` takes `regularMarketPrice`, `regularMarketTime` and today's move as a fraction (0.0582 = +5.82%).
  For a stock the rule is the engine's (`news_live._day_move_pct`, which returns percent): previous session's close from the
  daily bars, none when the quote is not from today's session or the previous bar is missing. For a 24/7 symbol the move is
  last / the previous daily bar's close - 1, with no NYSE calendar (the engine's function would give none on Sundays, Mondays and
  after holidays). `dashpub.py` does not import `news_live`: that import would load the alert code, the trade code and the paper
  broker into the publisher [C news_live.py:45-47]. A test feeds the same fixture replies to both functions and expects equal
  moves for stocks (percent / 100). Moving the engine onto `quotes.py` is a backlog item for after the open claim (8).
- A symbol that fails keeps its last quote and that quote's own time (`regularMarketTime`). A price is stale when it is the
  stored fallback, or when, while its market is open (always, for a 24/7 symbol), the quote's own time is older than
  `max_quote_age_seconds` (180: the engine's own limit [C config.json:256]). A closing price is not stale after the close.
- Load, computed, not measured: 16 symbols every 60 s = 16 calls a minute; every 30 s = 32 a minute, about 12,500 in a 6.5-hour
  session. The engine's stop looks use the same host from the same address, and when Yahoo answers 429 a stop look gets no
  price for that name in that step [C data.py:43-56; news_live `check_stops`: `if not px: continue`]. Yahoo's limit is **?**.
  So the publisher never gets ahead of the engine:
  1. Dry session first (step 1a): the loop runs one full session with `--no-push` at the ramp pace before any push is enabled.
  2. Ramp: pushes start with prices every 60 s. The full pace (30 s) is switched on by `--pace full` in the start line only
     after one clean pushed session at the ramp pace, and after the form "one request for many symbols" has been tried (**?**:
     whether such an address still answers without a sign-in; if it does it replaces the per-symbol calls, about 2 a minute).
  3. Yield, automatic, every tick: no quote call for `yield_seconds` (300) when, in session, (a) the heartbeat is fresh, shows
     held news names, and its `stops_checked_at` is null or older than `yield_stops_age_seconds` (120) [C news_live `_step`], or
     (b) the newest `news_health.jsonl` row, if younger than two of its periods, has `stop_quotes_missing` above 0, or (c) the
     publisher's last round got a 429, or timeouts on more than `yield_timeout_share` (0.25) of its calls. Pushes go on with the
     stored prices, the `stat` row says `quote_state` "yield", and the badge shows the prices' age (5.5).
  4. Pass numbers for target 10 (dt, fixed before the dry run, changed only with a written reason). Publisher: no 429 in the
     session; timeouts on at most 1% of quote calls. Engine, from the session's `news_health.jsonl` rows against the last full
     session before the publisher ran: the sum of `stop_quotes_missing` not higher; the largest `stop_gap_max_s` not higher by
     more than one engine poll (`news.poll_seconds`, 20 [C config.json:243]); the median of `step_s_median` not higher by more
     than 20%. A fail: the pace goes back one step (full to ramp, ramp to one round per `yield_seconds`) and open question 3 is
     asked.
- The hourly `dashboard` command fetches as today, one `_chart` call per symbol [C dashboard.py:63-68], and reads the same reply
  through `quotes.py`.

### 3.4 What the bot builds
`dashboard.py` stays the only place where rows are made. `build_now(quotes, pub)` returns the first tab's rows; `build()` returns
them plus every row it returns today [C dashboard.py:395-402], so the hourly file is a superset and the page does no arithmetic
on money. `quotes` is the publisher's quote table, or None for the hourly command (which then fetches). With a quote table
`build_now` makes no network call: a held name missing from it uses the stored `last_price` [C dashboard.py:76, 80], marked
stale. `pub` carries the fields only the publisher knows (`seq`, `mode`, timings, `quote_state`, `trimmed`, `writer`, the
session list). `build_now` reads nothing from a crypto directory that does not exist [C dashboard.py:310-315]. Existing tags and
fields are unchanged, the `rule` rows included: they are not pushed, so their words can stay as they are. `dump(rows)` is the
one serializer for both paths: NaN and Infinity become null, compact UTF-8, `allow_nan=False`; `write()` uses it too (the saved
hourly file of 2026-11-09 holds two `NaN` literals [M], which a strict JSON reader refuses [C dashboard.py:409]).

Rows on the first tab. The publisher pushes exactly these tags and, per tag, exactly these fields; a test fails on any other.
The bot sorts every table; the page draws rows in the order it gets them. Each row has a stable `key`.
- `pos`, `npos`, `cpos`: `key` (book and symbol), `book` (display word: כמותי, חדשות, קריפטו), `symbol`, `qty`, `avg_cost`,
  `last`, `day_pct` (fraction or null), `pnl_pct`, `pnl_usd` = qty x (last - avg_cost), `price_epoch`, `stale`. Order: quant,
  news, crypto; inside a book by symbol, so rows do not jump between refreshes.
- `money` (one row): `total_equity` (the three books), `cash_usd`, `cash_pct`; `day_usd`, `day_pct`, `day_date`, `day_is_today`,
  `day_base_at` (Israel time, text) for the two stock books together; `spy_day_pct`, `vs_spy_day` (= `day_pct` -
  `spy_day_pct`); `c_day_usd`, `c_day_pct` for the crypto book; `stale` and `price_epoch_min` (the oldest price in the total).
- `acct` (three rows): `key` (quant, news, crypto), `name` (display word), `equity`, `cash_usd`, `day_usd`, `day_pct`,
  `day_base_at`, `ret` (since start), `stale`.
- `tape`: trades of all books, newest first: `key` (time, symbol, side, book), `ts_epoch`, `time` (Israel: HH:MM for a trade of
  today, DD.MM for an older one), `today`, `book`, `side` (display word), `symbol`, `qty`, `price`, `value`, `pnl`. All trades of
  today, at most `tape_max` (12), with the count of those left out in `stat.tape_more`; under `tape_min` (5), older ones fill
  up to 5. `today` is true only when the trade's own day is the build's day: New York date for a stock trade, UTC date for a
  crypto trade. The trade's reason text is not carried.
- `plan`: `key`, `book`, `symbol`, `side`, `size` (display text from the bot: a share count, or "עד 5%" from
  `news.max_position_pct`), `when` (Israel time, text), `src` (display word), `score`, `note`. From: the quant decision while
  `pending.status` is "pending", each order of its preview with the desk's word in `note` (a veto or a smaller size is shown,
  not left out, as today's orders table does [C dashboard.py:147-153]); the crypto decision while it waits [C 349-357]; each
  item of `news_queue.json` (bought at the next open [C news_live `run_queue_at_open`]).
- `news`: the `headlines_first` (8) newest scored headlines: `key` (the score row's own `id`; 1,075 of 1,190 rows have one [M
  `state/news_scores.jsonl`]; else time and symbol), `ts_epoch`, `time`, `symbol`, `score`, `mark` ("hi" above
  `news.buy_min_score`, "lo" at or under `news.sell_on_score_at_most`, else ""), `headline`. The scorer's reasoning is not
  carried. A headline is cleaned and cut to 240 characters by the engine [C news_live `_clean`]; the longest stored is 205 [M].
- `stat` (one row), the status of the snapshot itself:

| Field | Meaning |
|-------|---------|
| `as_of_epoch`, `as_of_il`, `seq`, `mode` | build time (UTC seconds; Israel text to the second); push counter (0 in the hourly file); "session", "closed", "once" or "file" |
| `writer`, `state_epoch`, `code` | the first 8 hex digits of a hash of the machine's id; the newest time stamp among the state records this build read; the commit of the code that built it |
| `market_open`, `sessions`, `expect_next_by` | open at build time; the next `sessions_ahead` (5) sessions whose close is after the build, each `[open, close]` in UTC seconds, the one in progress first, empty when the calendar does not cover them; the time by which the next push is due: build time + two periods while the loop goes on; build time + `once_expect_seconds` (72,000) for a `--once` push and for the loop's last push |
| `engine_expected`, `engine_alive`, `hb_epoch`, `stops_epoch` | whether the engine should be up now (a session day, inside `engine_hours_ny`, today 08:07-16:05 [C dashboard.py:255]); heartbeat younger than `engine_alive_seconds` (180: today's 3 minutes [C dashboard.py:141]); the heartbeat's time; the heartbeat's `stops_checked_at` (null when nothing is held) |
| `buys_held`, `buys_why`, `queue` | from the heartbeat: `buys_blocked` is already a code, "loss_review" or "hold" [C news_live `_buys_blocked`]. With no fresh heartbeat: "hold" when `news_hold.json` is not empty, else null. The hold's reason text is never read into a row |
| `on_air_s`, `session_s`, `on_air_pct`, `on_air_src` | protected seconds of today's session so far; all null on a day with no session. Source "uptime": the function `uptime-report` uses, once `state/uptime.jsonl` exists [S 4.6]. Source "health": the sum of `window_s` of today's `news_health.jsonl` rows with steps, a lower bound |
| `quote_age_max_s`, `quotes_missing`, `quote_state` | in session: the age of the oldest quote used, by the quote's own time, at build time; null out of session. The count of stale held names. "ok" or "yield" |
| `build_ms`, `quotes_ms`, `prev_push_ms`, `missed`, `bytes`, `trimmed`, `tape_more`, `engine_code` | timings; failed pushes since the last good one; size; tables cut (3.5); today's trades beyond `tape_max`; the engine's commit from its heartbeat |

Worked `sessions`, so the field cannot be read two ways. Built Tuesday 2026-11-10 15:59 New York: `[[Tue 09:30, Tue 16:00], [Wed
09:30, Wed 16:00], ...]`; seen at 18:00 the same day, no pair holds the time, so the market is closed. Built Friday 22:00:
`[[Mon 09:30, Mon 16:00], ...]`; seen Monday 09:31, the first pair holds the time, so the market is open.

Today's change, exactly. `day` is the latest NYSE session whose open has passed; `day_is_today` says whether that is the build's
New York date.
- Quant base: the last `equity.jsonl` row dated the session before `day` and logged at or after that session's close. The close
  slot writes it [M `state/equity.jsonl`: the row of 2026-11-09 21:23 UTC has `market_open` false; the rows of 2026-11-10 14:53
  and 17:52 UTC have it true]. A midday mark is never a base: no closing row means `day_usd` null.
- News base: the last `news_equity.jsonl` row of the session before `day`, accepted only when it is at most
  `day_base_max_gap_seconds` (600) before that close. The engine writes one every 5 minutes and only in session [C news_live
  `_step`], so the base is up to 5 minutes before the close; older than the limit (the engine was down) means null.
- A book that never traded: 0. `money.day_usd` is the sum of the two stock books, null if either is null; `day_pct` is it over
  the sum of the two bases; `day_base_at` is the older base's time. `spy_day_pct` is SPY's move from its previous close.
- Crypto is measured from another moment and is never added to the stock number: `c_day_usd` is the crypto book's value now
  minus its mark of the latest closed UTC day (one mark per decision bar [C dashboard.py:367-368]); null when that mark is
  missing or there is no crypto book.
- Since-start numbers stay in `kpi`, on the second tab.

### 3.5 Size
- Computed, not measured: 37 positions x about 260 bytes (a position row is 163 bytes today [M] and gains five fields), 35 plan
  rows x 130, 12 trades x 150, 8 headlines x 350, the `stat`, `money` and `acct` rows about 2,000: about 21,000 bytes. Budget
  `max_payload_bytes` (60,000) of the compact text. The database measures `pg_column_size` of the value, which is not the text
  length: **?**; step 1 measures the ratio and both limits are then set from it.
- Over budget, in this order, each cut named in `stat.trimmed`: `news` to 4 rows; `plan` to 20; `tape` to 5; then "degraded"
  (below). Still over: no push, one journal row `too_big`.
- "degraded" keeps `stat`, `money`, `acct` and the three position tags, the tables with no text from outside. It is also what
  the next tick sends after the database refused a payload with a 400 (3.7). The page shows the missing tables as not in the
  snapshot (5.9), never as empty.

### 3.6 Reading state without half-written files
- JSON state is written to a `.tmp` file and renamed over the target [C journal.py:235-239]; `write_all` does the same [C
  223-227]. A reader sees the old file or the new one, never half. JSONL journals are appended one line at a time [C 163-164]; a
  torn last line is skipped by `journal.read` [C 208-220], so the newest record can be missing for one tick.
- Files are not written together (book, queue, trade journal), so one snapshot can show a trade whose position is not in the book
  yet. Stable-read check: stat the JSON files read before and after the build; if one changed, build once more; if one changed
  again, skip the push. Residual: one tick, healed by the next push. No lock is shared with the engine.
- Guards, checked before and after the build; either trip skips the push and journals once. (a) A git operation in progress:
  `MERGE_HEAD`, `rebase-merge`, `rebase-apply`, `index.lock`. `ai-trader/` has no `.git` of its own (it is in the parent, and in
  a worktree it is a file), so the four paths are resolved once at start with `git rev-parse --git-path`; a rebase pull showed a
  concurrent reader an older file in 4 of 4 rounds and no file in 1 of 4 [S 4.7]. (b) A core book file is missing
  (`portfolio.json`, `news_book.json`; the crypto one once it has existed): a missing book reads as a new $100,000 one [S 4.7].
  This holds from the first tick: with no earlier tick to compare, missing means skip.
- The calendar is read once at start: `journal._calendar()` returns nothing for a half-written `config.json` [C journal.py:64-68],
  which would make one tick say "market closed".
- `build_now()` switches module globals in `journal.use_book` [C journal.py:31-51]: the publisher is its own process and only its
  main thread builds. Quote workers touch no state.

### 3.7 Failure, guards, environment
- POST `$AITRADER_DASH_URL/rest/v1/rpc/publish_snapshot`, body `{"p_id": "snapshot", "p_payload": [rows]}`, header `apikey` with
  a fixed placeholder: the network proxy replaces it with the real key (6), which never reaches the machine. The write test of
  [F] used that one header and nothing else. Timeouts: connect 5 s, read 10 s. 204 is success [F].
- No retry inside a tick; the next tick is the retry. After `backoff_after_fails` (5) failures in a row, of any kind (timeout,
  5xx, 429, 401/403), the period becomes 60, 120, then 300 s until a success. A 400 is different: the payload itself was
  refused, and the same rows would be refused again (a headline stays in the snapshot for hours), so the next ticks send the
  degraded set of 3.5; the full set is tried again once its text rows have changed, or after `degraded_retry_seconds` (300).
  "too soon" from the database (4) in loop mode means another writer exists: journaled as `foreign_writer`; in `--once` it
  counts as done.
- Every string is cleaned before `dump()`: NUL and control characters dropped, encoded with errors="replace" (jsonb refuses a
  NUL and half a surrogate pair), cut to `text_max_chars` (240). Tests: a NUL, a lone surrogate, a 1 MB string.
- One row per problem per New York day in `state/dash_errors.jsonl` (place, error type, HTTP status), the engine's `error_once`
  pattern. Never `str(e)` of a network error: it holds the address. The address is never printed or logged.
- Who may publish. The address and the key reach every session of the environment, and a lock protects one checkout only. So
  the publisher pushes only when `state/dash_writer.json` exists: a machine-local, git-ignored marker written by `dash-publish
  --claim`, which only the trader session's watchdog and slot prompts run. Without it: one printed line, "not the publishing
  checkout", exit 78 in loop mode. `--once` without the marker prints the same line and exits 0. `--no-push` and
  `--dry-run` need neither the marker nor the variable. No mode claims by itself; a slot's line is `dash-publish --claim &&
  dash-publish --once`.
- What the publisher process may touch, enforced at start, not promised: `journal.save_json`, `append` and `write_all` are
  wrapped with an allow-list of its own file names; a test asserts that after `import aitrader.dashpub` none of
  `aitrader.notify`, `aitrader.news_live` and `aitrader.broker` is loaded (the alert path's quiet-hours code writes state [C
  notify.py:29-34]); one test runs a full tick over fixture state under these guards.
- Every tick is inside one try/except; the loop ends only at `--until`, on a signal, when its parent is gone, or by the
  watchdog. It runs at nice 10, takes no engine lock, and raises its own out-of-memory score (`/proc/self/oom_score_adj`) to
  `oom_score_adj` (500), so that a machine short of memory takes it before the engine (dt, best effort).
- Its files. Git-ignored: `state/dash_publish.json` (heartbeat: time, pid, seq, pace, last good push, failures in a row, last
  error type), `state/dash_publisher.lock`, `state/dash_writer.json`. Tracked, append-only, never rewritten by the publisher,
  like the engine's health journal: `state/dash_errors.jsonl` and `state/dash_health.jsonl` (one row per 300 s: pushes ok and
  failed; build, quote and push times as median and max; the largest gap between good pushes; bytes; quote calls, 429s,
  timeouts; yields; skipped ticks by reason; about 78 rows a session, computed).
- Environment: one variable, `AITRADER_DASH_URL`; `config.json` holds its name, like `alerts.ntfy_topic_env` [C
  config.json:235]. Missing: one printed line, one journal row `not_configured` per day, exit 78 in loop mode. No session ever
  runs `printenv` or `env` to look at it: the test is `[ -n "$AITRADER_DASH_URL" ]`. Nothing else in the bot changes.

### 3.8 `config.json` block `dashboard_push`, and what the build must measure
Rule 5: every number in section 3 is a key of `dashboard_push` with the value in brackets, a design value until measured. The
rest: `url_env`, `connect_timeout_seconds` 5, `push_timeout_seconds` 10, `backoff_max_seconds` 300, `health_log_seconds` 300.
The page's own numbers are not config: they are constants of the page (5.11).

Nothing was timed for this spec. Before step 1 the build measures: (a) `dash-publish --dry-run`, 20 runs on the trader machine
with the real state: state part, quote part, total, bytes, memory. If the state part is over 1 s: re-read a journal only when its
size or mtime changed, then read only appended bytes (`news_scores.jsonl` was 731,173 bytes on 2026-11-10 [M `state/`] and
today's builder reads it whole [C dashboard.py:120]). (b) The age of Yahoo's quotes in session: now minus `regularMarketTime`,
per symbol, one hour.

## 4. The database

As applied [F]:
- Table `public.trader_live(id text primary key, payload jsonb not null, updated_at timestamptz default now())`. Row level
  security on, no policies; all privileges revoked from `anon` and `authenticated`.
- Function `public.publish_snapshot(p_id text, p_payload jsonb)`: security definer, `search_path` empty; only id `snapshot`, only
  a JSON array of at most 400,000 bytes (`pg_column_size`); upsert with `updated_at = now()`. Execute granted to `anon`. Tested
  with the publishable key: a write 204 in 1.19 s; a wrong id 400 "unknown snapshot id"; a read 401; a delete denied.

Step 0 makes three changes, by one migration from the main session.
1. The grant the security advisor flags [F]. If the check still says true for `authenticated` after the first line, the right
   comes through PUBLIC and the next two lines are needed. Expected at the end: `anon_ok` true, `auth_ok` false.
```sql
revoke execute on function public.publish_snapshot(text, jsonb) from authenticated;
revoke execute on function public.publish_snapshot(text, jsonb) from public;
grant  execute on function public.publish_snapshot(text, jsonb) to anon;
select has_function_privilege('anon', 'public.publish_snapshot(text, jsonb)', 'execute') as anon_ok,
       has_function_privilege('authenticated', 'public.publish_snapshot(text, jsonb)', 'execute') as auth_ok;
```
2. A floor between writes, inside the function. The upsert becomes conditional, and a call that changed no row is refused. The
   30-second publisher never meets it; it bounds what a key holder can write to 12 rows a minute. The sketch below is written
   against the description of [F], not the applied body: the migration is written against the applied body.
```sql
  insert into public.trader_live as t (id, payload, updated_at) values (p_id, p_payload, now())
  on conflict (id) do update set payload = excluded.payload, updated_at = now()
    where t.updated_at <= now() - interval '5 seconds';
  get diagnostics n = row_count;
  if n = 0 then raise exception 'too soon'; end if;
```
3. The size limit goes from 400,000 to 100,000 (dt; set again from the ratio step 1 measures, 3.5).

Tests after step 0: the three of [F] again; two writes one second apart, the second refused with "too soon"; a payload over the
limit refused. Also checked then, **?** today: that sign-ups are off in the project's Auth settings (the same key reaches those
endpoints).

- The write-only door: whoever holds the address and the publishable key can overwrite the one row with any JSON list up to the
  size limit, once every 5 seconds. He cannot read it, delete it, write another id or change the schema [F]. That buys him false
  numbers and headlines on the owner's screen. It cannot reach the bot (nothing reads the row back), move paper or real money,
  run code on the page (the page writes text only, 5.11), or show him the book.
- The row is also a way to put text in front of a Claude session: a session that selects `payload` to debug reads whatever was
  written there, with its tools in hand. Rule, here and in the trader skill: sessions never select `payload` or any text out of
  it. Diagnostics are `updated_at`, sizes, counts, `jsonb_typeof`, and fields cast to numeric.
- The key lives only in the environment's credential store: not in the repository, the page, a variable, a log, a report, a
  fixture, a commit message or this spec. The page does not need it; it reads through the owner's signed-in connector. One unit
  test scans the tracked files for the platform's two key prefixes followed by 20 or more characters, a JWT-shaped string, a
  20-letter host under the platform's domain, and a 20-letter `project_id` value.
- Upgrade path, when the row holds anything but paper data, or at the first `foreign_writer` row: revoke execute from `anon`,
  grant it to the service role, and store a secret key in the same credential form. A foreign write can also be seen by
  comparing the row's `seq` and `writer` with what the publisher journals; not automated here (backlog).

Retention: one row, overwritten at every push; no history. Each overwrite leaves a dead row version until autovacuum; the build
reads `pg_total_relation_size('public.trader_live')` after the first full day. Traffic, computed from [M]: about 830 pushes a day
(780 in session, 41 before the open, about 10 slots) x 7.3 KB = about 6 MB a day up; an open page reads 7.3 KB twice a minute,
under 1 MB an hour. The free plan's quotas are **?**; the build compares these numbers with the project's usage page. A week
without activity: the free plan pauses an idle project after about a week (Supabase's published rule, not re-checked here; what
counts as activity is **?**). The crypto slots push every night, so the project is not idle while the bot runs. If it is paused,
pushes fail (one journal row), the page shows the file marked "not live", and the owner or his main session restores the project.

## 5. The dashboard

One file, `dashboard/index.html`, Hebrew, RTL, starting with `<meta name="dash-one-writer">` as today [C index.html:1]. The store
gains one dataset. `dash/settings.updates` becomes `"viewed"`, so that opening the page runs the query again [R sources]: the
main session reads the document first, records the old value for the undo, and writes with `update`, never `set`, because the
same document holds `shared`, which only the page writes [R sources]. The Supabase connector stays unshared: a shared one counts
`viewed` as 5 minutes [R sources], which ends live.

### 5.1 Dataset `live` (exact call)
```json
{"title": "תמונת מצב חיה", "description": "השורה האחת שהבוט כותב למסד הנתונים כל 30 שניות בשעות המסחר: המסך הראשון בלבד",
 "source": {"kind": "call", "connector": "Supabase", "tool": "execute_sql",
            "args": {"project_id": "<the project's ref>",
                     "query": "select id, extract(epoch from updated_at)::float8 as updated_epoch, extract(epoch from now())::float8 as now_epoch, payload from public.trader_live where id = 'snapshot'"}}}
```
This is the query verified in [F] with its two time columns returned as numbers: the write time otherwise arrives as Postgres
text, which JavaScript's date parsing does not promise to read. The two numeric expressions are run by the main session at step
1b (numbers only, section 4), and the whole call by the page itself at step 2. `connector` is copied from the probe dataset that
worked on the phone [F]. No filter, no rule. The existing dataset `snapshot` (kind file) is not touched. The hourly task writes
only that file: never `datasets/live`, never `index.html`. After any change to the page the main session reads the `live` source
back from the store and compares it with the text above, because the stored query runs with the owner's whole Supabase access.

### 5.2 Loader `live`
The tool answers `{"result": "<text>"}`: a sentence, the rows as a JSON list between `<untrusted-data-UUID>` and
`</untrusted-data-UUID>`, another sentence [F]. Both reviewers recall, from the connector's published code, that each sentence
also contains the opening tag as words; **?**, no one re-read it. The page type hands a loader the value out of a wrapper whose
only key is `result`, and a list for several items [R sources]. Before the loader is written, one real answer is saved byte for
byte as the harness fixture: the answer to the probe's constant query (it carries no row text), with a fixture payload put in
place of its empty list. `dash.loader('live', {description,
fn})`, using nothing from outside itself [R sources]:
1. Text: `answer` if it is a string; `answer.result` if that is a string; for a list of items with a string `text`, those texts
   joined. A list of row objects is taken as the rows and step 2 is skipped.
2. The id is taken from the first `<untrusted-data-(id)>` in the text (the tool's own words, before any data). The text must
   hold exactly one `</untrusted-data-(that id)>`. The block is what lies between the last `<untrusted-data-(that id)>` before
   that closing tag and the closing tag, trimmed and parsed as JSON. This rule reads both shapes, the verified one and the
   recalled one. The id is random per answer, so a headline cannot forge either tag.
3. It must be a list of exactly one object with `id` "snapshot" and finite numbers `updated_epoch` and `now_epoch`, with
   `now_epoch` not below `updated_epoch` by more than 5 and both between 2026 and 2100. `payload` is parsed again if it is a
   string.
4. `payload` must be a list of at most 2,000 objects, each with a string `t`, exactly one of them `stat`. Every `stat` field the
   badge or the timer uses is checked for type and range: `as_of_epoch` a finite number; `market_open` true or false; `sessions`
   a list of at most 10 pairs of finite rising numbers; `expect_next_by` a number or null; `quote_age_max_s` null or a number
   from 0 up; `quotes_missing` a whole number from 0 up; `seq` a whole number; `mode` and `quote_state` one of their words.
5. Return `{columns, rows, meta}`. `rows` is the payload as it is, except that the `stat` row gains `db_updated_epoch` and
   `db_now_epoch`. `columns` is the union of keys, as the `snapshot` loader builds it [C index.html:527-535]. `meta`: the write
   time, the age at the read, the row count, `seq`; only what the answer carried [R sources].
6. Anything else throws an `Error` with a short Hebrew sentence that names the step (5.10). When no data block was found, the
   first 200 characters of the answer follow it: those are the connector's own words [R sources], and they tell a paused project
   from a wrong project id. The source then fails and the page falls back (5.3).

### 5.3 The one place that chooses between live and file
The first tab is drawn from one snapshot: a list of rows built at one moment. The choice is made once per data change, in
`dash.onData` (it runs before the drawings [R one-writer]), and kept as `current = {source, rows, stat, seq}`. The first tab's
drawings read `current` only, through `nowData(id)`, so one draw pass can never mix two snapshots, and a single drawing that
reruns alone (a width change) reads the same one as its neighbours. `dash.data('live')` and `dash.data('snapshot')` are read in
`onData`, so both load at opening even while the second tab is hidden [R one-writer].
- Candidates: LIVE = the rows of `dash.data('live')` when its status is ok, else the last good live rows this page kept in
  memory (one failed refresh must not throw the page back an hour). FILE = the rows of `dash.data('snapshot')`. A FILE from
  before this change has no `stat` row: its time is `kpi.as_of`, and its first-tab tables count as not in the snapshot (5.9).
- Rule: LIVE is shown unless (a) there is no LIVE, or (b) FILE's build time is later than LIVE's write time on the database's
  clock (`db_updated_epoch`) by more than 120 s, or (c) FILE's `state_epoch` is later than LIVE's by more than 120 s: the live
  writer is reading older state than the hourly builder (a stale checkout, or someone else's row). The payload's own `as_of`
  plays no part in the choice, so a row cannot pin itself on screen by claiming a time in the future. Because the hourly task
  ends with a push (3.1), a healthy path never meets (b), in or out of the session.
- When `current` changes identity (another source, another `seq`, another file time), `onData` calls `dash.draw(name)` for
  every first-tab drawing. The page does not rely on the platform rerunning a drawing for a dataset its element is not marked
  with: that behaviour is **?** (probe P5).
- Marks. Seven calcs over `live`, written like the 25 existing ones (`dash.calc('now_book', {inputs: ['live'], ... fn: (live) =>
  live.filter((row) => row.t === 'pos' || ...)})`): `now_stat`, `now_money`, `now_accounts`, `now_book`, `now_tape`, `now_plan`,
  `now_heads`. Each first-tab element is marked with its calc and the row's `key`, so in the normal state Sources lights the
  true row. While the file is shown the mark is not true; the badge says so, and one stored line in the health card of "עוד"
  says where the first tab's numbers come from in that state. A harness test checks that `TABLES` (the tag list `nowData` uses)
  and the seven calcs agree. If probe P7 shows that the platform covers a marked element whose source failed, the first-tab
  elements are stored unmarked and only the badge is marked `now_stat`.
- Not used: one calc with both datasets as inputs. What a calc does while an input is failed or loading is **?** (probe P6);
  the `onData` form works under either answer. The choice of a source is not arithmetic on a shown number, so it needs no calc.
- The 25 existing calcs and the second tab's drawings are not changed [C index.html:536-560].

### 5.4 Clock and age
The phone's wall clock is used only as a difference. At each new answer of `live` (`db_now_epoch` differs from the last one
seen) `onData` records the arrival on both clocks, `performance.now()` and `Date.now()`, and the duration of the request when
the page started it.
- Database age at the read: `db_now_epoch` - `db_updated_epoch`. Skew: the phone's wall time at arrival - `db_now_epoch`.
- Age at arrival: database age + skew held between 0 and the request's duration, when the page started the request. For the
  first answer, which the platform started, or kept from an earlier visit [R sources]: database age + skew, when skew is above
  0. Both err on the old side.
- Age now: age at arrival + the larger of the two elapsed times. Android can freeze the monotonic clock while the phone sleeps,
  and the wall clock can be set back; the larger one is right in both cases.
- "Now" for every session test is `db_now_epoch` + the same held skew + the same elapsed time: the database's clock, not the
  phone's.
- An answer with the same `db_now_epoch` as the one before is a replay: nothing is recorded and the age keeps counting.
- A skew beyond 60 s either way is said in the reason line (5.5); it does not change the arithmetic above.
- For FILE: the same "now" when a live answer has ever arrived, else the phone's clock; age = now - the file's build time.
- If the payload's `as_of_epoch` is more than 120 s before `db_updated_epoch` (an old build written late), the age is counted
  from `as_of_epoch`, and a difference beyond 120 s either way is said in the reason line.

### 5.5 Freshness badge
In session at time T: one pair of `sessions` holds T. The session list comes from FILE's `stat` row while that list still reaches
past T (the file arrives through the owner's own upload path), else from LIVE's. With no list reaching T the state is `nocal`.
The 120 s is the owner's limit and is one constant of the page (`STALE_S`), not a field of the row it judges [R one-writer].

Stored HTML: one line `#fresh` in the header holding an empty chooser `<span data-draw="fresh">`, one `<span data-s="...">` per
sentence below (all but `wait` stored `hidden`), and inside a sentence each drawn part as its own `<b class="num"
data-draw="age" data-age="...">—</b>`. The chooser is marked `data-source="now_stat"`. It sets `hidden` on the sentences and a
state class on the line (outside a drawing a script may set only such attributes [R one-writer]), then calls
`dash.draw('age')`; it never writes text. `age` kinds: `s` whole seconds, `m` whole minutes, `hms` HH:MM:SS, `t` HH:MM when the
Israel date is today and DD.MM HH:MM when it is not, `pm` minutes since the oldest price (`money.price_epoch_min`). Seconds
are used up to 120 s, minutes up to 120 minutes, a time beyond that.

The first row that holds, top to bottom, is the state:

| # | State | Holds when | Stored sentence (‹x› = a drawn part of kind x) | Colour |
|---|-------|-----------|-----------------------------------------------|--------|
| 1 | `wait` | no source yet, a load still running, under 20 s since opening | מתחבר לנתונים | muted |
| 2 | `none` | no source, and both loads ended or 20 s passed | אין נתונים | bad |
| 3 | `file_wait` | FILE shown, the first load of `live` still running, under 20 s | תמונת מצב שעתית מ-‹t› · מתחבר לנתונים החיים | muted |
| 4 | `file` | FILE shown | לא חי · תמונת מצב שעתית מ-‹t› | warn; bad in session |
| 5 | `nocal` | LIVE shown, no session list reaches now | נכון ל-‹t› · לוח ימי המסחר לא ידוע | warn |
| 6 | `wait_open` | LIVE, in session, age over 120 s, the row was written before this session's open, under 120 s since the open | השוק נפתח · ממתין לעדכון ראשון | muted |
| 7 | `slow` | LIVE, in session, age over 120 s | לא מתעדכן · עודכן לפני ‹m› דקות; beyond 120 minutes: לא מתעדכן · מאז ‹t› | bad |
| 8 | `prices_old` | LIVE, in session, age at most 120 s, and `quotes_missing` is above 0, or `quote_state` is "yield", or `quote_age_max_s` + the time since the build is over 180 s | חי · המחירים מלפני ‹pm› דקות | warn |
| 9 | `ok` | LIVE, in session, age at most 120 s | חי · נכון ל-‹hms›, and the counting part: · לפני ‹s› שניות | ok |
| 10 | `not_final` | LIVE, not in session, the row says `market_open` true and its session has closed | שוק סגור · העדכון האחרון מ-‹t›, לפני הסגירה | warn |
| 11 | `late` | LIVE, not in session, now is more than 600 s past `expect_next_by` | שוק סגור · לא התעדכן מאז ‹t› | warn |
| 12 | `closed` | LIVE, not in session | שוק סגור · נכון ל-‹t› | muted |

- The reason line `#why`, under the badge, shows at most one stored sentence, in states `none`, `file`, `slow`, `prices_old`,
  `not_final`, `late` and whenever a clock differs: the connection waits for his approval (status "connect"); the read failed;
  the read did not come back in 20 s; the database has not moved since ‹t›; the live row is older than the hourly file; Yahoo
  gives no new prices; the prices are paused so as not to disturb the engine; the phone's clock differs from the server's; the
  bot's clock differs from the database's (5.10).
- True without any timer. Whatever is drawn at an answer is an absolute time and needs no tick: every sentence but the counting
  part of `ok`. A warn or bad state drawn at an answer keeps its colour. The counting part and the ok colour are shown only
  while the 1-second tick is alive: each tick restarts a CSS animation on `#fresh`; when it runs out (5 s with no tick) the
  counting part is hidden, the colour goes neutral and the stored sentence "הספירה נעצרה · לחץ רענן" shows. This dead-man is
  CSS only.
- Red without any timer. At each answer shown in session with an age under 120 s, the page arms a second CSS animation whose
  delay is the seconds left until 120 s (one custom property). When it fires, CSS alone hides the sentences and shows the
  stored "לא מתעדכן · לחץ רענן" in the bad colour. A new answer re-arms it; outside the session it is not armed. While the tick
  runs, the tick reaches state `slow` at the same second, so the two agree.
- Both animations are single steps, not motion. Whether the phone runs them is **?** (probe P2); if a reduced-motion setting
  stops them, the absolute time still stands. The exact CSS is the builder's; the harness cases of section 7 are the contract.
- Examples: a row that died at 15:59, seen at 18:00, is `not_final`, not red all evening. Friday's row on Monday is `wait_open`
  from 09:30 to 09:32 and `slow` after. A row from 08:00 seen at 09:30:01 is `wait_open`, not red.

### 5.6 The refresh
- The timers live in the `fresh` drawing, written as `{mount, update, unmount}`: a timer belongs in a drawing's `mount`, and
  inside a drawing code may write from a timer [R one-writer]. `mount` starts the 1-second tick (it recomputes the state, sets
  `hidden` and classes, calls `dash.draw('age')` and `dash.draw('why')`, and, when the state changed, the status block's
  drawings) and a `setTimeout` chain that calls `dash.refresh('live')`; `unmount` clears both. `mount` runs again after a throw
  [R one-writer]; until then the dead-man shows.
- Period, from the page's own clock (5.4), whatever the row says: 30 s from 60 s before a session's open to 120 s after its
  close; 300 s otherwise; 30 s before any row has loaded. One extra refresh 5 s after the open.
- While the state is none of `ok`, `prices_old`, `wait_open` and `closed`, the chain also calls `dash.refresh('snapshot')`, at
  most once in 300 s: a page left open through a dead live path still gets each new hourly file. In the other states it
  does so once in 1,800 s, so that "עוד" follows the hourly rebuild on a page left open.
- No call is made: after `unmount`; while the page is not visible (`visibilitychange`: none in the background, one at once on
  return); while a refresh the page started is still unanswered and younger than 20 s; while the status of `live` is "connect"
  (asking again could raise the platform's approval prompt again; only the button asks then). After a failed refresh the period
  doubles, up to 300 s, until a success.
- Fallback: a button "רענן" in the header, in the HTML. A plain listener calls `dash.refresh('live')` and
  `dash.refresh('snapshot')`. It works with no timer at all.
- `[data-dash-source-state=refreshing] { opacity: .5 }` [C index.html:58] must not dim the first tab every 30 seconds: the rule
  is limited to the second tab. Old numbers beside a new filter, the reason for the rule, cannot happen on the first tab.

### 5.7 Header and two tabs
- The header sits above both tabs and is never hidden: the title, "כסף נייר", the badge, the reason line, the button and the two
  tab buttons (עכשיו, עוד). If the badge were inside the first tab, opening "עוד" would unmount it and stop the timers [R
  one-writer]. Each button has a tap box of at least 44 x 44 px, measured in the harness.
- Two `<section>`s of `index.html`, `#now` and `#more`, the second stored `hidden`: nothing marked under `hidden` loads or draws
  until it comes off [R one-writer]. The tab listener sets `hidden` and `aria-selected`, calls `dash.setLink(id)`, and then
  calls `dash.draw(name)` for every drawing of the shown tab; that is allowed, and it removes the question whether drawings run
  by themselves when `hidden` comes off (**?**, probe P4).
- On opening, `location.hash` picks the tab. An old link such as `#crypto` opens `#more` and scrolls there: every existing
  section keeps its id. `#more` starts with a row of plain links to its sections (a navigation aid, not data; he is told at step
  3); a listener scrolls and calls `dash.setLink`.
- `#more` holds every section that exists today, unchanged and in today's order (tiles, equity chart, position tables, orders,
  desk, all 60 headlines, scorecard, the 40-trade journal, weights, time machine, rules, health, schedule, blackout, lessons,
  crypto, footer), the since-start sentence [C index.html:78-83], and today's header line [C 71-77] as its first line, with the
  stored words "תמונת מצב שעתית ·" before it: the tab says its own time. Nothing is deleted from the page. The first tab's plan
  block replaces that line's "last decision" words while a decision waits; at other times they are read here.
- New in the health card of `#more`, a small block "הנתיב החי" drawn from `current`: `seq`, bytes, build and push times, quotes
  missing and their age, the publisher's and the engine's commit, the next open, and `seen` (when the page last got an answer,
  how long the first file rows and the first live rows took, labelled as measured by the page). Basic law 2 asks for these
  numbers on the dashboard; the approved first tab does not list them, so they live here.

### 5.8 First tab, in order
Columns change at a card width of 480 px, by a container query, not the screen's width: the page also shows in a narrow pane [R
design-defaults].

| # | Block (id) | Rows | What is shown |
|---|-----------|------|---------------|
| 1 | Money (`#money`) | `money`, `acct` | the total as the big figure; today's change in dollars and percent, for the stock books; cash in dollars and percent; against SPY (`vs_spy_day`, with `spy_day_pct`); one line for the crypto book's change since 00:00 UTC, hidden when null; one caption with the base's time. The label is "היום" when `day_is_today`, else the stored sentence with `day_date`. Open question 1: a three-row accounts table under it |
| 2 | The book now (`#book`) | `pos`, `npos`, `cpos` | under 480 px four columns: `symbol`, `last`, `day_pct`, and one cell with `pnl_usd` over `pnl_pct`. From 480 px: `book`, and the two P&L numbers in their own columns. Every position is listed |
| 3 | Bought and sold (`#tape`) | `tape` | under 480 px four columns: `time`, one cell with `side` and `symbol`, `price`, `pnl`. From 480 px: `qty`, `book`. Today's rows carry a filled dot |
| 4 | Planned (`#plan`) | `plan` | one cell with `side` and `symbol`, `size`, `when`, `src`; `note` under the symbol when not empty. One stored sentence when `stat.buys_held` is true, chosen by `buys_why` |
| 5 | Headlines (`#heads`) | `news` | a list, not a table: line one the `score` as a pill coloured by `mark`, the `symbol`, the `time`; line two the `headline`, held to two lines by CSS. The class `.long` with its 240 px floor [C index.html:28] is not used here |
| 6 | Status (`#status`) | `stat` | one sentence for the engine and one for time on the air (5.10); nothing else |

- A stale price is muted and carries a hollow dot; when any row is stale a stored legend line shows. The total says, in one
  stored line, when it includes old prices and from when (`price_epoch_min`). A mark is a CSS shape, never a written character.
- The engine sentence is chosen by the page. "Active": the row says `engine_alive` and `hb_epoch` is within 180 s of the
  page's own "now" (5.4). Otherwise, while the badge is `ok`, `prices_old` or `closed`: "not answering" (bad) when the row
  says not alive and `engine_expected`; "off outside its hours" (muted) when it says not alive and not expected: at night and
  at weekends that is the plan, and today's code already tells the two apart [C dashboard.py:268]. In every other case "not
  known, as of ‹t›": a frozen row must not go on saying "active". The heartbeat's time and the stops' time are drawn as
  absolute times, so a long scorer step shows as an old beat with its time, not as a bare "dead".
- When `stat.tape_more` is above 0, a stored line under the trades says how many more of today's trades are in "עוד".
- [P] measured, with a rougher layout and stub fonts: at 400 px the tab was 2,062-2,224 px and the money block ended at 406 px;
  at 360 px the book was 43 px, the trades 41 px and an accounts table 9 px too wide, and the tab up to 2,393 px. The column
  merges above answer that. The harness numbers stay a proxy; the phone check of step 3 is the proof.

### 5.9 The state of each block
`nowData(id)` returns `{status, data, known}`, like `dash.data` plus one flag.

| `current` | `status` | `data` | `known` |
|-----------|----------|--------|---------|
| LIVE or FILE | "ok" | the rows of the table's tags, possibly none | true when the snapshot has a `stat` row and `stat.trimmed` does not name the table |
| none, a load still running, under 20 s | "loading" | none | false |
| none, both loads ended or 20 s passed | "error" | none | false |

| Block | loading | no rows, known | not known | error |
|-------|---------|----------------|-----------|-------|
| Money, accounts, status | skeleton on each figure | cannot happen: the rows always exist | "—" in each figure and the stored line "אין נתון בתמונת המצב הזו" | "—" and "הטעינה נכשלה" |
| Book | skeleton, 96 px | אין פוזיציות פתוחות. הכול במזומן. | the same stored line | הטעינה נכשלה |
| Bought and sold | skeleton | עוד לא היו עסקאות. With older trades but none today, the line "היום לא היו עסקאות. האחרונות:" above the rows | the same | the same |
| Planned | skeleton | אין קניות או מכירות מתוכננות. | the same | the same |
| Headlines | skeleton | עוד לא נקלטו כותרות. | the same | the same |

An empty sentence states a fact ("no positions"), so it shows only when `known` is true: a file built by older code, or a
trimmed payload, must not read as a true zero [R sources]. A field with no value shows "—". The skeleton class is removed by the
script once the status is not "loading" [R design-defaults].

### 5.10 Strings
Every word the owner reads is in the HTML and is listed here or in 5.5, 5.8 and 5.9; the spec is where they are approved. Stored
HTML (S) is chosen by a drawing that sets `hidden`; a display word (B) is sent by the bot inside a row; a code (C) is never
shown and picks a stored sentence or a class through a fixed list. Code-to-sentence choices are stored elements with
`data-when="<code>"`, as the page does today for `data-when` and `data-legend` [C index.html:357, 677].

| Where | Text | Kind |
|-------|------|------|
| Tabs, button | עכשיו · עוד · רענן | S |
| Reason line | החיבור ל-Supabase מחכה לאישור שלך · הקריאה מהמסד נכשלה · הקריאה לא חזרה · המסד לא התעדכן מאז ‹t› · הנתונים החיים ישנים מהתמונה השעתית · Yahoo לא מחזיר מחירים חדשים · המחירים בהמתנה כדי לא להפריע למנוע · שעון הטלפון שונה משעון השרת · שעון הבוט שונה משעון המסד | S |
| Money | כמה כסף · שווי כולל (שלושת התיקים) · היום (מניות) · ביום המסחר האחרון, ‹date› (מניות) · שינוי יומי: אין בסיס להשוואה · מזומן · מול SPY · SPY היום · קריפטו: ‹$› מאז 00:00 UTC · בסיס: סגירת ‹time› · השווי כולל מחירים ישנים, הישן מ-‹t› | S |
| Book | התיק עכשיו · מניה · מחיר · היום · רווח/הפסד · תיק · מחיר מעומעם = מחיר ישן | S |
| Bought and sold | נקנה ונמכר · שעה · פעולה · מחיר · רווח ממומש · כמות · תיק · נקודה מלאה = היום · ועוד ‹N› עסקאות היום בלשונית "עוד" | S |
| Planned | מה מתוכנן · פעולה · גודל · מתי · מקור · קניות חדשות מחדשות עצורות: יש הפסד שעוד לא נבדק (`loss_review`) · קניות חדשות מחדשות עצורות עד להודעה שלך (`hold`) · קניות חדשות מחדשות עצורות (any other code) | S |
| Headlines | כותרות אחרונות · ציון 1-10: ירוק = ציון קנייה, אדום = ציון מכירה | S |
| Status | מצב המערכת · מנוע החדשות פעיל · דופק אחרון ‹hms› · סטופים נבדקו ‹hms› · מנוע החדשות לא עונה · דופק אחרון ‹t› · מנוע החדשות כבוי עכשיו, מחוץ לשעות הפעילות שלו · מצב המנוע לא ידוע · נכון ל-‹t› · באוויר היום ‹h:mm› מתוך ‹h:mm› (‹%›) · באוויר היום לפחות ‹h:mm› מתוך ‹h:mm› · אין היום מסחר במניות | S |
| Loader errors | אין בלוק נתונים בתשובה · התשובה אינה שורה אחת · התוכן אינו רשימה · חסרה שורת המצב או שהיא לא תקינה | S in the loader's code, shown in Sources |
| In rows | `book`, `name`, `side`, `src`, `size`, `note`, `time`, `when`, `day_base_at` | B |
| In rows | `mark`, `buys_why`, `mode`, `quote_state`, `on_air_src`, `key`, `writer` | C |

### 5.11 Drawings, formats, safety, constants
- The existing drawings `kv`, `rows`, `equity`, `pick` and `gauge` [C index.html:624-799] keep reading `dash.data` and are not
  changed, with one repair: `td.className += ' st-' + v` [C 607] becomes a lookup in the fixed list ok, warn, bad. New drawings,
  all reading `current`: `nkv` (one value), `nrows` (a table body; a cell may hold two fields), `heads` (the headline list),
  `npick` (a stored sentence by a code or a flag), `fresh`, `age`, `why`, `seen`. They share `fmt` and `cell` with the old ones.
- The payload is untrusted (anyone with the key can write it; headlines come from the web). The page writes it only through
  `textContent`; formats only real numbers (a number sent as text shows "—"); renders no link; maps `mark`, `buys_why` and every
  status through fixed lists and never joins payload text into a class name; cuts a cell to 300 characters; draws at most 100
  rows a table.
- Formats: the existing `d3.format` table [C 565-569]. Dollars whole, prices with 2 decimals, percents signed with 2 decimals,
  colour by sign. `h:mm` for a duration from seconds. Badge times are formatted by the page in Israel time from epoch numbers;
  the times inside rows are formatted by the bot. Numbers and tickers run left to right inside the RTL text (`.num` [C 16]).
- Constants of the page, in one place in the script, each with a harness case: `STALE_S` 120; old-price limit 180 and engine
  beat limit 180 (a harness case compares them with `dashboard_push.max_quote_age_seconds` and `engine_alive_seconds`);
  in-session period 30, other period 300, open refresh 5; file refresh 300 and 1,800; wait 20; open grace 120; lead before
  the open 60; tail after the close 120; late 600; clock gap 60; tick dead-man 5; request time-out 20; failure period cap
  300; rows 100; cell 300; seconds up to 120 s, minutes up to 7,200 s.

## 6. What the owner does and is told
Raised by his main chat session, never by the trader session (it runs unattended, and a waiting prompt would hold every
scheduled turn [S 9]).
1. The write key, through the secure credential form: host = the project's address, header `apikey`, no prefix, label "dashboard
   write key (paper data)". He copies the key called "publishable" from his project's API settings page and pastes it into the
   form himself (the main session gives him the exact taps then; that page's wording is **?** today). It is never typed in chat
   and no session ever prints it. The proxy then adds it to requests to that host, within about a minute by the credential
   tool's own description (not timed here), and the value never reaches a machine. The form's sentence says: this lets the bot
   write the dashboard's one row; it is for the screen only and cannot trade.
2. One approval card for one variable, `AITRADER_DASH_URL`, and nothing else, after `get_environment`. It reaches the trader
   session when its machine is next restored or rebuilt [F], in practice the next morning.
3. Both are saved on the environment the trader session runs in. Which environment that is follows his answer to [S] question
   11; it is not asked again here. If he declines either, everything stays as it is today and no second prompt is shown.
4. The probe (7, step 1.5): he opens one page once, for two minutes.
5. The platform itself may ask him once, on the phone, to let the page use Supabase; that prompt is not ours.
6. What he sees change: nothing on the day of the form (the database fills, no page reads it); after step 2, a badge at the top
   and the money block under it; after step 3, the short first tab and the tab "עוד".
7. Told at step 3, a line each, in Hebrew, because he learns it only from the session [R design-defaults]: he can ask for any
   table, chart or button by name; he can download any source's rows as CSV from Sources; as editor he can edit the live query
   in Sources, test it, save it and restore an earlier one, and replace the attached file; the live query runs when the page is
   opened, when he taps "רענן" and every 30 seconds in market hours while the page is open, with his own Supabase access;
   everyone who can open the dashboard can read the attached hourly file; the first tab is live and "עוד" is hourly and opens
   with links to its parts; "today" is the stock books against the last close, and crypto has its own line.

## 7. Rollout (each step leaves the dashboard working)
| Step | Change | Check | Undo |
|------|--------|-------|------|
| 0 | The migration of section 4 | the privilege query; the five tests of section 4 | the previous function body, kept in the migration list |
| 1a | Python lands through the gate (8). The watchdog prompts start the loop with `--no-push` inside the engine's command (3.1) | the numbers of 3.8; one full dry session; the pass numbers of 3.3; the old page still renders the new file in the harness (unknown tags are ignored; no existing value changes) | the old prompt line |
| 1b | The form and the card of section 6; `--no-push` comes off; ramp pace; the slots and the hourly task end with a push (3.1), so that the row is never older than the hourly file | one full pushed session: `dash_health.jsonl` against targets 7-9, the pass numbers of 3.3 again; through the connector at five times of day, numbers only: `select updated_at, pg_column_size(payload), octet_length(payload::text), jsonb_array_length(payload)` | `--no-push` back, or the old prompt lines |
| 1c | The many-symbols form is tried; then `--pace full` | one full session; the pass numbers of 3.3 | `--pace ramp` |
| 1.5 | The probe page (below); can run beside step 1 | the ten answers written into this spec; then 5.3-5.7 are frozen | - |
| 2 | Dataset `live`, loader, the pick, header with badge, reason line and button, and the money block, above the page as it is today (one scroll; today's header line stays) | harness cases below; the page's own check report (no one-writer fault) and runs report (`live` ok with rows); the phone checks below | the previous `index.html` from git first, then delete the dataset [R sources: page before dataset]; `updates` back to the recorded value with `update`. The query text stays in the store's saved versions [R sources] |
| 3 | The two tabs, the rest of the first tab, today's header line moved into "עוד" | harness at 360, 400 and 1280 px: targets 3 and 4, every state of 5.9, opening "עוד" draws its tables, old `#` links, tap boxes. Check and runs reports. Phone. The lines of 6.7 | previous `index.html` |
| 4 | Drill, right after step 3. Later, after the [S] amendment, the supervisor starts the loop and the drill is repeated | in session the trader session ends the publisher alone (TERM); the owner looks: red inside 150 s; it is started again; green | the interim start line of 3.1 |

The hourly task stays as the fallback through every step and after; whether to slow it is decided after two weeks of
`dash_health.jsonl`.

Probe (step 1.5). The page that already ran a connector call on the owner's phone [F] is extended by the main session to print:
P1 how many 1-second ticks and 30-second timers fired in two minutes, and again after a screen lock; P2 whether a CSS
animation with a delay changes a stored element with no script; P3 what `dash.refresh` returns, whether each call under
`updates: "viewed"` makes a new database read (distinct `now()` values), and what `dash.data(id).status` and `.data` read during
a re-run and after a failure; P4 whether drawings run when `hidden` comes off; P5 whether a drawing reruns when a dataset its
element is not marked with changes; P6 what a calc does with a failed input; P7 what the platform itself draws on an element
whose source is in "connect" or "error", and whether the connect prompt appears when nothing is marked with the dataset; P8
whether answers of 60,000 and 200,000 bytes are read; P9 whether a file holding `NaN` is read; P10 the type and the whole
text of `answer` for the constant query `select 'snapshot' as id, 1.5::float8 as updated_epoch, 2.5::float8 as now_epoch,
'[]'::jsonb as payload`. The owner's part, sent as one message: "פתח את הקישור, חכה שתי דקות, נעל את המסך לחצי דקה, חזור לדף
ושלח לי צילום מסך". The harness stub is then written to match these answers; until they exist it models the pessimistic case
(only drawings marked with the changed source rerun; timers never fire).

Phone checks, each one question in its own message, each answer recorded separately. Step 2: (1) "המספר ליד 'לפני' רץ לבד?";
(2) "אחרי שתי דקות בלי לגעת: המספר חזר להיות קטן מעצמו?"; (3) "השווי הכולל השתנה בלי שנגעת?"; (4) "נעל את המסך לדקה וחזור: המספר
רץ?"; (5) "ואחרי חצי דקה נוספת: הוא חזר להיות קטן?". Step 3: (6) "במסך הראשון רואים את הכסף בלי לגלול?"; (7) "משהו נחתך בצד או
זז הצידה?". Step 4: (8) "עצרתי עכשיו את השידור בכוונה. אחרי שתי דקות וחצי: השורה למעלה אדומה?". The read-failure path (connector
off) is proven in the harness only, unless he chooses to switch the connector off once.

Harness. Today `harness/run.js` lives in one session's scratchpad, pastes the snapshot as a JavaScript literal (so `NaN`
passes), calls `(f.update||f.mount)(el)` with no unmount, has an empty `refresh`, and runs at 1280 and 400 px only [M]. It moves
into the repository as `tests/page/run.js` with `tests/page/fixtures/`, under builder B's claim (Node and Playwright, as used on
2026-11-10; a test tool, not a dependency of the bot; recorded in `THIRD_PARTY.md`). It must gain: fixtures loaded with
`JSON.parse`; a `live` dataset whose answer and status the fixture sets; `dash.refresh` with a call count; the real
`mount/update/unmount` contract; a clock and a visibility state the test moves; a 360 px run; the height of `#now`; sideways
overflow of every table wrapper; a `MutationObserver` check that every change of text or children lands inside an element
marked `data-draw` (the page's own check sees only writes made while scripts, `onData` and drawings run [R one-writer]).
- Pinned fixture for targets 3 and 4: 15 positions including BTC-USD at a six-figure price with a five-figure loss, 8 trades, 2
  plans, 8 real headlines including the longest stored one (205 characters).
- Loader: the saved real answer; one fixture per throw step of 5.2; an answer that arrives as a list of text items.
- Badge: one case per row of 5.5 and per overlap (file loaded while live loads; neither loaded; live ok after the file); 121 s
  old; a row from 08:00 with the clock moved to 09:30:01, then 09:32:01; died at 15:59, seen at 18:00; Friday's row on Monday;
  an empty session list; stale prices; a kept answer (old `db_now_epoch`); a phone clock 10 minutes off either way; a replay.
- No timers: with every timer stubbed dead, an answer aged 100 s shows the alarm sentence in the bad colour 20 to 21 s later,
  and the counting part is gone within 6 s.
- Refresh, every rule of 5.6: the period in and out of the session window; the extra call after the open; pause when hidden and
  one call on return; no overlap; doubling to 300 s; no call in "connect"; the button with no timer; `unmount` clears timers;
  the last good live rows are kept after a failed read; the file is refreshed while not live.
- Frozen tables: after a `live` refresh with a new `seq`, a first-tab value changes under the pessimistic stub.
- Hostile payload: markup in a headline, class names in `mark` and a status, 2,001 rows (the loader refuses), 150 rows of one
  table (100 are drawn), numbers as text, a 2,000-character cell; nothing but text reaches the page and no table widens.
- A person's edit: the button and one badge sentence are deleted from the HTML; the page runs with no error [R one-writer].

Python tests, new `tests/test_dash_publish.py` and additions to `tests/test_dashboard_books.py`. A helper, imported first by
both, removes `AITRADER_DASH_URL` and replaces the POST function with one that raises; one test proves that an unstubbed push
raises ([S 11.1] has the same rule for the phone). Then: every new row and field from fixture state; the pushed tags and fields
are exactly the lists of 3.4, and no text of the hold file, a lesson, a trade reason or a scorer's reasoning reaches the
payload; today's change on a Monday, after a holiday, on the first day, with only a midday mark, with a news mark older than
the limit, on a Saturday; the crypto move on a Sunday; the stock move equal to the engine's function; `dump()` output parses
with a strict parser and holds no NaN; the trim order and the degraded set; a 400 is followed by a degraded tick; a NUL, a lone
surrogate, a 1 MB string; no address in a journal row; a missing variable; no marker, exit 78; `--once` with a stale loop, exit
5; a hung tick ends the process with 4; a missing book file, a merge in progress (in a subfolder and in a worktree) and a file
that moved twice each skip the push; `build_now(quotes)` with the network call patched to raise; the yield rule for each of its
three causes; the write allow-list and the import check of 3.7; the scan for keys and refs of section 4.

## 8. Rule 4, the laws, claims
- Nothing here changes a trade. The publisher reads state and writes only its own files and the database row; `dashboard.py`
  only builds display rows; no strategy, risk, learning, engine or data module is edited. But `config.json` is under rule 4
  whatever the key, so the `dashboard_push` block lands through the whole gate: the time machine sweep before and after must be
  identical (the proof that no trading path reads `dashboard_push.*`), `quant-critic` checks that claim with a search, and
  `python3 -m unittest discover -s tests` passes. The golden stock test must not move. The ramp is switched by a start-line
  flag, not by a config edit, so it needs no second gate.
- Each unit that ships gets one independent adversarial review; every agent runs on Fable 5.2. Basic law 2: the publisher's
  speed is a number (`dash_health.jsonl`), shown in "הנתיב החי"; one that gets worse is a backlog defect.
- Build claims (`BUILD_CLAIMS.md`), one builder per file: builder A takes `aitrader/dashpub.py`, `aitrader/quotes.py`,
  `aitrader/dashboard.py`, `aitrader/__main__.py`, `config.json`, the two Python test files and `.gitignore`; builder B takes
  `dashboard/index.html` and `tests/page/`. They can work at the same time once the rows of 3.4 are frozen. `__main__.py` and
  `config.json` are under the open claim of 2026-11-10 20:40 [M `BUILD_CLAIMS.md`]: A waits until it is marked done. The
  watchdog and slot prompts and `skills/trader/SKILL.md` (the rule of section 4 about `payload`, the merge-only sync) are
  changed by the main session at steps 1a, 1b and 4, under a claim of their own.
- Backlog, not built here: the engine reads its day move from `quotes.py`; a second, read-only connector entry scoped to this
  one project for the page; an automatic check for a foreign writer; the slot times in `config.json`, so that a missed night
  push shows after minutes instead of after `once_expect_seconds`; the publisher's own closing mark as the base of "today".

## 9. Open questions for the owner
One question per message. Question 2 is asked before step 1a, because it decides what is pushed; question 1 before step 2.
The spec is written for answer א of question 2; question 1 decides only whether the accounts table's HTML exists.
1. The accounts table on the first tab. The approved first screen lists the total, today's change, cash and SPY; a table of the
   three books (value and today's change of each) was not on the list. "טבלת שלושת התיקים במסך הראשון (כמותי, חדשות, קריפטו:
   שווי ושינוי יומי) - א: להוסיף מתחת לכסף, עוד כ-110 פיקסלים. ב: בלי; שלושת התיקים רק בלשונית 'עוד'." Recommended: א, because
   it is where each book shows by itself. Cost, computed: three rows of about 27 px [P] and a header. The `acct` rows are built
   either way; only the table's HTML depends on the answer. On ב nothing else changes.
2. The tab "עוד". "הלשונית 'עוד' - א: מתעדכנת פעם בשעה, והשעה כתובה בראשה. ב: גם היא חיה כל 30 שניות; אז גם הלקחים, החוקים,
   מכונת הזמן ובריאות המערכת עולים למסד הנתונים." Recommended: א: he was told that only the paper book sits in the database,
   the row stays about 7 KB instead of about 42 KB [M], and the second tab keeps working exactly as today. On ב sections 3.4,
   3.5, 4 (size) and 5.3 are redone.
3. Asked only if the pass numbers of 3.3 fail. "Yahoo לא עומד בקצב המחירים שתוכנן בלי להפריע לבדיקת הסטופים של המנוע - א:
   מחירים בקצב האיטי שעבר את הבדיקה (כל דקה, ואם צריך כל 5 דקות), וכל השאר כל 30 שניות. ב: מקור מחירים שני, כפרויקט נפרד."
   Recommended: א: the stops come first (the basic law).

## 10. Honest limits
1. Timers and CSS animations on the phone are not proven: the probe showed a live connector call, not that a timer fired [F].
   Step 1.5 answers it. If timers do not fire, the button is the way, the badge shows an absolute time and "הספירה נעצרה", and
   the red alarm rests on the CSS animation; if that does not run either, nothing on the page turns red by itself, and the
   owner is told so in plain words.
2. The connector's call limits are **?**. An open page makes up to 120 calls an hour in session. The back-off limits a failing
   page; if a limit shows, the in-session period goes to 60 s.
3. The largest answer the page type accepts is **?** ("an answer too big for the platform is refused or comes back as a file"
   [R sources]); the row is about 7 KB and the budget 60,000 bytes; probe P8 measures two sizes.
4. Live only while the publisher is up. Before the supervisor amendment it lives and dies with the engine, with gaps of up to
   about 30 minutes and the 2-hour cap [S 4.5], and a dead engine shows as a red badge, not as a live "engine dead" line.
   Yahoo's delay is not measured (3.8); every price carries its own time. The load on Yahoo is shared with the engine's stop
   quotes: the ramp, the yield and the pass numbers of 3.3 are the guard, and Yahoo's real limit stays unknown.
5. The write-only door (section 4): accepted for paper data; the upgrade path is written. The key reaches every session of the
   environment; the marker of 3.7 stops an accident, not a session that chooses to claim. The free plan's pause and quotas are
   **?** against the traffic computed in section 4. Not measured: the stored size against the text size (3.5), the publisher's
   memory, the build time as journals grow.
6. One tick can show a trade without its position (3.6). The news book's base for today's change is up to 5 minutes before the
   close, and missing when the engine was down then; the quant base is missing on a day whose close slot did not run (3.4).
   "Today" is the stock books only; the crypto line has another base.
7. A missed push at night shows as a warning only after `once_expect_seconds` (20 hours: the longest planned gap between two
   slot pushes is about 18 hours, from Sunday morning's summary to Monday's crypto decision [C dashboard.py:254-263]).
8. While the hourly file is shown on the first tab, a clicked number is not lit in Sources (5.3). The page stores a SQL call
   that runs with the owner's whole Supabase access; only he opens and edits the dashboard, the connector is never shared, and
   the main session re-reads the stored query after every page change (5.1).
9. Not decided here: a phone line when live has been down for some minutes. It belongs to [S] section 8.
