# Install Logic

Entry point: `python running-relevant-tests/scripts/install.py`
Re-runnable; re-running switches enforcement modes.

## Step 1 — Detect test runner

Check in order, stop at first match:
1. `pyproject.toml` contains `[tool.pytest.ini_options]` → `pytest`
2. `manage.py` exists in project root → `django`
3. `pytest` is importable (`import pytest`) → `pytest`
4. Fallback → `unittest`

Print: `✔ Test runner: <detected>`

## Step 2 — Check dependencies

- Python >= 3.8 required; print error and exit if not met
- If runner is `pytest`: verify `pytest` is installed; if not, print `pip install pytest` and exit
- If mode is hooks (chosen in step 3): verify `pre-commit` is installed; if not, print `pip install pre-commit` and exit
- Dependency check for pre-commit runs after mode selection, before configuration

## Step 3 — Interactive enforcement mode prompt

```
How would you like running-relevant-tests to run?
1. Automatic — blocks commit/push via pre-commit hooks (default)
2. Manual    — run via make test-staged / make test-push
3. CI only   — GitHub Actions on push, no local friction
Press Enter for default [1]:
```

## Step 4 — Configure by mode

**Mode 1 — Automatic (pre-commit hooks)**
- Append hook entries to `.pre-commit-config.yaml`, or create the file if absent
- Check for conflicting existing pytest hook entries; warn if found
- Run `pre-commit install --hook-type pre-commit --hook-type pre-push`
- Hook args: `--mode commit` for pre-commit, `--mode push` for pre-push

**Mode 2 — Manual (make targets)**
- Create or append to `Makefile`:
  - `test-staged`: calls `python <absolute-path>/run_relevant_tests.py --mode commit`
  - `test-push`: calls `python <absolute-path>/run_relevant_tests.py --mode push`
- Use absolute path to the script to avoid working-directory issues

**Mode 3 — CI only (GitHub Actions)**
- Create `.github/workflows/running-relevant-tests.yml`
- Trigger: `on: push`
- Job: run `python running-relevant-tests/scripts/run_relevant_tests.py --mode push`
- No local hooks installed

## Step 5 — Scaffold test_mapping.json

If `test_mapping.json` does not exist in project root, create it:

```json
{
  "_runner": "<detected>",
  "_src_root": "src/",
  "_test_root": "tests/"
}
```

If it already exists, do not overwrite it.

## Step 6 — Print completion summary

Print a summary that includes:
- Detected runner
- Chosen enforcement mode and what was configured
- Location of `test_mapping.json`
- Reminder: unmapped files warn but never block
- Reminder: re-run the installer anytime to switch modes
