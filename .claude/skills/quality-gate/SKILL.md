---
name: quality-gate
description: Run format, lint, test, and build checks in parallel
---

# Quality Gate

## Role

You are a quality assurance coordinator orchestrating parallel quality checks. You launch sub-agents simultaneously, collect their results, and provide clear feedback about what passed and what failed.

## Prerequisites

- Project root directory
- Clean working tree (or changes ready to check)

## Procedure

### 1. Launch Parallel Checks

Launch the following sub-agents in parallel:

→ Run: `/check-format` — run code formatters
→ Run: `/check-lint` — run linters
→ Run: `/check-tests` — run test suite
→ Run: `/check-build` — run build process

Each sub-agent will detect appropriate tools from project configuration, run its check, and return a structured result.

### 2. Wait for All Checks

Wait for all 4 sub-agents to complete before proceeding.

Do not report results until all 4 have returned.

### 3. Aggregate Results

Combine the results from all 4 sub-agents into a single quality gate report:

```yaml
quality_gate:
  format: <from check-format>
  lint: <from check-lint>
  tests: <from check-tests>
  build: <from check-build>
  overall_status: pass | fail
```

### 4. Report Results

Present a clear summary to the user:

**If all passed**:
- Confirm all 4 checks passed
- Show execution time (for feedback on speed)
- Suggest proceeding (commit, merge, etc.)

**If any failed**:
- List which checks failed
- Show error details for failures
- Suggest fixes
- Ask if you should auto-fix (if safe)

### 5. Handle Failures

If any checks fail:
- Stop and report clearly
- Don't proceed to next step until fixed
- Provide actionable next steps
- Offer to auto-fix if safe (e.g., run formatter)

## Output

Return a structured object to the user:

```yaml
quality_gate:
  overall_status: pass | fail
  execution_time_seconds: <total time>
  checks:
    format:
      status: pass | fail | skipped
      tool: <tool name>
      <other details>
    lint:
      status: pass | fail | skipped
      tool: <tool name>
      <other details>
    tests:
      status: pass | fail | skipped
      framework: <framework name>
      <other details>
    build:
      status: pass | fail | skipped
      build_system: <build system name>
      <other details>
  next_steps: <what to do next>
```

## Example

```yaml
quality_gate:
  overall_status: fail
  execution_time_seconds: 38.5
  checks:
    format:
      status: fail
      tool: Prettier
      files_needing_formatting:
        - src/component.tsx
        - src/utils.ts
    lint:
      status: pass
      tool: ESLint
    tests:
      status: fail
      framework: pytest
      failed: 2
      failures:
        - test: test_payment
          error: AssertionError
    build:
      status: pass
      build_system: cargo
  next_steps: |
    Fix formatting: Run 'npm run format'
    Fix tests: Fix payment.test failures, then re-run pytest
```

## Next Step

If all checks pass, proceed with commit/merge. If any checks fail, fix issues and re-run.

