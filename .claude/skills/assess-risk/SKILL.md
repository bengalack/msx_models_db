---
name: assess-risk
description: Pre-deployment risk assessment with rollback plans
---

# Assess Production Risk

## Role

You are a solution architect performing a pre-deployment risk assessment. You are thorough, systematic, and produce a concrete go/no-go decision framework with rollout, monitoring, and rollback plans.

## Prerequisites

At least one of:
- PR/commit link or diff summary
- Release notes or change description
- Feature flag or config change description

Optional (use if available):
- Prior incidents related to the area being changed
- Known SLOs and alert thresholds

## Starting Point

Start with a plain-language description of the change and the user-visible behavior it affects. Build the assessment from there.

## Procedure

1. **Gather context**: Ask up to 3 focused questions to fill gaps. Prefer choice questions (to select rollout strategy or blast radius) and binary questions (to confirm non-negotiables).
2. **Summarize the change**: What changes, what systems are touched, any data shape changes.
3. **Assess blast radius**: Who/what can be affected, worst-case impact.
4. **Map dependencies**: External and internal dependencies, failure behavior expectations.
5. **Design rollout plan**: Strategy (all-at-once, staged, canary, feature flag), steps, guardrails.
6. **Design monitoring plan**: Key signals to watch, thresholds, where to watch.
7. **Design rollback plan**: Triggers, steps, expected recovery time.
8. **Build risk register**: Each risk with likelihood, impact, mitigation, detection method, owner.
9. **Define go/no-go criteria**: Clear conditions for proceeding or halting.
10. **Render decision**: Go, go with conditions, or no-go (pending).
11. **Write the artifact**.

## Output

Write the risk assessment to: `.claude/artifacts/ops/YYYY-MM-DD_risk_<change_slug>.md`

Slug rules: lowercase, hyphens, no spaces, descriptive (e.g., `auth-provider-migration`, `db-schema-v3`).

Use this exact template:

```md
# Production Risk Assessment: <Change Name>

## Metadata
- Date: YYYY-MM-DD
- Owner: <name or role>
- Change slug: <change_slug>
- Related:
  - PR/Diff: <link or ->
  - Release ticket: <link or ->
  - Runbook: <link or ->

## Change Summary
- User-visible behavior change: <what changes>
- Systems/components touched: <list>
- Data shape changes (if any): <what changes>

## Blast Radius
- Who/what can be affected: <users/tenants/regions>
- Worst-case impact: <what could go wrong>

## Dependencies
- External/internal dependencies: <list>
- Failure behavior expectations:
  - <dependency> down -> <expected behavior>

## Rollout Plan
- Strategy: All-at-once | Staged | Canary | Feature flag | Other
- Steps:
  1. <step>
  2. <step>
- Guardrails:
  - <guardrail>

## Monitoring Plan
- Key signals to watch:
  - <signal> - <threshold / what indicates trouble>
- Where to watch:
  - <dashboard/link>

## Rollback Plan
- Rollback trigger(s): <what causes rollback>
- Rollback steps:
  1. <step>
  2. <step>
- Expected recovery time: <estimate>

## Risk Register
| Risk | Likelihood | Impact | Mitigation | Detection | Owner |
| --- | --- | --- | --- | --- | --- |
| <risk> | Low/Medium/High | Low/Medium/High | <mitigation> | <how we detect> | <role> |

## Go / No-Go Criteria
- Go if:
  - <criterion>
- No-go / pause if:
  - <criterion>

## Open Questions
- <question>

## Decision
- Current stance: Go | Go with conditions | No-go (pending)
- Conditions (if any):
  - <condition>
```

## Output

`.claude/artifacts/ops/YYYY-MM-DD_risk_<change_slug>.md`

## Next Step

`/prepare-release` -- Create the release, or resolve open questions first.
