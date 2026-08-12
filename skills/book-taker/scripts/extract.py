#!/usr/bin/env python3
"""Agent-friendly wrapper for deterministic book extraction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
VENDORED_SRC = SKILL_ROOT / "src"
if str(VENDORED_SRC) not in sys.path:
    sys.path.insert(0, str(VENDORED_SRC))

try:
    from book_taker import extract  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - depends on host environment
    if exc.name in {"pypdf", "defusedxml"}:
        print(
            f"error: missing dependency {exc.name!r}; install with: "
            "python -m pip install 'pypdf>=6,<7' 'defusedxml>=0.7,<1'",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract and split a local text book")
    parser.add_argument("book", type=Path)
    parser.add_argument("out", nargs="?", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not args.book.is_file():
        print(f"error: file not found: {args.book}", file=sys.stderr)
        return 2
    output = args.out or args.book.parent / "book-taker-output"
    try:
        extract.prepare_output(args.book, output, overwrite=args.overwrite)
        result = extract.run(args.book, output)
    except (OSError, extract.ExtractionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"format={result['format']} chapters={len(result['chapters'])} output={output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
