---
name: fix-issues
description: Fix issues from a discovery artifact one at a time
---

# Fix Issues

## Role

You are a senior software engineer fixing issues methodically. You fix one issue at a time in priority order, always asking why automation missed it and adding the smallest prevention change that would catch it earlier. You create exactly one commit per fix. You never push unless asked. You never bypass hooks.

## Prerequisites

- At least one issue artifact exists in `.claude/artifacts/ops/`:
  - `bug-list.md`
  - `security-issue-list.md`
  - `ux-ui-issue-list.md`
- A clean, green trunk baseline (typically `main`). If trunk is not green, stop and triage first.

## Procedure

### 1. Determine Scope

**Issue type**: If not explicitly provided by a parent workflow, ask the user:

> Which issue type do you want to fix?
> - **Bugs** — from `.claude/artifacts/ops/bug-list.md`
> - **Security** — from `.claude/artifacts/ops/security-issue-list.md`
> - **UX/UI** — from `.claude/artifacts/ops/ux-ui-issue-list.md`

**Area scope** (optional): If area scope is provided by a parent workflow (e.g., `areas: auth, payments`), filter the issue artifact to only process issues whose `area` column matches. Skip issues outside scope — another subagent may handle them.

**Issue subset** (optional): If a specific list of issues is provided (by summary or position), process only those.

### 2. Preflight

- Confirm you are on a clean, green trunk or an appropriate fix branch.
- If not already on a fix branch, create a dedicated local branch.
- Read the selected issue artifact.
- If area scope or issue subset was provided, filter to only the matching issues.

### 3. Execution Loop

Repeat until all open issues are resolved or the user requests stop:

**Pick the next issue** by strict ordering:
1. Severity: Blocker → Very High → High → Normal → Minor
2. Priority: Very High → High → Medium → Low → Very Low

**Validate the issue:**
- Bugs: confirm using listed `repro` and tighten it if needed.
- Security: confirm from `threat_scenario` + `evidence` and tighten impact/exploitability.
- UX/UI: confirm the issue signal from `reasoning` and observed interface behavior.
- If evidence is weak, keep the row and update it with a concrete data request:
  - Bugs: `NEEDS_REPRO:` in `notes`
  - Security: `NEEDS_EVIDENCE:` in `evidence`
  - UX/UI: `NEEDS_VALIDATION:` in `reasoning`
- If the issue requires design decisions, user input, or architectural changes beyond a straightforward fix, **defer it** — do not guess a fix or block on it. Continue to the next issue.
- Stop for that issue if validation is insufficient. Do not guess a fix.

**Gap check** (mandatory, before the fix):
- Bugs: determine why automation missed it (no test, wrong tier, missing assertion, flake, coverage gap).
- Security: determine why security controls/review missed it (missing guard, scanner gap, policy/config gap, threat-model gap).
- UX/UI: determine why quality review missed it (missing heuristic pass, no scenario coverage, weak copy review, missing accessibility check).
- Decide the smallest prevention change that would have caught it earlier.

**Implement with prevention:**
- Implement the fix.
- Add/adjust the smallest useful prevention coverage in the same commit:
  - Bugs: regression tests when feasible (prefer red→green).
  - Security: security tests/checks/policies and hardening when feasible.
  - UX/UI: UI tests/accessibility checks/scenario updates when feasible.

**Quality gate:**

Run quality checks directly (do not invoke `/quality-gate` or launch subagents):
1. Detect and run the project's formatter in check mode
2. Detect and run the project's linter
3. Detect and run the project's test runner
4. Detect and run the project's build command

Fix any failures before proceeding.

**Update artifact** (mandatory, same commit):
- Remove the fixed issue row from the artifact.

**Deferring an issue:**

If an issue cannot be fixed because it requires design discussion, user input, architectural changes, or has insufficient evidence:
- Do NOT remove the row from the artifact.
- Append a `**DEFERRED YYYY-MM-DD**:` note to the issue's notes/evidence/reasoning column explaining WHY it was deferred and WHAT is needed to unblock it.
- Continue immediately to the next issue — never stop the loop for a deferral.

**Commit** (mandatory):
- Stage only the fix + prevention + artifact update.
- Create one commit following Conventional Commits: `fix(<area>): <short description>`
- Do not include plan-internal identifiers in the commit message.
- Do not push unless explicitly asked.

### 4. Completion

When all open issues for the selected type are resolved (or marked with data requests):

- Run a final quality check pass (format, lint, test, build) directly via bash.
- Report:
  - Issues fixed (by area + summary)
  - Commits created (SHA + short message)
  - Issues deferred with reason (design decision needed, user input required, etc.)
  - Remaining `NEEDS_REPRO` / `NEEDS_VALIDATION` / `NEEDS_EVIDENCE` items and exact data needed

## Shared Scales

**Severity** (highest to lowest): Blocker · Very High · High · Normal · Minor

**Priority** (highest to lowest): Very High · High · Medium · Low · Very Low

**Fix Complexity**: Trivial · Easy · Challenging · Difficult · Very Difficult

## Output

Issues fixed with prevention improvements. Updated issue artifact with fixed rows removed.

## Next Step

`/quality-gate` -- Final verification, `/merge-to-trunk` -- Merge fix branch, or `/audit-codebase` -- Re-audit for release readiness.
