# commit-skills

A collection of Claude Code skills for git workflow automation. Each skill lives in its own directory and can be installed independently into any Python project.

---

## running-relevant-tests

**What it does:** This skill runs only the Python unit tests that are directly affected by your staged or pushed file changes. It never runs the full test suite. Given a set of changed source files, it maps each one to its corresponding test file — either through a mirror path convention or an explicit mapping — and runs only those tests.

**Why it exists:** Running the full test suite on every commit is slow and interrupts developer flow. In large projects, a full run can take minutes for a change that touches two files. This skill finds exactly what needs testing for your current change and runs only that, giving you fast, relevant feedback without the noise.

---

## How it works

### Test discovery

The primary strategy is **mirror path**: a changed source file at `src/services/billing.py` maps to `tests/services/test_billing.py`. This convention requires no configuration and works for the majority of changes. For shared utilities or files that don't follow the convention, you can add explicit entries to `test_mapping.json` and point a single source file at one or more test files.

### Unmapped files

If a changed file has no mirror path match and no explicit mapping, it is flagged as **unmapped**. The skill prints a warning with three options to resolve it: create the mirrored test file, add an explicit entry to `test_mapping.json`, or map the file to an empty array to acknowledge it as intentionally untested. Unmapped files never block a commit or fail silently — you always see them.

### conftest.py

If `conftest.py` is among the changed files, the skill runs the full test suite automatically. Because `conftest.py` defines fixtures and hooks that can affect any test in the project, there is no safe way to scope the run to a subset.

---

## Supported test runners

| Runner   | Detected by                                                             |
|----------|-------------------------------------------------------------------------|
| pytest   | `pyproject.toml` has `[tool.pytest.ini_options]` or `pytest` is importable |
| Django   | `manage.py` exists in project root                                      |
| unittest | Fallback — always available                                             |

---

## Enforcement modes

**Automatic (pre-commit hooks):** The skill hooks into your commit and push lifecycle via pre-commit. Relevant tests run before every commit (`--mode commit`) and before every push (`--mode push`). A test failure blocks the operation. Best for teams that want consistent enforcement with no manual steps.

**Manual (make targets):** The installer adds `test-staged` and `test-push` targets to your Makefile. You run them yourself when you want feedback. Nothing blocks automatically. Best for developers who prefer explicit control or are working in a repo where pre-commit is not already in use.

**CI only (GitHub Actions):** The installer creates a workflow file that runs the push-mode script on every push to the remote. No local hooks are installed. Best for teams that keep local development frictionless and rely on CI as the gate.

Re-run the installer anytime to switch modes.

---

## Installation

```bash
npx playbooks add skill <author>/commit-skills \
  --skill running-relevant-tests
```

Then run the interactive installer:

```bash
python running-relevant-tests/scripts/install.py
```

---

## Quick start after install

1. Run the installer and choose your enforcement mode
2. Verify `test_mapping.json` was created in your project root
3. Add explicit mappings for any shared utilities that don't follow the mirror convention
4. Make a change and commit — watch it run only the relevant tests

---

## Configuring test_mapping.json

The mapping file lives in your project root. Keys prefixed with `_` are reserved for configuration and are never treated as file mappings.

```json
{
  "_runner": "pytest",
  "_src_root": "src/",
  "_test_root": "tests/",

  "src/services/billing.py": "tests/services/test_billing.py",

  "src/utils/date_helpers.py": [
    "tests/services/test_billing.py",
    "tests/reports/test_invoices.py"
  ],

  "src/scripts/seed_data.py": []
}
```

- **Normal entry**: one source file maps to one test file
- **Shared utility**: one source file maps to an array of test files — all are run when the utility changes
- **Intentional empty array**: the file is acknowledged as having no tests; no warning is emitted
- **`_` prefixed keys**: treated as configuration, never as file mappings

---

## License

MIT
