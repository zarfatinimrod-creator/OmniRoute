# Project skills (the owner's AI-trader work)

Installed on 2026-11-11 at the owner's request, so that every session of this repository can run them as slash
commands (`/trader-news`, `/trader-scanner`, ...).

Source: github.com/Jakeschincariol/day-trader-skill, MIT licence, pinned at commit 3d0f4ef (the same copy as
`ai-trader/vendor/jake-trader-skill-v2`, byte-identical, except `trader-broker` below). All eleven skills are here.

`trader-broker` (the eleventh) was added later the same day, at the owner's request, for the day he moves to real
money. Its copy here differs from upstream in two places only: `disable-model-invocation: true` (only he can start
it, by typing `/trader-broker`) and a guard paragraph at the top (paper accounts only, until he says in chat that
real money starts, as `ai-trader/CLAUDE.md` hard rule 1 requires). It needs an Alpaca connection he sets up himself.

The skills write their working files to `trader/` under the folder they run in; that folder is git-ignored.
Ten are read-only tools for research and planning; only `trader-broker` can lead to an order, and only as above.
