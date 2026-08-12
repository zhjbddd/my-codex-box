from __future__ import annotations

import json
import re
from pathlib import Path

MIN_LEN = 6


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def page_markers(fulltext: str) -> list[tuple[int, int, str]]:
    return [
        (match.start(), match.end(), match.group(1))
        for match in re.finditer(r"(?m)^【(第\d+页|块\d+)】$", fulltext)
    ]


def page_text(fulltext: str, markers: list[tuple[int, int, str]], page_name: str) -> str | None:
    for index, (_, end_of_mark, name) in enumerate(markers):
        if name == page_name:
            end = markers[index + 1][0] if index + 1 < len(markers) else len(fulltext)
            return fulltext[end_of_mark:end]
    return None


def find_page_for_text(text: str, fulltext: str, markers: list[tuple[int, int, str]]) -> int | None:
    normalized = normalize(text)
    for index, (_, end_of_mark, name) in enumerate(markers):
        end = markers[index + 1][0] if index + 1 < len(markers) else len(fulltext)
        if normalized in normalize(fulltext[end_of_mark:end]):
            match = re.fullmatch(r"第(\d+)页", name)
            if match:
                return int(match.group(1))
    return None


def verify_one(text: str, page: int, fulltext: str, markers: list[tuple[int, int, str]]) -> dict:
    normalized = normalize(text)
    result = {"text": text, "page": page, "verified": False, "note": None}
    if len(normalized) < MIN_LEN:
        result["note"] = "too short to verify"
        return result
    if page > 0:
        page_content = page_text(fulltext, markers, f"第{page}页")
        if page_content is not None and normalized in normalize(page_content):
            result["verified"] = True
            return result
    if normalized in normalize(fulltext):
        result["verified"] = True
        if page > 0:
            result["note"] = "found but on a different page"
            corrected_page = find_page_for_text(text, fulltext, markers)
            if corrected_page is not None:
                result["page"] = corrected_page
        return result
    result["note"] = "not found in source"
    return result


def _apply_result(item: dict, result: dict, prefix: str = "") -> None:
    item[f"{prefix}verified"] = result["verified"]
    if result.get("page") is not None:
        item["page"] = result["page"]
    note_key = f"{prefix}note"
    if result["note"]:
        item[note_key] = result["note"]
    else:
        item.pop(note_key, None)


def run(out_dir: Path) -> dict:
    raw_dir = out_dir / "raw"
    struct_dir = out_dir / "struct"
    fulltext = (raw_dir / "fulltext.txt").read_text("utf-8")
    markers = page_markers(fulltext)
    warnings = []
    verified = 0
    files_checked = 0
    for path in sorted(struct_dir.glob("chapter-*.json")):
        card = json.loads(path.read_text("utf-8"))
        for quote in card.get("quotes", []):
            result = verify_one(
                str(quote.get("text", "")), int(quote.get("page", 0)), fulltext, markers
            )
            _apply_result(quote, result)
            if result["verified"]:
                verified += 1
            else:
                warnings.append({"file": path.name, "kind": "quote", "item": quote.copy()})
        for ria in card.get("ria_cards", []):
            result = verify_one(str(ria.get("r", "")), int(ria.get("page", 0)), fulltext, markers)
            _apply_result(ria, result, "r_")
            if result["verified"]:
                verified += 1
            else:
                warnings.append({"file": path.name, "kind": "ria_r", "item": ria.copy()})
        path.write_text(json.dumps(card, ensure_ascii=False, indent=2), "utf-8")
        files_checked += 1
    result = {"files_checked": files_checked, "verified": verified, "warnings": warnings}
    (struct_dir / "warnings.json").write_text(
        json.dumps({"count": len(warnings), "items": warnings}, ensure_ascii=False, indent=2),
        "utf-8",
    )
    return result
