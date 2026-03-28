---
name: remediate-issues
description: Fix all discovered issues in priority order
disable-model-invocation: true
---

# Remediate Issues (Orchestrator)

You guide the user through fixing all discovered issues across all issue tracks, using parallel subagents for independent code areas when possible.

## Role

You are a senior software engineer coordinating a structured remediation pass. You analyze issues for parallelization opportunities, fix security issues first (compliance/safety implications), then bugs, then UX/UI issues. You provide checkpoints between tracks and ensure quality gates pass throughout.

## Prerequisites

- At least one issue artifact exists in `.claude/artifacts/ops/`:
  - `bug-list.md`
  - `security-issue-list.md`
  - `ux-ui-issue-list.md`
- A clean, green trunk baseline

## Procedure

### 1. Confirm Remediation Scope

- Read all three issue artifacts to understand the full picture.
- Confirm with the user: all open issues vs selected tracks/areas.
- Note any release target or timeline constraints.

### 2. Analyze and Group Issues

For each issue across all three artifacts:
- Note the `area` column (code module/directory)
- Estimate which files would likely be touched

Group issues into area-based batches:
- Issues in the same area → same batch (shared file context = fewer tokens, faster fixes)
- Issues in adjacent areas with likely shared files → same batch (avoid conflicts)

Classify batches:
- **Independent** (no file overlap between batches) → can run as parallel subagents
- **Overlapping** (shared files between batches) → merge into one batch, run sequentially

Present the grouping to the user:
- Number of issues across number of independent code areas
- Batch breakdown: [area: N issues] per batch
- Which batches can run in parallel vs must be sequential
- User confirms or overrides to force sequential mode

### 3. Launch All Fixes

**CRITICAL: Maximize concurrency across ALL tracks, not just within a single track.** The grouping in step 2 already identifies independent batches by code area — batches that don't share files can run concurrently regardless of whether they contain security, bug, or UX/UI issues.

Launch ALL independent batches in a SINGLE message using the Agent tool:
- One `issue-fixer` subagent per independent batch
- `subagent_type: issue-fixer`
- `isolation: worktree` (each gets its own isolated git worktree)
- Task prompt contains: issue type(s), area scope, filtered issue list for that batch
- A batch may contain issues from multiple tracks (security + bugs + UX/UI) if they touch the same area

Example: if you have 6 independent batches across all 3 tracks, launch all 6 as Agent subagents in one message. They all run concurrently.

**Ordering within a batch**: If a single batch contains issues from multiple tracks, the subagent should fix them in priority order: security first, then bugs, then UX/UI.

**If ALL issues overlap into a single batch** (no parallelism possible):
Fix inline sequentially: security → bugs → UX/UI.

### 4. Integrate Fixes

Once all subagents complete:
- Stash any working directory changes
- Remove worktrees to unlock branches
- Rebase each branch onto main in dependency order (independent branches in any order)
- Fast-forward merge (`git merge --ff-only`) — never use `--no-ff`
- Result: linear commit history, no merge commits
- If rebase conflicts: stop and report (should be rare given area independence)
- Clean up merged branches and restore stash

### 5. Checkpoint

Report per track:
- Issues fixed (count) by track (security / bugs / UX/UI)
- Issues deferred (count) with reasons (design decisions, user input, architectural changes)
- Remaining issues by severity
- Any blockers or missing data

### 6. Final Quality Gate

Run the full quality check suite directly (format, lint, test, build) and fix any failures.

### 7. Present Summary

Report:
- What was fixed by track (security / bugs / UX/UI)
- Commits created (SHA + short message)
- Issues deferred by track + reason (each annotated with `DEFERRED` date and note in artifact)
- Remaining issues by track + severity
- Explicit unresolved data requests (`NEEDS_REPRO` / `NEEDS_VALIDATION` / `NEEDS_EVIDENCE`)
- Recommended release status: `GO` | `GO WITH RISKS` | `NO-GO`

## Output

- Issues fixed across all tracks with prevention improvements
- Updated issue artifacts with fixed rows removed
- Final quality gate status

## Next Step

`/audit-codebase` -- Re-audit for verification, or `/merge-to-trunk` -- Merge fix branch to trunk.
