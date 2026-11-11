# Project skills (the owner's AI-trader work)

Installed on 2026-11-11 at the owner's request, so that every session of this repository can run them as slash
commands (`/trader-news`, `/trader-scanner`, ...).

Source: github.com/Jakeschincariol/day-trader-skill, MIT licence, pinned at commit 3d0f4ef (the same copy as
`ai-trader/vendor/jake-trader-skill-v2`, byte-identical). Ten of its eleven skills are here.

Left out on purpose: `trader-broker`. It walks the agent into placing orders at a real broker (Alpaca), and the
AI trader runs on paper money only (`ai-trader/CLAUDE.md`, hard rule 1). It stays out.

The skills write their working files to `trader/` under the folder they run in; that folder is git-ignored.
They are read-only tools for research and planning: none of them places an order.
