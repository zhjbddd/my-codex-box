#!/usr/bin/env python3
"""Agent-friendly wrapper for deterministic quotation verification."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
VENDORED_SRC = SKILL_ROOT / "src"
if str(VENDORED_SRC) not in sys.path:
    sys.path.insert(0, str(VENDORED_SRC))

from book_taker import verify  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify generated quotations against a source")
    parser.add_argument("out", nargs="?", type=Path, default=Path("book-taker-output"))
    args = parser.parse_args()
    if not (args.out / "raw" / "fulltext.txt").is_file():
        print(f"error: no extracted source under {args.out}", file=sys.stderr)
        return 2
    try:
        result = verify.run(args.out)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"verified={result['verified']} warnings={len(result['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
