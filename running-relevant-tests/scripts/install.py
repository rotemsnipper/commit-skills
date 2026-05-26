#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 8)
SCRIPT_DIR = Path(__file__).resolve().parent
RUN_SCRIPT = SCRIPT_DIR / "run_relevant_tests.py"


def fail(msg):
    print(f"✘ {msg}", file=sys.stderr)
    sys.exit(1)


def detect_runner(project_root):
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        if "[tool.pytest.ini_options]" in content:
            return "pytest"

    if (project_root / "manage.py").exists():
        return "django"

    try:
        import pytest  # noqa: F401
        return "pytest"
    except ImportError:
        pass

    return "unittest"


def check_importable(module):
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
    )
    return result.returncode == 0


def prompt_mode():
    print()
    print("How would you like running-relevant-tests to run?")
    print("1. Automatic — blocks commit/push via pre-commit hooks (default)")
    print("2. Manual    — run via make test-staged / make test-push")
    print("3. CI only   — GitHub Actions on push, no local friction")
    choice = input("Press Enter for default [1]: ").strip()
    if choice == "" or choice == "1":
        return 1
    if choice == "2":
        return 2
    if choice == "3":
        return 3
    print("Invalid choice, using default [1]")
    return 1


def configure_mode_1(project_root):
    if not check_importable("pre_commit"):
        fail("pre-commit is not installed. Run: pip install pre-commit")

    config_path = project_root / ".pre-commit-config.yaml"
    hook_block = (
        "\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: running-relevant-tests-commit\n"
        "        name: Run relevant tests (commit)\n"
        f"        entry: python {RUN_SCRIPT} --mode commit\n"
        "        language: python\n"
        "        types: [python]\n"
        "        pass_filenames: false\n"
        "        stages: [pre-commit]\n"
        "      - id: running-relevant-tests-push\n"
        "        name: Run relevant tests (push)\n"
        f"        entry: python {RUN_SCRIPT} --mode push\n"
        "        language: python\n"
        "        types: [python]\n"
        "        pass_filenames: false\n"
        "        stages: [pre-push]\n"
    )

    if config_path.exists():
        existing = config_path.read_text(encoding="utf-8")
        if "running-relevant-tests" in existing:
            print("  ⚠ running-relevant-tests hooks already present in .pre-commit-config.yaml — skipping append")
        else:
            if "pytest" in existing:
                print("  ⚠ Existing pytest hook detected in .pre-commit-config.yaml — verify there is no conflict")
            config_path.write_text(existing.rstrip() + "\n" + hook_block, encoding="utf-8")
            print("  ✔ Appended hooks to .pre-commit-config.yaml")
    else:
        config_path.write_text("repos:" + hook_block, encoding="utf-8")
        print("  ✔ Created .pre-commit-config.yaml")

    subprocess.run(
        ["pre-commit", "install", "--hook-type", "pre-commit", "--hook-type", "pre-push"],
        cwd=project_root,
        check=True,
    )
    print("  ✔ pre-commit hooks installed")


def configure_mode_2(project_root):
    makefile_path = project_root / "Makefile"
    targets = (
        "\ntest-staged:\n"
        f"\tpython {RUN_SCRIPT} --mode commit\n"
        "\ntest-push:\n"
        f"\tpython {RUN_SCRIPT} --mode push\n"
    )

    if makefile_path.exists():
        existing = makefile_path.read_text(encoding="utf-8")
        if "test-staged" in existing or "test-push" in existing:
            print("  ⚠ test-staged / test-push targets already present in Makefile — skipping append")
        else:
            makefile_path.write_text(existing.rstrip() + "\n" + targets, encoding="utf-8")
            print("  ✔ Appended targets to Makefile")
    else:
        makefile_path.write_text(targets.lstrip(), encoding="utf-8")
        print("  ✔ Created Makefile with test-staged and test-push targets")


def configure_mode_3(project_root):
    workflow_dir = project_root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    workflow_path = workflow_dir / "running-relevant-tests.yml"
    content = (
        "name: running-relevant-tests\n"
        "\n"
        "on: [push]\n"
        "\n"
        "jobs:\n"
        "  test:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "        with:\n"
        "          fetch-depth: 0\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version: '3.x'\n"
        "      - run: python running-relevant-tests/scripts/run_relevant_tests.py --mode push\n"
    )
    workflow_path.write_text(content, encoding="utf-8")
    print("  ✔ Created .github/workflows/running-relevant-tests.yml")


def scaffold_mapping(project_root, runner):
    mapping_path = project_root / "test_mapping.json"
    if mapping_path.exists():
        print("  ✔ test_mapping.json already exists — skipping scaffold")
        return
    mapping = {"_runner": runner, "_src_root": "src/", "_test_root": "tests/"}
    mapping_path.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    print("  ✔ Created test_mapping.json")


def main():
    if sys.version_info < MIN_PYTHON:
        fail(f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required (found {sys.version})")

    project_root = Path.cwd()
    print("running-relevant-tests installer")
    print("=================================")

    runner = detect_runner(project_root)
    print(f"✔ Test runner: {runner}")

    if runner == "pytest" and not check_importable("pytest"):
        fail("pytest is not installed. Run: pip install pytest")

    mode = prompt_mode()

    mode_names = {1: "Automatic (pre-commit hooks)", 2: "Manual (make targets)", 3: "CI only (GitHub Actions)"}
    print(f"\nConfiguring mode {mode}: {mode_names[mode]}")

    if mode == 1:
        configure_mode_1(project_root)
    elif mode == 2:
        configure_mode_2(project_root)
    else:
        configure_mode_3(project_root)

    scaffold_mapping(project_root, runner)

    print()
    print("Setup complete")
    print("--------------")
    print(f"  Runner:   {runner}")
    print(f"  Mode:     {mode_names[mode]}")
    print(f"  Mapping:  {project_root / 'test_mapping.json'}")
    print()
    print("  Reminders:")
    print("  • Unmapped files will warn but never block a commit or push")
    print("  • Re-run this installer anytime to switch enforcement modes")


if __name__ == "__main__":
    main()
