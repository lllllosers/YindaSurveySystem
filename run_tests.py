"""Dispatch independent product suites without sharing their module search paths."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("shared", "desktop", "web", "all"))
    args, pytest_args = parser.parse_known_args()
    suites = ("shared", "desktop", "web") if args.suite == "all" else (args.suite,)
    for suite in suites:
        cwd = ROOT / "web/backend" if suite == "web" else ROOT
        test_path = "tests" if suite == "web" else f"{suite}/tests"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT)
        executable = environment.get(f"YINDA_{suite.upper()}_TEST_PYTHON", sys.executable)
        result = subprocess.run([executable, "-m", "pytest", test_path, "-x", "-q", *pytest_args], cwd=cwd, env=environment)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
