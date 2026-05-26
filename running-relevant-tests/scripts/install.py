#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PYTHON = (3, 8)
SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"
RUN_SCRIPT = SCRIPT_DIR / "run_relevant_tests.py"
MODE_NAMES = {
    1: "Automatic (pre-commit hooks)",
    2: "Manual (make targets)",
    3: "CI only (GitHub Actions)",
}


def fail(msg):
    print(f"✘ {msg}", file=sys.stderr)
    sys.exit(1)


def detect_runner(project_root):
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            if "[tool.pytest.ini_options]" in pyproject.read_text(encoding="utf-8"):
                return "pytest"
        except OSError:
            pass
    if (project_root / "manage.py").exists():
        return "django"
    if subprocess.run([sys.executable, "-c", "import pytest"], capture_output=True).returncode == 0:
        return "pytest"
    return "unittest"


def check_importable(name):
    return (
        subprocess.run(
            [sys.executable, "-c", f"import {name}"], capture_output=True
        ).returncode
        == 0
    )


def detect_existing_mode(project_root):
    precommit = project_root / ".pre-commit-config.yaml"
    if precommit.exists():
        try:
            if "run_relevant_tests.py" in precommit.read_text(encoding="utf-8"):
                return 1
        except OSError:
            pass

    makefile = project_root / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text(encoding="utf-8")
            if "run_relevant_tests.py" in content and (
                "test-staged" in content or "test-push" in content
            ):
                return 2
        except OSError:
            pass

    if (project_root / ".github" / "workflows" / "running-relevant-tests.yml").exists():
        return 3

    return None


def prompt_mode():
    while True:
        print()
        print("How would you like running-relevant-tests to run?")
        print("1. Automatic — blocks commit/push via pre-commit hooks (default)")
        print("2. Manual    — run via make test-staged / make test-push")
        print("3. CI only   — GitHub Actions on push, no local friction")
        raw = input("Press Enter for default [1]: ").strip()
        if raw == "":
            return 1
        if raw in ("1", "2", "3"):
            return int(raw)
        print("  Invalid input. Enter 1, 2, or 3, or press Enter for the default.")


def _find_conflicting_hook(content):
    current_id = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("id:"):
            current_id = stripped[3:].strip().strip('"').strip("'")
        elif stripped.startswith("entry:"):
            entry_val = stripped[6:].strip()
            if "pytest" in entry_val or "run_relevant_tests" in entry_val:
                return current_id, entry_val
    return None, None


def configure_mode_1(project_root):
    if not check_importable("pre_commit"):
        fail("pre-commit is not installed. Run: pip install pre-commit")

    precommit_path = project_root / ".pre-commit-config.yaml"
    hook_entry = (
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

    if precommit_path.exists():
        content = precommit_path.read_text(encoding="utf-8")
        hook_id, entry_val = _find_conflicting_hook(content)
        if hook_id or entry_val:
            label = f"id: {hook_id}" if hook_id else entry_val
            fail(
                f"Conflicting hook found in .pre-commit-config.yaml ({label}).\n"
                "Remove it manually, then re-run install.py."
            )
        precommit_path.write_text(
            content.rstrip() + "\n  - repo: local\n    hooks:\n" + hook_entry,
            encoding="utf-8",
        )
        print("  ✔ Appended hooks to existing .pre-commit-config.yaml")
    else:
        asset = ASSETS_DIR / ".pre-commit-config.yaml"
        if asset.exists():
            raw = asset.read_text(encoding="utf-8").replace(
                "python running-relevant-tests/scripts/run_relevant_tests.py",
                f"python {RUN_SCRIPT}",
            )
            precommit_path.write_text(raw, encoding="utf-8")
        else:
            precommit_path.write_text(
                "repos:\n  - repo: local\n    hooks:\n" + hook_entry, encoding="utf-8"
            )
        print("  ✔ Created .pre-commit-config.yaml")

    subprocess.run(["pre-commit", "install"], cwd=project_root, check=True)
    subprocess.run(
        ["pre-commit", "install", "--hook-type", "pre-push"], cwd=project_root, check=True
    )
    print("  ✔ pre-commit hooks installed (commit + push)")


def configure_mode_2(project_root):
    makefile_path = project_root / "Makefile"
    targets = (
        "\ntest-staged:\n"
        f"\tpython {RUN_SCRIPT} --mode commit\n"
        "\ntest-push:\n"
        f"\tpython {RUN_SCRIPT} --mode push\n"
    )

    if makefile_path.exists():
        content = makefile_path.read_text(encoding="utf-8")
        conflicts = [t for t in ("test-staged", "test-push") if t in content]
        if conflicts:
            fail(
                f"Conflicting Makefile target(s) already exist: {', '.join(conflicts)}.\n"
                "Remove them manually, then re-run install.py."
            )
        makefile_path.write_text(content.rstrip() + "\n" + targets, encoding="utf-8")
        print("  ✔ Appended targets to existing Makefile")
    else:
        makefile_path.write_text(targets.lstrip(), encoding="utf-8")
        print("  ✔ Created Makefile with test-staged and test-push targets")


def configure_mode_3(project_root):
    wf_dir = project_root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "running-relevant-tests.yml").write_text(
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
        "          python-version: '3.11'\n"
        "      - name: Install dependencies\n"
        "        run: pip install pytest\n"
        "      - name: Run relevant tests\n"
        "        run: python running-relevant-tests/scripts/run_relevant_tests.py --mode push\n",
        encoding="utf-8",
    )
    print("  ✔ Created .github/workflows/running-relevant-tests.yml")


def scaffold_mapping(project_root, runner):
    mapping_path = project_root / "test_mapping.json"
    if mapping_path.exists():
        print("  ✔ test_mapping.json already exists")
        return "already exists"
    mapping_path.write_text(
        json.dumps({"_runner": runner, "_src_root": "src/", "_test_root": "tests/"}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print("  ✔ test_mapping.json created")
    return "created"


def main():
    parser = argparse.ArgumentParser(prog="install.py")
    parser.add_argument("--reconfigure", action="store_true")
    args = parser.parse_args()

    if sys.version_info < MIN_PYTHON:
        fail(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ required "
            f"(found {sys.version_info.major}.{sys.version_info.minor})"
        )

    project_root = Path.cwd()
    print("running-relevant-tests installer")
    print("=================================")

    runner = detect_runner(project_root)
    print(f"✔ Test runner: {runner}")

    if runner == "pytest" and not check_importable("pytest"):
        fail("pytest is not installed. Run: pip install pytest")
    print("✔ Dependencies OK")

    existing_mode = None
    if not args.reconfigure:
        existing_mode = detect_existing_mode(project_root)
        if existing_mode is not None:
            print(f"✔ Existing installation detected: {MODE_NAMES[existing_mode]}")
            print("  Skipping mode selection. Re-run with --reconfigure to change modes.")

    mode = existing_mode
    if mode is None:
        mode = prompt_mode()
        print(f"\nConfiguring mode {mode}: {MODE_NAMES[mode]}")
        if mode == 1:
            configure_mode_1(project_root)
        elif mode == 2:
            configure_mode_2(project_root)
        else:
            configure_mode_3(project_root)

    mapping_state = scaffold_mapping(project_root, runner)

    print()
    print(f"  ✔ Test runner: {runner}")
    print(f"  ✔ Dependencies OK")
    if existing_mode is not None:
        print(f"  ✔ Existing mode: {MODE_NAMES[mode]} (unchanged)")
    else:
        print(f"  ✔ Mode: {MODE_NAMES[mode]}")
    print(f"  ✔ test_mapping.json {mapping_state}")
    print()
    print("  running-relevant-tests is ready.")
    print("  Re-run with --reconfigure to switch modes.")


if __name__ == "__main__":
    main()
