#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def find_project_root():
    current = Path.cwd()
    for directory in [current] + list(current.parents):
        if (directory / "test_mapping.json").exists():
            return directory
        if (directory / ".git").exists():
            return directory
    return current


def load_config(project_root):
    mapping_path = project_root / "test_mapping.json"
    if not mapping_path.exists():
        print("Run install.py first — test_mapping.json not found.")
        sys.exit(0)
    try:
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Malformed test_mapping.json: {exc.msg} at line {exc.lineno}, col {exc.colno}")
        sys.exit(1)
    runner = data.get("_runner", "pytest")
    src_root = data.get("_src_root", "src/").rstrip("/") + "/"
    test_root = data.get("_test_root", "tests/").rstrip("/") + "/"
    mappings = {k: v for k, v in data.items() if not k.startswith("_")}
    return mappings, runner, src_root, test_root


def _run_git(args, cwd):
    result = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))
    return result.returncode, result.stdout.strip()


def _parse_names(output):
    files = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" in line:
            line = line.split("\t")[-1]
        elif " -> " in line:
            line = line.split(" -> ")[-1]
        if line.endswith(".py"):
            files.append(line)
    return files


def get_changed_files(mode, project_root):
    if mode == "commit":
        rc, out = _run_git(
            ["diff", "--cached", "--name-only", "--diff-filter=ACMR"], project_root
        )
        if rc != 0:
            return []
        return _parse_names(out)

    rc, branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], project_root)
    if rc != 0 or branch == "HEAD":
        print("Detached HEAD — cannot determine push range. Skipping tests.")
        sys.exit(0)

    for ref in (f"origin/{branch}", "origin/main", "origin/master"):
        rc, out = _run_git(
            ["diff", f"{ref}...HEAD", "--name-only", "--diff-filter=ACMR"], project_root
        )
        if rc == 0:
            return _parse_names(out)

    print("Could not determine push range — no reachable remote ref found. Skipping tests.")
    sys.exit(0)


FOUND = "FOUND"
INTENTIONAL = "INTENTIONAL"
UNMAPPED = "UNMAPPED"
FULL_SUITE = "FULL_SUITE"


def _mirror(f, src_root, test_root):
    rel = f[len(src_root):] if f.startswith(src_root) else f
    parts = rel.replace("\\", "/").split("/")
    parts[-1] = "test_" + parts[-1]
    return test_root + "/".join(parts)


def find_related_tests(files, mappings, src_root, test_root, project_root):
    results = []
    full_suite = False

    for f in files:
        if Path(f).name == "conftest.py":
            full_suite = True
            results.append((f, FULL_SUITE, None))
            continue

        if f in mappings:
            mapped = mappings[f]
            if isinstance(mapped, list) and len(mapped) == 0:
                results.append((f, INTENTIONAL, None))
            elif isinstance(mapped, list):
                for t in mapped:
                    results.append((f, FOUND, t))
            elif isinstance(mapped, str) and mapped:
                results.append((f, FOUND, mapped))
            else:
                results.append((f, UNMAPPED, None))
            continue

        mirror = _mirror(f, src_root, test_root)
        if (project_root / mirror).exists():
            results.append((f, FOUND, mirror))
            continue

        results.append((f, UNMAPPED, None))

    return results, full_suite


def print_summary(results):
    divider = "─" * 46
    print()
    print("running-relevant-tests")
    print(divider)
    for f, status, test in results:
        if status == FOUND:
            print(f"  ✔ {f:<38} → {test}")
        elif status == UNMAPPED:
            print(f"  ✘ {f:<38} → UNMAPPED")
        elif status == INTENTIONAL:
            print(f"  ✔ {f:<38} → (intentionally untested)")
        elif status == FULL_SUITE:
            print(f"  ✔ {f:<38} → FULL SUITE")
    print(divider)
    mapped = sum(1 for _, s, _ in results if s == FOUND)
    unmapped = sum(1 for _, s, _ in results if s == UNMAPPED)
    print(f"  {mapped} mapped | {unmapped} unmapped")
    print()


def print_unmapped_warnings(results, src_root, test_root):
    for f, status, _ in results:
        if status != UNMAPPED:
            continue
        mirror = _mirror(f, src_root, test_root)
        print(f"WARNING: {f} has no mapped tests.")
        print("  To fix, either:")
        print(f"    a) Create {mirror}")
        print( "    b) Add to test_mapping.json:")
        print(f'       "{f}": ["tests/path/test_file.py"]')
        print( "    c) To silence permanently:")
        print(f'       "{f}": []')
        print()


def main():
    parser = argparse.ArgumentParser(prog="run_relevant_tests.py")
    parser.add_argument("--mode", choices=["commit", "push"], required=True)
    args = parser.parse_args()

    project_root = find_project_root()
    mappings, runner, src_root, test_root = load_config(project_root)

    changed = get_changed_files(args.mode, project_root)
    if not changed:
        print("No Python files changed.")
        sys.exit(0)

    results, full_suite = find_related_tests(changed, mappings, src_root, test_root, project_root)

    if not results and not full_suite:
        print("No Python files in changed set.")
        sys.exit(0)

    print_summary(results)
    print_unmapped_warnings(results, src_root, test_root)

    test_files = [t for _, s, t in results if s == FOUND]

    if not test_files and not full_suite:
        print("No tests to run.")
        sys.exit(0)


if __name__ == "__main__":
    main()
