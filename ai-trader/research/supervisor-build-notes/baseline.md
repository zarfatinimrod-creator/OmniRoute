# Supervisor plan - baseline on the merged tip (Task 1, bullets 3-5)

Read this instead of exploring. Everything below was read on commit
`e3be944719f0727ba9199bb9185bca1ef930eb10` ("wave 3 merged onto the loss-protocol work"), the tip of the live
branch on 2026-11-11. Paths are relative to `ai-trader/`. Line numbers are of that commit. "nl" = `aitrader/news_live.py`
(1456 lines). The concise version is the "Baseline record" table at the end of
`research/plans/2026-11-10-supervisor.md`.

Settled before this file was written: question 7 = ב (2026-11-11, `CLAUDE.md` hard rule 4, "Owner's ruling"):
gate steps 3-5 (sweeps, compare, trials commit) are left out of every landing; quant-critic and the unit suite stay;
the critic's verdict must say the diff touches no file the time machine loads.

Compared with the commit before the merge (`e6a82895`), of the 47 listed names only these differ:
`score_batch` return type, `poll_headlines` signature, the six wave-3 names are new, `backtest.register` and
`backtest.diff_records` are new, and `save_book` does not exist at all. `tests/test_news_guards.py`,
`tests/test_core.py`, `journal.py`, `data.py`, `notify.py` are byte-identical to `e6a82895`.

---

## 1. Every listed name (47)

### 1.1 `aitrader/news_live.py` - module level

| Name | Line | Signature | What it does |
|---|---|---|---|
| `error_once` (wave 3) | nl:78 | `error_once(where: str, e: Exception) -> None` | One `news_errors.jsonl` row per (where, error type, New York day), kept in the module set `ERRORS_SAID` (nl:75). Never raises. Row: `{at, error, detail[:300], where}`. |
| `_feed` (wave 3) | nl:98 | `_feed(sym: str, session: requests.Session) -> list[dict] \| None` | One ticker's Yahoo RSS feed: `session.get("https://feeds.finance.yahoo.com/rss/2.0/headline", params={"s": sym, "region": "US", "lang": "en-US"}, timeout=10)` (nl:103). `None` = no answer or not HTTP 200. Items: `{key, symbol, title, link, published (UTC ISO), description}`; `key` = first 16 hex of sha1(`sym\|title`). |
| `fetch_headlines` | nl:131 | `fetch_headlines(sym: str, session: requests.Session) -> list[dict]` | Now one line: `_feed(sym, session) or []`. The engine loop no longer calls it. Callers: `__main__.py:310-313` (`news-score`), `tests/test_news_guards.py:837`. |
| `score_batch` | nl:182 | `score_batch(items: list[dict], model: str, timeout: int = 90) -> Scores` | One `claude -p` call (nl:198: `subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", prompt], capture_output=True, text=True, timeout=timeout)`), cwd = the engine's own. Returns a `Scores` (nl:170: a `dict` subclass, `{key: {"score": int 1..10, "why": str}}`, with `.facts`: model, prompt, sent, wall_s, CLI figures, answered or error, symbol_mismatch). Empty on failure, never raises on a reply. No items: no call, no facts. |
| `code_stamp` | nl:315 | `code_stamp() -> dict` | `{"commit": short hash or None, "dirty": bool or None, "started": UTC now}`. Two git calls through one lambda (nl:321): `subprocess.run(["git", *a], cwd=journal.ROOT, capture_output=True, text=True, timeout=15)` with `rev-parse --short HEAD` (nl:322) and `status --porcelain -- aitrader config.json` (nl:324, only when a commit was read). No `env`, no `--no-optional-locks`. Never raises. |
| `live_price` | nl:372 | `live_price(sym: str) -> tuple[float \| None, float \| None]` | `(last price, today's move in percent)` from `_chart(sym, "5d", "1d")` (nl:375). Writes the quote's own time into the module dict `QUOTE_TIME[sym]` (nl:336, UTC ISO, whole seconds), or pops it when the reply has no time. `(None, None)` on any failure. |
| `bars_since` | nl:397 | `bars_since(sym: str, since: datetime, now: datetime) -> list[tuple[datetime, float, float]] \| None` | Completed 1-minute bars `(start UTC, low, close)` with `since <= start` and `start + 60 <= now`, from `_chart(sym, "1d", "1m")` (nl:402). `None` = no answer or arrays that do not line up. |
| `market_open_now` | nl:416 | `market_open_now() -> bool` | `datetime.now(NY)` against `journal.session_hours(today)`. No network; reads `config.json`. |
| `run` | nl:1393 | `run(until_ny: str = "16:05", max_minutes: float \| None = None, prime: bool = True) -> int` | Opens `state/news_engine.lock` with `"w"` (nl:1397), `fcntl.flock(lock, LOCK_EX \| LOCK_NB)` (nl:1399). `BlockingIOError`: prints `[news] another news engine holds the book: this one does not start (exit 3)` and returns 3 (nl:1400-1402). Other `OSError`: prints `[news] the engine lock could not be taken (<type>): running without it` and goes on (nl:1403-1404). Then `_run(until_ny, max_minutes, prime)` (nl:1405), returns 0. Nothing is written into the lock file. |
| `_run` | nl:1409 | `_run(until_ny: str, max_minutes: float \| None, prime: bool) -> None` | Order today: `load_config()` (1410), `NewsTrader(cfg)` (1411), `nt.code = code_stamp()` (1412), print (1413), prime when `prime and not nt.seen` (1415-1418: `poll_headlines(prime=True)`, `save()`), calendar alert when `not journal.calendar_covers(today NY)` (1419-1422, urgent, the engine still enters the loop), loop (1426-1451), `nt.save()` (1452), `nt.drain_trial(wait=...)` (1455), print `[news] stopped`. Returns `None`. Loop exit: clock `>= until_ny` or `max_minutes` passed (1428), or `ChainBroken` (1436-1439: print, urgent alert, `break`). Any other exception: print, `news_errors.jsonl` row with no `where` (1444), `fails += 1`, one urgent alert when `fails == news.alert_after_errors` (1446-1450). Sleep: one `time.sleep(max(1.0, poll_seconds - elapsed))` (1451). |

Also at module level and used by the listed code: `DEFAULTS` (nl:51-67), `TRIAL_GUARDS` (nl:68), `ncfg(cfg)` (nl:71),
`PROMPT_ID` (nl:154), `Scores` (nl:170), `_scorer_dir()` (nl:253), `_ask_checker(item, model, timeout=60)` (nl:261),
`_rescore(item, model, timeout=60)` (nl:283), `context_id()` (nl:292), the seams `verify_headline = _ask_checker` and
`rescore_headline = _rescore` (nl:331-332), `QUOTE_TIME` (nl:336), `exit_requests()` (nl:431),
`update_exits(...)` (nl:452), `buy_hold()` (nl:487), `set_hold(...)` (nl:502), `class ChainBroken(RuntimeError)`
(nl:516), `_NO_MOVE`, `_UNSET` (nl:520-521). Imports that matter for stubbing (nl:45-48):
`from . import journal, notify, postmortem`; `from .data import UA, _chart, load_config, official_opens`.

### 1.2 `aitrader/news_live.py` - class `NewsTrader` (nl:524)

| Name | Line | Signature | What it does |
|---|---|---|---|
| `__init__` | nl:525 | `__init__(self, cfg: dict)` | Sets `cfg`, `n = ncfg(cfg)`, `session` (its own `requests.Session` with `UA`), `universe` (config universe minus `market.etf_groups`), `book` (`PaperBroker` on `news_book.json`; a file that does not parse raises here), `seen` (`news_seen.json`), `queue` (`news_queue.json`), `_eq_logged`, `_covered`, `_unseen_lows`, `_trial`, `_trial_gate`. May call `notify.send` (urgent) when `news.stop_catchup` or `news.guards` holds an unknown word (nl:542-546). |
| `save` | nl:548 | `save(self, seen: bool = True)` | Prunes `seen` older than `seen_keep_days`; writes `news_book.json` when the book really changed or 900 s passed; `news_seen.json` only when `seen=True`; always `news_queue.json`. `save(seen=False)` is the mid-step save. |
| `_tally` (wave 3) | nl:574 | `_tally(self) -> dict` | The in-memory window of the next `news_health.jsonl` row (`self._health`, created lazily). |
| `_seen_row` (wave 3) | nl:607 | `_seen_row(self, x: dict, outcome: str)` | One `news_seen_log.jsonl` row `{key, symbol, published, first_seen, outcome}` through `_record` (never raises). |
| `_stops_measured` (wave 3) | nl:617 | `_stops_measured(self, sight: dict, used: dict, now: datetime, t0: float, before: datetime \| None)` | Adds one stop check to the tally: `stop_checks`, `stop_names_max`, `stop_quotes_missing`, `stop_gap_max_s`, `stop_quote_age_max_s`, `stop_quotes_undated`. |
| `_step_measured` (wave 3) | nl:636 | `_step_measured(self, step_s: float)` | End of every step (from `step()`'s `finally`): writes `step_failed` for what is left in `_pending`, empties it, and one `news_health.jsonl` row per `health_log_seconds`. Never raises. |
| `poll_headlines` | nl:664 | `poll_headlines(self, prime: bool = False) -> list[dict]` | `_feed(s, self.session)` for every universe name in a `ThreadPoolExecutor(max_workers=8)` (nl:668-669). Marks every new key in `self.seen` (nl:680), returns the fresh ones, writes `stale` rows for the others; `prime=True` writes one `primed` row instead. |
| `_buys_blocked` | nl:692 | `_buys_blocked(self, log: bool = True) -> tuple[str, str] \| None` | `("loss_review", text)` when `postmortem.pending("news")` is not empty or cannot be read, then `("hold", text)` when `buy_hold()`, else `None`. |
| `check_stops` | nl:833 | `check_stops(self, events: list, now: datetime \| None = None)` | Per held name: `live_price(sym)` (nl:841), then exit request / stop / catch-up breach / time exit; sale through `_sell` and `_log_trade`. Sets `self._stops_checked_at` (nl:869), tidies `news_exits.json`, creates and prunes `self._blind` (nl:895), `_covered`, `_unseen_lows`, calls `_stop_sight` per name (nl:904), then `_stops_measured`. |
| `_last_stop_check` | nl:913 | `_last_stop_check(self) -> datetime \| None` | `self._stops_checked_at`, else `news_heartbeat.json["stops_checked_at"]` (nl:920), else the last `at` of `news_equity.jsonl` (nl:925). Aware UTC or `None`. |
| `catch_up_stops` | nl:932 | `catch_up_stops(self, events: list, now: datetime \| None = None, last=_UNSET, seen: dict \| None = None)` | For each held name whose last look is older than `stop_catchup_gap_seconds`: `bars_since(sym, since, now)` (nl:977); a breach sets `pos["stop_breach"]`, adds an event and sends `notify.send("AI Trader - סטופ שלא נבדק", text, self.cfg, "urgent")` (nl:1002). Unreadable bars: `_catchup_unread` (urgent, once per name). Never raises. |
| `_look_at_stops` | nl:1039 | `_look_at_stops(self, events: list, guarded: bool = False, now: datetime \| None = None) -> bool` | `check_stops`, then `catch_up_stops(events, now, last=self._prev_look, seen=<copy of _covered taken before the look>)`, a second `check_stops` in `sell` mode after a breach, `save(seen=False)` when events were added. Sets `self._prev_look` once, lazily (nl:1046-1049). Returns whether the live look ran. |
| `_stop_sight` | nl:1074 | `_stop_sight(self, sym: str, seeing: bool, now: datetime)` | The blind clock: `self._blind[sym] = [since: datetime, told: bool]`. After `stop_blind_alert_seconds` one urgent alert (nl:1091, `told = bool(notify.send(...))`); "the price is back" (high, nl:1080) only after a delivered alert. |
| `_log_trade` | nl:1095 | `_log_trade(self, f: dict, events: list)` | `journal.append("news_trades.jsonl", {**f, "logged_at": ...})`, event `f"{side} {qty} {symbol} @ {price} - {reason}"`, the Hebrew loss-pause line on a losing sale, then `save(seen=False)` (a failure goes to `_note_error(e, "save_after_trade")`). |
| `handle_scored` | nl:1122 | `handle_scored(self, items: list[dict], scores: dict, events: list)` | Per item: score row (`news_scores.jsonl`), prediction rows, then buy / queue / bad-news sale. Outside calls: section 4. |
| `_second_check` | nl:1252 | `_second_check(self, x: dict, s: dict, events: list) -> str \| None` | `_judge_second(x, s, *self._ask_second(x), events)`; `_ask_second` (nl:1191) runs `verify_headline` x `verify_calls` and `rescore_headline` on daemon threads and joins them for `verify_timeout_seconds + 5`. |
| `run_queue_at_open` | nl:1299 | `run_queue_at_open(self, events: list)` | Returns when the queue is empty or the market is closed. `official_opens([symbols], today)` (nl:1303), `live_price` as the fallback (nl:1307) and again for the move (nl:1318), `_buy`, `_log_trade`; the item leaves the queue in a `finally`. |
| `step` | nl:1324 | `step(self) -> list[str]` | `self.last_events = events`; `_step(events)`; in `finally`: when there are events one `notify.send("AI Trader - חדשות", "\n".join(events) + "\nתיק חדשות (נייר): $...", self.cfg, "high")` (nl:1335), then `_step_measured`. |
| `_step` | nl:1341 | `_step(self, events: list)` | Chain check (nl:1342-1347, at most every `news.chain_check_seconds`, raises `ChainBroken`), early look (1349-1350), queue (1351), poll (1352), `_pending` (1353), a quote per new headline (1355-1359), batches (1360-1371), end look (1372-1373), `drain_trial()`, `save()` (1375), the heartbeat (1382-1386), the equity point (1387-1390). |
| `save_book` (listed as wave 3) | - | - | **Does not exist** on the tip or on `e6a82895`. Nearest: `NewsTrader.save(self, seen: bool = True)`; the mid-step book save is `save(seen=False)`. The only other writers of `news_book.json` are tests. |

Other methods the tasks touch: `_record` (nl:567), `scorer_called` (nl:583), `_scored` (nl:595), `_buy` (nl:747),
`_sell` (nl:818), `_marks` (nl:830), `_catchup_unread` (nl:1011), `_earlier_days_unread` (nl:1020),
`_note_error(self, e: Exception, where: str)` (nl:1067; note the order: the exception first),
`_quote_is_live(self, price_at: str | None, published: str | None = None, now: datetime | None = None) -> bool`
(nl:1107), `_ask_second` (nl:1191), `_judge_second` (nl:1224), `_ask_later` (nl:1261), `drain_trial(self, wait: float = 0.0)`
(nl:1283).

Attributes that are NOT set in `__init__` and appear only later (read them with `getattr`):
`_blind` (first `check_stops`, nl:895), `_prev_look` (first `_look_at_stops`, nl:1049), `_stops_checked_at` (first
`check_stops`, nl:869), `code` (set by `_run`, nl:1412), `_early_look` (each `_step`, nl:1348), `last_events` (each
`step`, nl:1326), `_pending` (each `_step`, nl:1353), `_health` (`_tally`), `_saved_core` / `_saved_at` (`save`),
`_exits_bad` (`check_stops`), `_catchup_blind`, `_earlier_told`, `_chain_checked`.

### 1.3 `aitrader/__main__.py`

| Name | Line | Text | Note |
|---|---|---|---|
| `BOOK_CMDS` | 47 | `{"cycle", "status", "scorecard", "backtest", "verify", "predict", "context", "veto", "shrink", "summary"}` | `news-live` is not in it: with `--book crypto` `main` prints a refusal and returns 2 (139-141). |
| the `news-live` parser | 89-91 | `--until` (default `"16:05"`), `--minutes` (float, default `None`) | No other option today. |
| the `news-live` branch | 297-300 | `from .news_live import run` / `return run(a.until, a.minutes) or 0` | Positional call. It lives in `__main__._run(a: argparse.Namespace) -> int` (146), a different function from `news_live._run`. `main(argv=None) -> int` (59) wraps it in `journal.use_book(a.book)`. |

### 1.4 `aitrader/journal.py` (module functions, no class)

| Name | Line | Signature | What it does |
|---|---|---|---|
| `_path` | 26 | `_path(name: str) -> Path` | `STATE / name`; creates `STATE` as a side effect. |
| `NEWS_CHAINED` | 60 | a set | `{"news_trades.jsonl", "news_scores.jsonl", "news_predictions.jsonl", "news_grades.jsonl"}` (the `news_` names of `CHAINED`, 58-59). `news_errors`, `news_checks`, `news_seen_log`, `news_health`, `news_scorer_calls`, `news_equity`, `news_holds` are not chained. |
| `calendar_covers` | 71 | `calendar_covers(day) -> bool` | The date's year is in `config.json` `calendar.years` (2026, 2027). Reads `ROOT/config.json` each call (`_calendar`, 64), not the state directory. |
| `session_hours` | 76 | `session_hours(day) -> tuple[tuple[int, int], tuple[int, int]] \| None` | `((9, 30), (16, 0))`, `(13, 0)` on an early close, `None` on a weekend, a holiday or an uncovered year. Same real `config.json`. |
| `append` | 142 | `append(name: str, record: dict) -> None` | One JSON line; chained names get `prev_hash` and `hash`; a torn last line is closed off and named (`after_torn`). No lock. |
| `read` | 208 | `read(name: str) -> list[dict]` | Every readable line; an unreadable one is skipped with a print `[journal] skipped unreadable line in <name>`. `[]` when the file is absent. |
| `save_json` | 235 | `save_json(name: str, obj) -> None` | Writes `<stem>.tmp` (`p.with_suffix(".tmp")`), then `replace`. |
| `broken_chains` | 324 | `broken_chains(names=None) -> list[str]` | Sorted names whose chain does not verify (`verify_chain(name) -> (ok, n)`, 167). |

Also: `ROOT` (20), `STATE` (21), `use_book` (32), `now_utc()` (54, whole seconds, `+00:00`), `write_all` (223),
`load_json(name, default=None)` (230; raises on a file that does not parse).

### 1.5 `aitrader/data.py`, `aitrader/backtest.py`, `aitrader/notify.py`

| Name | Line | Signature | What it does |
|---|---|---|---|
| `data.official_opens` | data.py:397 | `official_opens(symbols: list[str], day) -> dict[str, float]` | The open of the 09:30 New York 1-minute bar per symbol: `_chart(sym, "5d", "1m")` (407) in a `ThreadPoolExecutor(max_workers=8)` (417). A symbol with no such bar is left out. `news_live` imports the name, so the engine calls `news_live.official_opens`. |
| `backtest.register` (wave 3) | backtest.py:299 | `register(df: pd.DataFrame, detail: dict, panel: dict, cfg: dict, start: str, end: str \| None = None) -> dict` | Appends the `trials.jsonl` line and writes the run record `state/trial_runs/<run_id>.json.gz` (`save_record`, 271). Called from `__main__.py:203`. |
| `backtest.diff_records` (wave 3) | backtest.py:320 | `diff_records(a: dict, b: dict) -> list[dict]` | Entries `{"what": "commit" \| "code_dirty" \| "config_sha256" \| "panel" \| "run" \| "daily", ...}`. Called from `__main__.py:170`; `backtest --compare` prints `{"a", "b", "identical", "differences"}` (171). |
| `notify.send` | notify.py:28 | `send(title: str, body: str, cfg: dict, priority: str = "default", force: bool = False) -> list[str]` | Returns the channels that took it: `["ntfy"]`, `["telegram"]`, both, `[]`, or `["queued"]` in quiet hours. Details in section 4. |

### 1.6 Tests

**`tests/test_news_guards.py::_Engine`** (line 32, `unittest.TestCase`, no test methods). `setUp` (33-54), one by one:

| Line | Stub | Replaces |
|---|---|---|
| 34-36 | `journal.STATE = self.tmp` (a `tempfile.mkdtemp()`), the old value in `self._state` | the live `state/` |
| 37 | `self.prices = {"AAA": 100.0, "BBB": 50.0, "SPY": 500.0}`, `self.moves = {}` | the data behind the price stub |
| 38-39 | `self.answers`, `self.asked`, `self.rescores` | what the checker stubs answer and record |
| 42-43 | `news_live.bars_since = lambda sym, since, now: []` (old one in `self._bars_since`) | the Yahoo minute bars |
| 44 | `news_live.live_price = lambda s: (self.prices.get(s), self.moves.get(s, 0.0))` | the Yahoo quote. It does NOT stamp `QUOTE_TIME`: a quote is "live" only when a test sets `news_live.QUOTE_TIME[sym]` or replaces `_quote_is_live`. |
| 45 | `news_live.market_open_now = lambda: True` | the clock and the calendar |
| 46 | `news_live.verify_headline = self._verify` (65-67: appends `(symbol, model)` to `self.asked`, pops `self.answers`, else `APPROVED`) | the checker call (`_ask_checker`) |
| 47 | `news_live.rescore_headline = lambda item, model, timeout=None: self.rescores.pop(0) if self.rescores else 10` | the re-score call (`_rescore`) |
| 48-49 | `news_live.notify.send = lambda title, body, cfg, prio="default", **kw: (self.sent.append((prio, body)), ["ntfy"])[1]` | the phone. It replaces `aitrader.notify.send` itself (the module attribute) for the whole process until `tearDown`. `self.sent` holds `(priority, body)`; the title is not kept. The fourth parameter is named `prio`: a send that passes `priority=` by keyword is recorded as `"default"`. |
| 50-53 | `self.cfg` = a deep copy of the real `config.json` with `universe = {"AAA": "Tech", "BBB": "Tech", "SPY": "Index"}`, `news.max_hold_days = 0`, `news.guards = "enforce"` | the config. The trader's universe is `["AAA", "BBB"]` (SPY is an ETF group). |
| 54 | `self.nt = news_live.NewsTrader(self.cfg)` | - |

NOT stubbed by `setUp`: `score_batch`, `_feed` / `poll_headlines`, `official_opens`, `code_stamp`, `load_config`,
`_chart`, `subprocess.run`, `time.sleep`, `journal.calendar_covers`, `journal.session_hours` (the real `config.json`),
`context_id` (reads the real `CLAUDE.md` / `AGENTS.md` above the working directory), the background "trial-check"
threads. Each test that reaches one patches it itself (`mock.patch.object(self.nt, "poll_headlines", lambda: [])` and
the like). `tearDown` (56-63) puts the six module attributes back, pops `QUOTE_TIME` for AAA and BBB only, restores
`journal.STATE`, removes the directory.

Helpers on `_Engine`: `_item(key="k1", sym="AAA", move=0.0, **extra)` (69; `published` is the fixed
`"2026-11-09T14:00:00+00:00"`, no `price_at`), `_score(item, score=9, events=None)` (73; `handle_scored` then
`drain_trial(wait=5)`), `_checks()` (79), `_verdicts()` (82), `_second()` (85), `_queued(sym="AAA")` (89; patches
`news_live.official_opens`), `_stop_row(days_ago)` (97).

**`tests/test_news_guards.py::OneEngine(_Engine)`** (762-787), three tests:
1. `test_a_second_engine_on_the_same_book_does_not_start` (763): holds `flock` on `news_engine.lock`; `NewsTrader` is
   replaced by a mock that fails when built; `news_live.run(max_minutes=0.001) == 3`; then with
   `news_live.run` replaced by `lambda until, minutes: 3` (770, positional, no `**k`) `cli.main(["news-live", "--minutes", "1"]) == 3`.
2. `test_a_lock_that_does_not_work_at_all_does_not_leave_the_book_without_an_engine` (775): `news_live.fcntl.flock`
   raises `OSError(37, ...)`; `news_live._run` replaced by `lambda *a: ran.append(a)` (778: positional only, returns
   `None`); `run(max_minutes=0.001) == 0` and `_run` ran once.
3. `test_the_lock_is_free_again_when_the_engine_ends` (782): `NewsTrader.step -> []`, `poll_headlines -> []`,
   `time.sleep` a no-op; `run(max_minutes=0.0001, prime=False) == 0` twice. `code_stamp` and `load_config` are real here
   (two real `git` calls per run, the real config).

`tests/test_loss_protocol_pins.py::OneEngine_(_ChecksOver, g.OneEngine)` (519) inherits these three and adds
`test_while_an_engine_runs_nobody_else_can_take_the_book_not_even_to_share_it` (520-539): opens the lock file with
`"a"`, tries `LOCK_SH` and `LOCK_EX`, ends the loop with `ChainBroken` and asserts `run("24:00", 1, prime=False) == 0`.

**The phone guard at the top of `tests/test_core.py`** (17-20): at import it pops `AITRADER_NTFY_TOPIC`,
`AITRADER_TELEGRAM_TOKEN`, `AITRADER_TELEGRAM_CHAT` from `os.environ`. Line 22: `CFG` = the real `config.json`.
Lines 24-31: the checker seams for the whole run: `APPROVED = {"kind": "company_announcement", "confirmed": True, "why": "test"}`,
`news_live.verify_headline = lambda item, model, timeout=60: dict(APPROVED)`,
`news_live.rescore_headline = lambda item, model, timeout=None: 10`. `test_news_guards.py:26` imports `APPROVED, CFG`
from it, so `from test_news_guards import _Engine` brings the guard and the seams with it.

Other helpers the plan names: `NothingSlowBeforeASale._held(self, sym="BBB", entry=50.0)` (`test_news_guards.py:900-902`):
`self.nt.book.state["positions"][sym] = {"qty": 10, "avg_cost": entry, "last_price": entry, "entry_date": "2026-11-09", "stop_price": round(entry * 0.97, 4)}`.
`SaidWhateverHappens(_Engine)` is at 1127. The heartbeat test is at 754, the code-stamp test at 877.

---

## 2. Fact (a): who writes `state/news_heartbeat.json`

One place: `NewsTrader._step`, nl:1382-1386, at the end of a step that did not raise, after `self.save()` (nl:1375):

```python
journal.save_json("news_heartbeat.json", {"at": journal.now_utc(), "headlines_seen": len(self.seen),
                                          "positions": len(self.book.positions), "queue": len(self.queue),
                                          "stops_checked_at": checked.isoformat() if checked else None,
                                          "buys_blocked": blocked[0] if blocked else None,
                                          "code": getattr(self, "code", None)})
```

- Seven keys: `at`, `headlines_seen`, `positions` (a count), `queue` (a count), `stops_checked_at`, `buys_blocked`, `code`.
- `checked` (nl:1376-1380): `self._stops_checked_at`; with positions held it is the oldest of
  `self._covered.get(sym, self._prev_look)` over the held names, or `None` when any of them is `None`.
- `blocked` = `self._buys_blocked(log=False)` (nl:1381): `"loss_review"`, `"hold"` or `None`.
- It is not written at a start, at priming, by a step that raised, or at the end of `_run`. A failing step leaves the
  old beat on disk.
- The write is atomic (`save_json`: `news_heartbeat.tmp`, then `replace`).
- Readers: `NewsTrader._last_stop_check` (nl:920, the key `stops_checked_at` only), `aitrader/dashboard.py:124-125`
  (`hb["at"]` for the age), `skills/trader/SKILL.md:190,194` (prose: `code.started`, `code.commit`, `code.dirty`).
- Tests write it as a fixture: `tests/test_news_guards.py:492, 506`; `tests/test_loss_protocol_pins.py:370, 390, 442`.
  Tests read it: `test_news_guards.py:757, 892, 1276, 1442-1452`; `test_loss_protocol_pins.py:135, 156, 596, 691`.
- The file is git-ignored (`.gitignore:4`), with `state/news_seen.json` and `state/news_engine.lock`.

## 3. Fact (b): a polled headline with no outcome yet

- `poll_headlines` marks a new headline seen in memory at once: `self.seen[x["key"]] = <UTC now>` (nl:680). It reaches
  `news_seen.json` only through `save(seen=True)`: after priming (nl:1417), the end of the step (nl:1375) and the end of `_run` (nl:1452).
  Every save in the middle of a step is `save(seen=False)` (nl:875, 1064, 1103) and leaves the file alone, so an
  engine killed mid-step finds its unscored headlines unseen at the next start.
- A stale one (older than `fresh_minutes`, younger than `seen_keep_days`) gets its row at once: `_seen_row(x, "stale")`
  (nl:686). A first start writes one `{"at", "outcome": "primed", "count"}` row (nl:688).
- The fresh ones are held in `self._pending = {x["key"]: x for x in new}` (nl:1353), set right after the poll and
  before the quotes. It is a plain dict on the trader, in memory only.
- After each batch (nl:1364-1367) every headline of the chunk is popped from `_pending` and gets its row:
  `"scored"` when its key is in the scores, else `"scorer_failed"` (`"error" in facts`), `"symbol_mismatch"` (its key
  in `facts["symbol_mismatch"]`) or `"scorer_no_answer"`. The row is written after `handle_scored` returned.
- What is still in `_pending` when the step ends, failed or not, gets `"step_failed"` in `_step_measured`
  (nl:640-642), called from `step()`'s `finally` (nl:1338); then `_pending = {}`.
- Row shape (`_seen_row`, nl:614-615): `{"key", "symbol", "published", "first_seen": self.seen.get(key), "outcome"}`.
  `news_seen_log.jsonl` is not hash-chained, and a row that cannot be written costs nothing (`_record`, nl:567).
- For Task 8: a headline that was polled and not handed to the scorer is in two places, `self.seen[key]` and
  `self._pending[key]`. Left in `_pending` it would get a `step_failed` row at the end of that step; taken out of
  `self.seen` only, the next engine would poll it again and write a second row for the same key.

## 4. Fact (c): every call that leaves the process

"Leaves the process" = the network, a subprocess, or the model. All Yahoo price calls go through one function:
`data._chart(sym: str, rng: str, interval: str) -> dict` (data.py:59) -> `data._get_json(url, params=None, retries=3, headers=None)`
(data.py:43) -> `data._session.get(url, params=params, timeout=20, headers=headers)` (data.py:47), where
`data._session` is one module-level `requests.Session` (data.py:34). Three tries, a sleep of 1, 2, 3 s after a
failure (2, 4, 6 s after HTTP 429): one dead call costs up to 3 x 20 + 6 = 66 s. `news_live` imports `_chart` by name,
so `live_price` and `bars_since` use `news_live._chart`; `official_opens` uses `data._chart`.

### 4.1 The list `tests/helpers/engine_child.py` must replace

| # | Call | Signature | Reaches | Called from |
|---|---|---|---|---|
| 1 | `news_live._feed` | `_feed(sym: str, session: requests.Session) -> list[dict] \| None` | Yahoo RSS, `session.get(..., timeout=10)` on the trader's own `self.session` (nl:103) | `poll_headlines` nl:669, once per universe name, 8 threads. Also through `fetch_headlines` (nl:131) from `news-score` only. |
| 2 | `news_live.live_price` | `live_price(sym: str) -> tuple[float \| None, float \| None]`; side effect `QUOTE_TIME[sym]` | Yahoo chart `5d/1d` through `news_live._chart` | `check_stops` nl:841 (each held name); `handle_scored` nl:1123 (the benchmark, once per call) and nl:1169 (after an enforced second check); `run_queue_at_open` nl:1307 and nl:1318; `_step` nl:1356 (each new headline). |
| 3 | `news_live.bars_since` | `bars_since(sym: str, since: datetime, now: datetime) -> list[tuple[datetime, float, float]] \| None` | Yahoo chart `1d/1m` through `news_live._chart` | `catch_up_stops` nl:977 (each held name with an old look). |
| 4 | `news_live.official_opens` | `official_opens(symbols: list[str], day) -> dict[str, float]` | Yahoo chart `5d/1m` through `data._chart`, 8 threads | `run_queue_at_open` nl:1303. Replace the name in `news_live`; replacing `data.official_opens` does not reach the engine. |
| 5 | `news_live.score_batch` | `score_batch(items: list[dict], model: str, timeout: int = 90) -> Scores` | the model: `subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", prompt], capture_output=True, text=True, timeout=timeout)` (nl:198) | `_scored` nl:599 as `score_batch(chunk, self.n["model"])` (two arguments); `_rescore` nl:286 as `score_batch([item], model, timeout)`. A stand-in that returns a plain dict leaves no `news_scorer_calls.jsonl` row and every unanswered key reads `scorer_no_answer`. |
| 6 | `news_live.verify_headline` (seam for `_ask_checker`) | `_ask_checker(item: dict, model: str, timeout: int = 60) -> dict` | the model: `subprocess.run(["claude", "-p", "--model", model, "--output-format", "json", "--tools", "", "--", prompt], capture_output=True, text=True, timeout=timeout, cwd=_scorer_dir())` (nl:270-272); `_scorer_dir` makes `<tempdir>/aitrader-scorer` | `_ask_second` nl:1205, `verify_calls` times, on daemon threads: before the buy when `news.guards` is `"enforce"` (`handle_scored` nl:1159), in the background thread "trial-check" when it is `"log"` (`_ask_later`, nl:1185 and 1261). |
| 7 | `news_live.rescore_headline` (seam for `_rescore`) | `_rescore(item: dict, model: str, timeout: int = 60) -> int \| None` | the model, through `score_batch` | `_ask_second` nl:1211, when `news.verify_rescore`. |
| 8 | `notify.send` | `send(title: str, body: str, cfg: dict, priority: str = "default", force: bool = False) -> list[str]` | `requests.post("https://ntfy.sh/", timeout=15, json={"topic", "title", "message", "priority", "tags"})` (notify.py:41, only when the topic variable is set; the base URL is a literal, there is no `alerts.ntfy_base_url` key); `requests.post("https://api.telegram.org/bot<token>/sendMessage", timeout=15, ...)` (notify.py:51, only when both Telegram variables are set); always `print("ALERT: ...")` (57). In quiet hours (`market.quiet_hours`, `None` for the stock book) it writes `alert_queue.json` and returns `["queued"]`. | See 4.2. |
| 9 | `news_live.code_stamp` | `code_stamp() -> dict` | two `git` subprocesses, `cwd=journal.ROOT`, `timeout=15` each (nl:321-324) | `_run` nl:1412, once per start. |

Nothing else in the six functions reaches the network, a subprocess or the model. Checked and local only:
`load_config()` (data.py:337, reads `ROOT/config.json`), `journal.calendar_covers` / `session_hours` (the same file),
`market_open_now` (clock + that file), `journal.broken_chains` (state files), `postmortem.pending("news")` (state
files, from `_buys_blocked` nl:697), `exit_requests` / `update_exits` (state file, `flock` on the state directory),
`buy_hold` (state file), `context_id()` (nl:292, reads `CLAUDE.md` / `AGENTS.md` from the working directory upward,
called at nl:1139 for every score row), `PaperBroker`, `time.sleep` (nl:1451, and nl:476 inside `update_exits`).
`requests.Session()` in `__init__` (nl:528) opens no connection.

The engine uses `subprocess.run`, never `subprocess.Popen` by name; `run` builds a `Popen` underneath.
`notify.send` uses the module function `requests.post`, which builds a `Session` and calls `Session.request`.

### 4.2 Every `notify.send` of the engine

| Line | In | Title | Priority | When |
|---|---|---|---|---|
| nl:544 | `NewsTrader.__init__` | `AI Trader - תקלה` | urgent | an unknown word in `news.stop_catchup` or `news.guards` |
| nl:1002 | `catch_up_stops` | `AI Trader - סטופ שלא נבדק` | urgent | a stop traded through while unwatched |
| nl:1016 | `_catchup_unread` | `AI Trader - תקלה` | urgent | bars unreadable, once per name |
| nl:1035 | `_earlier_days_unread` | `AI Trader - תקלה` | urgent | a stretch of an earlier day, once per name |
| nl:1080 | `_stop_sight` | `AI Trader - חדשות` | high | the price is back, after a delivered blind alert |
| nl:1091 | `_stop_sight` | `AI Trader - תקלה` | urgent | no fresh quote for `stop_blind_alert_seconds` |
| nl:1335 | `step` | `AI Trader - חדשות` | high | the step's events and the book line |
| nl:1420 | `_run` | `AI Trader - תקלה` | urgent | the calendar does not cover the year |
| nl:1438 | `_run` | `AI Trader - תקלה` | urgent | `ChainBroken` |
| nl:1449 | `_run` | `AI Trader - תקלה` | urgent | `news.alert_after_errors` failed rounds in a row |

Every one passes the priority as the fourth positional argument.

### 4.3 The six functions, in call order

- `_run` (nl:1409): `load_config()` (file) -> `NewsTrader(cfg)` (maybe send 544) -> `code_stamp()` (git x 2) ->
  `poll_headlines(prime=True)` when the seen file is empty (feeds) -> `journal.calendar_covers` (file; send 1420) ->
  loop: `nt.step()`; sends 1438 / 1449; `time.sleep`. After the loop: `nt.save()`, `nt.drain_trial(wait=0 | verify_timeout_seconds)`.
- `_step` (nl:1341): `broken_chains` (files) -> `market_open_now()` -> `_look_at_stops(events, guarded=True)` ->
  `run_queue_at_open` -> `poll_headlines()` (feeds) -> `live_price` per new headline -> per batch `_scored` ->
  `score_batch` (model), `handle_scored`, and between batches `_look_at_stops(guarded=True)` -> `_look_at_stops(events)`
  -> `drain_trial()` -> `save()` -> heartbeat -> equity point. `step()` then sends 1335.
- `poll_headlines` (nl:664): `_feed` x universe.
- `check_stops` (nl:833): `live_price` x held; `_stop_sight` (sends 1080 / 1091).
- `catch_up_stops` (nl:932): `bars_since` x held names with an old look; sends 1002, 1016, 1035.
- `run_queue_at_open` (nl:1299): `market_open_now()`; `official_opens`; `live_price` (fallback, then the move).
- `handle_scored` (nl:1122): `live_price(benchmark)`; `market_open_now()`; `context_id()` (files); in `"enforce"`:
  `_second_check` (checker x `verify_calls`, re-score), `_look_at_stops(guarded=True)`, `live_price(sym)` again; in
  `"log"`: `_ask_later` (the same checker and re-score calls on a background thread).

### 4.4 The wall clock and the real calendar (not outside calls, but a test or a drill meets them)

`market_open_now`, `_quote_is_live` (nl:1107: today's session by `journal.session_hours`, at or after the open, at
most `news.max_quote_age_minutes` old), `catch_up_stops` (returns at once on a closed day, nl:948-950), the hold-days
count (nl:862), the loop's end test (nl:1427-1428) and `_day_move_pct` all read `datetime.now(NY)` and the calendar of
the real `config.json`. `calendar.years` is `[2026, 2027]`.

## 5. The grep for `pull --rebase` and `git log`

`git grep -n -e "pull --rebase" -e "git log" <tip> -- ai-trader ':!ai-trader/logs' ':!ai-trader/research' ':!ai-trader/vendor'`
gives four hits, all expected by the plan:

- `README.md:68` - `git log -p -- state/<file>` (prose of the repair procedure).
- `skills/trader/SKILL.md:35` - `git pull --rebase` in section 0.
- `skills/trader/SKILL.md:160` - `git pull --rebase` in section 3א (the section runs from line 92 to 179).
- `state/backlog.md:104` - item 40 (prose).

No other hit. No code under `aitrader/`, `tests/`, `scripts/` or `bin/` runs `git log` or `git pull`.

## 6. Config on the tip (what the tasks add is not there yet)

- Top-level keys: `_note, account, calendar, _note_market, market, benchmark, universe, costs, risk, signals,
  prior_weights, learning, alerts, sec_user_agent, _note_priors, news, postmortem, _note_bootstrap, bootstrap, drift, books`.
  No `supervisor` block.
- `alerts` = `{"ntfy_topic_env", "telegram_token_env", "telegram_chat_env"}` (three variable names). No `ntfy_base_url`.
- `news` has `_note` and `_note_guards`; `poll_seconds` 20, `batch_max` 12, `chain_check_seconds` 300,
  `alert_after_errors` 5, `max_quote_age_minutes` 3, `stop_catchup` "alert", `guards` "log", `seen_keep_days` 3,
  `health_log_seconds` 300, `verify_timeout_seconds` 60. No `sleep_slice_seconds`. `equity_log_seconds` is read with a
  fallback of 300 and is in neither `config.json` nor `DEFAULTS`.
- `tests/test_loss_protocol_pins.py:222` (`test_the_fallbacks_in_the_code_say_what_config_says`) fails on any key of
  `news_live.DEFAULTS` that `config.json` `news` lacks or sets to another value.
- `market.quiet_hours` is `None` for the stock book (the crypto book has 23:00-08:00 Asia/Jerusalem).
- Not on the tip: `tests/helpers/`, `tests/fixtures/ntfy/`, `tests/fixtures/list_triggers_sample.json`,
  `skills/trader/slots/`, `scripts/drill_supervisor.py`, every `aitrader/` module the plan creates.
  `tests/fixtures/` holds `golden_stock_backtest.json`, `golden_stock_cycle`, `stock_panel.pkl`.

---

## 7. Surprises for Tasks 2-8

Checked: every function, attribute, file, config key and test helper that Tasks 2-8 treat as already there.
Existence and spelling only.

### 7.1 Names

1. **Task 1's list (not used by Tasks 2-8): `save_book` does not exist.** Nearest is `NewsTrader.save(self, seen=True)`;
   `save(seen=False)` is the mid-step save.
2. **Task 3 (the engine child): four names live in `news_live`'s own namespace.** `official_opens`, `load_config`,
   `_chart` and `UA` are imported with `from .data import ...` (nl:47). A stand-in must be set on `news_live`
   (`news_live.official_opens`, `news_live.load_config`); one set on `data` does not reach the engine. `_run` calls
   `load_config()` with no argument.
3. **Task 3: `fetch_headlines` exists but the engine loop does not call it.** The poll calls `_feed` (nl:669). The plan's
   table already replaces both.
4. **Task 3: the refusal line on the tip** is `[news] another news engine holds the book: this one does not start (exit 3)`
   (nl:1401) and the lock file is opened with `"w"` (nl:1397, it truncates the file at every start attempt, a refused
   one too). No test asserts the printed text.
5. **Tasks 3-7: `_Engine`'s `notify.send` stand-in names its fourth parameter `prio`** (`test_news_guards.py:49`). A new
   send that passes `priority="urgent"` by keyword is recorded in `self.sent` as `"default"`. Every existing send
   passes it positionally. `self.sent` holds `(priority, body)`, no title.
6. **Tasks 4, 6: several attributes the new code reads are not set in `__init__`:** `_blind`, `_prev_look`,
   `_stops_checked_at`, `code`, `_early_look`, `last_events`, `_pending` (list in 1.2). A beat written at "boot",
   before the first look, finds none of them. `_blind` values are `[since: datetime, told: bool]`, as the plan writes.
7. **Task 4: the heartbeat on the tip has exactly the seven keys the plan keeps** (`at`, `headlines_seen`, `positions`,
   `queue`, `stops_checked_at`, `buys_blocked`, `code`). No mismatch.
8. **Tasks 5, 7: there is no chain-check function.** The check is inline at the top of `_step` (nl:1342-1347), throttled
   by `news.chain_check_seconds` through `self._chain_checked`; "the existing alert" is in `_run`'s
   `except ChainBroken` (nl:1436-1439). `journal.broken_chains(journal.NEWS_CHAINED)` is the call to reuse.
9. **Task 5: `skills/trader/SKILL.md` section 3ב (line 180) has no list of exit codes today.** Only code 3 is described,
   in prose (lines 191-193). The two new lines are additions, not replacements.
10. **Task 5: "the existing urgent calendar alert" (nl:1419-1422) does not end the start today.** The engine goes on
    into the loop after it. Its text is English with "(כסף נייר)" at the end.
11. **Task 7: `code_stamp` runs `subprocess.run` twice through one lambda** (nl:321) with no `env`. The second call
    (`status`) runs only when the first returned a commit.
12. **Task 8: `news._note` exists** (and `news._note_guards`). `news.sleep_slice_seconds` must be added to both
    `DEFAULTS` and `config.json` in the same commit (the pin test in section 6).
13. **Global constraints (used from Task 13 on): `alerts.ntfy_base_url` is not in `config.json`,** and `notify.send`
    has the literal `"https://ntfy.sh/"` (notify.py:41).

Everything else Tasks 2-8 name as existing is there under that name: `news_live.fcntl`, `news_live.time`,
`NewsTrader._quote_is_live`, `_note_error(e, where)`, `_covered`, `_last_stop_check`, `_buys_blocked(log=True)`,
`_log_trade`, `_look_at_stops(events, guarded=False, now=None)`, `ChainBroken`, `DEFAULTS`, `self.seen`,
`journal.verify_chain`, `journal.calendar_covers`, `journal.broken_chains(names=None)`, `journal._path`,
`journal.save_json`, `cli.main`, `NothingSlowBeforeASale._held`, `SaidWhateverHappens`, `OneEngine`'s two stand-ins,
`test_core`'s seams and phone guard (the same three variable names as `PHONE_VARS`).

### 7.2 Existing tests outside the plan's file lists that pin what a task changes (facts only)

14. **Task 5 (`_run` returns 4 on `ChainBroken`):** four tests in `tests/test_loss_protocol_pins.py` end the loop with
    `ChainBroken` and assert `news_live.run("24:00", 1, prime=False) == 0`: lines 538 (`OneEngine_`), 595 and 622
    (`NothingSlowBeforeASale_`), 674 (`SaidWhateverHappens_`). The file is in no task's file list and not in the build
    claim; `BUILD_CLAIMS.md` ("Waiting", item 1) says it is free to edit.
    `tests/test_audit_fixes.py:433` (`NewsLoopStops`) does the same without asserting the return value; its
    `notify.send` stand-in takes no `**kw`.
15. **Tasks 3, 5, 7, 8 (the start path changes): every direct caller of `run` / `_run` in the tests.**
    `test_news_guards.py:769, 779, 786, 787` (`run`), `1049, 1215` (`_run("23:59", <minutes>, False)`);
    `test_loss_protocol_pins.py:538, 595, 622, 674` (`run("24:00", 1, prime=False)`);
    `test_audit_fixes.py:433` (`run(until_ny="24:00", max_minutes=1, prime=False)`);
    `test_news_measure.py:335` (`run(until_ny="00:00")`, a priming start with `subprocess.run` replaced by a scorer
    stand-in, so `code_stamp`'s git calls land in it). All pass the three old arguments positionally or by their
    present names.
16. **Tasks 4, 7 (the stamp a start adopts): tests that write the heartbeat as a fixture and read it lazily through
    `_last_stop_check`:** `test_news_guards.py:492, 506`; `test_loss_protocol_pins.py:370, 390, 442`. `691` asserts a
    `None` stamp while a held name has had no quote.
17. **Task 3 (`"lock"` in the heartbeat, the lock file's text):** `test_loss_protocol_pins.py:520-539` opens
    `news_engine.lock` with `"a"` while the engine runs.

### 7.3 Could not be determined here

- Whether the live branch's scheduled tasks, the trader session's checkout or the gate clone match the tip: not looked
  at (other rows of the Baseline record; later tasks).
- The claim line in `BUILD_CLAIMS.md` that this work refreshed was stamped 10:20 UTC in commit `e3be9447`, whose own
  commit time is 09:54 UTC on the same day. The refreshed time is this machine's `date -u`.
