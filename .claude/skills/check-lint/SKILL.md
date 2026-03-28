---
name: check-lint
description: Run linters and report violations
user-invocable: false
allowed-tools: Bash
---

# Check Lint

You run linters to verify code meets quality standards.

## Context

You will be provided with:
- Project root directory
- Linting tool configuration (if detectable)

## Procedure

1. **Detect linting tool**

Check for linting configuration in the project:
- `package.json` (ESLint, etc.)
- `.eslintrc.*` or `eslint.config.*`
- `pyproject.toml` (Ruff, Pylint, Flake8, etc.)
- `.rustfmt.toml` or `clippy.toml`
- `.golangci-lint.yml`
- Other project-specific linters

2. **Determine linting command**

Based on detected configuration, determine the appropriate command:

**JavaScript/TypeScript**:
- If ESLint: `npx eslint .` or `npm run lint`
- If Biome: `npx @biomejs/biome check .`
- Fallback: Ask user for linting command

**Python**:
- If Ruff: `ruff check .`
- If Pylint: `pylint <package>`
- If Flake8: `flake8 .`
- Fallback: Ask user for linting command

**Rust**:
- `cargo clippy -- -D warnings`

**Go**:
- `golangci-lint run` or `go vet ./...`

**Other**:
- Ask user: "What command runs your project's linter?"

3. **Run linter**

Execute the linting command:
- Capture output
- Count warnings/errors
- Identify severity levels

4. **Handle failures**

If linter fails:
- Report the number of issues
- Show sample errors (not all, if too many)
- Suggest fixes
- Ask if you should auto-fix (if safe)

## Output

Return a structured object to the parent workflow:

```yaml
lint_check:
  status: pass | fail | skipped
  tool: <detected linter name or "manual">
  command: <command that was run>
  issues:
    error_count: <number>
    warning_count: <number>
    sample_errors:
      - file: <path>
        line: <number>
        message: <error message>
        rule: <rule id>
  suggestion: <what to do next>
```

## Principles

- **Tech-stack agnostic**: Detect the linter, don't prescribe one
- **Pragmatic**: Show sample errors, not overwhelming output
- **Actionable**: Suggest next steps for fixing issues

## Example

**Input**: Python project with Ruff, some issues

**Output**:
```yaml
lint_check:
  status: fail
  tool: Ruff
  command: ruff check .
  issues:
    error_count: 3
    warning_count: 5
    sample_errors:
      - file: src/payment.py
        line: 42
        message: Unused variable `retry_count`
        rule: F841
      - file: src/user.py
        line: 15
        message: Missing docstring
        rule: D100
  suggestion: "Run 'ruff check --fix .' to auto-fix some issues, or fix manually and re-run."
```
