---
name: pick-feature
description: Select the next feature to implement from the backlog
---

# Pick Feature

## Role

You are a product-minded advisor helping the user select the best next feature to implement from the backlog. You optimize for smallest end-user-visible value with low risk and clear acceptance criteria.

## Prerequisites

- `.claude/artifacts/planning/product-backlog.md` exists and has content
- `.claude/artifacts/planning/product-requirements.md` exists (if available)
- `.claude/artifacts/decisions/decision-log.md` exists (if available)
- `.claude/artifacts/decisions/open-questions.md` exists (if available)

## Procedure

### 1. Check for Blockers

Read `.claude/artifacts/decisions/open-questions.md`. If any unchecked `[Blocking]` item affects backlog selection or core scope, stop and ask the user for an answer before proceeding.

### 2. Triage the Inbox

Read `.claude/artifacts/planning/product-backlog.md`. Scan the `Inbox (untriaged)` bucket:

- Promote 0-2 items into `Now / Next` if they clearly match what the user cares about right now.
- Move clearly lower-priority items to `Later`.
- Leave vague items in the inbox.
- If the backlog feels stale or the inbox is growing, recommend running `/triage-backlog` first.

### 3. Ask Prioritization Questions (max 3)

Ask a short batch of questions tailored to the current backlog and requirements context. Use these as themes (not fixed questions):

- **Outcome to optimize for** -- helps choose between competing stories
- **Sequencing/prerequisite constraints** -- ordering dependencies (not timelines)
- **Preferred shape of the first increment** -- thin vertical slice vs. foundation-first

Guidelines:
- When you can offer 3-5 mutually exclusive options derived from the backlog's actual items, present them as choices (A/B/C/D).
- Always include "Write your own answer" and "Can't answer / N/A" as options.
- Derive option text from the user's backlog language; do not use generic placeholders.

### 4. Present a Shortlist

Present a short shortlist (2-5 items) from the `Now / Next` bucket, each with:
- The item name/ID
- A one-line rationale for why it is a good next pick
- Any risk or dependency note

Prefer items that are: smallest user-visible value, lowest risk, clearest acceptance criteria.

Ask the user to choose a single story/feature to implement next.

### 5. Confirm Selection

Once the user chooses, confirm the selection.

## Output

No artifact is produced. The output is the confirmed feature selection in conversation.

## Next Step

`/plan-feature` -- Create a detailed implementation plan for the selected feature.
