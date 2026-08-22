#!/usr/bin/env python3
"""Run script for JioSip application."""

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
JFC_DIR = PROJECT_ROOT / "jfc-pjproject"


def build_runtime_library_path() -> str:
    library_directories = [
        JFC_DIR / "pjsip" / "lib",
        JFC_DIR / "pjmedia" / "lib",
        JFC_DIR / "pjnath" / "lib",
        JFC_DIR / "pjlib-util" / "lib",
        JFC_DIR / "pjlib" / "lib",
        JFC_DIR / "third_party" / "lib",
    ]

    return ":".join(
        str(directory)
        for directory in library_directories
        if directory.exists()
    )


def main() -> int:
    venv_python = VENV_DIR / "bin" / "python"

    if not venv_python.exists():
        print("Virtual environment not found. Run setup.py first.")
        return 1

    library_path = build_runtime_library_path()

    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = (
        library_path
        + (":" + environment["LD_LIBRARY_PATH"] if environment.get("LD_LIBRARY_PATH") else "")
    )

    # Add project root to Python path
    environment["PYTHONPATH"] = (
        str(PROJECT_ROOT)
        + (":" + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    )

    return subprocess.run(
        [str(venv_python), "-m", "app"],
        env=environment,
        cwd=PROJECT_ROOT,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())