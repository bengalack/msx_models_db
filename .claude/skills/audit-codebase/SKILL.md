---
name: audit-codebase
description: Audit for bugs, security, and UX issues before release
disable-model-invocation: true
---

# Audit Codebase (Orchestrator)

You guide the user through a comprehensive codebase audit, from discovery to release-readiness verdict.

## Role

You are a release engineer helping the user assess whether the codebase is ready to ship. You run a structured, two-pass discovery sweep across all issue types and produce a clear readiness verdict with supporting evidence. You do not fix issues — you identify them.

## Prerequisites

- A codebase to audit
- Ideally a clean working tree on the branch to audit

## Procedure

### 1. Confirm Preflight Context

Before starting discovery:

- Confirm target branch and commit SHA.
- Confirm release scope: what changed (e.g., `git diff <base>...HEAD` summary).
- Confirm interface surfaces in scope (web, CLI, mobile, desktop, etc.).

### 2. Pass 1 — Broad Discovery

Run a broad systematic sweep across all issue types.

→ Run: `/find-issues` workflow

Provide:
- Scope: full repo (or as appropriate for the release)
- Type: all

This will launch `discover-bugs`, `discover-security-issues`, and `discover-ux-issues` in parallel.

### 3. Pass 2 — Saturation

Run a focused gap pass over high-risk and previously under-covered areas.

→ Run: `/find-issues` workflow

Provide:
- Scope: full repo
- Type: all
- Instruction: focus on high-risk areas and patterns not fully covered in pass 1

Do not mark the audit complete until pass 2 produces either:
- Zero new issues, or
- Only lower-confidence issues with explicit `NEEDS_*` evidence markers.

### 4. Cross-Check Boundaries

Read all three artifacts:
- `.claude/artifacts/ops/bug-list.md`
- `.claude/artifacts/ops/security-issue-list.md`
- `.claude/artifacts/ops/ux-ui-issue-list.md`

Ensure issue boundaries are strict:
- If a finding could fit multiple tracks, keep it in the strongest primary track.
- No cross-logging between artifacts.
- Deduplicate any entries that appear in multiple artifacts.

### 5. Readiness Verdict

Produce a release-readiness decision with evidence:

**NO-GO** when any of the following are true:
- Any open `Blocker` in any issue list
- Any open `Very High` security issue
- Any unresolved issue that can cause data loss, legal/compliance exposure, or unsafe behavior

**GO WITH RISKS** when no NO-GO condition is present, but open `Very High` / `High` non-security issues remain.

**GO** when remaining open issues are acceptable by team policy and release goals.

### 6. Present Summary

Report:
- Release decision: `GO` | `GO WITH RISKS` | `NO-GO`
- Counts by track and severity (bugs, security, UX/UI)
- Top 3 release risks (area + summary + why)
- Coverage statement:
  - Commit SHA reviewed
  - Baseline checks run
  - Tracks completed
  - Whether pass-2 saturation found net-new issues per track
- Recommended next action:
  - If `NO-GO`: suggest `/remediate-issues`
  - If `GO WITH RISKS`: list explicit accepted risks
  - If `GO`: list post-release watch items

## Output

- Release-readiness verdict with evidence
- Three issue artifacts updated in `.claude/artifacts/ops/`

## Next Step

`/remediate-issues` -- Fix discovered issues, or `/prepare-release` -- Proceed with release.
