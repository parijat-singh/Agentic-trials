#!/usr/bin/env python
"""Run unit tests with coverage. Use for CI and pre-commit checks."""
import os
import subprocess
import sys

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "tests/",
            "-v", "--tb=short",
            "--cov=.", "--cov-report=term-missing",
            "--cov-fail-under=30",
        ],
        cwd=root,
    )
    sys.exit(result.returncode)
