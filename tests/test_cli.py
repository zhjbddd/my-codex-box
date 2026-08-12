from __future__ import annotations

import json
from pathlib import Path

from book_taker import cli


def test_dry_run_never_requires_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    book = tmp_path / "book.txt"
    book.write_text("第一章 开始\n这是正文内容。", "utf-8")

    code = cli.main([str(book), "--out", str(tmp_path / "out"), "--dry-run"])

    assert code == 0
    assert (tmp_path / "out" / "raw" / "chapters.json").is_file()


def test_drop_unverified_is_fail_closed(tmp_path: Path) -> None:
    struct = tmp_path / "struct"
    struct.mkdir()
    path = struct / "chapter-0001.json"
    path.write_text(
        json.dumps(
            {
                "quotes": [
                    {"text": "good", "verified": True},
                    {"text": "bad", "verified": False},
                    {"text": "unknown", "verified": None},
                ],
                "ria_cards": [
                    {"r": "good", "r_verified": True},
                    {"r": "bad", "r_verified": False},
                ],
            }
        ),
        "utf-8",
    )

    cli._drop_unverified(struct)

    result = json.loads(path.read_text("utf-8"))
    assert [quote["text"] for quote in result["quotes"]] == ["good"]
    assert [card["r"] for card in result["ria_cards"]] == ["good"]


def test_noninteractive_confirmation_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    try:
        cli._confirm()
    except RuntimeError as exc:
        assert "--yes" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")
