export const meta = {
  name: 'supervisor-build-wave',
  description: 'Supervisor plan BUILD tasks, one at a time: implementer, task review, fix loop (max 5), ledger',
}

const CLONE = '<SCRATCH>/clones/sup'
const WS = '/home/user/OmniRoute/.superpowers/sdd/2026-11-10-supervisor'
const PLAN_REL = 'ai-trader/research/plans/2026-11-10-supervisor.md'
const PKG = 'bash <SESSION-DIR>'
const SPEC = `${CLONE}/ai-trader/research/specs/2026-11-10-supervisor-design.md`
// Owner's order of 2026-11-11: Fable builds and creates, Opus does everything else.
const BUILD = 'claude-opus-5-5' // TEMPORARY (owner, 2026-11-11 after the Fable limit): Opus builds until Fable is back; restore 'claude-fable-5-2' then
const CHECK = 'claude-opus-5-5'

const short = s => String(s || '').slice(0, 7)
const sameSha = (a, b) => !!a && !!b && (String(a).startsWith(String(b)) || String(b).startsWith(String(a)))

const IMPL = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['DONE', 'DONE_WITH_CONCERNS', 'BLOCKED', 'NEEDS_CONTEXT'] },
    head_sha: { type: 'string' },
    commits: { type: 'array', items: { type: 'string' } },
    test_summary: { type: 'string' },
    concerns: { type: 'string' },
    report_file: { type: 'string' },
  },
  required: ['status', 'head_sha', 'commits', 'test_summary', 'concerns', 'report_file'],
}
const FINDING = {
  type: 'object',
  properties: {
    severity: { type: 'string', enum: ['Critical', 'Important'] },
    kind: { type: 'string', enum: ['spec', 'quality'] },
    where: { type: 'string' },
    what: { type: 'string' },
    why: { type: 'string' },
    fix: { type: 'string' },
    plan_mandated: { type: 'boolean' },
  },
  required: ['severity', 'kind', 'where', 'what', 'why', 'fix', 'plan_mandated'],
}
const REVIEW = {
  type: 'object',
  properties: {
    spec_compliant: { type: 'boolean' },
    quality_approved: { type: 'boolean' },
    findings: { type: 'array', items: FINDING },
    minor: { type: 'array', items: { type: 'string' } },
    cannot_verify: { type: 'array', items: { type: 'string' } },
    review_file: { type: 'string' },
  },
  required: ['spec_compliant', 'quality_approved', 'findings', 'minor', 'cannot_verify', 'review_file'],
}
const VERIFY = {
  type: 'object',
  properties: {
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          item: { type: 'string' },
          verdict: { type: 'string', enum: ['VERIFIED', 'REAL_GAP', 'BELONGS_TO_LATER_TASK', 'NEEDS_RUN', 'UNSURE'] },
          evidence: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['item', 'verdict', 'evidence', 'fix'],
      },
    },
  },
  required: ['items'],
}
const REREVIEW = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: { id: { type: 'string' }, addressed: { type: 'boolean' }, evidence: { type: 'string' } },
        required: ['id', 'addressed', 'evidence'],
      },
    },
    new_breakage: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['Critical', 'Important', 'Minor'] },
          where: { type: 'string' },
          what: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['severity', 'where', 'what', 'fix'],
      },
    },
    out_of_scope: { type: 'array', items: { type: 'string' } },
    fix_report_has_test_evidence: { type: 'boolean' },
    review_file: { type: 'string' },
  },
  required: ['verdicts', 'new_breakage', 'out_of_scope', 'fix_report_has_test_evidence', 'review_file'],
}

const STASH_BAN = `NEVER run \`git stash\` or \`git stash pop\` - ANYWHERE in this repository, in ANY form, including the read-only \`git stash list\` and inside a command line built for something else. git stash works on the SHARED object store, so it can clobber or resurrect another parallel session's uncommitted work (a recorded incident came through a subagent). To compare with a base, use \`git show <ref>:<path>\` or \`git diff <ref> -- <path>\`. Never touch the _tasks directory.`
const READ_FIRST = t => `## Read first, in this order
1. Your task brief - it is your requirements, with the exact values to use verbatim: ${WS}/task-${t.n}-brief.md
2. Controller notes (binding; they win over the brief): ${WS}/controller-notes.md
3. The plan's Global Constraints and Review Focus, verbatim: ${WS}/constraints.md
4. The baseline of the code you build on (where every name really is, the engine's outside calls, the test stubs): ${WS}/baseline.md${t.needsBaseline ? ' - if this file does not exist, stop and report NEEDS_CONTEXT' : ' - read it only if it exists and you need it'}
5. Only the spec sections your brief names ("Spec: 5.2" = section 5.2): ${SPEC}`

function implPrompt(t, base) {
  return `You are implementing Task ${t.n} of the supervisor build for a paper-money trading bot: ${t.title}.

Where it fits: ${t.fit}

${READ_FIRST(t)}

${STASH_BAN}
${t.extra ? '\n' + t.extra + '\n' : ''}
## Where you work
The gate clone: ${CLONE} (project folder ${CLONE}/ai-trader), branch supervisor-build. Before anything else run \`git -C ${CLONE} rev-parse HEAD\`, \`git -C ${CLONE} branch --show-current\` and \`git -C ${CLONE} status --short\`: HEAD must start with ${base}, the branch must be supervisor-build and the tree must be clean. If not, stop and report BLOCKED with what you saw.

## Your job
1. Write the task's tests first, run them, keep the failing output (RED).
2. Implement exactly what the brief specifies - nothing more.
3. Run the task's tests until they pass (GREEN). A test file that starts processes is run 3 times in a row; a test that fails once in three is a defect to fix, not to retry.
4. Run the whole suite once before the commit (the command is in the controller notes); it must end with OK.
5. Commit as the brief says (its paths and its message), with no attribution lines of any kind. Then \`git status --short\` prints nothing.
6. Self-review your own diff (\`git diff ${base}..HEAD\`) with fresh eyes: completeness against the brief line by line, edge cases, names that say what things do, YAGNI, existing patterns followed, tests that verify behaviour rather than mocks, pristine test output. Fix what you find (a further commit is fine) before reporting.
7. Write the report file, then answer.

You cannot ask questions mid-task. If a requirement is unclear in a way that changes what you build, if the task needs an architectural decision with several valid answers, or if the plan contradicts the code, the spec or itself: do not guess. Stop and report NEEDS_CONTEXT or BLOCKED with the exact question, what you tried and what you need. Bad work is worse than no work; you are not penalized for escalating.

You do not dispatch subagents - no helper, and never a reviewer. The controller dispatches a fresh reviewer against your diff after you report; a reviewer you spawn counts for nothing.

Code organization: follow the file structure the brief defines; follow the patterns already in the codebase; do not restructure anything outside your task. If a file grows beyond the brief's intent, or an existing file you modify is tangled, work carefully and report it as a concern instead of splitting files on your own.

## Report
Write the full report to ${WS}/task-${t.n}-report.md:
- what you implemented (or attempted, if blocked);
- TDD evidence - RED: the command, the relevant failing output and why that failure was expected; GREEN: the command and the passing output;
- the whole-suite result (its last three lines and its wall time);
- files changed;
- self-review findings and what you did about them;
- every place you departed from the brief, and why;
- concerns.
Then return the structured answer: status (DONE | DONE_WITH_CONCERNS when you finished but doubt something | BLOCKED | NEEDS_CONTEXT); head_sha (the full \`git -C ${CLONE} rev-parse HEAD\` after your last commit; when you stop before any commit, the HEAD you found); commits (short SHA and subject of each commit you made); test_summary (one line, e.g. "5 new tests pass, suite 551 OK, output pristine"); concerns (empty when none; when BLOCKED or NEEDS_CONTEXT the specifics go here, in full); report_file.`
}

function reviewPrompt(t, base, head) {
  return `You are reviewing one task's implementation: first whether it matches its requirements, then whether it is well-built. This is a task-scoped gate, not a merge review - a broad whole-branch review happens separately after all tasks. The task: Task ${t.n} of the supervisor build for a paper-money trading bot, "${t.title}".

## What was requested
${STASH_BAN}

Read the task brief: ${WS}/task-${t.n}-brief.md
Constraints that bind this task: ${WS}/constraints.md (the plan's Global Constraints and Review Focus, verbatim) and ${WS}/controller-notes.md (the controller's rulings; they win over the brief). The spec the plan argues from is ${SPEC} - read only the sections the brief names. Where names sat before the build: ${WS}/baseline.md (if it exists).

## What the implementer claims
Read the implementer's report: ${WS}/task-${t.n}-report.md

## Diff under review
Base ${base}, head ${head}, in the gate clone ${CLONE}.
First run exactly this one command. It writes the review package (commit list, stat summary, full diff with 10 lines of context) and prints its path:
  cd ${CLONE} && ${PKG} ${PLAN_REL} ${base} ${head} ${WS}/review-task-${t.n}.diff
If it exits non-zero, return that as one Critical finding (where: "review package", what: the error text) and stop.
Read that file once - it is your view of the change. Its context lines ARE the changed files: do not read a changed file separately unless a hunk you must judge is cut off mid-function, and say so in your report. Do not crawl the broader codebase. Inspect code outside the diff only to evaluate a concrete risk you can name - one focused check per named risk, naming both the risk and what you checked. Cross-cutting changes are legitimate named risks: when the diff changes lock handling, a function's contract or shared state, checking the call sites is the right method.
Your review is read-only on the clone: do not change the working tree, the index, HEAD or any branch.

## You do not dispatch subagents
Do all of this review yourself. No helper, no second opinion. If the diff is too large for one pass, review it in passes and say so.

## Do not trust the report
The report is unverified claims: it may be incomplete, inaccurate or optimistic. Verify claims against the diff. A stated rationale ("kept it simple on purpose", "left per YAGNI") is the implementer grading its own work and never downgrades a finding.

## Tests
The implementer ran the tests and reported the results with TDD evidence. Do not re-run the suite to confirm the report. Run a test only when reading the code raises a specific doubt that no existing run answers - then one focused test (prefix it with \`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT\`), never the whole suite or a repeat loop. Warnings or noise in the reported test output are findings. If the test evidence looks truncated or missing, re-read the report file; if it really is missing, report that as a gap.

## Part 1: spec compliance
Compare the diff with what was requested:
- Missing: requirements skipped, missed, or claimed without being implemented. Every test the brief names must exist under its name with the assertion the brief gives; every file the brief lists must have its hunk.
- Extra: features that were not requested, over-engineering.
- Misunderstood: the right feature built the wrong way.
A requirement you cannot verify from this diff alone (it lives in unchanged code or spans tasks) is a "cannot verify" item, not a reason to broaden your search.

## Part 2: code quality
Separation of concerns, error handling, DRY without premature abstraction, edge cases. Do the new tests verify real behaviour and not the mocks? Are the task's edge cases covered? Does each file keep one clear responsibility? Did this change make a file large or tangled (judge what this change added, not what was there)?
What this project cannot afford, from its constraints: anything that delays, skips or reorders a stop look beyond what the brief says; a test or helper that could reach the phone, the network, the model or the live state; a threshold as a literal in the logic instead of config.json; the ntfy topic, a URL or an exception's text in a log or an error path; an owner line that does not end with "כסף נייר"; a trading rule changed beyond the brief.

## Calibration
Categorize by actual severity. Important = this task cannot be trusted until it is fixed: incorrect or fragile behaviour, a missed requirement, or maintainability damage you would block a merge over (verbatim duplication of a logic block, swallowed errors, a test that asserts nothing). "Coverage could be broader" and polish are Minor. If the brief or the plan explicitly mandates something this rubric calls a defect, that IS a finding: report it as Important with plan_mandated true - the plan does not grade its own work. Say what was done well before the issues.

## Output
Write your full report to ${WS}/task-${t.n}-review.md in this shape: "### Spec Compliance" (compliant or the issues with file:line; then the cannot-verify items), "### Strengths", "### Issues" with "#### Critical (Must Fix)", "#### Important (Should Fix)", "#### Minor (Nice to Have)" (each: file:line, what is wrong, why it matters, how to fix), "### Assessment" (Task quality: Approved | Needs fixes, and one or two sentences of reasoning). Every line is a verdict, a finding with file:line, or a check you ran.
Then return the structured answer:
- spec_compliant: true only when nothing is missing, extra or misunderstood among what you could verify;
- quality_approved: true only with no Critical and no Important issue;
- findings: EVERY spec-compliance issue (kind "spec") and EVERY Critical or Important quality issue (kind "quality"), each with severity, where (file:line), what, why, fix (how, or "" when obvious) and plan_mandated (true only when the brief or the plan text explicitly mandates the very thing you flag);
- minor: one line each (file:line and the point);
- cannot_verify: one line each - the requirement and what should be checked;
- review_file: the path you wrote.`
}

function verifyPrompt(t, head, items) {
  return `A task reviewer of the supervisor build (Task ${t.n}, "${t.title}") could not verify the requirements below from the task's diff alone: they live in unchanged code or span tasks. You have the cross-task view the reviewer lacked. Decide each one. Read-only: change nothing anywhere, dispatch no subagents. ${STASH_BAN}

You may read: the task brief ${WS}/task-${t.n}-brief.md; the whole plan ${CLONE}/${PLAN_REL}; the spec ${SPEC}; the controller notes ${WS}/controller-notes.md; the baseline ${WS}/baseline.md; the implementer's report ${WS}/task-${t.n}-report.md; and the code in the gate clone ${CLONE}/ai-trader as it stands at ${head} (the checked-out tree).

Items:
${items.map((s, i) => `${i + 1}. ${s}`).join('\n')}

For each item return: item (repeat it), verdict, evidence (file:line or plan line that settles it), fix (for REAL_GAP: what must change; otherwise "").
- VERIFIED: the requirement is met at this commit - cite the code.
- REAL_GAP: the brief of THIS task requires it and the code at this commit does not do it - cite both.
- BELONGS_TO_LATER_TASK: the plan gives it to a later task - cite the task and the plan line.
- NEEDS_RUN: only an actual test run can settle it (a reported test result, a suite count, a repeat run) and the code read gives no reason to doubt it - the workflow runs the suite independently at this commit next.
- UNSURE: you could not settle it - say exactly what is missing.
Default to REAL_GAP over VERIFIED when the code does not clearly do what the brief requires.`
}


const RUN = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    head_checked: { type: 'string' },
    repeat_files: { type: 'array', items: { type: 'string' } },
    repeats_ok: { type: 'boolean' },
    whole_suite_last_lines: { type: 'string' },
    failures: { type: 'string' },
  },
  required: ['ok', 'head_checked', 'repeat_files', 'repeats_ok', 'whole_suite_last_lines', 'failures'],
}

function runPrompt(t, base, head) {
  return `Independent test run for Task ${t.n} of the supervisor build ("${t.title}"), a paper-money trading bot. You run tests and report; you change nothing (no edit, no commit, no checkout of another commit), and you dispatch no subagents. Never use git stash or git stash pop in any form, not even \`git stash list\`.

1. In ${CLONE}, confirm \`git rev-parse HEAD\` starts with ${short(head)} and \`git status --short\` prints nothing. If either fails, stop and report ok=false with what you saw.
2. Find the test files this task changed: \`git diff --name-only ${base}..${head} -- ai-trader/tests/\`. Of those, the ones that start processes or threads (they import subprocess, use tests/helpers/engine_child.py or dummy_child.py, or test the news loop: test_news_supervised.py, test_supervise.py, and any test_supervise_*.py) are run 3 times in a row each.
3. Then the whole suite once.
Every python command goes through the safe wrapper, from ${CLONE}/ai-trader, for example:
  ${WS}/safe python3 -m unittest discover -s tests -p test_supervise.py   (one file: discover with -p; the form "unittest tests/x.py" fails to import)
  ${WS}/safe python3 -m unittest discover -s tests
(One run of test_supervise.py takes about 270 s and the whole suite about 310 s. Run each repeat and the whole suite as its OWN Bash command, one after the other, each with timeout 600000 ms; never chain two runs in one command, since a command is cut off at 600000 ms.)
Report: ok (true only if every repeat and the whole suite end with OK), head_checked, repeat_files, repeats_ok, whole_suite_last_lines (the last 3 lines of the whole-suite output, verbatim), failures (the shortest decisive lines of any failure or error, or "").`
}

const findingsText = open => open.map(f => `- [${f.id}] (${f.severity}, ${f.kind || 'quality'}) ${f.where}: ${f.what} Why it matters: ${f.why}${f.fix ? ' Suggested fix: ' + f.fix : ''}`).join('\n')

function fixPrompt(t, round, open, base, fixBase) {
  return `You are fixing review findings on Task ${t.n} of the supervisor build for a paper-money trading bot ("${t.title}"). This is fix round ${round} of at most 5. ${round >= 4 ? `A prior implementer attempted this task ${round - 1} times; you own it now. Read the report file for what was tried.` : 'A fresh reviewer read this task\'s diff and found the issues below.'}

${READ_FIRST(t)}

${STASH_BAN}
6. The implementer's report, with earlier fix reports at its end: ${WS}/task-${t.n}-report.md
7. The reviewer's full report, for context only: ${WS}/task-${t.n}-review.md

## Where you work
The gate clone: ${CLONE} (project folder ${CLONE}/ai-trader), branch supervisor-build. First run \`git -C ${CLONE} rev-parse HEAD\`, \`git -C ${CLONE} branch --show-current\` and \`git -C ${CLONE} status --short\`: HEAD must start with ${fixBase}, the branch must be supervisor-build and the tree must be clean. If not, stop and report BLOCKED. The task's commits so far are ${base}..${fixBase} (\`git diff ${base}..HEAD\` shows the task).

## Findings to fix (verbatim from the review)
${findingsText(open)}

Fix each finding at its root: the specific defect must no longer exist. Fix nothing that is not on this list. If you are convinced a finding is wrong, do not silently skip it: leave the code as it is and say in the fix report exactly why, with file:line evidence - the re-reviewer rules on it. If a fix would contradict the brief or the spec, stop and report BLOCKED with the contradiction.

Then: re-run the tests that cover the amended code (a test file that starts processes: 3 times in a row), and the whole suite once before the commit (the command is in the controller notes; it must end with OK). Commit as new commit(s) - never amend or rewrite an existing commit - with a plain-English message that says what was fixed and why, and no attribution lines of any kind. \`git status --short\` then prints nothing. You do not dispatch subagents.

Append a section "## Fix round ${round}" to the END of ${WS}/task-${t.n}-report.md: for each finding id what you changed (file:line) or why you left it; the covering tests you ran; the exact command; its output; the whole-suite last three lines.
Then return the structured answer: status (DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT); head_sha (the full \`git -C ${CLONE} rev-parse HEAD\` after your last commit); commits (short SHA and subject of each commit of this round); test_summary (one line); concerns (empty when none; the specifics when blocked; and every finding you left unfixed with the reason); report_file.`
}

function reReviewPrompt(t, round, open, fixBase, head) {
  return `You are re-reviewing one task's fix round (Task ${t.n} of the supervisor build, "${t.title}", fix round ${round}). A previous review produced findings; an implementer has attempted to fix them. Your job is to verdict each finding and inspect the fix diff - nothing else. It is not a fresh review.

## The task
${STASH_BAN}

Read the task brief: ${WS}/task-${t.n}-brief.md. Binding constraints: ${WS}/constraints.md and ${WS}/controller-notes.md.

## The findings under verification
${findingsText(open)}

## The fix
Read the implementer's report; the fix reports are appended at its end, the last one is "Fix round ${round}": ${WS}/task-${t.n}-report.md
Fix base ${fixBase} (the head the previous review saw), head ${head}, in the gate clone ${CLONE}.
First run exactly this one command; it writes the fix diff package and prints its path:
  cd ${CLONE} && ${PKG} ${PLAN_REL} ${fixBase} ${head} ${WS}/review-task-${t.n}-fix${round}.diff
If it exits non-zero, return every finding as not addressed with that error as the evidence.
Read that file once. Your review is read-only on the clone. You do not dispatch subagents.

## Scope
The findings list and the fix diff. Verdict every finding: ADDRESSED only when the specific defect no longer exists - "attempted" is not addressed. Where the implementer left a finding unfixed and argued it is wrong, judge the argument on the code: addressed = true only if the finding really was wrong, and say so in the evidence. Inspect the fix diff for problems the fix itself introduced. Do NOT re-review code the fix did not touch: an issue entirely outside the fix diff goes under out-of-scope observations, which block nothing.

## Tests
The implementer re-ran the covering tests and appended the results. Treat that as unverified claims: confirm the fix report names the covering tests, the command and the output, and check the claims against the diff. Do not re-run the suite. Run one focused test only when reading the code raises a specific doubt no existing run answers (prefix it with \`env -u AITRADER_NTFY_TOPIC -u AITRADER_TELEGRAM_TOKEN -u AITRADER_TELEGRAM_CHAT\`).

## Output
Write your report to ${WS}/task-${t.n}-rereview-${round}.md: "### Finding Verdicts" (each finding id: ADDRESSED | NOT ADDRESSED with file:line evidence), "### New Breakage in the Fix Diff" (severity and file:line, or None), "### Out-of-Scope Observations", "### Verdict".
Then return the structured answer: verdicts (one per finding id above: id, addressed, evidence); new_breakage (what the fix itself broke: severity Critical | Important | Minor, where, what, fix); out_of_scope (one line each); fix_report_has_test_evidence (true only when the fix report shows the covering tests, the command and the output); review_file.`
}

async function ledger(n, lines) {
  if (!lines.length) return
  await agent(`Append the text between the two marker lines to the END of the file ${WS}/progress.md, exactly as given: each line on its own line, nothing added, nothing else in the file changed, the marker lines themselves not written. Use one shell command of the form  cat >> FILE <<'LEDGER_EOF'  ...  LEDGER_EOF  . Then run \`tail -n ${lines.length} ${WS}/progress.md\` to confirm, and reply with the single word done. Do nothing else.

=====BEGIN=====
${lines.join('\n')}
=====END=====`, { label: `ledger T${n}`, phase: `Task ${n}`, effort: 'low', model: CHECK })
}

async function runTask(t, base) {
  const ph = `Task ${t.n}`
  phase(ph)
  const impl = await agent(implPrompt(t, base), { label: `implement T${t.n}`, phase: ph, schema: IMPL, model: BUILD })
  if (!impl) {
    await ledger(t.n, [`Task ${t.n}: implementer ended without a result (base ${short(base)}); not complete`])
    return { n: t.n, state: 'implementer_died', base }
  }
  if (impl.status === 'BLOCKED' || impl.status === 'NEEDS_CONTEXT' || !impl.head_sha || sameSha(impl.head_sha, base)) {
    const st = (impl.status === 'BLOCKED' || impl.status === 'NEEDS_CONTEXT') ? impl.status : 'no_commit'
    await ledger(t.n, [`Task ${t.n}: implementer stopped (${st}), waits for the controller: ${String(impl.concerns).replace(/\n+/g, ' ').slice(0, 600)}`])
    return { n: t.n, state: st, base, concerns: impl.concerns, report: impl.report_file }
  }
  let head = impl.head_sha
  log(`T${t.n} implemented at ${short(head)} (${impl.status}): ${impl.test_summary}`)
  const rev = await agent(reviewPrompt(t, base, head), { label: `review T${t.n}`, phase: ph, schema: REVIEW, model: CHECK })
  if (!rev) {
    await ledger(t.n, [`Task ${t.n}: implemented at ${short(head)} (commits ${short(base)}..${short(head)}); the reviewer ended without a result; not complete`])
    return { n: t.n, state: 'reviewer_died', base, head }
  }
  let fid = 0
  const mk = f => ({ ...f, id: `F${++fid}` })
  const all = rev.findings.map(mk)
  const mandated = all.filter(f => f.plan_mandated)
  let open = all.filter(f => !f.plan_mandated)
  const minors = [...rev.minor]
  const unresolved = []
  const lines = []
  if (!rev.spec_compliant && !all.length && !rev.cannot_verify.length) {
    await ledger(t.n, [`Task ${t.n}: implemented at ${short(head)}; the review says "not spec compliant" with no finding listed (see task-${t.n}-review.md); waits for the controller`])
    return { n: t.n, state: 'review_inconsistent', base, head }
  }
  if (rev.cannot_verify.length) {
    const ver = await agent(verifyPrompt(t, head, rev.cannot_verify), { label: `verify T${t.n}`, phase: ph, schema: VERIFY, model: CHECK })
    if (!ver) unresolved.push(...rev.cannot_verify)
    else {
      for (const it of ver.items) {
        if (it.verdict === 'REAL_GAP') open.push(mk({ severity: 'Important', kind: 'spec', where: it.evidence, what: it.item, why: 'a requirement of this task that the code does not meet (confirmed by the cross-task verifier)', fix: it.fix || '', plan_mandated: false }))
        else if (it.verdict === 'UNSURE') unresolved.push(`${it.item} - ${it.evidence}`)
        else if (it.verdict === 'NEEDS_RUN') lines.push(`Task ${t.n}: cannot-verify item left to the independent run: ${String(it.item).slice(0, 160)}`)
        else lines.push(`Task ${t.n}: cannot-verify item settled (${it.verdict}): ${String(it.item).slice(0, 140)} - ${String(it.evidence).slice(0, 160)}`)
      }
    }
  }
  log(`T${t.n} review: ${open.length} to fix, ${mandated.length} plan-mandated, ${minors.length} minor, ${unresolved.length} unresolved`)
  let round = 0
  let fixBase = head
  while (open.length && round < 5) {
    round++
    const fix = await agent(fixPrompt(t, round, open, base, fixBase), { label: `fix T${t.n} r${round}`, phase: ph, schema: IMPL, model: BUILD })
    if (!fix || fix.status === 'BLOCKED' || fix.status === 'NEEDS_CONTEXT' || !fix.head_sha || sameSha(fix.head_sha, fixBase)) {
      lines.push(`Task ${t.n}: fix round ${round}/5 stopped (${fix ? fix.status : 'the fixer ended without a result'}), waits for the controller: ${fix ? String(fix.concerns).replace(/\n+/g, ' ').slice(0, 600) : ''}`)
      await ledger(t.n, lines)
      return { n: t.n, state: 'fix_stopped', base, head: fixBase, round, open, mandated, minors, unresolved, concerns: fix ? fix.concerns : 'the fixer ended without a result' }
    }
    const newHead = fix.head_sha
    const rr = await agent(reReviewPrompt(t, round, open, fixBase, newHead), { label: `re-review T${t.n} r${round}`, phase: ph, schema: REREVIEW, model: CHECK })
    if (!rr) {
      lines.push(`Task ${t.n}: fix round ${round}/5 committed (${short(fixBase)}..${short(newHead)}); the re-reviewer ended without a result; waits for the controller`)
      await ledger(t.n, lines)
      return { n: t.n, state: 'rereviewer_died', base, head: newHead, round, open, mandated, minors, unresolved }
    }
    const addressed = new Set(rr.verdicts.filter(v => v.addressed).map(v => v.id))
    const still = open.filter(f => !addressed.has(f.id))
    const fresh = rr.new_breakage.filter(b => b.severity !== 'Minor').map(b => mk({ severity: b.severity, kind: 'quality', where: b.where, what: b.what, why: `introduced by the fix of round ${round}`, fix: b.fix || '', plan_mandated: false }))
    if (!rr.fix_report_has_test_evidence) fresh.push(mk({ severity: 'Important', kind: 'quality', where: `${WS}/task-${t.n}-report.md`, what: `the fix report of round ${round} does not show the covering tests, the command and the output`, why: 'the report is the only test evidence the review has', fix: 'run the covering tests and append the command and its output to the report', plan_mandated: false }))
    minors.push(...rr.new_breakage.filter(b => b.severity === 'Minor').map(b => `${b.where}: ${b.what}`), ...rr.out_of_scope)
    const left = [...still, ...fresh]
    lines.push(`Task ${t.n}: fix round ${round}/5 (${open.length - still.length} addressed, ${left.length} open${left.length ? ' - ' + left.map(f => String(f.what).slice(0, 90)).join('; ') : ''}; commits ${short(fixBase)}..${short(newHead)})`)
    open = left
    fixBase = newHead
    log(`T${t.n} fix round ${round}: ${left.length} open`)
  }
  head = fixBase
  for (const m of minors) lines.push(`Task ${t.n}: minor (deferred): ${String(m).replace(/\n+/g, ' ').slice(0, 300)}`)
  for (const f of mandated) lines.push(`Task ${t.n}: plan-mandated finding, waits for the controller's ruling: [${f.severity}] ${f.where}: ${String(f.what).replace(/\n+/g, ' ').slice(0, 300)}`)
  for (const u of unresolved) lines.push(`Task ${t.n}: could not be verified, waits for the controller: ${String(u).replace(/\n+/g, ' ').slice(0, 300)}`)
  if (impl.status === 'DONE_WITH_CONCERNS') lines.push(`Task ${t.n}: implementer's concerns: ${String(impl.concerns).replace(/\n+/g, ' ').slice(0, 500)}`)
  if (open.length) {
    for (const f of open) lines.push(`Task ${t.n}: OPEN at the cap (5 rounds), waits for the controller: [${f.severity}] ${f.where}: ${String(f.what).replace(/\n+/g, ' ').slice(0, 300)}`)
    await ledger(t.n, lines)
    return { n: t.n, state: 'cap', base, head, rounds: round, open, mandated, minors, unresolved }
  }
  const run = await agent(runPrompt(t, base, head), { label: `run suite T${t.n}`, phase: ph, schema: RUN, model: CHECK, effort: 'low' })
  if (!run || !run.ok) {
    unresolved.push(run ? `the independent test run at ${short(head)} did not end OK: ${String(run.failures).slice(0, 400)} | ${String(run.whole_suite_last_lines).slice(0, 200)}` : 'the independent test runner ended without a result')
  } else {
    lines.push(`Task ${t.n}: independent test run at ${short(head)}: repeats OK (${run.repeat_files.join(', ') || 'no process test changed'}); whole suite: ${String(run.whole_suite_last_lines).replace(/\n+/g, ' ').slice(0, 120)}`)
  }
  if (unresolved.length) {
    lines.push(`Task ${t.n}: implemented and reviewed (commits ${short(base)}..${short(head)}), NOT yet complete: ${unresolved.length} item(s) wait for the controller's check`)
    await ledger(t.n, lines)
    return { n: t.n, state: 'unresolved', base, head, rounds: round, mandated, minors, unresolved, concerns: impl.concerns }
  }
  lines.push(`Task ${t.n}: complete (commits ${short(base)}..${short(head)}, ${round ? `review clean after ${round} fix round(s)` : 'review clean'}${mandated.length ? `, ${mandated.length} plan-mandated finding(s) wait for a ruling` : ''})`)
  await ledger(t.n, lines)
  return { n: t.n, state: 'complete', base, head, rounds: round, mandated, minors_count: minors.length, concerns: impl.concerns, test_summary: impl.test_summary }
}

let base = args.startBase
const results = []
for (const t of args.tasks) {
  const r = await runTask(t, base)
  results.push(r)
  if (r.state !== 'complete') {
    log(`stopped at Task ${t.n}: ${r.state}`)
    break
  }
  base = r.head
}
return { results, nextBase: base }
