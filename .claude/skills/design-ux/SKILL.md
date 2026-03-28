---
name: design-ux
description: Establish UX guardrails and interaction patterns
---

# Design UX Guide

## Role

You are a UX designer who can design across web, mobile, desktop, TUI, and CLI interfaces. Your focus is to establish clear UX guardrails -- visual direction, interaction patterns, and conventions. Reduce interface entropy by defining reusable rules. Adapt guidance to the actual interface surfaces in scope. Avoid pixel-perfect spec work when high-level guardrails are sufficient.

## Prerequisites

- `.claude/artifacts/project/project-meta.md` exists.
- `.claude/artifacts/planning/problem-description.md` exists.
- `.claude/artifacts/planning/product-requirements.md` exists.
- `.claude/artifacts/planning/risk-assumption-review.md` exists.
- `.claude/artifacts/decisions/decision-log.md` exists.
- `.claude/artifacts/decisions/open-questions.md` exists.

If any prerequisite is missing, tell the user which artifact is needed and which skill to run first.

## UX Applicability Gate (Run First)

Before doing any UX work, determine whether the project has any user-facing interface surface: Web, Mobile, Desktop, TUI, or CLI.

**If no user-facing interface exists** (e.g., pure library, backend-only service, batch job, data pipeline):
1. Do NOT produce the UX artifact.
2. Append a row to `.claude/artifacts/decisions/decision-log.md`:
   - Date: today
   - Decision: Skip UX design guide (no user-facing interface)
   - Why: No UI surfaces are in-scope
   - Tradeoff: Less UX guidance if UI is added later; revisit UX at that point
3. Tell the user: "UX design guide skipped -- no user-facing interface in scope. Run `/design-technical` to continue."
4. Stop here.

**If a user-facing interface exists**, continue with the procedure below.

## Procedure

### 1. Review Artifacts and Check Open Questions

Read all prerequisite artifacts. Check `.claude/artifacts/decisions/open-questions.md` for any `[Blocking]` items that affect `ux-design-guide.md`. If blocking questions exist, surface them and resolve before proceeding.

### 2. Collect Visual References

Ask the user for 3-5 visual references that match the intended look and feel. Accept:
- Websites or product pages (URLs)
- Design system documentation
- Screenshots or images
- CLI/TUI tools (name + description)
- A short textual description of the desired direction

Examples of textual directions:
- "Light Nordic design with ample whitespace, muted neutrals, minimal borders"
- "Dark and gloomy with bold red accents, high contrast typography"
- "Warm editorial: off-white paper background, serif headings, generous line height"

If the user cannot provide references, ask them to pick a direction: Minimal / Editorial / Playful / Enterprise / Retro / Luxury.

### 3. Clarify Design Decisions

Ask questions (no more than 3 per turn) about:
- Primary interface surfaces
- Brand personality and visual tone
- Density preferences (compact vs. spacious)
- Target users and their context
- Accessibility expectations
- Input modalities: Keyboard-only / Keyboard+Mouse / Touch / Mixed
- Offline/latency constraints

Do NOT assume UI toolkits or libraries unless already decided.

### 4. Record Decisions

Append any new design decisions to `.claude/artifacts/decisions/decision-log.md`.

### 5. Write the Artifact

Write `.claude/artifacts/planning/ux-design-guide.md` using this exact structure:

```md
# UX Design Guide: <Project Name>

## Metadata
- Date: YYYY-MM-DD
- Related:
  - PRD: .claude/artifacts/planning/product-requirements.md

## Visual References
- Reference 1: <URL or description>
- Reference 2: <URL or description>
- Reference 3: <URL or description>
- Reference 4: <optional>
- Reference 5: <optional>
- Textual direction: <optional>

## Design Principles
- <principle>

## Interface Surfaces
- Surfaces: Web | Mobile | Desktop | TUI | CLI
- Primary surface: <one>
- Input modalities: Keyboard-only | Keyboard+Mouse | Touch | Mixed

## Accessibility
- Target: WCAG 2.1 AA | WCAG 2.2 AA | Other
- Keyboard: Required | Optional
- Color contrast: Required | Optional

## Typography
- Font families:
  - Sans: <name>
  - Serif: <optional>
  - Mono: <optional>
- Type scale:
  - H1: <size/weight/line-height>
  - H2: <size/weight/line-height>
  - Body: <size/weight/line-height>
- Usage rules: <short>

## Color System
- Brand colors:
  - Primary: <hex>
  - Secondary: <hex>
- Semantic colors:
  - Success: <hex>
  - Warning: <hex>
  - Danger: <hex>
  - Info: <hex>
- Neutrals:
  - Background: <hex>
  - Surface: <hex>
  - Text: <hex>

## Layout Rules
- Layout model: Grid/container | Screen-based | Command-driven | Other
- Spacing scale: <e.g. 4, 8, 12, 16, 24, 32>
- Density: Compact | Comfortable | Spacious

## Components
- Screens/views: <key screens + purpose>
- Navigation model: <pattern>
- Data entry: <inputs/forms rules or ->
- Data display: <tables/lists/log output rules or ->
- Feedback: <loading/success/error patterns>
- Confirmations/dialogs: <pattern or ->
- Empty states: <pattern or ->

## CLI/TUI Conventions (If Applicable)
- Command surface: <commands/subcommands or screens>
- Flags/options style: <rules>
- Output formats: Human-readable | JSON | Both
- Errors and exit codes: <rules>
- Help/usage style: <rules>

## Interaction Patterns
- Loading states: <short>
- Errors: <short>
- Confirmations: <short>
- Forms: <validation rules>

## Content Style
- Voice: <short>
- Terminology: <short>

## UI Definition of Done
- <check>
```

## Output

`.claude/artifacts/planning/ux-design-guide.md` (or skipped if no user-facing interface)

## Next Step

`/design-technical` -- Create the technical design blueprint.
