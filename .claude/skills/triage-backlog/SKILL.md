---
name: triage-backlog
description: Reprioritize backlog to reflect current state
---

# Triage Backlog

## Role

You are a product-minded advisor helping the user triage and reprioritize the backlog. You keep it a living document that reflects both upcoming work and what is already in the product. You optimize for clarity and actionability.

## Prerequisites

- `.claude/artifacts/planning/product-backlog.md` exists and has content
- `.claude/artifacts/planning/product-requirements.md` exists (if available)
- `.claude/artifacts/decisions/decision-log.md` exists (if available)
- `.claude/artifacts/decisions/open-questions.md` exists (if available)

## Procedure

### 1. Check for Blockers

Read `.claude/artifacts/decisions/open-questions.md`. If any unchecked `[Blocking]` item affects backlog priority or scope, stop and ask the user for an answer before proceeding.

### 2. Read the Current Backlog

Read `.claude/artifacts/planning/product-backlog.md` in full.

### 3. Ask Prioritization Questions (max 3)

Ask a short batch of questions tailored to the actual branches implied by this backlog. Use these as themes (not fixed questions):

- **Outcome to optimize for** -- what "better" means right now
- **Sequencing/prerequisite constraints** -- ordering dependencies that should affect priority (not timelines)
- **Non-timeline constraints** -- compliance, security, operational limits, infrastructure considerations, budget constraints

Guidelines:
- When you can offer 3-5 mutually exclusive options derived from the backlog's actual items, present them as choices.
- Always include "Write your own answer" and "Can't answer / N/A" as options.
- Derive option text from the user's backlog language.

### 4. Triage and Rewrite the Backlog

Based on the user's answers, rewrite the backlog so it stays clean and actionable:

- Keep these top-level buckets (required, in this order):
  - `Now / Next`
  - `Later`
  - `Inbox (untriaged)`
  - `In product (shipped)`
- Ensure every item appears in exactly one bucket.
- Promote a small number of inbox items into `Now / Next` or `Later` if they are clear.
- Rewrite unclear titles into plain, user-facing language.
- Keep `Now / Next` intentionally short and ordered.
- `In product (shipped)` contains plain capability names only (no dates, versions, or metadata).

### 5. Write the Updated Backlog

Write the updated backlog to `.claude/artifacts/planning/product-backlog.md`.

## Output

Updated `.claude/artifacts/planning/product-backlog.md`

## Next Step

`/pick-feature` -- Select the next feature to implement from the reprioritized backlog.
