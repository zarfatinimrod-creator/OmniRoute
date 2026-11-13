### Task 19c: the same no-touch merge check in SKILL 0 and 3א, R12 once a day, and five literal-reading gaps in the watchdog text

**Kind:** BUILD (texts and one test file). **Authority:** the controller's Ruling 59 in the ledger (`progress.md`), from
Task 19b's review: its plan-mandated finding F2 and some of its minors. Not in the plan. It must be committed before Task
20 replaces the scheduled tasks' texts. It changes no trading rule and touches no file the time machine loads.

**Files:** Modify `ai-trader/skills/trader/SKILL.md` (sections 0, 3א and 3ב only), `ai-trader/skills/trader/slots/news-watch.md`,
`ai-trader/CLAUDE.md` (hard rule 8 and the "One builder at a time" line only), `ai-trader/tests/test_slot_files.py`. Read
Task 19b's report (`task-19b-report.md`) and review (`task-19b-review.md`) first. Keep every other line as 19b left it.
S2 and R12 are copied from `ownerlines.py` as built.

1. **SKILL 0 and 3א sync like the slots (F2).** SKILL section 0 (every session) and section 3א (the sync after a loss
   review) still run `git fetch ... && git merge --no-edit origin/ccr-120121ba-vsvwlj` with no check. The slots send the
   trader session there in market hours. Give both the same sync as the slot files (Task 19b, item 4):
   - fetch;
   - `git merge-tree --write-tree --name-only HEAD origin/ccr-120121ba-vsvwlj`, where exit 1 is a conflict: do not merge,
     follow the conflict rule;
   - `git merge --no-edit` only on exit 0;
   - the abort backstop.
   Use the same words as the slot files where you can.
2. **CLAUDE.md names the check where it states the rule.** Hard rule 8 (fetch, then `git merge --no-edit`, never rebase)
   gets the merge-tree check in its own words, so the "One builder at a time" line's "sync as hard rule 8 says" is true.
3. **R12 at most once per New York day.** A parent that dies at start is relaunched by every :07/:37 watchdog; the
   `launch` action is not gated, and that stays. So each crash wakes the session, finds the marker, and sends R12 again:
   every 30 minutes all day. From now on R12 is sent at most once per New York day: when R12 goes out, the session adds
   ` R12` to the marker file's line (`.cache/parent_relaunched`), and it does not send R12 when the line already has it.
   Say it the same way in news-watch.md step 2(a) and the SKILL 3ב last-line table.
4. **Five places a literal reading stalls (19b's review minors).**
   - (a) In the exit-1/2 cell, "in (b) a `launch` is not run" also withholds the trailing "then launch" of
     `replace_parent` and `kill_stray`; say so.
   - (b) In the 75-tripped cell, the abort-fails branch ends with "and go on with (b)".
   - (c) The exit-1/2 cell's read of `.cache/supervise.log` gets its own `cd /home/user/OmniRoute/ai-trader && tail -n 20
     .cache/supervise.log`, like the 75-tripped cell.
   - (d) news-watch.md step 6's git commands start with `cd /home/user/OmniRoute && ` (steps 2-3 leave the shell in
     ai-trader/).
   - (e) The session's own `kill -9` in the replace_parent fallback (exit 137, no last line) is a planned replacement,
     not a crash. It neither writes nor reads the marker.
5. **Tests** in `tests/test_slot_files.py`:
   - (a) SKILL.md names `git merge-tree --write-tree --name-only HEAD origin/` in sections 0 and 3א. Find each section by
     its heading.
   - (b) `ai-trader/CLAUDE.md` names it in hard rule 8.
   - (c) news-watch.md and SKILL 3ב say R12 at most once per New York day, with ` R12` in the marker line.
   - (d) Every git command line in news-watch.md step 6 starts from `cd /home/user/OmniRoute`.
   - (e) `test_the_crypto_slots_and_the_skill_carry_the_same_loop` asserts exactly one loop match per text, not a set
     comparison: a file that loses its loop must fail.

- [ ] Write the tests of item 5; run them: they fail (RED).
- [ ] Edit the texts (items 1-4).
- [ ] Run `tests/test_slot_files.py` 3 times in a row, then the whole suite once, every python command through the safe
  wrapper: `OK`.
- [ ] Commit: `git add` the files you changed from the list above, by name; message
  `docs(ai-trader): SKILL 0 and 3א test a merge before making it, R12 once a day, and the watchdog text reads the same when taken literally`.

**For the report and the gate:** no buy, sale or stop rule changes; no stop look delayed or skipped; config.json is not
changed; no file the time machine loads is touched.
