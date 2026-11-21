# SEC filings feed, log-only - design spec (2026-11-11, rev 2)

Status: a design for the owner's review. Nothing here is built. Rev 2 answers two independent reviews of rev 1 (a
measurement review and a build review); what they changed is in the text, not in a list. It follows backlog item 65
and the owner's decision of 2026-11-11 on the SEC contact address [K 65]. Paper money only (כסף נייר). This feed
never places, changes or cancels a trade, never changes a score, and no trading code reads what it writes. It
serves Basic law 2, items 2, 3 and 6 (`CLAUDE.md`). This file holds no address, no key, no session or task id and no scratch path; where the contact
address would appear it says `<the value of AITRADER_SEC_CONTACT>`.

## תקציר לנמרוד (כסף נייר בלבד)

1. מה זה: תהליך קטן ונפרד שבודק פעם בדקה, אצל רשות ניירות ערך האמריקאית (SEC), אם אחת מ-74 החברות שלך הגישה דיווח
   חדש (תוצאות, החלפת מנהל, עסקה). הוא רק רושם: מה הוגש, מתי ה-SEC קיבל את זה, ומתי הבוט ראה.
2. הוא לא קונה, לא מוכר ולא משנה שום ציון. מנוע החדשות לא קורא ממנו כלום. זה שלב "רישום בלבד", כמו שחוק יסוד 2 דורש.
3. למה: היום Yahoo מראה כותרת בחציון 572 שניות אחרי הפרסום. כאן היעד הוא בערך חצי דקה בממוצע, ובדרך כלל עד כדקה
   (לכל היותר כ-80 שניות, כשבקשה ל-SEC נמשכת עד הגבול שלה). זה יעד, עוד לא נמדד. המדידה היא כל המטרה.
4. מהירות היא לא רווח. המחקר הגדול לא מצא תשואה בדקות 1-15 אחרי כותרת. אחרי שבועיים תקבל דף אחד עם המספרים.
   הדף הזה מחליט רק אם ממשיכים לרשום. הוא לא יכול להגיד אם למקור יש יתרון על Yahoo: לזה צריך לפחות 30 אירועים
   תואמים, ובשבועיים צפויים בערך 2 עד 5 (הערכה, לא מדידה), ופחות אם החלפות המנוע מתעכבות (פריט 8). זה חודשים,
   לא שבועיים.
5. עלות: $0. בלי מפתח ובלי חשבון. ה-SEC מבקש רק כתובת קשר בכל בקשה.
6. הכתובת שתפתח לבוט נשמרת רק כהגדרה בסביבת הענן (`AITRADER_SEC_CONTACT`). היא לא נכתבת בשום קובץ, יומן, הודעת
   שגיאה או פלט. יש בדיקה אוטומטית שמוודאת את זה. בלי הכתובת שום דבר לא פונה ל-SEC.
7. עומס על ה-SEC: בערך 1.2 בקשות בשנייה, מול מגבלה של 10 שה-SEC מפרסם. אבל כל בקשה מורידה את כל רשימת הדיווחים
   של החברה (שנה או 1,000 דיווחים לפחות), לא רק את החדש. כמה זה שוקל באמת יימדד בבדיקה הראשונה. אם ה-SEC חוסם,
   התהליך נעצר ומחכה, ולא מנסה לעקוף.
8. מגבלה ראשונה: הוא רץ רק כשהמנוע רץ, בערך 08:07 עד 16:05 שעון ניו יורק. הרבה דוחות רבעוניים יוצאים אחרי 16:05
   או לפני 08:00. אלה יירשמו רק למחרת, בלי מדידת מהירות. וגם: אחרי 16:05 אף אחד לא בודק את Yahoo, אז דיווח של
   אחר הצהריים לא תמיד ניתן להשוואה. כך גם דיווח בשעה הראשונה אחרי שהמנוע עולה בבוקר (בערך 08:07-09:07), ודיווח
   סביב הפסקה של המנוע. החלפה מתוכננת של המנוע (4 ביום) לא נחשבת הפסקה אם הוא חזר תוך דקה. הדוח סופר את אלה בנפרד
   ("קטוע") ולא מציג אותם כניצחון. זו שאלה 1 אליך.
9. מגבלה שנייה: הוא בודק פעם בדקה, לא "בשנייה". וה"פחות משנייה" של ה-SEC הוא משפט שלהם, לא מדידה שלנו.
10. מגבלה שלישית: לא ידוע באיזה שעון ה-SEC כותב את שעת הקבלה (ניו יורק או UTC). הבדיקה הראשונה מביאה שנה של
    חותמות ומכריעה. עד אז המדידה הראשית לא נשענת על החותמת, אלא על השוואה בין מתי ראינו ב-SEC ומתי ב-Yahoo.
11. מגבלה רביעית: דיווח שה-SEC לא הראה לנו בכלל - אין היום מי שיספור. הדוח יכתוב "לא נמדד" עד שתיבדק רשימה
    לילית נפרדת של ה-SEC (בדרך כלל בקשה אחת ביום).
12. מגבלה חמישית: ה-SEC חוסם לפי כתובת רשת, והסשן יוצא לרשת דרך שרת של ספק הענן שאולי משותף לאחרים. חסימה יכולה
    לבוא גם מתעבורה שאינה שלנו. הדוח סופר "חסימות שנראו", לא "חסימות שגרמנו".
13. הוא מחכה בתור: קודם המפקח, אחר כך חדר המסחר החי, ואז הוא. הוא משתמש בחלקים שלהם ולא בונה מנגנון שני.
14. מה רק אתה עושה: פותח את הכתובת ונותן אותה פעם אחת; מאשר כרטיס אחד (הגדרת סביבה); מאשר שלוש משימות
    חד-פעמיות: אחת בבוקר שאחרי הכרטיס, שבודקת שהכתובת הגיעה, ושתיים לבדיקה הראשונה; עונה על 6 השאלות בסעיף 12, אחת
    בכל פעם.

## Evidence tags

A number with no tag is a design value ("dt"): a test or a rollout check of section 10 must prove it.

- [C file:line] code under `ai-trader/` at commit 36a39111, read 2026-11-11.
- [K n] item n of `state/backlog.md`. [R] `research/2026-11-10-upgrade-roadmap.txt` ([R n] = line n); its VERIFY
  block is the roadmap's verifier.
- [S n] section n of `research/specs/2026-11-10-supervisor-design.md` rev 2; [SP n] Task n of
  `research/plans/2026-11-10-supervisor.md`. [T n] section n of
  `research/specs/2026-11-10-live-trading-room-design.md` rev 2; [TP n] Task n of
  `research/plans/2026-11-11-live-trading-room.md`.
- [V file:line] the vendored pack `vendor/jake-trader-skill-v2` (MIT, pinned commit 3d0f4ef6 [C
  vendor/jake-trader-skill-v2/PINNED_COMMIT]). [F] measured for this spec on the pack's own test fixtures, in the
  upstream checkout at the same commit (the vendored copy omits tests [C THIRD_PARTY.md:27]).
- [W1]-[W5] SEC pages read on 2026-11-11 (section 6). They were read through a fetch tool that passes the page
  through a small model, and long sentences came back in pieces that are joined here: every quote must be re-read
  against the page by the plan's first task before anything is built on its exact words. [W1], [W3] and [W4] were
  read a second time for rev 2, the same way; the sentences on EDGAR's hours, the nightly indexes and the limit by
  IP address come from that reading.
- No request was made to `data.sec.gov` for this spec, and none to `www.sec.gov` beyond those documentation pages.

## 1. Goal, non-goals, targets

Goal: the bot knows of a filing by one of its own companies within about a minute of the SEC showing it, and the
gain over Yahoo is a number in a journal. What can be measured is narrower than the goal: the bot has no clock for
"the SEC showed it", only the SEC's acceptance stamp (which also holds the time from acceptance to showing, and
whose clock is not yet known, 4.4) and its own two poll times.

Non-goals: no trade, no score, no input to the scorer, no alert to the phone, no reading of a filing's text or
exhibits, no XBRL numbers, no Form 4 parsing (backlog item 3 [K 3]), no earnings table for the time machine (item 2
[K 2]), no second news wire, no change to the engine (`aitrader/news_live.py` is not edited), no change to
`aitrader/data.py`.

| # | Number | Today | Target (dt) | Read from |
|---|--------|-------|-------------|-----------|
| 1 | The SEC accepted a filing -> the bot has seen it (`delay_s`; it includes the SEC's own time from acceptance to showing) | not measured (one sample, "within 165 s" [R 53]) | mean about 30 s; at worst about 60 s with a normal request and about 80 s when a request runs to its deadline, while the feed is healthy (section 2.5); printed only once the stamp's clock is calibrated (4.4). Beside it, always, the bound that needs no stamp: `at` minus `prev_poll`, the longest the filing can have been in the file unseen | `sec_filings.jsonl`, rows with `kind` "fresh" |
| 2 | Lead over Yahoo for the same event | unknown; Yahoo's own delay is a median 572 s, n=524 [R 150] | reported, whatever it is; it may be negative (4.2) | `sec-report` |
| 3 | Companies polled per sweep | 0 | 74 of 74 | `sec_health.jsonl` `answered_min` |
| 4 | Failed requests | - | under 1% | `sec_health.jsonl` |
| 5 | Days with a block SEEN (403 or 429). The SEC limits by IP address and the session's egress address may be shared (2.4), so this counts blocks seen, not blocks this feed caused | - | 0 | `sec_health.jsonl`, `sec_errors.jsonl` |
| 6 | Effect on the engine's stop looks and steps | `stop_quotes_missing`, `stop_gap_max_s` and `step_s_median` per 5 minutes [C news_live.py:654-659] | the engine half of the trading room's pass rule [TP 11], stated in 3.4: missing stop quotes not above the base day's, the largest stop gap not above it by more than `news.poll_seconds`, the median step not above 1.2 times it | `news_health.jsonl` |
| 7 | The contact address in any file, log, journal, error text or output | - | never; a test proves it (7.3) | the suite |

## 2. What is polled, and how

### 2.1 The endpoint
- One GET per company: `https://data.sec.gov/submissions/CIK##########.json` (10-digit CIK with leading zeros) [W1;
  V trader-analyst/facts.py:55]. The SEC says of it: "Each entity's current filing history is available at the
  following URL", and the reply holds "at least one year's of filing or to 1,000 (whichever is more)" of the newest
  filings [W1]; older ones sit in "additional JSON files" the reply names [W1], which the feed never asks for. So
  every reply is the company's whole recent history, not "what is new": at the 176 bytes a row of the pack's
  fixture (5,105 bytes for 29 rows [F]) a reply of 1,000 rows is about 170 KB of JSON before compression, and a
  company that files more than 1,000 forms a year sends more (2.4). The feed reads only `filings.recent` and the
  top-level `name` and `tickers`.
- Shape, read from two fixtures [F]: `filings.recent` is a set of parallel arrays, newest first, among them
  `accessionNumber`, `form`, `items`, `acceptanceDateTime`, `filingDate`, `reportDate`, `primaryDocument`,
  `primaryDocDescription`, `size`. `items` is a comma-separated text such as "2.02,9.01", empty for most forms.
- Why this endpoint and not the "latest filings" Atom feed on `www.sec.gov`: the roadmap chose it [R 119-120]. The
  per-company file is exactly about the bot's companies, its mapping is exact and the SEC documents its delay. The
  roadmap's other reason is weaker than rev 1 said: `www.sec.gov` answered 403 to the GENERIC string
  'ai-trader-research' [R 119], which says nothing about a declared client, and the Atom feeds were read 29 s and
  68 s behind [R 119]. The Atom feed needs one request where this needs 74, and it carries only what is new. So the
  choice is not closed: step 2 of section 10 must reach `www.sec.gov` with the declared agent anyway (the ticker
  map), and in the same run it makes ONE declared request to the Atom feed and records its status, size and the
  age of its newest entry. Its address is the one the bot's uncalled `data.sec_recent_form4` already builds,
  `https://www.sec.gov/cgi-bin/browse-edgar` with `action=getcurrent` and `output=atom` [C data.py:304-305], here
  without that function's Form 4 filter; that it answers the declared client from the trader's machine is not
  confirmed (section 13, fact 3). Question 2 then offers the owner both designs with measured numbers: the
  per-company file every 60 s, or the Atom feed as the trigger with the per-company files as a slow backstop for
  coverage (by arithmetic, not measurement, 10 to 70 times fewer requests). Until he answers, this spec's design
  stands.
- Which companies: every ticker of `universe` whose group is not in `market.etf_groups` [C config.json:37, 42]:
  74 names today, the same list the engine polls [C news_live.py:530]. The 19 funds are not polled: a fund's
  filings are not company news. The crypto book has no filer.

### 2.2 Ticker to CIK
- Source: `https://www.sec.gov/files/company_tickers.json`, which the SEC describes as "data file for ticker, CIK,
  EDGAR conformed company name associations" and of which it says "We periodically update these files ... but do
  not guarantee accuracy or scope" [W3]. The vendored pack reads the same file [V trader-news/news.py:59, 198-208].
- Kept in a tracked file, `state/sec_ciks.json`: `{"AAPL": {"cik": "0000320193", "name": "...", "checked":
  "<UTC>"}, ...}` for the polled tickers only. It is public data. Being tracked, a new machine needs no request to
  start, and a change of a company's CIK shows in a diff.
- Matching: tickers are compared in upper case with "." and "-" removed on both sides, so `BRK-B` in the universe
  [C config.json universe] meets the SEC's spelling whichever it is (the fixture spells it `BRK-B` [F]).
- Kept fresh, with at most ONE map request a New York day whatever happens, and only on one of two triggers. The
  file carries `built_at` and `tried_at`. (a) `sec-feed --map` rebuilds it with one request. The loop runs it at a
  start only when `tried_at` is older than `cik_map_refresh_days` (7: the normal case, once a week), or when a
  company answered 404 since the last build (2.7) and `tried_at` is older than one New York day. A ticker with no
  entry is NOT a reason to fetch again: with one ticker the SEC's file lacks, that rule would have meant a
  download from `www.sec.gov` at each of about five starts a day, from the host that refused generic clients. (b) Every poll checks the map for free: the submissions
  reply carries the company's own `tickers` list [F]; when the universe ticker is not in it, the row and the health
  window are marked `map_mismatch` and one error row is written. It is named in the daily line and waits for the
  weekly rebuild. (c) A ticker with no CIK is not polled, counts as "not covered" in target 3 and is named in the
  daily line (8.3).
- A refusal of the map is not a refusal of the feed: see the per-host rule of 2.7.
- The map file is never edited by hand to make a number look better; a hand fix is a commit with its reason.

### 2.3 The User-Agent, and what happens without the address
- The SEC asks: "Please declare your user agent in request headers" [W3, W5], and its sample is a company name
  followed by an administrator's contact address, with `Accept-Encoding: gzip, deflate` [W3].
- The header is built in one place, `aitrader/sec.py::user_agent(env)`, as `<sec.agent_name> <the value of
  AITRADER_SEC_CONTACT>`. `sec.agent_name` is "ai-trader-research-bot" (the name the placeholder already uses [C
  config.json:239]). The variable's NAME is in `config.json` (`sec.contact_env`), as the ntfy topic's is [C
  config.json:235]; its value is read from the process environment at start and is held only in memory.
- The value must be one token of at most 100 characters, printable ASCII only (`s.isascii() and s.isprintable()`),
  with exactly one "@" and no white space, and it must not contain "example": anything else is treated as missing.
  This guards against a header split across lines, against the old placeholder, and against a character outside
  latin-1, on which the HTTP library raises an error whose text quotes the character and its place. The reason is
  written as a word ("missing" or "malformed"), never with the value.
- Missing or malformed: nothing calls the SEC. The loop prints one line ("SEC feed: no contact configured, nothing
  is polled"), writes one row `not_configured` per New York day to `state/sec_errors.jsonl` and exits 78, the code
  the publisher uses for "not configured, do not restart me" [T 3.1]. The launch line also guards on the variable
  (3.2), so normally the process is not even started.
- The address is never a command-line argument (arguments show in `ps` and in the supervisor's log), never a config
  value, never part of a URL. What a session may and may not do with it is the SKILL paragraph of 8.4; the only
  test is `[ -n "$AITRADER_SEC_CONTACT" ]`, the rule the trading room set for its own variable [T 3.7].
- The header is sent only to the hosts of `sec.allowed_hosts` (`data.sec.gov`, `www.sec.gov`); `_get` refuses any
  other host before it opens a connection. The client does not follow redirects: `_get` calls the HTTP library
  with redirects switched off (`requests`, the library the engine already uses [C news_live.py:43], follows them by
  default and keeps the User-Agent on a cross-host redirect), and a 3xx is a failed request of kind `redirect`.
  Without this rule a redirect would carry the address to another host. These defences live inside `_get`, so they
  are tested on the real `_get` over a real socket, not on a stand-in (7.1, 7.3).
- How the value gets there (owner's decision [K 65]): he opens the address and gives it once; the main session puts
  it in the cloud environment through an approval card that shows him the exact value; no session repeats it in
  text afterwards. The card edits only the environment of the session that shows it, so step 0 of section 10 first
  checks that this is the trader session's environment and that it is personal, not shared with an organization
  (a shared environment shows its variables to every member). The tool that sets it says that variables apply the
  next time a session starts or resumes; step 0 proves the next morning that it arrived.

### 2.4 Pace and the request budget
- The SEC's limit, in its words: "Current guidelines limit each user to a total of no more than 10 requests per
  second, regardless of the number of machines used to submit requests" [W2], and "please use efficient scripting,
  downloading only what you need and please moderate requests to minimize server load" [W2].
- Design: one sweep of all companies every `sweep_seconds` (60), one request at a time on one connection, evenly
  spaced: 74 requests in 60 s is one request every 0.81 s, 1.23 requests a second, 12% of the limit. The roadmap
  proposed a 30-second sweep (2.5 a second) [R 54]; this spec halves that, because every poll downloads the whole
  file (2.6) and the SEC asks for moderation. The owner can choose otherwise (question 2).
- A hard ceiling that no config value can lift past: the gap between two requests is never under
  `min_request_gap_seconds` (0.5), that is 2 requests a second, 20% of the limit, counting every SEC request of the
  process (the map included). A larger universe makes the sweep longer; it never makes the requests faster. Nothing
  is ever sent in parallel, and a slow sweep is not "caught up" with a burst: requests sit on a grid on the
  monotonic clock and a late one skips to the next free place.
- The limit is per user "regardless of the number of machines". Other SEC callers under the same address would
  share it. Today there are none: `data.sec_recent_form4` has no caller [C data.py:304; a search of `aitrader/`,
  `tests/` and `skills/` finds only its definition], and the vendored skills read their own variable. Rule for the
  future: every SEC request of the bot goes through `aitrader/sec.py` and its one pacer. A session that runs an
  installed `trader-news` or `trader-analyst` skill with its own `SEC_USER_AGENT` [V trader-analyst/facts.py:80]
  would be a second requester outside the pacer; 8.4 forbids copying the address there.
- The SEC enforces by network address, not by the declared name: "further requests from the IP address(es) may be
  limited for a brief period" [W4]. The trader session reaches the internet through the cloud provider's outbound
  proxy. Whether that egress address is shared with other sessions or other customers, and who else calls the SEC
  from it, is not known (section 13). So a 429 or 403 may be caused by traffic that is not this feed's, and this
  feed's requests add to an address it does not own. Every number about blocks in this spec is "blocks seen".
- Volume. Units first, because rev 1 had none: `bytes`, `megabytes_today` and `max_daily_megabytes` count WIRE
  bytes (the body as it crossed the network, compressed), read from the raw stream; `max_body_bytes` caps the
  DECODED body, and `max_wire_bytes` caps the wire body of one reply. The estimate: the roadmap's verifier measured
  24.7 KB per file, 1.8 MB per sweep of 74 [R 157]; since a reply holds at least 1,000 rows (2.1), 24.7 KB can only
  be a compressed size, and it is one file extrapolated to all 74. At one sweep a minute over the launch window of
  3.2 (about 478 minutes) that is about 35,400 requests and about 0.9 GB a day on the wire, and at least about
  12.6 MB a sweep, 6 GB a day, decoded in memory and thrown away. Four names of the universe (JPM, BAC, GS, MS [C
  config.json:100-105]) may file structured-note documents (424B2, FWP) by the thousand a year; if so their replies
  are several times larger than the rest (not measured). Step 2 of section 10 records wire size, decoded size and
  row count for each company, and `max_wire_bytes`, `max_body_bytes` and `max_daily_megabytes` are set from those
  maxima, in a config commit, before step 3. The values in 8.1 are placeholders until then.
- The daily guard, `max_daily_megabytes`: above it the feed stops polling until the next New York day and says so
  in the health row and the daily line.
- No polling on a day with no session: the parent starts nothing on such a day [S 4.5], and the feed lives under
  the same launch line (3.2).

### 2.5 The honest delay floor
A filing is seen at the first poll of its company after the SEC has put it in the file. With a 60-second sweep that
wait is between 0 and 60 s, 30 s on average, plus the request itself (timeouts: connect 5 s, read 10 s, and
`request_deadline_seconds` 20 for the whole request) and plus the SEC's own step, of which it says "The
submissions API is updated with a typical processing delay of less than a second" and "these processing delays may be longer during peak filing times" [W1]. So: about half a minute on
average; at worst the 60 s wait plus the request, which is about 60 s when the request takes the usual second or
less (not measured) and about 80 s when it runs to `request_deadline_seconds`; plus the SEC's own step. All of this
holds while the feed is up, not backing off and not between two launches. It is a poll.
It is never "to the second". Outside the launch window the delay is hours (3.2). None of this is measured yet:
the only sample is one filing seen "within 165 s" [R 53]. Two more things can stand between the SEC and the bot
and are recorded so that they can be told apart later (4.4): a cache in front of the SEC's server (the reply's
`Age` and `Cache-Control` headers) and the machine's own clock after a pause (the reply's `Date` header against
the local clock).

### 2.6 Sparing the SEC
- What this design does NOT spare, said plainly: to find a few tens of new filings a day it downloads every
  company's whole recent history once a minute, about 35,400 requests a day. Against the SEC's "downloading only
  what you need" [W2] that is the weak point of the design, and the reason question 2 carries the Atom
  alternative (2.1). The points below reduce it; they do not remove it.
- Conditional requests: the verifier found that the file sends no `ETag` and no `Last-Modified` [R 157], so today
  every poll downloads the whole file. The client still remembers both headers per company and, when a reply ever
  carries one, sends `If-None-Match` / `If-Modified-Since` on the next poll and counts a 304 as "answered, nothing
  new". It costs nothing now and halves the load the day the SEC adds them. A test covers both paths.
- `Accept-Encoding: gzip, deflate` on every request, as in the SEC's sample [W3].
- An unchanged body (same SHA-256 as the last one for that company) is not parsed again.
- The bulk archive the SEC recommends for large pulls ("recompiled nightly", "republished nightly at approximately
  3:00 a.m. ET" [W1]) is no use for a same-minute feed and is not used.
- No request for a filing's index, text or exhibit. No second request per company. Besides the per-company polls
  the loop makes two other kinds of request: the ticker map, normally once a week and never more than once a New
  York day (2.2), and the SEC's nightly index, at most one per start and only while an EDGAR business day is
  unchecked, so normally one a day, and none before step 2's config commit has switched it on (5.2, "missed").
  Step 2's one-off `--once --history` adds, once, one request to the Atom feed and one to the nightly index (4.5).

### 2.7 Failures and back-off
One rule first: on a refusal the feed slows down or stops. It never changes its User-Agent, its address, its host
or its route to get around one.

| Answer | What the feed does |
|--------|--------------------|
| 200 with the expected object | parse; a parse fault on one company costs that company one poll |
| timeout, connection error, 5xx | that company is skipped; the next sweep is the retry. After `backoff_after_fails` (5) failed requests in a row the sweep period doubles each sweep up to `backoff_max_seconds` (600), until one request succeeds |
| 200 or any status with a body that is not that object (an HTML page, cut JSON) | failure `bad_body`. `bad_body_block_after` (3) in a row, on different companies, are treated as a 429: the SEC is very likely answering with a notice page |
| a body over `max_wire_bytes` on the wire, or over `max_body_bytes` once decoded (the stream is cut at the cap; the body is never held whole and never parsed) | failure `too_big`, a kind of its own. It NEVER counts toward `bad_body_block_after` and never starts a block: a large honest reply (a bank's year of offering documents, 2.4) is not a refusal. That company is marked `too_big` in the health row and the daily line until the cap is raised by a config commit |
| the whole request takes longer than `request_deadline_seconds` (20), however slowly the bytes arrive | failure `timeout`; the connection is closed |
| 429, from either host | all SEC requests stop for `block_429_seconds` (600), or for `Retry-After` when it is longer. `Retry-After` is read in both its forms (a number of seconds, an HTTP date); one that does not parse counts as absent. The SEC: "Once the rate of requests has dropped below the threshold for 10 minutes, the user may resume accessing content" [W4]. After the wait the pace is halved (`slow_factor_after_block` 2) for the rest of the day |
| 403 from `data.sec.gov` | all SEC requests stop for `block_403_seconds` (3,600): it is the answer the SEC gives a client it does not accept [R 157]. After the wait one company is tried; a second 403 ends polling for the day |
| 403 from `www.sec.gov` (the map, the nightly index; not the one-off Atom request of step 2, which is only recorded) | that HOST is not asked again until the next New York day; it is counted as `map_403` and named in the daily line; polling of `data.sec.gov` goes on with the map file it has. Reason: the two hosts are known to answer differently ([R 157]: `www.sec.gov` refused a client `data.sec.gov` accepted), and with one rule for both a refused weekly map would switch off a feed the SEC is serving. If `data.sec.gov` then answers 403 too, the row above applies. With no map file at all, nothing is polled and the feed says so |
| a second block of either kind on one day (`blocks_per_day_max` 2) | no SEC request until the next New York day |
| 3xx | failure `redirect`; never followed (2.3) |
| 404 for one company | that CIK is wrong or gone: `map_mismatch`, the company is left out until the map is rebuilt (2.2) |

- A block is written to the heartbeat file (`blocked_until`, `blocks_today`, `host_blocked`) at the moment it
  starts, atomically (a temporary file, then a rename), BEFORE anything else is done: before the error row, the
  health count or the wait. A handover or a kill in the first second after a 429 therefore still leaves the next
  process a block to honour; rev 1 wrote the heartbeat up to a minute later, and a restart inside that minute would
  have polled inside the SEC's ten minutes.
- `blocked_until` is never later than the start of the next New York day, whatever `Retry-After` says: a huge or
  hostile value cannot keep the feed off for ever.
- Every form of the command that can send a request (the loop, `--once`, `--map`, `--dry-run`, `--history`) reads
  `blocked_until` before its first request and sends nothing while it holds, and writes it when it is refused.
- For every block the error row also keeps `body_class`: "json", "html", "empty" or "other", and the first 12
  characters of the SHA-256 of the body, never its text. A later report can then tell one kind of notice page from
  another, and a block that came with the SEC's own page from one the proxy made.
- Every failure leaves a count in the health row and one row per kind and day in `state/sec_errors.jsonl` holding
  the place, the error class, the HTTP status and the two fields above, and nothing else: never the text of an
  exception, a header or a URL (7.3).

## 3. Where it runs

### 3.1 Its own process
`python3 -u -m aitrader sec-feed --until <supervisor.until_ny> [--supervised PID]` (New York time, like the
engine; the launch line takes the hour from the supervisor's key, as the publisher's does [TP 15], and the `sec`
block has no hour of its own). New files:
`aitrader/sec.py` (pure parts and the one network seam: `user_agent`, the pacer, `_get`, `parse_submissions`,
`classify`, the item table) and `aitrader/secfeed.py` (the loop, the lock, the heartbeat, the journals, the report).
`aitrader/__main__.py` registers `sec-feed` and `sec-report`.

Why not inside the engine:
- The engine is the only thing that looks at the stops, and a step does its stop look first, between scorer batches
  and last [C news_live.py:1349-1350, 1368-1373]. A sweep of 74 paced requests takes a minute by design; it cannot
  sit in a step, and a thread inside the engine would share its memory, its crash and its file. The trading room
  made the same choice for the same reason [T 3.1, 3.7].
- A back-off of an hour, or an SEC notice page, has no business near the code that sells at a stop.
- `news_live.py` is under an open build claim [C BUILD_CLAIMS.md, claim of 2026-11-11 10:09] and under the engine's
  own gate. A feed that edits no engine file is gated as rule 4's third ruling says (section 9).

Other forms of the command: `--once` (one sweep, then exit: 2.2's map check, primes what is new to it, writes
rows; used by rollout step 2), `--once --history` (the one-off measurement run of step 2: the sweep, and from the
replies while they are in memory the file `state/sec_history.json` of 4.5; plus one request to the nightly index of
the previous EDGAR business day at `sec.index_url`, whatever `sec.index_enabled` says, and AFTER it one request to
the Atom feed, both recorded there (the Atom request goes last and its refusal does not invoke the host rule of 2.7:
the cgi-bin path refused generic clients before [R 119], and a 403 there must not cancel the index request); with no `index_url` the index request is left out and recorded as not made), `--map`
(rebuild `state/sec_ciks.json`, one request), `--status` (read-only: the heartbeat's age, today's counts, a block and its end; no network), `--leak-check` (7.3; no
network), `--offline DIR` (replies are read from files in DIR named `submissions-CIK##########.json` and
`company_tickers.json`, the pack's own convention [V trader-analyst/facts.py:36-37]; no network object is built at
all), `--state-dir DIR` and `--config FILE` (tests), `--dry-run` (everything but the journal writes; it does poll
the SEC).

One requester at a time: every form that can send a request (the loop, `--once` with or without `--history`,
`--map`, `--dry-run`) takes the lock of 3.3 first and honours `blocked_until` (2.7). `--status`, `--leak-check`,
`--offline` and `sec-report` send nothing and take no lock.

Exit codes, the publisher's set [T 3.1] so that one rule fits both: 0 the end of the run (`--until`, or its parent
is gone); 3 another feed still holds the lock after the wait of 3.3; 4 a request that hung, ended by its own
watchdog; 78 not configured (no usable contact, 2.3, or a config that lacks one of the keys 8.1 gives no
fallback), which nothing may restart.

### 3.2 Who starts it and keeps it alive
This spec builds no launcher, no restart loop and no keep-awake of its own. It rides on what the two plans build:

| Need | Whose part | The feed waits for |
|------|-----------|--------------------|
| A long-running process in the trader session, started by a tracked background command that also keeps the machine awake | the supervisor's parent and its launch by the watchdog turns [S 4.2, 4.4] | [SP 20] (rollout step 2 of the supervisor) |
| A side process started by the same launch line, with no extra model turn | the publisher's start prefix in `skills/trader/slots/news-watch.md` and its one tested shape, `no_dash.launch_prefix()`, with the test that only the launcher has the launcher's pipe, and the two-run launch-line drill [TP 10, 15, 16] | [TP 15], [TP 16] |
| Ending when the parent is gone | `--supervised PID`, the same flag and rule as the publisher [T 3.1, 3.7] | - (built here, same behaviour) |
| Final form: started and restarted by the supervisor itself | the amendment the trading room asks of the supervisor spec (a second child) [T 3.1; TP 25] | that amendment; this spec asks that it be written for a LIST of side children, not for one (section 11) |

- The feed's part of the prefix is a background list of its own, in the one shape the trading-room plan measured
  [TP 10]:
  `([ -n "$AITRADER_SEC_CONTACT" ] && cd ai-trader && mkdir -p .cache && exec >> .cache/sec_feed.log 2>&1 < /dev/null && python3 -u -m aitrader sec-feed --until <supervisor.until_ny> --supervised $$ &); `
  It is written in front of `launch.command`, beside the publisher's list and never inside either. `$$` inside the
  list is still the launching shell, the one `exec` turns into the parent [TP 10, 15].
- Why this shape and not rev 1's (`[ -n ... ] && python3 ... >> log 2>&1 &` "before the exec"): rev 1's line
  fails three ways. (a) Under bash, `&` puts the whole AND list into a background subshell and a redirection on the
  last command binds to that command only, so the subshell keeps the launch command's output pipe for as long as
  the feed lives. The harness then sees the parent's background command as ended only when the FEED ends, and the
  watchdog turn that must relaunch the engine after a handover or a crash is late by that much (measured for the
  trading-room plan on bash 5.2, and again by the build review of rev 1 on bash 5.2.21: rev 1's shape held the
  pipe 3.0 s where the list above let go after 1.0 s) [TP 10, Review Focus 1]. The list therefore redirects its own three streams first (`exec >>
  ... 2>&1 < /dev/null` is a step of the list), and from that step on nothing in it has the launcher's pipe. (b)
  `launch.command` begins with `cd ai-trader` [SP 14]; a feed started in front of it without its own `cd` runs
  from the repository root, where there is no `aitrader` package and no `.cache/`, and never starts. (c) Written
  after that `cd`, the `&` takes the `cd` into the background list, the parent is started from the wrong folder
  and no engine runs. The parentheses keep the feed's `cd` to itself.
- The line is produced by code, not typed: `no_dash.launch_prefix(commands, guard=False, folder="ai-trader")` [TP
  10] gains two keyword arguments with the publisher's values as defaults,
  `launch_prefix(commands, guard=False, folder="ai-trader", guard_var="AITRADER_DASH_URL", log=".cache/dash_publish.log")`.
  `guard` stays a bool, so the publisher's existing calls, with no guard or with `guard=True` ([TP 10]'s test,
  [TP 15]'s `LAUNCH`), give the same text and need no edit; the feed's call is
  `launch_prefix(<the feed's command>, guard=True, guard_var="AITRADER_SEC_CONTACT", log=".cache/sec_feed.log")`.
  The slot file's prefix is the two lists one after the other.
  `test_started_by_the_slot_files_line_only_the_launcher_has_the_launchers_pipe` [TP 10] is extended to the line
  with both lists. That helper and that test are under the trading room's claim (section 11, collision 2).
- So the feed runs when the parent runs: from the first watchdog launch after 08:00 New York (`launch_from_ny`
  [S 4.4]) to 16:05, on session days only. Until the 9-hour setting is proven the parent hands over four times a
  day [S 4.5]; the feed ends with each parent and starts with the next, a gap of one model turn. (How the match
  with Yahoo treats the engine's side of a handover is 5.1.) A restarted feed loses nothing but time: what it has seen is rebuilt from its own journal (4.1), and what was filed in the gap is
  written as a `catchup` row (or as `fresh`, when the heartbeat shows that company's last good poll at most
  `fresh_gap_seconds` earlier).
- If the feed ends by itself in the middle of a leg (exit 4, or a bug), nothing restarts it until the next launch
  of the parent. With handovers that is at most about two hours; once the long timeout is proven it is the rest of
  the day. For a log-only feed that is accepted and shown (the daily line of 8.3 gives the minutes it was down);
  the amendment of the last table row is what closes it. No second restart mechanism is built for it.
- Before the launch parts land ([TP 15], [TP 16]): nothing runs in a loop. The code can land once S-Task 20 has
  brought `supervise.py` to the live branch (step 1 of section 10; section 11 gives its dependencies), and `--once`
  can then be run after the close by a one-time task (step 2). No interim `nohup`, `setsid` or bare `&`: an
  engine started that way died three times [S 4.4].

### 3.3 Lock, heartbeat, hang
- `state/sec_feed.lock`: an exclusive `flock` held for as long as the process may send a request, taken with
  `supervise.take_lock(path, now)` [SP 10], the standard-library helper that writes `{pid, started_at}` into the
  file. Not [SP 3]: that task writes the engine's lock inline in `news_live.run`, builds no helper, and importing
  `news_live` would break this spec's own import rule (7.2). `supervise` imports no pandas and no engine module
  [SP 10]. `supervise.py` is built on the supervisor's work branch and reaches the live branch only with S-Task
  20's landing [SP 20], so every part of the feed that takes this lock waits for that landing (section 11).
- The lock is waited for. At each of the four daily handovers the earlier feed may still be inside a request when
  the next launch starts its feed; with rev 1's "exit 3 at once" the new feed would leave and nothing would poll
  for the whole leg, up to about two hours. So a start that finds the lock held tries again every
  `sleep_slice_seconds` for `lock_wait_seconds` (25: the request deadline of 20 s, plus two slices, plus slack; a
  test asserts `lock_wait_seconds` >= `request_deadline_seconds` + 2 x `sleep_slice_seconds`), then prints the
  holder's pid and exits 3. The publisher does the same [TP 10]. `--once`, `--map` and `--dry-run` beside a live
  loop do not wait: they see the lock and leave with 0 and one line.
- Every request has a total deadline, `request_deadline_seconds` (20), enforced while the body is read, so a body
  that arrives one byte at a time cannot hold the process past it. With it, the parent check below is never later
  than 20 s plus one slice.
- `state/sec_feed.json` (git-ignored), written atomically after every sweep, once a minute during any wait, and at
  once when a block starts (2.7): `at`, `pid`, `parent`, `seq` (sweep number), `last_ok` (last good request),
  `answered` (companies in the last sweep), `fails_in_a_row`, `blocked_until`, `blocks_today`, `host_blocked`,
  `megabytes_today`, `last_error` (a class name), `configured` (true/false), and `polls`: each company's last good
  poll time. `polls` is what lets a restarted feed call a row "fresh" honestly (4.1). It holds only the LAST poll
  and the file is not in git, so no report can read from it whether one company was answered over a day; nothing
  in section 5 needs that ("late" is keyed on the stamp, "missed" on the nightly index). Which index days were
  checked is read from the journal's `index_check` rows (5.2), not from this file, which a new machine loses.
- The watchdog times only the request in progress, on the monotonic clock: the loop records the start of each
  request and clears it when the request returns, and a daemon thread ends the process with exit 4 and one
  printed line only while ONE request has been running for more than `hang_seconds` (180). A feed that is waiting
  (the pacing gap, a back-off, a block of 600 s or 3,600 s, the megabytes stop, a day-long idle, a map with no
  company) has no request in progress and never fires it. Rev 1's wording, "no request has finished for
  `hang_seconds` outside a back-off", is the wording the trading-room plan found would end a healthy loop [TP 10,
  Where-decides 9]. With the deadline above, exit 4 means the deadline itself failed.
- Every wait is sliced: in every `sleep_slice_seconds` of every wait of every kind named above, the loop tests
  `--until` and, under `--supervised`, whether `/proc/<PID>` is still there, and ends with 0 when either says so.
  A feed idling through a day-long block therefore still leaves within a slice of its parent, and frees the lock.
- Every sweep is inside one try/except. The loop ends only at `--until`, on a signal, when its parent is gone, or
  by the watchdog. A day-long block does not end it: it idles, sliced, until one of those.

### 3.4 It cannot slow or block the engine's stop looks
- A separate process. It takes no engine lock, writes no file the engine reads or writes, and reads none of the
  engine's files while it loops (only `sec-report`, a separate command, reads the news journals and the
  supervisor's uptime log).
- It never calls Yahoo. The publisher needed a rule to yield to the engine's stop quotes [T 3.3]; the feed has no
  quote and needs none.
- It runs at `nice` 10 and raises its own out-of-memory score to `oom_score_adj` (500), so a machine short of
  memory takes it before the engine: the publisher's two settings [T 3.7], best effort.
- One connection, one request at a time, no thread pool. Its CPU work is decompressing and parsing 74 files a
  minute of at least about 170 KB each (2.1), about 12.6 MB a minute or more; not small, and measured in step 2
  (CPU seconds per sweep). A body is read as a stream and cut at its caps, so the TEXT of one reply is never more
  than `max_body_bytes`. That does not bound memory: parsing a body near the cap (the placeholder is 50,000,000
  bytes decoded, 8.1) builds Python objects several times its size (not measured). Peak resident memory next to
  the engine is therefore measured in step 2 (4.5) and `max_body_bytes` is set with it in view; `oom_score_adj`
  makes the feed the first process a short machine takes, not a small one. It also imports `aitrader.journal`,
  which imports pandas [C journal.py:18].
- Measured, not assumed: target 6, by the engine half of the pass rule the trading-room plan wrote for the same
  engine numbers [TP 11], stated here as that task states it. The base is the last full session before the feed's
  loop first ran, whatever else ran that day (if the publisher is already running it is in both days, which is the
  point). A day's rows are the rows of `news_health.jsonl` [C news_live.py:654-659] whose `at` lies inside that
  day's NYSE session. The pass, all three, on the feed's first full session: the day's sum of
  `stop_quotes_missing` is not above the base day's; its largest `stop_gap_max_s` is not above the base day's by
  more than `news.poll_seconds` (20 [C config.json:243]); the median of its `step_s_median` is not above the base
  day's times `report.pass_step_ratio` (1.2). A day's largest `stop_gap_max_s` is the largest of its values that
  are not null; when either day has none (no stop look was made, because nothing was held), the number is null on
  both sides, does not fail, and is named in the report as not compared. A day with no rows fails, named
  `no_rows`: silence is not a pass. The feed computes this itself in `secfeed.py` and does not call TP 11's
  `dashpub.pass_numbers`, which also judges the publisher's own rows and fails a day on which the publisher wrote
  none.

## 4. What a "new filing" is, and what is kept

### 4.1 New, primed, fresh, catch-up
- A filing is its accession number. It is new when that number, for that CIK, is not in the set the feed has
  already seen.
- The seen set has no file of its own. At a start it is rebuilt from `state/sec_filings.jsonl`: every accession in
  a filing row or a prime row whose filing date (`filed`) is within `seen_keep_days` (14). A filing in a reply
  that is older than that window is never new. The window decides only which accessions are loaded; it does not
  decide whether a company has been seen before.
- First sight of a CIK means: no row of any kind for that CIK anywhere in the journal, however old (the start
  reads the whole file once for this; it is small, 8.2). Only then are its filings inside the window marked seen
  under ONE row, `{"outcome": "primed", "cik", "ticker", "at", "filings": [{"accession", "filed"}, ...]}`, the way
  the engine primes its headlines [C news_live.py:687-688]; a company with no filing in the window gets a prime
  row with an empty list, so that it too has been seen. No filing row is written for primed filings and they are
  in no delay number. Rev 1 tested first sight against the rebuilt 14-day set: a company with no filing for 14
  days would have been primed again at the next start, and whatever it filed while the feed was down would have
  vanished into the prime row with no catch-up row and no count. That falls hardest on the foreign names, which
  file no insider forms and can go two weeks with nothing (4.2).
- Every new filing after that gets one row. `kind` is "fresh" when that company's previous good poll (in this
  process, or the heartbeat's `polls` after a restart, 3.3) was at most `fresh_gap_seconds` (150) before this one,
  so the filing became visible inside a known short window. Otherwise it is "catchup": the feed was down, backing
  off, between two launches or outside its hours. Catch-up rows are kept for coverage and for the earnings times
  of backlog item 2; they are in no speed number.
- "Late" is not "catch-up", and rev 1 confused them. A catch-up row is by definition one whose company was NOT
  polled in the last 150 s, so "a catch-up row while the company was answering" cannot exist. The two real cases
  of a filing the feed could not see in time are: (a) the SEC shows a filing late, which arrives as a FRESH row
  whose acceptance stamp is well before `prev_poll`; (b) a filing never appears in the company's file. Both are
  defined in 5.2 ("late", "missed"), from the stamp and from the SEC's nightly index, not from the `kind` flag.
- A machine that is replaced loses the rows written since the last state commit (up to about 30 minutes [S 13]).
  Those filings come back once, as catch-up rows with a later first-seen time. The report counts such re-logged
  rows apart (same accession, no earlier row on the branch).

### 4.2 Which forms
Every new filing of the 74 companies is logged, whatever its form. It costs no request (the reply already lists
them), and without the whole list neither coverage nor missed filings can be counted. Each row gets a `class`:

| `class` | Forms (`sec.forms`) | Used for |
|---------|---------------------|----------|
| `event` | 8-K, 8-K/A, 6-K, 6-K/A | the comparison with Yahoo (section 5); the only class in the lead-time number |
| `report` | 10-Q, 10-K, 20-F, 40-F and their /A | logged; shown as a count |
| `ownership` | 3, 4, 5, 144, SC 13D, SC 13G, SCHEDULE 13D, SCHEDULE 13G and their /A | logged with the acceptance time only; nothing is parsed (Form 4 content is backlog item 3) |
| `offering` | S-1, S-3, F-1, F-3, 424B*, FWP and their /A | logged; shown as a count |
| `other` | everything else | logged; shown as a count |

- 8-K items: the `items` text is split into codes. The labels and the "important" set are the vendored tables
  `ITEMS_8K` and `IMPORTANT_ITEMS` (earnings 2.02, officer change 5.02, bankruptcy 1.03, cyber incident 1.05, debt
  acceleration 2.04, impairment 2.06, delisting notice 3.01, unreliable past financials 4.02, change in control
  5.01) [V trader-news/news.py:65-76]. They are copied into `aitrader/sec.py` with the licence note (section 6),
  because the vendored folder is not an importable package; a test reads the vendored file and fails when the two
  tables differ.
- 6-K is in `event` because a foreign filer reports its results and its news on it and files no 8-K. Five names of
  the universe are foreign companies (TEVA, CHKP, NICE, WIX, MNDY [C config.json universe]); which forms each of
  them files is not confirmed here and is read from the first sweep (`sec_history.json` counts forms per
  company). A foreign private issuer files no Forms 3, 4 or 5, so for those names the 6-K rows are most of what
  there is. A 6-K has no item codes, so it can only be matched loosely (5.1).
- The vendored `parse_sec_atom` [V trader-news/news.py:258] parses the Atom feed of `www.sec.gov`, which this
  design does not poll; it is not used. `latest_filings` [V trader-analyst/facts.py:353] reads the same JSON arrays
  and is the model for `parse_submissions`, which is written new: it must survive arrays of different lengths and a
  missing `items` array, which the vendored one indexes directly.

### 4.3 The row
`state/sec_filings.jsonl`: one JSON object per line, append only, tracked in git, NOT hash-chained. It is a
measurement, like the engine's three [C news_live.py:14-17]: a damaged line must never stop anything, a reader
skips a line it cannot parse, and a row that cannot be written costs nothing but itself. It is written with
`journal.append`, which chains only the names in its own list [C journal.py:58, 154].

| Field | Meaning |
|-------|---------|
| `v` | 1 |
| `at` | first seen: UTC, ISO-8601, milliseconds, the moment the reply was parsed |
| `cik`, `ticker`, `company` | the 10-digit CIK; the universe's ticker; the SEC's `name`, cleaned and cut to `text_max_chars` (120) |
| `accession` | the SEC's accession number |
| `form`, `class` | as filed; the class of 4.2 |
| `items`, `important` | list of item codes (empty when none); true when one is in the important set |
| `accepted_raw` | the SEC's `acceptanceDateTime`, character for character |
| `filed`, `report_date` | the SEC's `filingDate` and `reportDate` |
| `doc` | `primaryDocument`, cleaned and cut |
| `prev_poll` | that company's previous good poll (UTC), or null |
| `kind` | "fresh" or "catchup" (4.1) |
| `skew_s` | the reply's `Date` header minus the local clock at the reply, in whole seconds; null when the header is missing. The machine's own clock error, which every time in this row carries |
| `age_s` | the reply's `Age` header in seconds, or null: how long a cache in front of the SEC held this reply |
| `map_mismatch` | present and true when the reply's own tickers do not hold this ticker (2.2) |

The row holds no `delay_s`. Rev 1 computed it at write time by reading the stamp as UTC, before anyone knew the
stamp's clock. The raw stamp and the bot's own times are kept; the delay and its checks are computed by the
report, under the clock that 4.4 decides, and can be recomputed for every row ever written. The other two rows
of this file are the prime row (4.1) and the nightly-index row (5.2).

Company names and document names come from outside and are data: control characters and markup characters are
removed as the engine does for headlines [C news_live.py:93-95]. Nothing in a filing can change a config value or a
path.

### 4.4 The acceptance time is not trusted until it is calibrated
- The field ends in "Z" in the pack's two fixtures [F], and the fixtures settle nothing. One of them (CIK
  0000320193) cannot be a raw capture. Its insider forms are stamped between 00:09Z and 02:44Z, all on
  summer-time dates, and the SEC says EDGAR accepts filings "Monday through Friday, from 6:00 a.m. to 10:00 p.m.,
  ET" [W3]. Read as UTC, the stamps up to 01:59Z are 20:09-21:59 New York time, inside those hours, but the 21 of
  its 29 rows stamped from 02:30Z on are 22:30-22:44, after EDGAR closes; read as New York time, 28 of the 29 fall
  outside the hours [F]. So under either reading some of those filings were accepted while EDGAR was closed. The
  fixtures carry no weight on the clock and are used only for the shape of the reply.
- Two readings are possible: the stamp is true UTC, or it is New York wall-clock time with a "Z" on it. They
  differ by 14,400 s in summer time and 18,000 s in winter time; the first sessions of this feed are in winter
  time.
- The test that decides, on the same page: under the right reading no weekday stamp falls outside 06:00-22:00 New
  York time [W3]. Step 2's run reads a year of stamps for 74 companies and writes, into `sec_history.json` (4.5),
  the hour-of-day histogram and the count of stamps outside those hours under EACH reading. One reading should
  put about none outside and the other thousands. The result is written into config as `sec.accept_clock` ("utc" or
  "et") in a commit that cites the two counts; until then the key says "unknown". If neither reading is clean, it
  stays "unknown" and that is reported.
- New York time is always converted with `zoneinfo` ("America/New_York"), date by date. Never with a fixed four
  hours.
- Until the clock is known, the main speed number of this design, the lead over Yahoo (5.2), uses only the bot's
  own two first-seen clocks and does not touch this field, and every number that does need the stamp (`delay_s`,
  "late", the fresh share's denominator) is printed as "not calibrated".
- Once it is known, the report computes for every fresh row `delay_s` = `at` minus the stamp under
  `accept_clock`, and sorts each row into one of four causes, which rev 1 lumped under one flag:

  | `delay_why` | Rule | What it means |
  |-------------|------|---------------|
  | "ok" | 0 <= `delay_s` <= (`at` - `prev_poll`) + `publish_slack_seconds` (120) | the filing appeared inside the poll gap, as it should |
  | "et_clock" | `delay_s` is off that range by the New York offset of that date, within `clock_tolerance_seconds` (120), in either direction | this stamp is in the other clock; a few of these say the SEC mixes clocks, many say `accept_clock` is wrong |
  | "late_publish" | `delay_s` is above the range and not an offset | the SEC showed the filing later than it accepted it ("may be longer during peak filing times" [W1]; a filing begun after 17:30 "will be disseminated the next business day" [W3]), or a cache held an old reply (`age_s`). This is the "late" count of 5.2 |
  | "negative" | `delay_s` < 0 and not an offset | a stamp after the bot saw the filing: the machine's clock (`skew_s`) or a stamp that is not a time of acceptance |

- The report prints the median of `delay_s` over the "ok" rows only when they are at least
  `report.min_delay_ok_share` (0.9) of the fresh rows; otherwise it prints the four shares and the sentence "the
  SEC's acceptance stamp is not calibrated".
- Also recorded, so that a cache and a wrong local clock can be told from a late SEC: `skew_s` and `age_s` in each
  row (4.3), their largest values in each health row, and the reply's `Cache-Control` text once in
  `sec_history.json`.

### 4.5 The one-off history file
`state/sec_history.json`, tracked, written once by `sec-feed --once --history` in rollout step 2 from the replies
while they are in memory, and written again only by the same command. Rev 1 planned to calibrate "from the primed
rows" and to answer the sample-size question with `sec-report --history`, but prime rows hold no stamps, unchanged
bodies are kept only as a hash, and the report has no network: the data those two steps needed was never kept.
This file keeps it, as counts only (no filing text, nothing a prime row or a filing row does not already make
public):

- `built_at`, the number of companies answered, and for each company: rows in the reply, the oldest `filed` date in
  it, wire bytes, decoded bytes, parse time, and the count of its filings by form;
- filings by `class` x month x "inside / outside 08:07-16:05 New York on a session day", and the part of the
  inside count that falls in 09:07-16:00 (where a match with Yahoo is possible at all when every handover is
  bridged, 5.1), under BOTH clock readings;
- for `event` filings also: by 8-K item, and how many map to a strict class of 5.1 (so the share that can ever be
  strictly matched is known before any is);
- the hour-of-day histogram of all stamps, and the count outside 06:00-22:00 New York on weekdays, under both
  readings (4.4);
- filings a day by class and by company, mean and largest (how much the journal grows, and whether four banks
  drown the rest, 8.2);
- the headers of one reply by name (whether `ETag`, `Last-Modified`, `Age`, `Cache-Control`, `Content-Length` and
  `Content-Encoding` are sent; the text of `Cache-Control`), and the largest `skew_s`;
- the one Atom request (2.1): status, wire bytes, entries, the age of the newest entry;
- the one nightly-index request (5.2): the day asked for, status, wire bytes, rows, rows of the 74 CIKs; or "not
  made" when `sec.index_url` is null. One request with the one address the config holds: a refused or unreadable
  answer is recorded, and no other file name is tried;
- process numbers: peak resident memory over the run (`ru_maxrss`), CPU seconds for the sweep.

`sec-report --history` only reads this file. A reader that finds no file says "history not measured".

## 5. The forward measurement

### 5.1 The match with Yahoo
What exists on the Yahoo side: `state/news_seen_log.jsonl`, one row per new headline with `key`, `symbol`,
`published`, `first_seen` and `outcome`, and no title [C news_live.py:607-615]; `state/news_scores.jsonl`, one row
per scored headline with its `headline` text [C state/news_scores.jsonl, last row]. A headline first seen more than
`news.fresh_minutes` (30) after its publication is "stale": it is in the first file only, with no text [C
news_live.py:681-686]. On 2026-11-11 that was 423 of 655 rows, many of them from an engine start [C
state/news_seen_log.jsonl].

One Yahoo clock for everything: the seen log's `first_seen`. A scores row has no `first_seen`, only `logged_at`,
the moment it was scored, which is first sight plus the scorer (about 9 s in the median [R 150], minutes when
headlines queue) [C news_live.py:1135-1138]. So a scores row is joined to its seen row by `news_scores.id` =
`news_seen_log.key` [C news_live.py:615, 1135], and the time used is that seen row's `first_seen`, for the strict
match as for the loose one. A scores row with no seen row is counted and left out. "Earliest" always means the
smallest `first_seen`. Without this an implementer could take `logged_at` for one match and `first_seen` for the
other and build a gap between the two numbers out of scorer delay.

For each fresh `event` filing, the candidates are the Yahoo rows of the same ticker with `published` no earlier
than `match.before_seconds` (3,600) before the filing's `at` and `first_seen` no later than `match.after_seconds`
(14,400) after it. The window opens BEFORE the filing on purpose: a company usually sends its press release to the
wires and files the 8-K minutes later, so Yahoo can be first and the lead negative.

Censoring comes before matching. The only thing that ever looks at Yahoo is the engine, every 20 s [C
config.json:243], and it stops at 16:05 [C news_live.py:1393]; when it is not polling, Yahoo's side of the
comparison does not exist, while the feed, a separate process, may go on. A Yahoo story that arrives after the
engine's last poll is first seen the next morning as a stale row, outside the window. Rev 1 would have counted
such a filing as "unmatched" or as a long lead; it is neither. So:

- Engine uptime is read from `state/news_health.jsonl`: a row with `steps` > 0 says the engine polled through
  [`at` - `window_s`, `at`] [C news_live.py:654-656]. Windows that follow each other with holes of at most
  `match.engine_gap_seconds` (120) form one stretch.
- The handovers. Until the 9-hour setting is proven the parent stops and restarts the engine four times a day, at
  09:18, 10:48, 12:28 and 14:17 New York [S 4.5], with a target of 60 s from the old engine's last stop look to the
  new one's first [S 4.5, target 11]. A planned stop leaves a hole in the health rows that is usually larger than
  120 s: the unfinished window at the end of a run writes no row, so the hole is that window (anything up to
  `news.health_log_seconds`, 300 [C config.json:279]) plus the stop itself. Read from the health rows alone, most
  handovers would be breaks: with legs of 71 to 109 minutes, "unmatched" (four unbroken hours) could almost never
  happen and "matched" only for filings late in a leg. The health rows also cannot tell a stop of 60 s from an
  outage of six minutes, because the unwritten window hides the difference. So a hole is BRIDGED, and its two stretches count as one, when the supervisor's
  `state/uptime.jsonl` [S 4.6], tracked, read with `supervise.read_rows` [SP 10], shows that it was one planned
  handover that came back within the stop target: between the two stretches there is exactly one child `exit`,
  with `why` "planned", and one `up` after it, and no `hang`; the `up` row is at most
  `supervisor.handover_target_seconds` (60) after the `exit` row; every `mark` between the end of the earlier
  stretch and the `exit` shows `hb` at most `supervisor.up_hb_max_seconds` (60), the test the uptime number already
  applies to the same minutes [S 4.6], so the old engine was alive through its unwritten window; and the later
  stretch begins at most `match.engine_gap_seconds` after the `up` row. A hole that fails any part, and every hole
  on a day whose uptime log is missing or holds none of these rows, stays a break: the rule errs toward censoring.
  The report prints each day's handovers as bridged or not, with the seconds from `exit` to `up`.
- Why a bridged hole is not a break in Yahoo coverage: the next engine keeps the seen list [C news_live.py:535,
  1415], and Yahoo's feed still holds a headline a minute later (it holds headlines older than 30 minutes: the
  stale rows found at engine starts, above, show it [C state/news_seen_log.jsonl]). A headline published during the
  stop is first seen by the new engine's first poll, late by at most the stop plus one `news.poll_seconds`, far
  under `news.fresh_minutes` (30), so it is neither lost nor stale. What it costs: that `first_seen` is late, so a
  lead can be too HIGH by up to about 80 s. A matched candidate first seen within `match.engine_gap_seconds` after
  the `up` row of a bridged handover is marked `across_handover`; the report prints how many leads carry the mark,
  and the median with and without them.
- A fresh `event` filing gets exactly one of three outcomes, for the strict match and again for the loose one:
  - `matched`: a candidate exists, and the engine polled without a break (one stretch, bridged holes included)
    from (`at` - `match.before_seconds`) to that candidate's `first_seen`. Only these have a `lead_s`.
  - `unmatched`: no candidate, and the engine polled without a break over the whole window, to `at` +
    `match.after_seconds`. Only a filing first seen before about 12:00-12:05 New York (the last health row comes a
    few minutes before 16:05) on a day whose handovers were all bridged can be this.
  - `censored`: everything else. Printed as "Yahoo not shown by the engine's last poll at T", with T. It is its
    own count, in no `lead_s` and not in `unmatched`.
- Censored by rule, whatever Yahoo did: a filing first seen within `match.before_seconds` after the day's first
  engine start (about 08:07 to 09:07 New York), because its window opens before the engine's first poll and a
  headline found waiting at that poll would carry a `first_seen` set by the engine's start, not by Yahoo; the same
  for the hour after any restart that is not a bridged handover; and a filing whose earliest candidate, if any,
  comes after the day's last health row. With every handover bridged a match is possible for filings first seen
  from about 09:07 to 16:00, about 6.9 of the feed's 8 hours; each handover that misses its target cuts out about
  one more hour, and more for filings just before it.
- What censoring does to the numbers, said beside them: it removes the cases where Yahoo was slowest, so the
  median of the matched leads is too LOW whenever the censored count is not 0, and the report says so in that
  line. An engine that dies in mid-session censors the same way; today a dead engine is replaced in up to about
  39 minutes [S 3, row 2].

Two matches are reported side by side:

- Strict (same event, by text): the earliest candidate from `news_scores.jsonl` whose headline hits the keyword
  class of one of the filing's items. The classes are the vendored `KEYWORDS` table [V trader-news/news.py:77-88]
  and the map is `match.item_classes` in config: 2.02 -> earnings; 5.02 -> people; 1.01, 2.01, 5.01 -> deal; 1.03,
  1.05, 2.04, 2.06, 3.01, 4.02 -> risk; 3.02, 3.03 -> capital. A filing whose items map to no class (7.01, 8.01,
  9.01 alone, and every 6-K) has no strict match by rule.
- Loose (same company, any headline): the earliest candidate of any outcome from `news_seen_log.jsonl`. It needs
  no text and is biased toward Yahoo: an unrelated headline counts. Among `matched` filings it is a lower bound on
  the lead, "Yahoo showed nothing at all on this company for at least this long". It is a bound only inside the
  engine's uptime; rev 1 called it a floor without that condition.
- The built-in handicap, printed beside every lead: the feed asks the SEC once in `sweep_seconds` (60, a mean wait
  of 30 s) and the engine asks Yahoo once in `news.poll_seconds` (20, a mean wait of 10 s). The comparison
  therefore starts about 20 s in Yahoo's favour; the report prints that number, computed from the two config
  values, and does not subtract it.
- The known hole: a stale Yahoo headline about the event cannot be matched strictly, since it has no text. The
  report prints, per filing, how many stale rows fell in its window. Closing the hole means one more field in the
  engine's seen row; that is the engine's file and Yahoo's unread terms [R 173], so it is question 4, not part of
  this build.
- The sample will be small (5.3), so every strict match and every unmatched or censored event filing is also read
  by a session for the two-week report, and the report says how many automatic matches that reading overturned.

### 5.2 The numbers
`python3 -m aitrader sec-report [--days 14 | --day YYYY-MM-DD | --history]`: read-only, no network, prints one
page.

| Number | Definition |
|--------|------------|
| `lead_s` (strict, loose) | the Yahoo seen row's `first_seen` minus the filing's `at` (5.1); positive = the SEC feed was first. Over `matched` filings only. Median, quartiles, the share above 0 and n; split by item class and by "in the regular session / before the open". Beside it: the censored count, the sentence on its bias, the poll handicap, and the count of `across_handover` leads with the median without them (5.1) |
| the test of the lead | 5.3's sign test and clustered range, printed only at `report.min_events` or more; below that the line reads "n = {n}, under {min_events}: no test" |
| censored | fresh `event` filings whose Yahoo side was cut off by the engine's hours or a break, strict and loose, each listed with T; split into "first hour after the day's first start", "after the last health row" and "around a break"; beside it each day's handovers, bridged or not, with the seconds from `exit` to `up` (5.1) |
| unmatched | fresh `event` filings the engine watched through the whole window with no strict match, and with no loose match, as counts; each one listed |
| headlines explained | of Yahoo's scored headlines at or beyond the engine's action lines (above `buy_min_score`, or at or under `sell_on_score_at_most` [C config.json news]), the share that had an `event` filing of the same ticker in the window. This is the number that says whether the SEC knows about the headlines the bot would act on |
| coverage | companies with a CIK out of 74; `answered_min` per sweep; the share of the launch window with a sweep at most `fresh_gap_seconds` old, per day. This is the feed's uptime number |
| fresh share | fresh rows / all filing rows whose acceptance stamp, under `accept_clock`, falls inside a stretch in which the feed was up (from the health rows). "Not calibrated" while `accept_clock` is "unknown". Always printed with its numerator and denominator. Rev 1's denominator took every catch-up row filed on a day the feed ran, which counts everything accepted before 08:07, after 16:05 and the evening before: it measured when companies file, not how well the feed captures, and could not reach any bar under session hours |
| late | fresh rows with `delay_why` "late_publish" (4.4): the filing was accepted more than `publish_slack_seconds` before a poll that did not show it. Keyed on the stamp, not on `kind`. "Not calibrated" while the clock is unknown. Each listed with its `age_s` and `skew_s` |
| missed | from the SEC's nightly index, an independent list: "Indexes incorporating the current business day's filings are updated nightly starting about 10:00 p.m., ET" under `/Archives/edgar/daily-index` [W3]. The days are EDGAR business days, not NYSE days: weekdays not in `sec.edgar_closed`, the federal holidays on which EDGAR takes no filings (EDGAR is closed on Veterans Day, when NYSE is open, and open on Good Friday, when NYSE is closed; to be confirmed, section 13). At each start, after the first full sweep (so that catch-up rows had their chance), the feed takes the OLDEST EDGAR business day that has no `index_check` row in the journal, from the day after the last such row up to the previous EDGAR business day and never older than `seen_keep_days` (older filings would not be logged anyway), and makes ONE request for that day's index. So a day on which the feed did not run is checked later, and a backlog clears one day per start (about five starts a day); with nothing unchecked, no request. It keeps the rows of its 74 CIKs and writes one row `{"outcome": "index_check", "day", "listed", "in_journal", "missing": [accessions]}` to `sec_filings.jsonl`. `missing` is the missed-filings count. The address is `sec.index_url`, a template the plan's first task copies from the SEC's documentation of the index (the file's name was not read here); null means no request. The loop asks only once `sec.index_enabled` is true, which step 2's config commit sets after its one request has shown the file's shape and size; until then this line reads "missed filings: not measured". It is never printed as 0 on no data |
| error rate | failed requests / requests, by kind (`too_big` apart); blocks seen (403, 429), their length and `body_class`; `map_mismatch` and `map_403`; wire megabytes a day |
| `delay_s` | as 4.4, with the four `delay_why` shares; only when calibrated. Beside it, always, the stamp-free bound `at` - `prev_poll` (median and largest) |
| the engine beside it | target 6 as 3.4 defines it: the base day, each of the feed's days, the three numbers on both sides, the stop gap named when not compared, `no_rows` named |

Every number is printed with its n and its file. No number is a claim of profit.

### 5.3 What will decide, later, whether this source may ever move money
Not this spec. It only fixes, before any data exists, what a later proposal must bring (Basic law 2, item 3):
- at least `report.min_events` (30) fresh `event` filings with a strict `matched` outcome, the count the guards on
  trial also wait for [C config.json `_note_guards`].
- How long that takes, as arithmetic and not as a measurement. Assume about 10 8-Ks a company a year (an
  assumption, not read anywhere): 74 x 10 / 250 trading days is about 3 `event` filings a trading day, about 30 in
  10 sessions, at ALL hours. Rev 1's "about ten in two weeks" was that number cut to the launch window; it is a
  guess at fresh event filings, not at strict matches. A strict match needs more: an item that maps to a class
  (a filing with only 7.01, 8.01 or 9.01, every 5.07, every 2.03 and every 6-K has none by rule), a Yahoo headline
  the engine scored that hits that class's keywords, and no censoring. Censoring alone leaves, with every handover
  bridged, only filings first seen from about 09:07 to 16:00 (5.1), and each handover that misses its 60 s target
  takes about one more hour; how often handovers meet it is not measured yet (the uptime log will say). A plausible
  strict count is 2 to 5 in 10 sessions when the handovers are bridged, fewer when they are not (a guess, not a
  measurement), so 30 is months away, not two weeks. The first 10 sessions can also only start after [SP 20] and
  [TP 15-16], about December 2026: between earnings seasons (few 2.02), with a holiday on 2026-11-26 and early closes
  on 2026-11-27 and 2026-12-24 [C config.json:12-14].
- The estimate is replaced by a projection as soon as step 2 has run: from `sec_history.json` (4.5), `event`
  filings a year x the share inside 09:07-16:00 New York on a session day (where a match is possible when every
  handover is bridged, 5.1) x the share whose items map to a strict class = strict CANDIDATES per 10 sessions (an
  upper bound on strict matches: the Yahoo side and the handovers are still unknown), and from it the months to
  30. `sec-report --history` prints it, and the two-week report repeats it with the count actually
  matched. (2.03 is not mapped to "capital" to raise n: that class's keywords are dividend, buyback, offering [V
  trader-news/news.py:82], which a new debt obligation does not match; widening the map after seeing a small n
  would be fitting the test to the data.)
- The test of the lead, registered here before any row exists, and computed in `aitrader/secfeed.py` from the
  `sec.report` block. NOT with the project's bootstrap code, as rev 1 said: that code is a block bootstrap of
  DAILY RETURNS that reports Sharpe, growth and drawdown and refuses under `min_blocks` x `block_days` = 800
  observations [C metrics.py:131-140; config.json:289-296], so it could never run on 30 event leads; and adding a
  median bootstrap to `metrics.py` would touch a file the time machine loads and bring a sweep (section 9). The
  test is two numbers over the strict `matched` leads: (a) an exact two-sided sign test of `lead_s` > 0 against
  one half (leads of exactly 0 dropped), passed at p under `report.sign_alpha` (0.05); (b) the range of the
  median from a percentile bootstrap that resamples whole New York DAYS (filings of one day move together: one
  slow Yahoo afternoon is one observation, not five), `report.boot_draws` (2,000), `report.boot_seed` (0), level
  `report.boot_level` (0.95), passed when the range lies above 0. Both must pass. Neither value is changed after a
  result has been seen. The censored count is printed with the verdict, since it biases the median down (5.1).
- error rate under `report.max_error_rate` (0.01, `too_big` counted) and no day with a block seen. If there was a
  block, the proposal must say what its `body_class` and the egress address show about whose traffic caused it
  (2.4); a block that cannot be attributed still counts against the source as the bot can reach it.
- no bar on the fresh share. Rev 1 asked for 0.95; under session hours that number shows the filing habits of
  companies (5.2), and the feed's uptime is already the coverage row. The fresh share is reported, with its
  denominator, and decides nothing.
- the "missed" line measured, not "not measured", and its count shown;
- and, above all, graded returns: lead time is not edge [R 122, 160]. A proposal must show what the price did after
  filing events, graded forward at fixed horizons net of the news book's cost, which needs the minute-bar archive
  and the grading of roadmap sub-projects 5 and 6 [R 58-66]. This journal makes that possible (it has the second
  each filing was first seen); it computes none of it.
- Then rule 4 for a trading rule of the news engine: the critic, the unit suite and a written forward measurement
  (the second ruling), and the owner's answer.

### 5.4 The two-week report
After 10 sessions with the loop running: `sec-report --days 14`, the hand reading of 5.1, and one file,
`reports/YYYY-MM-DD-sec-feed.md`, with the table of 5.2, the facts of section 6 as they then stand (cost, delay,
error rate), what was not measured, the projection of 5.3 (strict matches so far, strict candidates per 10
sessions, months to 30), and a recommendation among: keep logging as is; widen the hours; switch to the lighter
Atom feed; stop. What this report can and cannot decide: it decides whether to keep logging and in which form. It
cannot test whether the lead is above 0, because n will be far under 30, and it says so in its first line. It
goes through `data:validate-data` before the owner sees it (the skills table of `CLAUDE.md`). He gets five short
Hebrew lines and one question.

## 6. Terms, licence, cost (Basic law 2, item 3)

| | |
|-|-|
| Source | U.S. Securities and Exchange Commission, EDGAR, `data.sec.gov` submissions API |
| Cost | $0. "These APIs do not require any authentication or API keys to access" [W1]. No account, no key, no card |
| Delay | the SEC's statement: "typical processing delay of less than a second", "may be longer during peak filing times" [W1]. This design adds a poll wait of 0-60 s (2.5). Measured by the bot: nothing yet |
| Error rate | not measured. Written into this table by the two-week report (5.4) |
| Rate limit | "no more than 10 requests per second, regardless of the number of machines" [W2, W4]; this design: 1.23, ceiling 2. Enforced by IP address [W4] |
| Identification | "Please declare your user agent in request headers" [W3, W5] |
| Reuse of the data | "Information presented on sec.gov is considered public information and may be copied or further distributed by users of the web site without the SEC's permission", "Please consider appropriate citation to the SEC as the source" [W4]; "All Government-created content on sec.gov and EDGAR public filing content are free to access and reuse" [W5]. So accession numbers, forms and times may sit in the public repository; every report names the SEC as the source |
| Parser licence | MIT, (c) 2026 Jake Schincariol [C vendor/jake-trader-skill-v2/LICENSE; THIRD_PARTY.md:22-27]. Copied into `aitrader/sec.py`: the two 8-K tables and the keyword table, with the notice and the pinned commit in the file's header. `THIRD_PARTY.md` gains one line under that entry saying what was copied and where. The test fixtures copied in 7.1 come from the same repository under the same licence |

The fair-access policy in the SEC's words, with where and when it was read (all on 2026-11-11):

- [W2] https://www.sec.gov/about/developer-resources (page dated "Last Reviewed or Updated: March 10, 2025"): "To
  ensure that everyone has equitable access to SEC EDGAR content, please use efficient scripting, downloading only
  what you need and please moderate requests to minimize server load. Current guidelines limit each user to a total
  of no more than 10 requests per second, regardless of the number of machines used to submit requests. To ensure
  that SEC.gov remains available to all users, we reserve the right to block IP addresses that submit excessive
  requests." And: "The SEC does not allow "unclassified" bots or automated tools to crawl the site. Any request
  that has been identified as part of an unclassified bot or an automated tool outside of the acceptable policy
  will be managed to ensure fair access for all users."
- [W3] https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data ("June 26, 2024"): "Current
  max request rate: 10 requests/second." "SEC reserves the right to limit request rates to preserve fair access for
  all users." "Please declare your user agent in request headers". On hours: EDGAR accepts filings "Monday through
  Friday, from 6:00 a.m. to 10:00 p.m., ET"; "Some filing submissions that begin after 5:30 p.m. ET will be
  disseminated the next business day". On the independent list: "Indexes incorporating the current business day's
  filings are updated nightly starting about 10:00 p.m., ET", under "/Archives/edgar/daily-index".
- [W4] https://www.sec.gov/about/privacy-information ("Nov. 29, 2023"): "If a user or application submits more than
  10 requests per second, further requests from the IP address(es) may be limited for a brief period. Once the
  rate of requests has dropped below the threshold for 10 minutes, the user may resume accessing content on
  SEC.gov."
- [W1] https://www.sec.gov/search-filings/edgar-application-programming-interfaces: "Automated access must comply
  with SEC.gov's Privacy and Security Policy"; "The JSON structures are updated throughout the day, in real time,
  as submissions are disseminated."; "data.sec.gov does not support Cross Origin Resource Scripting (CORS)."
- [W5] https://www.sec.gov/about/webmaster-frequently-asked-questions ("Aug. 23, 2024"): "We allow scripted access
  to sec.gov content"; "Note that our current maximum access rate is 10 requests per second."; "We do not offer
  technical support to programmatically download filings."

How the design meets it: a declared client with a contact; 12% of the rate; one request at a time; a stop, not a
workaround, on any refusal (2.7). Where it does not meet it well: "downloading only what you need". Each request
fetches a company's whole recent history, at least 1,000 filings, about 35,400 times a day, to find a few tens of
new ones (2.6); rev 1 called that "one small file per company", which was wrong. The lighter design is measured in
step 2 and put to the owner in question 2. What the pages do not say, and so is not known: which status a
throttled client gets, how long a 403 lasts, and whether the limit is counted per declared client or only per IP
address. The pages speak of limiting and blocking "IP addresses" [W2, W4], and the bot does not own its egress
address (2.4), so "blocks seen" is a number about the network path as well as about the source.

## 7. Tests

All in `tests/test_sec_feed.py`, run by `python3 -m unittest discover -s tests`. No test reaches the network, the
live `state/` or a real address.

### 7.1 The harness (reused, not rebuilt)
- `tests/helpers/no_phone.py` [SP 2] is imported first by the new module, as the supervisor's plan requires of
  every new test module; child processes get `no_phone.clean_env()`, which carries no `AITRADER_*` variable and no
  proxy variable.
- `tests/helpers/no_sec.py` (new, about 20 lines, the shape of the trading room's `no_dash.py` [TP 3]): imports
  `no_phone` first; removes `AITRADER_SEC_CONTACT` from the test process's environment at import (`no_phone` pops
  only the three phone variables in-process [SP 2]); replaces the one network seam, `aitrader.sec._get`, with a
  function that records the call and raises; its `Case` class fails any test that tripped it, even when the feed's
  own try/except swallowed the error. One test proves that an unstubbed call raises.
- A second fence that does not depend on a stub: the config every test uses sets every URL of the `sec` block to
  `127.0.0.1` on a closed port and `sec.allowed_hosts` to that host, so a seam that was missed still cannot reach
  the SEC. This fence alone is not enough for a child process: 7.2 requires the code's fallbacks to equal
  `config.json`, so the fallbacks ARE the real SEC addresses, and a test config that lacks a key would send a
  child's request, sentinel and all, to the SEC. Hence the third fence.
- A third fence, for every process a test starts: `tests/helpers/sec_child.py --state-dir DIR --config FILE
  [sec-feed options]`, in the order of the trading room's `dash_child.py` [TP 9]: (1) `ai-trader/` and
  `ai-trader/tests/` at the front of `sys.path`; (2) `journal.STATE` pointed at DIR, and the two git listings of
  `--leak-check` (7.3) replaced by a listing of the files under DIR, as `dash_child.py` replaces the publisher's
  git look-ups before its tripwire [TP 9]; (3) the tripwire of `tests/helpers/engine_child.py`, by its name
  `tripwire(sent_file)` [SP 3; TP 9], writing to `DIR/child.tripwire`:
  a call to any host but the literal 127.0.0.1, or a `git` or `claude` child, ends the process with 97; (4)
  `sys.exit(aitrader.__main__.main(["sec-feed", *options]))`. Rev 1 said the tripwire "serves the engine only";
  the trading-room plan already reuses it for a child that is not the engine, and so does this. The child classes
  stand on the supervisor's `Procs` (`import test_supervise as ts`, `class SecProcs(ts.Procs)`, as `DashProcs`
  does [TP 9]) and fail any test that left a tripwire file. Children get `no_phone.clean_env()` plus the sentinel.
- Loops that a test starts get `--until 24:00`, which never comes, and end by their `--supervised` pid or are
  killed at `tearDown`; or the test uses `--once`. Never "a minute ahead": that breaks in the last minute of the
  New York day, the fault the trader session already logged for old tests [C BUILD_CLAIMS.md, Waiting 2; TP Global
  Constraints].
- The wire class, the only real HTTP in the suite: a stand-in server on the literal host 127.0.0.1, port 0, in a
  thread, that the test starts (the `Row` pattern of [TP 9]: scripted answers, and `.seen` holding every request's
  path, headers and body; the supervisor's `http_stub.py` [S 11.1] is used instead if it can script a redirect, a
  gzip body and a slow body, and no third stub is written). With `allowed_hosts` = ["127.0.0.1"] the REAL
  `aitrader.sec._get` runs against it, in a child through `sec_child.py`. Everything else in the suite replaces
  `_get` and so proves the caller, not `_get`; the wire class is what proves `_get` (cases in 7.2).
- Fixtures in `tests/fixtures/sec/`: the pack's `submissions-CIK0000320193.json`, `submissions-CIK0000021344.json`
  and `company_tickers.json`, unchanged [F]; and files made by hand for the cases below.
- The contact in tests is a sentinel made at run time from random letters, with a domain under the reserved
  `invalid` top-level name. No fixed address appears in any test file or fixture; a test scans `tests/` for an
  address-shaped string and allows none.

### 7.2 Each failure mode, pinned
| Case | Expected |
|------|----------|
| the two pack fixtures | every filing parsed; the 8-K rows carry items ["2.02", "9.01"] and `important` true, the 8-K/A carries ["5.02"]; classes as 4.2 |
| first sight of a company | one `primed` row listing {accession, filed} inside the window; no filing row; a company with nothing in the window gets a prime row with an empty list |
| the same file again | nothing written (and the body is not parsed twice) |
| the file with one accession added, previous good poll 60 s earlier | one row, `kind` "fresh", `prev_poll` set |
| the same, previous good poll 10 minutes earlier, or none in this process and none in the heartbeat's `polls` | `kind` "catchup" |
| restart: an empty process over an existing journal | the seen set is rebuilt; nothing is logged twice |
| a company whose only rows are a prime row 30 days old; the feed starts and the reply holds a filing of 3 days ago | NOT primed again: one `catchup` row for that filing |
| a filing older than `seen_keep_days` appears | no row |
| arrays of different lengths; no `items` array; a 6-K; an unknown form | no crash; `items` empty; class `event` / `other` |
| the report, clock "utc", on rows whose stamp is: inside the poll gap; 18,000 s off on a winter date and 14,400 s off on a summer date; 2 hours before `prev_poll`; after `at` | `delay_why` "ok" / "et_clock" (both dates, by `zoneinfo`) / "late_publish" (and the row is in "late") / "negative" |
| the report with `accept_clock` "unknown" | `delay_s`, late and fresh share print "not calibrated"; lead numbers print as usual |
| a year of made-up stamps, once all inside 06:00-22:00 New York as UTC and once as New York time | the history file's outside-hours counts are 0 under the right reading and large under the other, in both cases |
| the reply's `tickers` lacks the universe ticker; a 404 | `map_mismatch`; one error row; the company left out after a 404 |
| five starts in one day with a ticker the map lacks; a 404 with `tried_at` two days old | one map request at most, then none; one map request |
| a 403 on the map; then a 403 on a company | `map_403`, no request to that host until the next day, polling goes on; then the 3,600 s block |
| a ticker spelled with "-" in the universe and "." (and "-") in the map | matched |
| timeout; 500; 5 failures in a row | the company skipped; the sweep period doubles, capped at 600; back to 60 after a success |
| an HTML page with status 200, three companies in a row; cut JSON | `bad_body`; the 429 rule |
| three companies in a row over `max_body_bytes`; one over `max_wire_bytes` | `too_big` each; NO block; the other 71 are polled; nothing oversized is parsed |
| `megabytes_today` after replies whose wire size and decoded size differ | it is the sum of the wire sizes |
| 429 with no `Retry-After`, with seconds, with an HTTP date, with a value of 10 days, with rubbish; 403; a second block the same day | no request for 600 s (or longer), then half pace; never later than the start of the next New York day; rubbish read as absent; none for 3,600 s; none until the next day. All on a fake clock |
| a 429, and the process is killed at once (before any sweep ends); a new process starts | the heartbeat already holds `blocked_until`; the new process, and `--once`, `--map` and `--dry-run`, send nothing until then |
| a 302 to another host (the seam) | not followed; the seam is called once; failure `redirect` |
| WIRE: a 302 from the stub to a second stub on another port | the second stub's `.seen` is empty; failure `redirect` |
| WIRE: a host not in `allowed_hosts` | no connection is opened |
| WIRE: a gzip body of a few KB that decodes past `max_body_bytes` | cut while streaming; `too_big`; resident memory of the child stays under a stated bound |
| WIRE: a body sent one byte a second | ended at `request_deadline_seconds`; failure `timeout`; the watchdog does not fire |
| WIRE: a reply that echoes the request's User-Agent in its body and in a malformed header | the sentinel is in no file under the state directory and not in stdout or stderr (7.3) |
| a reply with an `ETag`, then a 304 | the next request carries `If-None-Match`; the 304 counts as answered; no row |
| the pacer on a fake clock: 74 companies; 500 companies; a 30 s stall in the middle | 60 s sweep at 0.81 s gaps; the gap stays 0.5 s and the sweep grows to 250 s; no burst after the stall. Never two requests in flight |
| `max_daily_megabytes` crossed | polling stops until the next New York day; the health row says so |
| no contact; a contact with a space, with a line break, with two "@", with "example" | no call to the seam; one `not_configured` row per day; exit 78; the row and the output say only "missing" or "malformed" |
| no contact; a contact with a character outside ASCII | as above, "malformed"; no exception text anywhere |
| a second feed while the first holds the lock for good; a second feed while the first is ending | exit 3 after `lock_wait_seconds`, with the holder's pid; the second takes the lock within `lock_wait_seconds` and polls |
| `--once`, `--map`, `--dry-run` beside a live loop | each leaves with 0 and sends nothing |
| one request the seam holds open past `hang_seconds` (the deadline lives inside the real `_get`, which the seam replaces, so this is the case "the deadline itself failed") | exit 4 and a free lock |
| a 600 s back-off, a 3,600 s block, the megabytes stop, a day-long idle, each longer than `hang_seconds` | the watchdog does not fire; the loop is alive at the end |
| `--supervised` with a pid that is gone: in the pacing gap; during a 403 block; during the day-long idle | the loop ends with 0 within `sleep_slice_seconds`; the lock is free |
| WIRE: `--supervised` with a pid that goes while the real `_get` reads a body the stub sends one byte a second | the request ends at `request_deadline_seconds`, the loop ends with 0 within one slice after it, the watchdog does not fire, the lock is free |
| the launch line: `launch_prefix` with the feed's guard and log, alone and after the publisher's list, under bash and sh, with `sleep` in the loop's place | only the launcher has the launcher's pipe (the line returns when the launcher ends, not when the side process does); with the variable unset nothing starts and the parent still starts; the parent's working folder is `ai-trader/` |
| the nightly index: a fixture index with 5 rows of polled CIKs, 4 of them in the journal | one `index_check` row, `missing` holds the fifth; a second start the same day makes no request |
| the index days: last check 2026-11-10, a start on 2026-11-12; last check 2026-11-13, two starts on 2026-11-18; `index_enabled` false; `index_url` null | no request (2026-11-11 is in `edgar_closed`); one request for 2026-11-16 at the first start and one for 2026-11-17 at the second; no request; no request |
| `lock_wait_seconds` against `request_deadline_seconds` + 2 x `sleep_slice_seconds`; `hang_seconds` against `request_deadline_seconds` | the first is at least the sum; the second is larger |
| the two item tables and the keyword table against the vendored file | equal |
| every key the code reads from `sec` with a fallback is in `config.json` with the same value as the fallback; the seven keys that a measurement or a dated list sets (`accept_clock`, `index_url`, `index_enabled`, `edgar_closed`, `max_wire_bytes`, `max_body_bytes`, `max_daily_megabytes`) have NO fallback in code | equal (the pattern of `test_the_fallbacks_in_the_code_say_what_config_says` [C BUILD_CLAIMS.md, Waiting 1]); a config that lacks one of the seven makes every form that can send a request print one line and exit 78, sending nothing |
| `import aitrader.secfeed` | `aitrader.news_live`, `aitrader.broker`, `aitrader.notify`, `aitrader.strategy` and `aitrader.backtest` are not loaded. `aitrader.ownerlines` and `aitrader.deadman` may be: `supervise`, imported for `take_lock`, loads them [SP 13]. A search of `sec.py` and `secfeed.py` finds no use of `ownerlines`, `deadman` or `Sender` |
| `sec-report` on a fixture set (a filings journal, a seen log, a scores journal, an engine health log, an uptime log) with known answers | the exact strict and loose `lead_s`, taken from the seen row's `first_seen` (the fixture's `logged_at` differs by minutes and must not show); one negative lead; one unmatched filing; one stale-only window; a 15:55 filing with no Yahoo row and one whose Yahoo row comes after an engine break, both `censored` with T and in neither `lead_s` nor `unmatched`; a filing at 08:30, `censored` (first hour); the poll handicap line |
| the same, with one handover at 10:48 whose `up` row comes 50 s after its planned `exit`; again 200 s after; again with no uptime log; again with a `hang` row in the hole. Each time a 10:30 filing whose candidate is first seen at 11:00, and a 10:47 filing whose candidate is first seen 20 s after the `up` row | the first: bridged, both `matched`, the second lead marked `across_handover`; the other three: not bridged, both `censored` |
| the engine pass of 3.4 on fixture health rows: a clean day; each of the three numbers failing alone; a day with no rows; a day whose stop gaps are all null; rows outside the session | pass; that one number named; `no_rows`; pass, the stop gap noted as not compared; not counted |
| the test of the lead on made-up leads: 29 rows; 30 rows all positive on 12 days; 30 rows, half negative; the same input twice | "no test"; both parts pass; neither passes; identical output (the seed) |
| fresh share on a fixture with filings stamped before the feed's start, during it and after its end | only those stamped inside an up stretch are in the denominator |

### 7.3 The privacy test
One sentinel contact, then every path that could leak it, then a scan.
- In-process: the loop runs over the fixtures with the sentinel in the environment handed to `user_agent`, and the
  seam is scripted to fail in each way of 2.7, including an exception whose text contains the sentinel and a reply
  whose headers and body echo the request's User-Agent (a server error page can). After each: no journal row, no
  heartbeat, no health row, no error row and no captured log line contains the sentinel, its part before the "@" or
  its domain. The sentinel's parts are random letters and a domain under `invalid` (7.1), so each of the three is
  unique to it and a hit is never a false alarm; the real value is searched differently (below).
- As a child process over the network path, which is the path that matters: the wire class of 7.1, the real
  `_get` against the 127.0.0.1 stub, with the sentinel in the child's environment, through each wire case of 7.2
  (the echo in a body and in a malformed header, the redirect, the oversized body, the slow body, a reset
  connection). Then stdout, stderr and every byte of every file under the state directory are scanned for the
  same three strings. Rev 1 ran this scan only under `--offline`, where no network object is built and the
  sentinel never reaches a header: that scan proved nothing about the path that carries the address.
- The same scan for `sec-feed --once --offline DIR` (once normally, once with a broken fixture that makes it
  raise), `--status`, `--map --offline` and `--leak-check`.
- The header itself: the stub's `.seen` shows the sentinel in the `User-Agent` header and nowhere else (not in the
  path, not in another header), and the second stub of the redirect case saw no request at all.
- The process's argument list never holds it: the test reads the child's own `/proc/<pid>/cmdline`.
- A static check: `aitrader/sec.py` and `aitrader/secfeed.py` contain no `str(e)`, `repr(e)`, `%s` of an exception
  or `traceback` call on a network path (a search the test runs), and no `print` of a headers object. An uncaught
  exception in the loop prints its class name only.
- A repository check, narrowed. Rev 1 asked that no tracked file under `ai-trader/` hold an address-shaped string
  except in `vendor/`. That fails on the tree as it stands (research notes quote sample addresses; five rows of
  `state/news_scores.jsonl` carry one inside a headline's link) and it would hang the unit suite, which is the
  gate for every change including an urgent defect fix, on whatever text Yahoo sends next. The check covers what
  the bot treats as code or instructions, and the feed's own outputs: `aitrader/`, `tests/`, `scripts/`,
  `skills/`, `agents/`, `dashboard/`, `config.json` and `state/sec_*`. None of them may hold an address-shaped
  string, and `config.json` no longer has `sec_user_agent`.
- The real value, which no suite can know: `python3 -m aitrader sec-feed --leak-check`. It reads the variable into
  memory and searches, case-insensitively, for the WHOLE value only, in: every file git tracks or would add
  (`git ls-files --cached --others --exclude-standard`: the tracked files and every untracked file that is not
  ignored, so the new state files that `--map` and `--once --history` have just written in step 2, and any new
  `state/` or `reports/` file a close slot's state commit is about to add, are read too); every file under `logs/`
  and `.cache/`; `state/sec_feed.json`; and the messages of the commits not yet pushed
  (`git log --format=%B @{u}..HEAD`, or the last commit's message when the branch has no upstream). Those two
  read-only listings are the only git calls in the feed's code (a seam in tests); the loop makes none. It does not
  search the value's part before the "@" or its domain, as the suite does for its random sentinel: a common mail
  domain is already in tracked files (`yahoo.com` in `aitrader/news_live.py:101` and `aitrader/data.py:30`), and
  a local part that is a person's name would be too, so those searches would stop the close slot's state commit
  every day on a false alarm. It prints only `leak-check: {n} files hold the contact` and the NAMES of those
  files, never a line of them. Exit 0 when n is 0, 1 otherwise, 78 with no variable. The trader session runs it
  once step 1 has landed (the command does not exist before), after step 2, and in the close slot before its state commit (one line in `close.md`,
  with the feed's other line); a count above 0 stops that commit and is told to the owner in chat.
- What neither check can stop, and a rule covers instead: the main session has the value in its chat when the
  owner gives it. Its session log for step 0 names the variable only, and before the push of that turn it reads
  `git diff --cached` for any "@" (section 10, step 0).

## 8. Config, files, the owner's lines

### 8.1 `config.json` (rule 5)
The top-level key `sec_user_agent` [C config.json:239] is removed. Nothing reads it: a search of `aitrader/`,
`tests/` and `skills/` finds no reader, and `data.sec_recent_form4` takes its User-Agent as an argument and has no
caller [C data.py:304-308]. A dummy address in a public file is also what the owner's decision rules out [K 65]. In
its place, a new top-level block `sec`, placed where the old key stood. Its `_note` says: read only by
`aitrader/sec.py` and `aitrader/secfeed.py`; log-only; changes no trade; the contact address is never written
here.

| Key | Value | Key | Value |
|-----|-------|-----|-------|
| `contact_env` | "AITRADER_SEC_CONTACT" | `agent_name` | "ai-trader-research-bot" |
| `submissions_url` | "https://data.sec.gov/submissions/CIK{cik}.json" | `tickers_url` | "https://www.sec.gov/files/company_tickers.json" |
| `allowed_hosts` | ["data.sec.gov", "www.sec.gov"] | `accept_clock` | "unknown" (then "utc" or "et", 4.4) |
| `index_url` | a template for one day's nightly index under "https://www.sec.gov/Archives/edgar/daily-index/", copied by the plan's first task from the SEC's documentation of the index; null when that documentation does not name the file (then no index request is ever made) | `atom_url` | "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&owner=include&count=100&output=atom": the address of [C data.py:304-305] without its `type` filter, asked once in step 2 |
| `index_enabled` | false; true only by step 2's config commit (5.2) | `edgar_closed` | the dates of 2026 and 2027 on which EDGAR takes no filings (federal holidays), with their source, written by the plan's first task (5.2) |
| `sweep_seconds` | 60 | `min_request_gap_seconds` | 0.5 |
| `connect_timeout_seconds` | 5 | `read_timeout_seconds` | 10 |
| `request_deadline_seconds` | 20 | `lock_wait_seconds` | 25 |
| `max_wire_bytes` | 5000000, wire; a placeholder until step 2 | `max_body_bytes` | 50000000, decoded; a placeholder until step 2 |
| `max_daily_megabytes` | 1500, wire; a placeholder until step 2 | `clock_tolerance_seconds` | 120 |
| `backoff_after_fails` | 5 | `backoff_max_seconds` | 600 |
| `bad_body_block_after` | 3 | `block_429_seconds` | 600 |
| `block_403_seconds` | 3600 | `blocks_per_day_max` | 2 |
| `slow_factor_after_block` | 2 | `seen_keep_days` | 14 |
| `fresh_gap_seconds` | 150 | `publish_slack_seconds` | 120 |
| `cik_map_refresh_days` | 7 | `text_max_chars` | 120 |
| `health_log_seconds` | 300 | `hang_seconds` | 180 |
| `sleep_slice_seconds` | 1 | `nice` | 10 |
| `oom_score_adj` | 500 | `forms` | the lists of 4.2, by class |
| `match.before_seconds` | 3600 | `match.after_seconds` | 14400 |
| `match.engine_gap_seconds` | 120 | `match.item_classes` | the map of 5.1 |
| `report.min_events` | 30 | `report.max_error_rate` | 0.01 |
| `report.min_delay_ok_share` | 0.9 | `report.days` | 14 |
| `report.sign_alpha` | 0.05 | `report.boot_level` | 0.95 |
| `report.boot_draws` | 2000 | `report.boot_seed` | 0 |
| `report.pass_step_ratio` | 1.2 (the trading room's value [TP 11]) | | |

Gone since rev 1: `until_ny` (the launch line takes `supervisor.until_ny`, as the publisher's does; a second hour
in a second block could only disagree with it) and `report.min_fresh_share` (5.3). The three placeholders are set
from step 2's measured maxima (and `max_body_bytes` with step 2's peak memory in view, 3.4), with `accept_clock`
and `index_enabled`, in one config commit through the gate of section 9, before step 3. It is a config-only
commit: the seven keys that a measurement or a dated list sets (`accept_clock`, `index_url`, `index_enabled`,
`edgar_closed` and the three caps) have no fallback in the code, so `aitrader/sec.py` does not change with them.
A config that lacks one of the seven makes every form that can send a request print one line and exit 78, so a
missing safety cap never becomes a silent default (7.2).

`data.sec_recent_form4` itself stays as it is: `aitrader/data.py` is on the list of files the time machine loads,
and deleting a dead function is not worth a sweep. It goes to the backlog (section 13): when backlog item 3 is
built, or when `data.py` is next opened under its own gate, the function moves behind `sec.user_agent()` and the
pacer, or is deleted. Until then it stays uncalled; a test asserts that nothing under `aitrader/` calls it.

### 8.2 Files
| File | Git | Writer |
|------|-----|--------|
| `state/sec_filings.jsonl` | tracked, append-only | the feed |
| `state/sec_health.jsonl` | tracked, append-only | the feed, one row per `health_log_seconds` |
| `state/sec_errors.jsonl` | tracked, append-only | the feed, one row per place, kind and New York day (the engine's `error_once` pattern [C news_live.py:78-90]) |
| `state/sec_ciks.json` | tracked | `sec-feed --map` |
| `state/sec_history.json` | tracked | `sec-feed --once --history` (4.5), in step 2 |
| `state/sec_feed.json`, `state/sec_feed.lock` | ignored (two lines in `.gitignore`) | the feed |
| `.cache/sec_feed.log` | ignored already [C .gitignore:1] | the launch line |

The tracked files reach git with the state commits the scheduled turns already make [S 4.6]; the feed's loop
never runs git, and no form of the command writes to git (`--leak-check` only lists, 7.3). Size: a filing row
is about 450 bytes and a health row about 450 bytes, about 96 a day. How many filing rows a day is NOT known: rev 1 said "some tens", which ignores that JPM, BAC, GS and MS may each file offering
documents (424B2, FWP) in large numbers [C config.json:100-105]. `sec_history.json` counts filings a day by class
and by company (4.5); if `offering` rows dominate, question 3 has an option that logs that class as one daily
count per company and not one row per filing. Until step 2 has that count, the loop is not started (step 3
follows step 2).

A health row: `at`, `window_s`, `sweeps`, `sweep_s_median`, `sweep_s_max`, `requests`, `ok`, `not_modified`,
`failed` (by kind: timeout, http_5xx, http_403, http_429, map_403, bad_body, too_big, redirect, other),
`request_s_median`, `request_s_max`, `bytes` (wire), `decoded_bytes`, `megabytes_today` (wire), `companies`,
`mapped`, `answered_min`, `poll_gap_max_s` (the longest time one company went without a good poll), `new` (by
class), `fresh`, `catchup`, `map_mismatch`, `too_big` (tickers), `skew_s_max`, `age_s_max`, `backoff_s`, `blocked`
(null, "429", "403" or "day"). These are sums over all companies. What one company did over a day is kept
nowhere a report can read: a filing row's `prev_poll` gives one poll time only when that poll found a new filing,
and the heartbeat's `polls` holds only each company's last poll and is not in git (3.3). No number of section 5
needs it.

### 8.3 Lines to the owner
- No phone line, ever, from this feed. It is log-only; a stopped feed puts no money at risk, and the supervisor's
  cap of 6 lines an hour [S 8] is for things that do. So it adds nothing to the table of owner lines [SP 2],
  imports no `notify` and calls no sender. `supervise`, which it imports for `take_lock`, itself loads `ownerlines`
  and `deadman` with its `Sender` [SP 13]; the feed uses neither, and the import case of 7.2 checks both halves.
- One sentence in the daily summary, written by the close slot from `sec-feed --status` (a line added to
  `skills/trader/slots/close.md` once [SP 18-19] have put the slot files in git):
  `מקור SEC (רישום בלבד): {n} דיווחים חדשים היום, מהם {k} אירועים (8-K/6-K). רץ {p}% מהשעות. כסף נייר`
  and, when it applies, one of: `מקור SEC נחסם היום ({status}) ונעצר עד מחר. לא ידוע אם בגללנו. לא נוגע למסחר. כסף נייר` /
  `מקור SEC לא רץ היום: אין כתובת קשר בסביבה. כסף נייר` / `מקור SEC: ל-{names} אין מספר חברה ב-SEC. כסף נייר` /
  `מקור SEC: הקובץ של {names} גדול מהתקרה ולא נקרא. כסף נייר` /
  `מקור SEC: {m} דיווחים מיום {day} לא הופיעו אצלנו בכלל. כסף נייר`.
- A block on two days in a row, or a feed that did not run for two sessions, is a backlog defect (Basic law 2,
  item 2) and is said to him in chat by the session that sees it.
- Health rows on the dashboard ("הנתיב החי" [T 5]) are not built here: backlog, after the trading room's page.

### 8.4 The SKILL paragraph (its content, so that no one has to guess it)
One paragraph in `skills/trader/SKILL.md`, in Hebrew like the rest of the file, beside the publisher's section 3ג
[TP 15], added with the slot lines (step 3). It says:
- what `sec-feed` is: it asks the SEC once a minute about the bot's companies and writes what it saw; it cannot
  trade and changes no score; paper money;
- the address is never shown. No session prints the environment: not `env`, not `printenv` without a name and not
  with this name, not `set`, not `export -p`, not `ps e` or `ps eww`, not `cat /proc/<pid>/environ`. A transcript
  becomes a session log, and a log is pushed to a public repository;
- the only check is `[ -n "$AITRADER_SEC_CONTACT" ] && echo set || echo missing`;
- the value is never copied: not into another variable (`SEC_USER_AGENT` of the installed `trader-news` and
  `trader-analyst` skills included), not into a file, a command line, a prompt or a message. Those skills are not
  run against the SEC from the trader session; every SEC call of the bot goes through `aitrader/sec.py`;
- no session calls the SEC by hand (`curl`, a fetch tool) "to check": it would be a second requester on the same
  address, outside the pacer;
- the feed's output is in `.cache/sec_feed.log`; its state is `python3 -m aitrader sec-feed --status`;
- exit codes and what the session does: 0, 3 and 78 nothing; 4 is told at the next slot's summary;
- a block: nothing is tried around it; it is in the daily line; two days in a row go to the owner in chat;
- `sec-feed --leak-check` in the close slot before the state commit; a count above 0 stops the commit.

## 9. Rule 4 for this change

- It touches no file the time machine loads. New: `aitrader/sec.py`, `aitrader/secfeed.py`, the test files,
  `tests/helpers/no_sec.py` and `sec_child.py`, the fixtures. Edited: `aitrader/__main__.py` (two commands
  registered), `config.json` (the top-level `sec` block in, the top-level `sec_user_agent` out; no key of `risk`,
  `signals` or `costs`; later the three measured caps, `accept_clock` and `index_enabled`), `.gitignore`,
  `THIRD_PARTY.md`, and later the slot file lines, `launch_prefix` and its test, and the SKILL paragraph of 8.4.
  Not edited:
  `backtest.py`, `strategy.py`, `signals.py`, `learn.py`, `metrics.py` (the test of the lead lives in
  `secfeed.py`, 5.3), `broker.py`, `data.py`, `news_live.py`, `journal.py`, `notify.py`, `supervise.py` (its
  `take_lock` is imported, not changed).
- So, by the owner's third ruling of 2026-11-11 (`CLAUDE.md`, hard rule 4): no sweep. The gate is the
  `quant-critic` agent on the diff and `python3 -m unittest discover -s tests` printing OK (the golden stock test is
  in it and must not move). The critic's verdict must say, in words, that the diff touches no file on the list, and
  must confirm by search that no trading path reads `sec.*` or any `state/sec_*` file and that nothing read
  `sec_user_agent`.
- It changes no trading rule, so the second ruling's forward measurement is not owed. The feed is itself a forward
  measurement; what the journals show before (nothing: no SEC row exists) and what will be read after are written
  in section 5.
- One independent adversarial review of the unit before it lands, with the privacy test of 7.3 as its first target.
- If a later task of the plan finds it must touch a listed file after all (it should not), that task stops and gets
  the sweep before and after, as the rule says.

## 10. Rollout (each step leaves everything working if the next never comes)

| Step | Lands | Proof | Undo |
|------|-------|-------|------|
| 0 | The owner's address in the environment variable, by an approval card of the main session. No file changes. See "Step 0" below | the next trading morning, a one-time scheduled task bound to the trader session answers "set" (the value is never printed); then `sec-feed --leak-check` prints 0 once step 1 has landed | he removes the variable; the feed then exits 78 |
| 1 | The code, the config block, the tests, through the gate of section 9, after the close. Nothing starts it. It waits for S-Task 20's landing and for the tripwire's name on the live branch (section 11) | the suite OK; the privacy test with its wire cases; the critic's PASS with its sentence about the list | revert the commit |
| 2 | First contact with the SEC, in the trader session, after the close, by two one-time scheduled tasks. See "Step 2" below | 74 of 74 tickers mapped, or the missing ones named; 74 answered; no 403, no 429; `state/sec_history.json` with everything 4.5 lists: wire and decoded size and rows for each company, the headers, the stamps under both clocks, filings a day by class and company, the projection of 5.3, the Atom request, the one index request (or "not made"), peak memory and CPU; prime rows only on the first run and only new filings on the second; `--leak-check` 0. Then one config-only commit through the gate (8.1): `accept_clock`, the three caps, and `index_enabled` true only when the index request answered 200 with a file whose rows were read and whose rows of the 74 CIKs were counted; and the numbers go into this spec's evidence | nothing runs afterwards; the files stay |
| 3 | The feed's list in the launch prefix (3.2), the close-slot lines and the SKILL paragraph (8.4), by a forward edit of the slot files. Waits for [SP 20], [TP 15-16] and step 2's config commit | [TP 16]'s two-run launch-line drill with the feed in its child helper (the line returns when the launcher ends; the parent starts in `ai-trader/`; with the variable unset the parent still starts). Then one full session: `answered_min` 74, failed requests under 1%, no block seen, no `too_big`, `poll_gap_max_s` at most 150 outside handovers, a feed running in every leg after each handover (no exit 3), megabytes as measured in step 2; target 6 by the rule of 3.4; one `fresh` row checked by hand against the SEC's own page for that filing | remove the feed's list from the prefix (a forward edit; the publisher's list is not touched) |
| 4 | Ten sessions, then the report of 5.4 and one question to the owner | the report file, validated | - |
| 5 | When the supervisor's side-children amendment has landed: the prefix part goes, the parent starts the feed | one session as in step 3; a kill of the feed alone is restarted and the engine is not touched | the prefix part back |

Steps 0 and 2 need the address. Step 1 does not, and can land while he opens it.

Who can do what, as in the two other plans [SP Global Constraints; TP Global Constraints]: the main session is the
owner's chat; it shows cards and creates scheduled tasks on his word, and has no shell in the trader session's
machine. The trader session acts only in scheduled turns. So a proof about the trader session is read in one of
three ways, and each step says which: the pushed state; the trader session's transcript (`list_events`); a
one-time scheduled task bound to the trader session, created on the owner's word, whose prompt is one exact
command. Rev 1 said "by the trader session, after the close" and named none.

Step 0, in order:
1. Before any card: `get_session` on the trader session for its environment, then `get_environment` on that
   environment. Go on only when the answer says it is the environment the main session itself runs in (the card
   edits only the caller's own environment [TP 18]) AND that it is personal. If it is another environment, or one
   shared with an organization (its variables are shown to every member), stop and ask the owner one question:
   move the main chat to the trader's environment and continue (recommended), or stop here. No environment id is
   written anywhere.
2. He gives the address once, in chat. The card shows him the exact value. No session repeats it afterwards.
3. The main session's log for that turn names the variable only. Before its push it reads `git diff --cached` and
   pushes only when no line holds an "@" that it did not expect.
4. The next trading morning (a variable reaches a session when it next starts or resumes): a one-time scheduled
   task bound to the trader session, on the owner's word, whose prompt is to run
   `[ -n "$AITRADER_SEC_CONTACT" ] && echo set || echo missing` and answer with the word only; read back with
   `list_events`. "missing": the machine has not been restored since the card; wait a morning.

Step 2, in order, after step 1 has landed and a close has passed:
1. The trader session's checkout must hold the landing. Either its next pushed state commit descends from it
   (`git merge-base --is-ancestor`), or each task's prompt begins with
   `git fetch origin <branch> && git merge --no-edit origin/<branch> && ` [TP 14].
2. Task one, on the owner's word:
   `(cd ai-trader && python3 -m aitrader sec-feed --map; python3 -m aitrader sec-feed --once --history; python3 -m aitrader sec-feed --leak-check)`
   in one subshell, as ONE Bash call that names its timeout (300000 ms: a sweep is 60 s of pacing plus the three
   extra requests, and a call that names no timeout is cut at 2 minutes [TP 25]), answering with the output only.
3. Task two, set at least 10 minutes after task one:
   `(cd ai-trader && python3 -m aitrader sec-feed --once; python3 -m aitrader sec-report --history; python3 -m aitrader sec-feed --leak-check)`,
   the same way. Two tasks, not one call that sleeps ten minutes.
4. Both are read back with `list_events`, and the files (`state/sec_ciks.json`, `sec_history.json`,
   `sec_filings.jsonl`, `sec_health.jsonl`, `sec_errors.jsonl`) from the trader session's next pushed state commit.
5. If the map is refused, or any company answers 403 or 429, the step stops there and is reported; nothing is
   tried under another identity or route. A 403 to the one-off Atom request does not stop the step: it is recorded,
   and question 2's option of the Atom feed as a trigger is then off the table.

## 11. Build claims, order, and where this meets the other two plans

Claims this build needs (`BUILD_CLAIMS.md`, one builder per file): new `aitrader/sec.py`, `aitrader/secfeed.py`,
`tests/test_sec_feed.py`, `tests/helpers/no_sec.py`, `tests/helpers/sec_child.py`, `tests/fixtures/sec/`; edits
to `aitrader/__main__.py`, `config.json`, `.gitignore`, `THIRD_PARTY.md`; later `skills/trader/slots/news-watch.md`,
`skills/trader/slots/close.md`, `skills/trader/SKILL.md`, `tests/test_slot_files.py` and the launch-prefix helper
in `tests/helpers/no_dash.py`. Files it shares with the two open builds, named in its claim line as shared:
`__main__.py`, `config.json`, `.gitignore`, `tests/helpers/`, `skills/trader/SKILL.md` and `skills/trader/slots/`
(the supervisor's claim of 2026-11-11 10:09 [C BUILD_CLAIMS.md]; the trading room's claim [TP 1]), and
`THIRD_PARTY.md`, which the trading room's claim also lists [TP 1] and rev 1 did not name as held.

The queue rule. "Third in the queue" was not a rule: the trading room's claim stays open until its Task 25, weeks
away, and by the claim rule of `CLAUDE.md` step 1 could not land at all while it is open. So the feed joins the
one queue the two other plans already share, on the same terms [TP Global Constraints]:
- Its BUILD tasks are dispatched in the order their imports reach the live branch, which the controller can merge
  (it never merges another plan's work branch). After S-Task 9's landing, which brings `no_phone` [SP 2] and
  `test_supervise.Procs` with `engine_child.py` [SP 3]: the pure parts of `sec.py` (`user_agent`, the pacer,
  `parse_submissions`, `classify`, the item table) with their in-process tests, as the trading room's first task
  waits for the same landing. After S-Task 20's landing, the first that carries `supervise.py` and its
  `take_lock` [SP 10, 20]: the lock, the loop, every form that can send a request, and the report (it reads the
  uptime log with `supervise.read_rows`, 5.1). Once `tripwire(sent_file)` is on the live branch (with S-Task 9 if
  [SP 3] gave the tripwire that name, else with [TP 14]'s landing, which carries [TP 9]; collision 8):
  `sec_child.py`, the wire class and every child test of 7.2 and 7.3. The plan's first task checks each of the
  three by `git grep` on the live branch.
- Its BUILD tasks run one at a time in the same queue as the supervisor's and the trading room's: never two
  builders at once across the three plans.
- They commit on a work branch of their own, in a clone of its own ("the feed clone"), cut from the live branch.
  The work branch is local to that clone and is never pushed; only gated landings reach the live branch.
- Before each dispatch the controller fetches and merges the live branch into the work branch, so the task builds
  on what the other two plans have landed. A conflict in a file the plans share is settled there, by the
  controller, by keeping every plan's lines, and the whole suite runs again; a conflict under `state/` is
  reported, never settled by hand. An implementer never fetches, pulls or merges.
- The feed's claim line is added when its first task is dispatched and says which files it shares and with whom.
- Step 1 of section 10 lands when all of those are committed: so after S-Task 20's landing and after the
  tripwire's name, never after S-Task 9 alone. Step 2 needs nothing more than step 1. Neither needs the slot
  files. The slot-file tasks (step 3: the prefix, `launch_prefix`, `close.md`, the SKILL paragraph) wait further
  for [TP 15-16] and for step 2's config commit.

What it uses from them, and builds no second copy of: the launch and keep-awake (the parent and its watchdog
launch); the side-process start line and its measured shape (`launch_prefix`, the pipe test, the launch-line
drill); "die with the parent" (`--supervised`); the exit codes 3, 4 and 78; the lock helper
(`supervise.take_lock` [SP 10]) and the lock wait; the watchdog that times the work in progress; `no_phone.clean_env()`;
the child tripwire and `Procs`; the stand-in server pattern; the three ways to read a proof about the trader
session; the environment check before a card [TP 18]; the pass rule for the engine's numbers [TP 11] (the rule;
its code stays the publisher's, 3.4); the uptime log and its handover rows [S 4.6], to bridge handovers (5.1);
the slot files in git and the merge-only sync rule [S 4.7]; the state commits that carry its journals; the publisher's
nice and out-of-memory settings; the engine's `error_once` pattern.

Where it collides, each for the controller to settle before the plan is written:
1. The one `&`. [TP 15] writes into SKILL section 3ב that the single exception to "never `&`" is the `&` of the
   dashboard publisher's prefix. The feed adds a second `&` in the same prefix. The sentence must say "the side
   processes of the launch prefix", or the feed's line contradicts the skill.
2. `launch_prefix()` in `tests/helpers/no_dash.py` is defined as "the one shape of the publisher's start line",
   with the publisher's variable and log written into it [TP 10], and `tests/test_slot_files.py` pins the prefix
   by step. The feed needs it with a `guard_var` and a `log` argument whose defaults are the publisher's, `guard`
   kept as a bool so that no call of the publisher changes (3.2), and needs the pinned prefix to be two lists;
   both files are under the trading room's claim, so that edit is a task in the shared queue after [TP 15-16],
   not a second helper.
3. The supervisor amendment. [S 4.2] has one child; [TP 25] hands the supervisor's author an amendment for one
   second child. A third process makes it a list: started with the engine, restarted with back-off, never counted
   in uptime, never a reason to stop or restart the engine, never restarted after exit 78.
4. Hours. The parent launches only between 08:00 and 16:00 New York and ends at 16:05 [S 4.4, 4.5]. A feed under it
   cannot see an after-close filing the same evening, and the engine, which is the only Yahoo poller, stops at the
   same minute: every filing after about 12:05 has its Yahoo window cut short, and one near the close is censored
   (5.1). So is every filing in the hour after the day's first engine start, about 08:07-09:07 (5.1). Wider hours
   for the feed alone would add SEC rows with no Yahoo side at all (question 1).
5. Handovers. Until the long timeout is proven the parent exits four times a day [S 4.5]; each ends the feed too,
   and the next feed waits for the lock (3.3). On the engine's side the match bridges a handover only when the
   uptime log shows the return within the 60 s target (5.1); how often that holds decides how much of each day
   can be compared, and it is not measured yet.
6. The gate. [T 8] says every `config.json` change takes the sweep before and after, and the supervisor's plan
   gates "by the letter" until its question 7 is answered [SP Global Constraints]. Both were written before the
   owner's third ruling of 2026-11-11. This spec follows the ruling (section 9). If those plans still run sweeps
   for their config blocks, the feed's landing should not copy that.
7. Two small test helpers of the same shape (`no_dash.py`, `no_sec.py`), and two child helpers (`dash_child.py`,
   `sec_child.py`). Folding them is a backlog item for when both claims are closed; doing it now would edit a file
   under another claim.
8. The tripwire. [SP 3] may leave it inline in `engine_child.py`; [TP 9] gives it the name `tripwire(sent_file)`
   there "with no change of behaviour". The feed's `sec_child.py` calls it by that name (7.1), so it, and step 1
   with it, waits for whichever of the two tasks reaches the live branch with the name (S-Task 9's landing or
   [TP 14]'s), and adds no tripwire of its own.
9. The close slot. [TP 18] ends each slot with a push by the publisher; the feed adds two lines to `close.md` (the
   daily sentence and `--leak-check` before the state commit). Their order in the file is settled where the slot
   lines are written, by the controller.

## 12. Open owner decisions

Asked one per message, in Hebrew. None is designed in; the last column is what holds until he answers.

| # | Question | Options | Recommended | Until he answers |
|---|----------|---------|-------------|------------------|
| 1 | The feed runs only while the engine runs, about 08:07-16:05 New York. Many results are filed after 16:05 or before 08:00 and would be logged only the next morning, with no speed number. Widen the hours? | א: no, session hours only, and decide after the first sweep shows how many filings of the last year fell outside. ב: an extra evening run to about 20:00 New York (one more tracked command and one more model turn a day; the machine stays awake longer). ג: evening and early morning. In ב and ג the evening rows get the SEC's time only: nobody polls Yahoo then, so they have NO comparison with Yahoo unless the engine's hours are widened too, which is a change to the engine and not part of this spec | א: it costs nothing, the first sweep gives the real share within a day, and wider hours without the engine add no lead number | א |
| 2 | How to ask the SEC? Asked after step 2, with its measured sizes | א: each company's file once a minute (1.2 requests a second, 12% of the SEC's limit; about 35,400 requests a day, each the company's whole recent history; about 0.9 GB a day by estimate). ב: the same every 30 seconds (twice the download). ג: every 2 minutes. ד: the "latest filings" Atom feed as the trigger (one small request a minute for all companies) and each company's file only a few times a day as a check on coverage: by arithmetic 10 to 70 times fewer requests; it is a second design and a new spec section; possible only if step 2 shows `www.sec.gov` accepts the declared client | decided on step 2's numbers. If the Atom request is accepted and fresh: ד, because the SEC asks to download only what is needed. If not: א | א is what is built first; nothing loops before he answers |
| 3 | What to log? | א: every filing of the 74 companies (insider forms and quarterly reports too; no extra request), and compare only the 8-K/6-K with Yahoo. ב: 8-K/6-K only. ג: as א, but the `offering` class as one count a day for each company, not one row per filing (for the case that the four banks file such documents by the thousand; step 2 counts it) | א, or ג if step 2 shows offering rows are most of the journal | א |
| 4 | To compare fairly, the engine would also have to keep the title of Yahoo headlines it saw too late to score. That is one more field in the engine's journal, in a public repository, and Yahoo's terms were never read | א: add it now. ב: not until the terms are read or the state moves to a private repository; meanwhile the report says how many such headlines it could not compare | ב | ב |
| 5 | If the SEC refuses the bot even with the declared address | א: the feed stops and you are told; nothing is tried around it. ב: the same, and you write to the SEC's webmaster yourself from the bot's address. Note on ב: the SEC asks such a letter to "include your IP address" [W5], and the address the bot goes out from belongs to the cloud provider, may be shared and may change; you cannot name it with certainty | א first; ב only if it repeats | א |
| 6 | Where does the variable live? | א: in the same cloud environment as the ntfy topic, which serves all your cloud sessions. ב: in an environment for the trader session only. Either way it must be a personal environment, not one shared with an organization, and the one the trader session really runs in (step 0 checks both before the card) | the same answer you give to the supervisor's question 11, so the trader has one environment | no card is shown |

## 13. Honest limits, facts not confirmed, backlog

Honest limits:
- It is a poll once a minute, on a machine that pauses and under a parent that is relaunched. "To the second" does
  not exist here. Outside about 08:07-16:05 New York on session days it sees nothing until the next start, and the
  SEC also takes filings on some days the market is closed.
- Knowing sooner is not earning. The news rule has one round trip, a loss, and the one large study found no
  significant return in minutes 1-15 after an intraday headline [R 160, 169]. This feed measures time and coverage
  and nothing else.
- The company's own press release often reaches the wires before its 8-K reaches the SEC. The lead over Yahoo can
  be negative, and the report must show it when it is.
- The comparison with Yahoo is partly blind: strict matching sees only headlines the engine scored, keyword
  matching is crude, and 6-K and "other events" filings can only be matched loosely. The sample will be small: a
  plausible 2 to 5 strict matches in the first two weeks when the engine's handovers are bridged, fewer when they
  are not, 30 in months (5.3).
- The comparison exists only while the engine polls Yahoo. Filings near or after the close, filings in the hour
  after the day's first engine start (about 08:07-09:07), and filings around an engine break are censored, and
  censoring makes the matched median too low (5.1). A planned handover is not a break when the supervisor's uptime
  log shows the engine back within its 60 s target; a handover that misses the target is one, and how often that
  happens is not measured yet. A bridged handover can make a lead too high by up to about 80 s; those leads are
  marked. The comparison also starts about 20 s in Yahoo's favour, because the two are polled at different paces.
- Missed filings are not measured until the nightly index is proven in step 2, and not at all if the SEC's
  documentation does not name the index file. Before that the report says "not measured"; after it, a filing that
  is in the index and not in the journal is counted at the next start, also for a day on which the feed did not
  run. A filing the index itself lacks is seen by nothing.
- The speed number against the SEC's own stamp measures "accepted -> seen", not "shown -> seen", and is printed
  only after the stamp's clock is decided from a year of stamps (4.4). If neither reading is clean it is never
  printed.
- The SEC limits by IP address, and the bot goes out through an address it does not own and may share. A block
  may be someone else's doing, and the feed's own requests count against whoever shares the address. Blocks are
  reported as seen, with the class of the reply, and cannot always be attributed.
- The load is not small: every company's whole recent history, once a minute (2.6). The lighter design is
  question 2.
- A replaced machine loses the rows since the last state commit; they return as catch-up rows. A prime row lost
  that way is primed again, and what that company filed in between is not counted.
- A feed that ends itself stays down until the parent's next launch (3.2).
- The address is readable by every process of the trader session, the engine's scorer child included, and it
  crosses the session's outbound proxy inside the request header. It is in the chat where he gives it and on the
  approval card. The tests prove only that the bot's own code never writes it; `--leak-check` finds it in files
  after the fact; a session that prints its environment into a transcript is stopped only by the rule of 8.4.
- The lock is per machine; a second session with its own clone could run a second feed and double the request
  rate under the same address. The same limit as the engine's [S 13].
- The daily volume (about 0.9 GB on the wire) rests on one reading of one file's size, and the caps of 8.1 are
  placeholders until step 2.

Facts this spec could not confirm:
1. What clock `acceptanceDateTime` is in (4.4). The fixtures cannot say (one of them is not a raw capture); step
   2's year of stamps against EDGAR's hours decides.
2. Whether a throttled or refused client gets 429, 403 or a notice page with status 200; how long a 403 lasts;
   whether the limit is counted per declared client or only per IP address. The pages read do not say.
3. Whether `www.sec.gov` (the ticker file, the Atom feed, the nightly index) answers the declared User-Agent from
   the trader's machine (generic clients got 403 [R 119, 157]). If the ticker file is refused, step 2 stops
   there; no other identity is tried.
4. Whether the file sends `ETag` or `Last-Modified` (the verifier says no, one reading [R 157]). That 24.7 KB is a
   compressed size is inferred from the SEC's "at least ... 1,000" [W1], not read.
5. The size of each company's reply, on the wire and decoded, and whether the four banks' replies are several
   times the others'.
6. The SEC's real delay as seen from the bot (one sample, an upper bound of 165 s [R 133]); whether a cache sits
   in front of the file (`Age`, `Cache-Control`).
7. Which forms TEVA, CHKP, NICE, WIX and MNDY file, whether each is a foreign private issuer, and whether all 74
   tickers are in the SEC's ticker file.
8. How many `event` filings a session brings inside the launch window, and how many can be strictly matched (the
   arithmetic of 5.3 rests on an assumed 10 8-Ks a company a year).
9. How many filings a day the 74 companies make by class, and whether offering documents dominate.
10. When a running session picks up a new environment variable; whether the main chat and the trader session run
    in one environment, and whether it is personal (step 0 checks).
11. Whether the session's egress address is shared, and who else calls the SEC from it.
12. The exact wording of the SEC quotes (read through a summarising fetch tool; see the tags).
13. The name and shape of the nightly index file under `/Archives/edgar/daily-index`, its size, and how it writes a
    CIK: not read on an SEC page here; the plan's first task copies the name from the SEC's documentation, and
    step 2's one request shows the rest. The Atom feed's address is in the bot's own code [C data.py:304-305];
    whether it answers the declared client is fact 3.
14. Whether the supervisor's `http_stub.py` can script a redirect, a gzip body and a slow body (7.1).
15. That the pack's fixtures carry the same fields as today's live reply (one fixture has a field, `core_type`,
    not named on the SEC page read).
16. That EDGAR is closed on U.S. federal holidays and open on the market's other closed days (Good Friday), and the
    list of those dates for 2026 and 2027 (5.2, `sec.edgar_closed`): the plan's first task reads it against the
    SEC's page [W3] and cites its source.
17. How long the engine's handovers really take, and so how many of them the match can bridge (5.1): the uptime
    log measures it from the first day the supervisor's parent runs.

Confirmed since rev 1: the hours in which EDGAR accepts filings, 06:00 to 22:00 New York time on weekdays [W3,
read 2026-11-11]. Rev 1 listed them as not read.

For `state/backlog.md` (not designed here): the design of the Atom trigger, if question 2 is answered ד;
`data.sec_recent_form4` behind `sec.user_agent()` or deleted (with backlog item 3); the earnings table of backlog
item 2 from the `2.02` rows this journal collects; the title of stale Yahoo headlines in the seen log (question
4); one test helper and one child helper in place of two each; the feed's health in the dashboard's live-path
block; the engine polling Yahoo after the close, so that evening filings can be compared (an engine change, with
its own gate); grading of filing events at fixed horizons (roadmap sub-project 6).
