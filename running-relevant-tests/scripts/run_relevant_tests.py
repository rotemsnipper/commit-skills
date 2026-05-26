#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def load_config(project_root):
    mapping_path = project_root / "test_mapping.json"
    if not mapping_path.exists():
        return {}, "pytest", "src/", "tests/"
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    runner = data.get("_runner", "pytest")
    src_root = data.get("_src_root", "src/").rstrip("/") + "/"
    test_root = data.get("_test_root", "tests/").rstrip("/") + "/"
    mappings = {k: v for k, v in data.items() if not k.startswith("_")}
    return mappings, runner, src_root, test_root


def get_current_branch():
    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def get_changed_files(mode):
    if mode == "commit":
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True,
        )
        return [f for f in result.stdout.splitlines() if f]

    branch = get_current_branch()
    if branch is None:
        print("ERROR: detached HEAD — cannot determine push range", file=sys.stderr)
        sys.exit(0)

    result = subprocess.run(
        ["git", "diff", f"origin/{branch}...HEAD", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return [f for f in result.stdout.splitlines() if f]

    for fallback in ("main", "master"):
        result = subprocess.run(
            ["git", "diff", f"{fallback}...HEAD", "--name-only", "--diff-filter=ACMR"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.splitlines() if f]

    return []


def find_related_tests(files, mappings, src_root, test_root, project_root):
    results = []
    full_suite = False

    for f in files:
        if not f.endswith(".py"):
            continue

        if Path(f).name == "conftest.py":
            full_suite = True
            continue

        if f in mappings:
            mapped = mappings[f]
            if mapped == [] or mapped == "":
                results.append((f, "INTENTIONAL", None))
            elif isinstance(mapped, list):
                for t in mapped:
                    results.append((f, "FOUND", t))
            else:
                results.append((f, "FOUND", mapped))
            continue

        if f.startswith(src_root):
            relative = f[len(src_root):]
            parts = Path(relative)
            mirrored = test_root + str(parts.parent / ("test_" + parts.name)).replace("\\", "/")
            if (project_root / mirrored).exists():
                results.append((f, "FOUND", mirrored))
                continue

        results.append((f, "UNMAPPED", None))

    return results, full_suite


def print_summary(results):
    found = [(f, t) for f, s, t in results if s == "FOUND"]
    unmapped = [f for f, s, t in results if s == "UNMAPPED"]
    intentional = [f for f, s, t in results if s == "INTENTIONAL"]

    col1 = max((len(f) for f, _, _ in results), default=30)
    col1 = max(col1, 30)

    header = f"{'File':<{col1}}  {'Status':<10}  Test file"
    print(header)
    print("-" * len(header))

    for f, status, test in results:
        if status == "FOUND":
            print(f"{f:<{col1}}  {'✔ FOUND':<10}  {test}")
        elif status == "UNMAPPED":
            print(f"{f:<{col1}}  {'✘ UNMAPPED':<10}  —")
        elif status == "INTENTIONAL":
            print(f"{f:<{col1}}  {'✔ INTENT.':<10}  (intentionally untested)")

    print()
    print(f"Mapped: {len(found)}  |  Unmapped: {len(unmapped)}  |  Intentional: {len(intentional)}")
    print()

    for f, status, _ in results:
        if status != "UNMAPPED":
            continue
        src_root_guess = "src/"
        test_root_guess = "tests/"
        relative = f[len(src_root_guess):] if f.startswith(src_root_guess) else f
        parts = Path(relative)
        mirror = test_root_guess + str(parts.parent / ("test_" + parts.name)).replace("\\", "/")
        print(f"⚠ No test found for: {f}")
        print(f"  Resolve by choosing one:")
        print(f"  a) Create the mirrored test file: {mirror}")
        print(f'  b) Add an explicit entry to test_mapping.json:')
        print(f'       "{f}": "{mirror}"')
        print(f'  c) Acknowledge as intentionally untested:')
        print(f'       "{f}": []')
        print()

    return found, unmapped


def path_to_module(path):
    return path.replace("/", ".").replace("\\", ".").removesuffix(".py")


def run_tests(test_files, runner, mode, full_suite):
    if full_suite:
        if runner == "pytest":
            cmd = ["pytest", "--tb=short", "-q"]
        elif runner == "django":
            cmd = ["python", "manage.py", "test"]
        else:
            cmd = ["python", "-m", "unittest", "discover"]
        print(f"conftest.py changed — running full suite: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        sys.exit(result.returncode)

    if not test_files:
        print("No tests to run.")
        sys.exit(0)

    unique_tests = sorted(set(test_files))

    if runner == "pytest":
        base = ["pytest"] + unique_tests + ["--tb=short", "-q"]
        if mode == "commit":
            base.insert(1, "-x")
        cmd = base
    elif runner == "django":
        labels = [path_to_module(t) for t in unique_tests]
        cmd = ["python", "manage.py", "test"] + labels
        if mode == "commit":
            cmd.append("--failfast")
    else:
        modules = [path_to_module(t) for t in unique_tests]
        cmd = ["python", "-m", "unittest"] + modules
        if mode == "commit":
            cmd.append("--failfast")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["commit", "push"], required=True)
    args = parser.parse_args()

    project_root = Path.cwd()
    mappings, runner, src_root, test_root = load_config(project_root)

    changed = get_changed_files(args.mode)
    if not changed:
        print("No relevant Python files changed.")
        sys.exit(0)

    results, full_suite = find_related_tests(changed, mappings, src_root, test_root, project_root)

    py_results = [r for r in results]
    if not py_results and not full_suite:
        print("No Python files in changed set.")
        sys.exit(0)

    found_pairs, _ = print_summary(py_results)
    test_files = [t for _, t in found_pairs]

    run_tests(test_files, runner, args.mode, full_suite)


if __name__ == "__main__":
    main()
