# Execution Logic

Entry point: `python running-relevant-tests/scripts/run_relevant_tests.py`
Required argument: `--mode commit` or `--mode push`

## Load config from test_mapping.json

| Key | Default |
|---|---|
| `_runner` | `pytest` |
| `_src_root` | `src/` |
| `_test_root` | `tests/` |

Keys prefixed with `_` are config; skip them during file resolution.

## get_changed_files(mode)

**commit mode:**
```
git diff --cached --name-only --diff-filter=ACMR
```

**push mode:**
```
git diff origin/<current-branch>...HEAD --name-only --diff-filter=ACMR
```

Edge cases:
- **New branch with no remote**: fall back to `git diff main...HEAD`; if `main` doesn't exist, try `master`
- **Detached HEAD**: print `ERROR: detached HEAD — cannot determine push range`, exit 0 (never block)
- **Renamed files**: `--diff-filter=ACMR` includes R (renamed); resolve to new filename from diff output

## find_related_tests(files)

For each `.py` file in changed files:

1. **Check test_mapping.json** for an explicit key matching the file path (skip `_` prefixed keys)
2. **Mirror path**: `<_src_root>/X/Y.py` → `<_test_root>/X/test_Y.py`
3. **conftest.py changed**: set flag `FULL_SUITE` — skip individual resolution

Resolution status per file:

| Status | Meaning |
|---|---|
| `FOUND` | Test file located via mapping or mirror |
| `UNMAPPED` | No mapping and no mirror file exists on disk |
| `INTENTIONAL` | Mapped to `[]` — acknowledged as untested |
| `FULL_SUITE` | `conftest.py` changed; run entire suite |

## print_summary

Print a table before running tests:

```
File                          Status     Test file
----------------------------  ---------  ---------------------------
src/services/billing.py       ✔ FOUND    tests/services/test_billing.py
src/utils/helpers.py          ✘ UNMAPPED —
src/config.py                 ✔ INTENT.  (intentionally untested)
```

Footer line: `Mapped: N  |  Unmapped: N  |  Intentional: N`

## UNMAPPED warning (actionable, never silent)

For each UNMAPPED file, print:

```
⚠ No test found for: src/utils/helpers.py
  Resolve by choosing one:
  a) Create the mirrored test file: tests/utils/test_helpers.py
  b) Add an explicit entry to test_mapping.json:
       "src/utils/helpers.py": "tests/utils/test_helpers.py"
  c) Acknowledge as intentionally untested:
       "src/utils/helpers.py": []
```

Do not block. Continue to run tests for all FOUND files.

## run_tests — commands by runner and mode

**pytest**
- commit: `pytest <files> -x --tb=short -q`
- push:   `pytest <files> --tb=short -q`
- FULL_SUITE: `pytest --tb=short -q`

**django**
- commit: `python manage.py test <dot.labels> --failfast`
- push:   `python manage.py test <dot.labels>`
- FULL_SUITE: `python manage.py test`

**unittest**
- commit: `python -m unittest <dot.modules> --failfast`
- push:   `python -m unittest <dot.modules>`
- FULL_SUITE: `python -m unittest discover`

Convert file paths to dot-notation module labels for django and unittest:
`tests/services/test_billing.py` → `tests.services.test_billing`

If the resolved test file list is empty (all INTENTIONAL or all UNMAPPED): print `No tests to run.` and exit 0.
