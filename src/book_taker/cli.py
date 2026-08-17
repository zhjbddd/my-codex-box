from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import RunOptions, _drop_unverified, run_book_taker

__all__ = ["build_parser", "main", "_confirm", "_drop_unverified"]


def _confirm() -> bool:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "confirmation requires an interactive terminal; pass --yes in automation"
        )
    return input("proceed? [y/N] ").strip().lower() in {"y", "yes"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="book-taker", description="Extract and deconstruct a local text PDF, EPUB, or TXT book"
    )
    parser.add_argument("book", type=Path)
    parser.add_argument("--out", type=Path, help="default: <book directory>/book-taker-output")
    parser.add_argument("--base-url", help="OpenAI-compatible API base URL")
    parser.add_argument("--model", help="model ID; defaults to OPENAI_MODEL or gpt-5-mini")
    parser.add_argument("--yes", action="store_true", help="approve estimated API use")
    parser.add_argument(
        "--dry-run", action="store_true", help="extract and split without API calls"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="replace a prior output for the same source"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return run_book_taker(
        RunOptions(
            book=args.book,
            out=args.out,
            base_url=args.base_url,
            model=args.model,
            yes=args.yes,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        ),
        confirm=None if args.yes or args.dry_run else _confirm,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
