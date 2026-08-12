from __future__ import annotations

import json
from pathlib import Path

from book_taker import verify


def test_verification_reports_exact_wrong_page_and_missing_quotes(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    struct = tmp_path / "struct"
    raw.mkdir()
    struct.mkdir()
    raw.joinpath("fulltext.txt").write_text(
        "【第1页】\n第一句话确实存在。\n【第2页】\n第二句话也存在。\n", "utf-8"
    )
    struct.joinpath("chapter-0001.json").write_text(
        json.dumps(
            {
                "quotes": [
                    {"text": "第一句话确实存在。", "page": 1},
                    {"text": "第二句话也存在。", "page": 1},
                    {"text": "不存在的幻觉引用。", "page": 2},
                    {"text": "太短", "page": 1},
                ],
                "ria_cards": [],
            },
            ensure_ascii=False,
        ),
        "utf-8",
    )

    result = verify.run(tmp_path)

    assert result["verified"] == 2
    assert len(result["warnings"]) == 2
    updated = json.loads(struct.joinpath("chapter-0001.json").read_text("utf-8"))
    assert updated["quotes"][0]["verified"] is True
    assert updated["quotes"][1]["note"] == "found but on a different page"
    assert updated["quotes"][1]["page"] == 2
    assert updated["quotes"][2]["verified"] is False
    assert updated["quotes"][3]["note"] == "too short to verify"


def test_missing_page_marker_does_not_silently_use_full_text() -> None:
    fulltext = "【第1页】\n这句话在第一页。\n"
    result = verify.verify_one("这句话在第一页。", 99, fulltext, verify.page_markers(fulltext))

    assert result["verified"] is True
    assert result["note"] == "found but on a different page"
