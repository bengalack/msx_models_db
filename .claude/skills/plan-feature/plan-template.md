# Plan: <Feature Name>

## Metadata
- Date: YYYY-MM-DD
- Backlog item: <epic/story name>
- Feature slug: <feature_slug>

## Context
- Intended outcome: <short>

## Functional Snapshot
- Problem: <1-2 sentences>
- Target user: <who + context>
- Success criteria (observable):
  - <outcome>
- Primary user flow:
  1. <step>
  2. <step>
- Alternate flows (optional):
  - <alt flow>
- Must never happen:
  - <unacceptable outcome>
- Key edge cases:
  - <edge case> -> <expected behavior>
- Business rules:
  - <rule>
- Integrations (if any):
  - <system> - <what data moves / what the user expects>
  - Failure behavior: <what happens when the dependency is down>
- Non-functional requirements:
  - Privacy/Security: <expectation>
  - Performance: <expectation>
  - Reliability: <expectation>
- Minimal viable increment (MVI): <smallest valuable version>
- Deferred:
  - <explicitly not in this feature>

## Executable Specification (Gherkin)

Feature: <short capability name>
  <1-2 sentence narrative>

  Scenario: <happy path>
    Given <precondition>
    When <action>
    Then <observable outcome>

  Scenario: <must never happen>
    Given <precondition>
    When <action>
    Then <unacceptable outcome is prevented>

  Scenario: <key edge case>
    Given <precondition>
    When <action>
    Then <expected behavior>

## Baseline Gate
- Start from a clean, green trunk. If not green, stop and fix first.
- Sync latest trunk before branching.
- Local feature branches for development.

## Architecture Fit
- Touch points: <key components/boundaries affected>
- Compatibility notes: <what must remain backward-compatible>

## Observability (Minimum Viable)
- Applicability: Required | N/A (Reason: <one line>)
- Failure modes:
  - <failure mode> -> <expected degraded behavior>
- Logs (structured): <events + key fields; no sensitive data>
- Signals/metrics: <1-3 key signals>

## Testing Strategy (Tier 0/1/2)
- Tier 0 (required): <unit/contract tests>
- Tier 1 (if applicable): <deterministic integration tests>
- Tier 2 (if applicable): <sandbox/third-party validation>

## Data and Migrations
- Applicability: N/A | Schema only | Backfill | Expand/contract
- Up migration: <approach>
- Down migration: <yes/no + why>
- Backfill plan: <if any>
- Rollback considerations: <what happens on revert>

## Rollout and Verify
- Applicability: Required | N/A (Reason: <one line>)
- Strategy: Feature flag | Canary | Staged | All-at-once
- Verify (smoke path): <2-6 steps>
- Signals to watch: <1-3>

## Cleanup Before Merge
- Remove: <temporary flags/debug logs/spike code/transitional scaffolding>
- If anything temporary remains: <decision log row + follow-up backlog item>
- Squash intermediate commits into logical commits
- Ensure all commits follow Conventional Commits
- Rebase onto trunk and merge with fast-forward only

## Definition of Done
- Gherkin specification is complete and current in the plan artifact
- Tier 0 green; Tier 1 green when applicable
- Observability requirements implemented (or explicitly N/A)
- Cleanup gate satisfied
- Backlog updated (shipped item moved to "In product (shipped)")

## Chunks
- <chunk name>
  - User value: <short>
  - Scope: <short>
  - Ship criteria: <short, testable>
  - Rollout notes: <flags/migrations/backfill or none>

## Relevant Files (Expected)
- `<path>` - <why>

## Notes
- Include tests where appropriate.
- Include any migrations, backfills, or feature flags explicitly.
- Prefer small, reviewable commits that map to chunks.
- Each chunk should deliver user value, be testable, and reduce risk.

## Assumptions
- <assumption made to proceed>

## Validation Script (Draft)
1. <step>
2. <step>

## Tasks
- [ ] T-001 Create and checkout a local branch (e.g. `feature/<feature_slug>`)

- [ ] Implement: <chunk name>
  - [ ] T-010 <leaf task completable in one commit>
  - [ ] T-011 <leaf task completable in one commit>
  - [ ] T-012 Tests: <what to add>

- [ ] Quality gate
  - [ ] T-900 Run formatters
  - [ ] T-901 Run linters
  - [ ] T-902 Run tests

- [ ] Merge to trunk
  - [ ] T-950 Squash intermediate commits into logical commits
  - [ ] T-951 Ensure all commits follow Conventional Commits
  - [ ] T-952 Rebase onto trunk and merge (fast-forward only)

## Open Questions
- <any non-blocking questions or none>
