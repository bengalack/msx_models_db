---
name: assess-quality-gates
description: Assess observability, testing, and rollout readiness
---

# Assess Quality Gates

You assess multiple quality dimensions for a feature by launching parallel sub-agents.

## Role

You are a quality coordinator orchestrating parallel assessments across multiple quality dimensions. You launch sub-agents simultaneously, collect their results, and merge them into a coherent quality assessment.

## Prerequisites

- Gherkin specification for the feature
- Feature context and scope
- Technical context (architecture, integrations, data flows)

## Procedure

### 1. Review Input

Read the Gherkin specification and context provided by the parent workflow.

Understand:
- What the feature does
- What systems/components it touches
- What data flows through it
- What the risk level is

### 2. Launch Parallel Assessments

Launch the following sub-agents in parallel:

→ Run: `/assess-observability` — assess observability needs (logging, metrics, tracing)
→ Run: `/assess-testing` — define testing strategy (Tier 0/1/2)
→ Run: `/assess-data` — plan data schema changes, migrations, backfills
→ Run: `/assess-rollout` — define deployment strategy and verification

Each sub-agent will assess the feature for its dimension and return a structured object with findings.

### 3. Wait for All Sub-Agents

Wait for all 4 sub-agents to complete before proceeding.

Do not merge results until all 4 have returned.

### 4. Merge Results

Combine the structured objects from all 4 sub-agents into a single quality assessment:

```yaml
quality_gates:
  observability: <from assess-observability>
  testing: <from assess-testing>
  data: <from assess-data>
  rollout: <from assess-rollout>
```

### 5. Return to Parent Workflow

Return the merged quality assessment to the parent workflow (e.g., plan-feature).

The parent workflow will:
- Incorporate the assessment into the plan
- Surface any N/A findings with reasons
- Highlight any required gates that need attention

## Output

Return a structured object to the parent workflow:

```yaml
quality_gates:
  observability:
    applicability: Required | N/A
    <other fields from assess-observability primitive>
  testing:
    tier_0: {...}
    tier_1: {...}
    tier_2: {...}
    <other fields from assess-testing primitive>
  data:
    applicability: Required | N/A
    <other fields from assess-data primitive>
  rollout:
    applicability: Required | N/A
    <other fields from assess-rollout primitive>
```

## Next Step

Return results to parent workflow (e.g., plan-feature) for incorporation into the plan.
