---
name: running-relevant-tests
description: Runs only the Python unit tests affected by staged or pushed file changes, never the full suite. Trigger on: Python file edits, staged files, commit/push workflows, test mapping configuration, or requests to install running-relevant-tests.
---

## When to read references/install-logic.md

Read this file when the user:
- Asks to install or set up running-relevant-tests
- Asks how enforcement modes work or wants to switch modes
- Asks about test runner detection or dependency requirements
- Asks about test_mapping.json scaffolding or initial setup
- Re-runs the installer

## When to read references/execution-logic.md

Read this file when the user:
- Triggers a commit or push and tests need to run
- Asks how changed files are resolved to test files
- Asks about mirror path strategy or test_mapping.json lookups
- Asks how edge cases (detached HEAD, new branch, renames) are handled
- Asks about summary output or test run commands

## Unmapped file behavior

When a changed `.py` file has no mapped test:
- **Always warn** with actionable next steps (three options)
- **Never block** the commit or push
- **Never fail silently** — every unmapped file must appear in the summary

## Never do

- Run the full test suite unless `conftest.py` changed
- Block a commit or push due to an unmapped file
- Modify `test_mapping.json` without explicit user instruction
