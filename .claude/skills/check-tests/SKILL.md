---
name: check-tests
description: Run test suite and verify correctness
user-invocable: false
allowed-tools: Bash
---

# Check Tests

You run the test suite to verify code correctness.

## Context

You will be provided with:
- Project root directory
- Test framework configuration (if detectable)
- Test coverage requirements (if specified)

## Procedure

1. **Detect test framework**

Check for testing configuration in the project:
- `package.json` (Jest, Vitest, Mocha, etc.)
- `pytest.ini`, `pyproject.toml`, `setup.py` (pytest)
- `Cargo.toml` (cargo test)
- `go.mod` (go test)
- Other project-specific test frameworks

2. **Determine test command**

Based on detected configuration, determine the appropriate command:

**JavaScript/TypeScript**:
- If Jest: `npm test` or `npx jest`
- If Vitest: `npm test` or `npx vitest run`
- If Mocha: `npm test`
- Fallback: Ask user for test command

**Python**:
- If pytest: `pytest` or `python -m pytest`
- If unittest: `python -m unittest discover`
- Fallback: Ask user for test command

**Rust**:
- `cargo test`

**Go**:
- `go test ./...`

**Other**:
- Ask user: "What command runs your project's tests?"

3. **Run tests**

Execute the test command:
- Capture output
- Count passed/failed tests
- Identify test failures
- Measure execution time

4. **Handle failures**

If tests fail:
- Report which tests failed
- Show failure messages
- Suggest debugging steps
- Ask if you should re-run with verbose output

## Output

Return a structured object to the parent workflow:

```yaml
test_check:
  status: pass | fail | skipped
  framework: <detected test framework or "manual">
  command: <command that was run>
  results:
    passed: <number>
    failed: <number>
    skipped: <number>
    duration_seconds: <number>
  failures:
    - test: <test name>
      file: <path>
      error: <error message>
  suggestion: <what to do next>
```

## Principles

- **Tech-stack agnostic**: Detect the test framework, don't prescribe one
- **Fast feedback**: Prefer fast test commands for local development
- **Clear reporting**: Show what failed, not just that it failed

## Example

**Input**: Python project with pytest, some failures

**Output**:
```yaml
test_check:
  status: fail
  framework: pytest
  command: pytest
  results:
    passed: 38
    failed: 2
    skipped: 1
    duration_seconds: 15.7
  failures:
    - test: test_payment_processing
      file: tests/test_payment.py
      error: AssertionError: Expected 200, got 500
    - test: test_user_authentication
      file: tests/test_auth.py
      error: AssertionError: User not authenticated
  suggestion: "Run 'pytest -v' to see detailed failure output, or 'pytest <file>::<test>' to run specific failing tests."
```
