#!/usr/bin/env python3
"""Build the standalone Book Taker desktop client with PyInstaller."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from book_taker.client import artifact_name

ROOT = Path(__file__).resolve().parents[1]


def built_binary_name() -> str:
    suffix = ".exe" if sys.platform == "win32" else ""
    return f"book-taker-client{suffix}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Book Taker desktop client")
    parser.add_argument(
        "--name-only",
        action="store_true",
        help="print the platform artifact name and exit",
    )
    args = parser.parse_args(argv)
    name = artifact_name(platform.system())
    if args.name_only:
        print(name)
        return 0

    spec = ROOT / "packaging" / "book-taker-client.spec"
    subprocess.check_call(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(spec)],
        cwd=ROOT,
    )
    source = ROOT / "dist" / built_binary_name()
    if not source.is_file():
        raise FileNotFoundError(f"PyInstaller did not produce {source}")
    target = ROOT / "dist" / name
    if source.resolve() != target.resolve():
        if target.exists():
            target.unlink()
        shutil.copy2(source, target)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
