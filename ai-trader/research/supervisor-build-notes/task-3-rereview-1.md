# Task 3 re-review, fix round 1 (25d18a4b..2c5cf812)

### Finding Verdicts

- **F1: ADDRESSED.** `ai-trader/tests/test_news_supervised.py:27` (Lock) and `:51` (Unlocked) now call `news_live.run("23:59", max_minutes=0.0005, prime=False)`. `run`'s first positional parameter is `until_ny` (`aitrader/news_live.py:1412`), so the loop no longer breaks before its first step after 16:05 New York. The fix report shows the RED run (2 ERRORs, TypeError at 17:00 NY) and the GREEN run at 17:00 NY and at the real hour.
- **F2: ADDRESSED.** `engine_options` is gone from `ai-trader/tests/helpers/engine_child.py`. `main` now returns `cli.main(["news-live", *options])` (`:178`), and the docstring (`:29-34`) says the child passes options through unchanged. `Procs.start_engine` (`ai-trader/tests/test_supervise.py:81-85`) adds `--until 23:59` when the options carry no `--until`, in either the `--until X` or the `--until=X` spelling. It has a comment that names the 23:59-00:00 ceiling, as ruling 11:10 requires. Two pins guard this:
  - `test_a_start_made_here_ends_at_23_59_new_york_unless_its_options_name_an_end` checks the command line passed to a mocked Popen.
  - `test_the_engine_child_hands_the_engine_its_options_as_they_came` runs the real child with `cli.main` replaced by a print.

### New Breakage in the Fix Diff

None.
- The mock-Popen pin clears `self._started`, so tearDown never calls `poll`, `wait` or `close` on MagicMocks.
- The scenario files the pin writes sit in `self.tmp` and are removed with it.
- Removing the `from helpers import engine_child` import is safe: the old pin was its only user.

### Out-of-Scope Observations

- `TheLoopsAnswer` (`tests/test_news_supervised.py:37`) still calls `news_live.run(max_minutes=0.001)` with no end. `_run` is stubbed there, so the clock never matters. The controller may still want `"23:59"` added for literal compliance with "every in-process start". This blocks nothing.
- Task 8's PARENT script and the Task 17 drills must now pass `--until` themselves when they start the child outside `start_engine`. The fix report already notes this as a hand-off.

### Verdict

Both findings are addressed and the fix introduces no new breakage. The fix report includes test evidence: the commands, RED/GREEN output, an evening run at a pretended 17:00 NY, a ceiling check at 23:59 vs 23:57, mutation checks, and a full-suite run of 567 tests, OK. These are the implementer's claims. I checked them against the diff and did not re-run them. Task 3 can proceed.
