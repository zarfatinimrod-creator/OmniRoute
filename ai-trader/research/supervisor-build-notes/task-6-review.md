# Task 6 review - A sale is said at once (67096b47..ce6abbe3)

### Spec Compliance

Compliant, with three departures from the brief's letter that the report names and that I accept as readings of the brief's own governing rule ("told_through never passes a row whose line nobody got"); the controller should ratify them:

- news_live.py:1146-1152 (`_log_trade`) - a row's hash joins `_unsent` when it is appended, not after a failed send (report departure 1). This matches the interface's definition of `_unsent` and is pinned by `test_a_delivered_look_does_not_move_the_mark_past_a_buy_whose_line_is_still_to_come`.
- news_live.py:1181-1189 (`_mark_told`) - "the last row's hash" is the journal's last row known to this process (`_last_row`), not the last entry of `hashes` (departure 2). Needed so a late line said after a delivered look does not set the mark back.
- news_live.py:1286-1287 (`adopt_previous`) - a mark that is not a row of the journal becomes the journal's last row, where the brief says `told_through = prev["told_through"]` whenever the key exists (departure 3). Same "nothing late" result the brief asks for. Keeping the foreign mark would mean an unsent trade of this process is never said at the next start.

Checked against the brief, item by item:
- The brief's five tests exist under their names with the brief's assertions: `SaidAtOnce` (4) at test_news_supervised.py:386-424, `SaidBeforeTheKill` at test_supervise.py:637-644 (verbatim). In tests 1-3, `self.nt.step()` is replaced by the module's `step(nt, ...)` helper, because the bare call would poll Yahoo for real. The stand-ins the brief's comments describe are written in the tests (`at_scorer`, `calls` with `(body, told_through)`, the first send returning `[]`).
- `_log_trade` reads back the hash of the last row (1149). `_look_at_stops` sends its own lines after the look, its save and its beat, with title "AI Trader - חדשות", the book line and priority "high" (1108-1114). The step's closing message leaves out lines a look delivered (1219). `_mark_told` (1181). `say_late`: body `"דווח באיחור: " + " | ".join(...) + ". כסף נייר"`, asserted character for character at test 567-568. It is called in `_run` after `adopt_previous` (1751). `_beat` writes `told_through` (1328).
- Files: only the three the brief lists.

Cannot verify from this diff:
- Task 7's move of `say_late` to after the first stop look, and the case where a first look outside a step fails to deliver (report concern 2). Its rows stay owed until the next start; Task 7 should decide whether the first step retries them.
- That `notify.send` never raises an exception whose text holds the topic. `_note_error` writes `str(e)[:300]` for the new `look_alert` and `late_line` rows. The pattern was already there (`step_alert`), and notify.py catches `requests.RequestException` itself. Not re-audited.

### Strengths

- Smallest shape that works. `_say` replaces the old closing-message code instead of copying it, so the look's message and the step's message both end with the book line and "כסף נייר" (asserted at test 443-445).
- Order is safe. The sale is journaled and saved, and the look's beat is written, before the send. The send comes after the catch-up and the second "sell" look (1102-1114), so no stop look is reordered. The look inside the buy path (news_live.py:1226) still comes before the fresh quote the buy uses (1233-1234). I checked this because the new send is an extra network call inside that look.
- `SaidBeforeTheKill` is not racy. I checked every `_beat(` call: "quotes" is written only in the headline-quote loop (1467), after the top-of-step look and its send. A process that reaches "quotes" has already sent the sale.
- Every new failure path ends in a `news_errors.jsonl` row and never costs the sale or the start: `trade_hash`, `look_alert`, `late_line`. Each has its own test.
- The `adopt_previous` table test (529-553) covers Review Focus 1 and 4: no heartbeat, a pre-field heartbeat, a null mark, yesterday's mark, a foreign hash, a non-hash mark, a torn line and an unreadable journal.
- No literal threshold added. Every send passes the priority positionally. Every test stays behind the stubs (`step()` helper, `_Starts.start`, `Procs` behind the tripwire).

### Issues

#### Critical (Must Fix)
None.

#### Important (Should Fix)
None.

#### Minor (Nice to Have)
- news_live.py:1286-1287 - departure 3 (a foreign mark is replaced by the journal's last row) goes against the brief's literal `told_through = prev["told_through"]`. It is defensible, but the controller should record a ruling on it, so Task 7 and later tasks do not read the brief's sentence as the contract.
- news_live.py:1196-1205 (`say_late`) - the late line has no length cap (report concern 3). A day with many unsent trades could build a body that ntfy refuses (4,096 bytes) at every start of that day, and it would never be delivered. The step message has the same exposure, so this is not new, but the late line piles up across restarts. A later task could split it or cap it, with the cap in config.json.
- news_live.py:1187-1188 - once one row of a process is never retried (a failed look outside a step), `told_through` stays put for the rest of that process. The next start then says late every later trade, including those already delivered (report concern 1). This is the brief's design ("at least once"), noted here for the owner-facing behaviour.
- news_live.py:1149 - every trade reads the whole journal to get one hash. The `ponytail:` comment names the limit (measured 15 ms at 2,000 rows) and the upgrade. Fine for now.
- news_live.py:1213 - `getattr(self, "_unsent", ())` exists only for a test that builds the trader with `__new__`. The comment explains it. Acceptable, but it is a test-shaped branch in production code.

### Assessment

Task quality: Approved. Every requirement of the brief is built and pinned by tests that check real behaviour (what was sent, when, and what the heartbeat holds). The departures are reported and each one enforces the brief's own invariant. I found no defect on the stop path, the trading rules or the topic path in the code this change adds.
