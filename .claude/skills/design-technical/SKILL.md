---
name: design-technical
description: Design architecture, components, and data flows
---

# Technical Design

## Role

You are a pragmatic solution architect. Your focus is to design a simple, evolvable system with clear boundaries and data flows. Prefer operational simplicity and minimize moving parts. Make tradeoffs explicit and record them. Choose a coherent tech stack and repo shape aligned with constraints. Avoid premature infrastructure and speculative complexity.

## Prerequisites

- `.claude/artifacts/project/project-meta.md` exists.
- `.claude/artifacts/planning/problem-description.md` exists.
- `.claude/artifacts/planning/product-requirements.md` exists.
- `.claude/artifacts/planning/risk-assumption-review.md` exists.
- `.claude/artifacts/decisions/decision-log.md` exists.
- `.claude/artifacts/decisions/open-questions.md` exists.
- `.claude/artifacts/planning/ux-design-guide.md` -- optional. If the project has no user-facing interface and the UX step was skipped, proceed without it.

If required prerequisites are missing, tell the user which artifact is needed and which skill to run first.

## Procedure

### 1. Review All Artifacts

Read all prerequisite artifacts. Check `.claude/artifacts/decisions/open-questions.md` for any `[Blocking]` items that affect `technical-design.md`. If blocking questions exist, surface them and resolve before proceeding.

### 2. Ask Targeted Clarifications

Ask only the smallest set of questions needed (no more than 3 per turn) to lock:

- **System boundaries and key flows** -- what are the main components and how do they interact?
- **Data durability, integrity, and retention** -- what data matters and how is it protected?
- **External integrations and failure behavior** -- what external systems are involved?
- **Operational posture** -- hosting, environments, deployment frequency.
- **Team constraints** -- language familiarity, operational tolerance.
- **Repo conventions** -- commands and CI outline needed for implementation.

### 3. Set Global Posture

Define project-wide defaults (not per-feature):
- **Observability**: choose defaults for logging, metrics, and tracing.
- **Testing**: choose a pragmatic baseline and CI expectations.

These are starting points. Per-feature specifics are refined during implementation.

### 4. Record Decisions

Append all new or finalized decisions to `.claude/artifacts/decisions/decision-log.md` with date, decision, rationale, and tradeoff.

### 5. Write the Artifact

Write `.claude/artifacts/planning/technical-design.md` using this exact structure:

```md
# Technical Design: <Project Name>

## Metadata
- Date: YYYY-MM-DD
- Related:
  - PRD: .claude/artifacts/planning/product-requirements.md
  - Risk review: .claude/artifacts/planning/risk-assumption-review.md
  - Decision log: .claude/artifacts/decisions/decision-log.md
  - UX guide: .claude/artifacts/planning/ux-design-guide.md (if applicable)
  - Open questions: .claude/artifacts/decisions/open-questions.md

## System Shape
<1-2 paragraphs describing the overall shape>

## Domain Boundaries
- <domain>
  - Responsibilities: <short>
  - Owns Data: <yes/no + what>
  - External Interfaces: <APIs/events/files/manual>

## Components
- <component name>
  - Type: Service | Web App | Worker | Job | Library | External
  - Responsibilities: <short>
  - Depends On: <list or ->
  - Data Stores: <list or ->

## Key Flows
- <flow name>
  - Trigger: <what starts it>
  - Steps:
    1. <step>
    2. <step>
  - Data touched: <list>
  - Failure handling: <short>

## Data Model
- <entity name>
  - Purpose: <short>
  - Key fields: <comma-separated>
  - Relationships: <relationship notes>
  - Retention: <short>

## Integrity Strategy
- Invariants: <bullet list>
- Idempotency: <short>
- Concurrency: <short>

## Audit and Compliance
- Audit needs: <short>
- PII handling: <short>

## Integrations
- <system>
  - Direction: Inbound | Outbound
  - Interface: API | Webhook | File | Manual
  - Notes: <short>

## Technology Stack

### Backend
- Language/Runtime: <choice>
- Web toolkit: <choice>
- API style: REST | GraphQL | RPC
- Background jobs: <choice>

### Frontend (If Applicable)
- Approach: SPA | MPA | SSR | Static
- UI toolkit: <choice>
- Styling: <choice>

### Data
- Primary database: <choice>
- Migrations: <choice>
- Search/indexing: <choice or ->
- Caching: <choice or ->

### Infrastructure Posture
- Hosting: <choice>
- Environments: Local | Dev | Staging | Prod
- Deployment style: <choice>

### Observability
- Logging: <choice>
- Metrics: <choice>
- Tracing: <choice or ->

### Testing Posture
- Unit: <short>
- Integration: <short>
- E2E: <short>

## Repository & Delivery Conventions

### Repository Structure (Sketch)
<tree of key directories>

### Command Surface
- dev: <what it does>
- test: <what it does>
- lint: <what it does>
- build: <what it does>
- format: <optional>

### CI Outline
- Lint: <command>
- Typecheck: <command>
- Test: <command>
- Build: <command>
- Security checks: <optional>

### Environment Model
- Configuration sources: <.env/secret manager/etc>
- Required environment variables:
  - VAR_NAME: <purpose>

## Evolution Strategy
- Versioning approach: <short>
- Migration approach: <short>

## Known Tradeoffs
- <tradeoff>
  - Why chosen: <short>
  - Cost: <short>
```

## Output

`.claude/artifacts/planning/technical-design.md`

## Next Step

`/create-backlog` -- Translate the technical design into a prioritized product backlog.
