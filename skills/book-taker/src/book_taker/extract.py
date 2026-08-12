from __future__ import annotations

import json
import re
import shutil
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader

TITLE_RES = [
    re.compile(r"^\s*(第[一二三四五六七八九十百千零〇0-9]+[章卷篇回节部][^\n]{0,60})\s*$"),
    re.compile(r"^\s*(chapter\s+[0-9一二三四五六七八九十]+[^\n]{0,60})\s*$", re.I),
    re.compile(r"^\s*((?:\d{1,3})[、.．]\s*\S[^\n]{0,60})\s*$"),
    re.compile(r"^\s*(前言|序言|绪论|引言|结语|后记|附录[^\n]{0,40}|参考文献)\s*$"),
]

CHUNK = 4000
MAX_INPUT_BYTES = 200 * 1024 * 1024
MAX_EPUB_MEMBERS = 10_000
MAX_EPUB_MEMBER_BYTES = 20 * 1024 * 1024
MAX_EPUB_TOTAL_BYTES = 500 * 1024 * 1024
MAX_EPUB_RATIO = 200
MAX_CHAPTERS = 1000
TEXT_ENCODINGS = ("utf-8-sig", "gb18030", "big5")
OUTPUT_MARKER = ".book-taker-output.json"
GENERATED_ENTRIES = {"raw", "struct", "out", OUTPUT_MARKER}


class ExtractionError(ValueError):
    """Raised when a book cannot be safely or reliably extracted."""


def prepare_output(book_path: Path, out_dir: Path, *, overwrite: bool = False) -> None:
    """Create a bounded output directory without deleting unrelated files."""
    source = str(book_path.resolve())
    output = out_dir.resolve()
    if output == book_path.resolve():
        raise ExtractionError("output path cannot be the input file")
    if output.exists() and not output.is_dir():
        raise ExtractionError("output path exists and is not a directory")
    entries = list(output.iterdir()) if output.exists() else []
    marker = output / OUTPUT_MARKER
    if not entries and overwrite:
        raise ExtractionError("--overwrite requires output from a prior Book Taker run")
    if entries:
        if not overwrite:
            raise ExtractionError("output directory is not empty; use --overwrite for a prior run")
        if not marker.is_file():
            raise ExtractionError("refusing to overwrite a directory not created by Book Taker")
        try:
            metadata = json.loads(marker.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExtractionError("output marker is unreadable; refusing to overwrite") from exc
        if metadata.get("source") != source:
            raise ExtractionError(
                "output belongs to a different source file; refusing to overwrite"
            )
        unexpected = sorted(entry.name for entry in entries if entry.name not in GENERATED_ENTRIES)
        if unexpected:
            raise ExtractionError(
                f"output contains unrelated entries; refusing to overwrite: {unexpected[:3]}"
            )
        for name in ("raw", "struct", "out"):
            target = output / name
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)
    output.mkdir(parents=True, exist_ok=True)
    temporary_marker = output / f"{OUTPUT_MARKER}.tmp"
    temporary_marker.write_text(json.dumps({"version": 1, "source": source}, indent=2), "utf-8")
    temporary_marker.replace(output / OUTPUT_MARKER)


def detect_format(path: Path) -> str:
    suffix = path.suffix.lower()
    with path.open("rb") as stream:
        head = stream.read(8)
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK"):
        if suffix != ".epub":
            raise ExtractionError("ZIP input is only accepted when the file extension is .epub")
        return "epub"
    if suffix not in {".txt", ".md"}:
        raise ExtractionError("unsupported input; expected a text PDF, EPUB, TXT, or Markdown file")
    return "txt"


def _check_input_size(path: Path) -> None:
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ExtractionError(f"input exceeds the {MAX_INPUT_BYTES // (1024 * 1024)} MiB limit")


def extract_pdf(path: Path) -> dict:
    try:
        reader = PdfReader(path, strict=False)
        if reader.is_encrypted:
            raise ExtractionError("encrypted PDFs are not supported")
        page_texts = [(page.extract_text() or "") for page in reader.pages]
        bookmarks = []
        for item in reader.outline:
            if isinstance(item, list):
                continue
            page_index = reader.get_destination_page_number(item)
            title = str(getattr(item, "title", "")).strip()
            if title and page_index is not None and 0 <= page_index < len(reader.pages):
                bookmarks.append({"title": title, "page": page_index + 1})
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"could not read PDF: {exc}") from exc
    if not any(text.strip() for text in page_texts):
        raise ExtractionError("no extractable text found; scanned PDFs require OCR")
    return {"pages": page_texts, "bookmarks": bookmarks}


def _safe_epub_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise ExtractionError(f"unsafe EPUB member path: {name!r}")
    return path.as_posix()


def _inspect_epub(zf: zipfile.ZipFile) -> None:
    infos = zf.infolist()
    if len(infos) > MAX_EPUB_MEMBERS:
        raise ExtractionError(f"EPUB contains more than {MAX_EPUB_MEMBERS} members")
    total = 0
    for info in infos:
        _safe_epub_name(info.filename)
        if info.file_size > MAX_EPUB_MEMBER_BYTES:
            raise ExtractionError(f"EPUB member is too large: {info.filename!r}")
        total += info.file_size
        if total > MAX_EPUB_TOTAL_BYTES:
            raise ExtractionError("EPUB uncompressed size exceeds the safety limit")
        if info.file_size and not info.compress_size:
            raise ExtractionError(f"EPUB member has an invalid compressed size: {info.filename!r}")
        if info.compress_size and info.file_size / info.compress_size > MAX_EPUB_RATIO:
            raise ExtractionError(
                f"EPUB member has a suspicious compression ratio: {info.filename!r}"
            )


def _first_attr(element: ET.Element, local_name: str) -> str | None:
    for key, value in element.attrib.items():
        if key.rsplit("}", 1)[-1] == local_name:
            return value
    return None


def _epub_join(base: PurePosixPath, href: str) -> str:
    clean_href = unquote(href.split("#", 1)[0])
    return _safe_epub_name((base / PurePosixPath(clean_href)).as_posix())


def extract_epub(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as zf:
            _inspect_epub(zf)
            names = {_safe_epub_name(name) for name in zf.namelist()}
            if "META-INF/container.xml" not in names:
                raise ExtractionError("EPUB is missing META-INF/container.xml")
            container = ET.fromstring(zf.read("META-INF/container.xml"))
            rootfile = next(
                (
                    element
                    for element in container.iter()
                    if element.tag.rsplit("}", 1)[-1] == "rootfile"
                ),
                None,
            )
            opf_name = _first_attr(rootfile, "full-path") if rootfile is not None else None
            if not opf_name:
                raise ExtractionError("EPUB container does not identify an OPF package")
            opf_name = _safe_epub_name(opf_name)
            opf = ET.fromstring(zf.read(opf_name))
            base = PurePosixPath(opf_name).parent

            manifest: dict[str, str] = {}
            for element in opf.iter():
                if element.tag.rsplit("}", 1)[-1] != "item":
                    continue
                item_id = _first_attr(element, "id")
                href = _first_attr(element, "href")
                if item_id and href:
                    manifest[item_id] = _epub_join(base, href)

            spine = [
                _first_attr(element, "idref")
                for element in opf.iter()
                if element.tag.rsplit("}", 1)[-1] == "itemref"
            ]
            blocks = []
            for item_id in spine:
                href = manifest.get(item_id or "")
                if not href or href not in names:
                    continue
                blocks.append(html_to_text(zf.read(href).decode("utf-8", "replace")))
    except ExtractionError:
        raise
    except (OSError, KeyError, ET.ParseError, DefusedXmlException, zipfile.BadZipFile) as exc:
        raise ExtractionError(f"could not read EPUB: {exc}") from exc
    if not any(block.strip() for block in blocks):
        raise ExtractionError("EPUB spine contains no extractable text")
    return {"blocks": blocks, "bookmarks": []}


class TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip_depth += 1
        if tag in {"p", "div", "h1", "h2", "h3", "h4", "li", "tr", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "h1", "h2", "h3", "h4", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = TextCollector()
    parser.feed(html)
    return re.sub(r"\n{3,}", "\n\n", "".join(parser.parts))


def read_text_file(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ExtractionError("text encoding is not UTF-8, GB18030, or Big5")


def mark_positions(blocks: list[str], kind: str) -> str:
    parts = []
    for index, block in enumerate(blocks, 1):
        label = f"第{index}页" if kind == "pdf" else f"块{index}"
        parts.append(f"【{label}】\n{block}\n")
    return "".join(parts)


def title_line(line: str) -> str | None:
    line = line.strip()
    if not 2 <= len(line) <= 60:
        return None
    for regex in TITLE_RES:
        match = regex.match(line)
        if match:
            return match.group(1).strip()
    return None


def find_markers(fulltext: str) -> list[tuple[int, int, str]]:
    return [
        (match.start(), match.end(), match.group(1))
        for match in re.finditer(r"(?m)^【(第\d+页|块\d+)】$", fulltext)
    ]


def marker_index_for_pos(markers: list[tuple[int, int, str]], pos: int) -> int:
    index = 0
    for candidate, (start, _, _) in enumerate(markers):
        if start <= pos:
            index = candidate
        else:
            break
    return index


def scan_titles(fulltext: str, start: int = 0) -> list[dict]:
    hits = []
    for match in re.finditer(r"(?m)^.*$", fulltext[start:]):
        title = title_line(match.group(0))
        if title:
            hits.append({"title": title, "pos": start + match.start(), "end": start + match.end()})
    return hits


def _find_body_title(fulltext: str, title: str, after: int) -> int | None:
    normalized = re.sub(r"\s+", "", title)
    for hit in scan_titles(fulltext, after):
        if re.sub(r"\s+", "", hit["title"]) == normalized:
            return int(hit["pos"])
    return None


def scan_toc(fulltext: str) -> list[dict]:
    toc = re.search(r"(?im)^\s*(目\s*录|目录|contents|table\s+of\s+contents)\s*$", fulltext)
    if toc is None:
        return []
    search_end = min(len(fulltext), toc.end() + 5000)
    entries = []
    seen_titles = set()
    for hit in scan_titles(fulltext, toc.end()):
        if hit["pos"] >= search_end:
            break
        if re.match(r"^第[一二三四五六七八九十百千零〇0-9]+[章卷篇回节部]", hit["title"]):
            normalized = re.sub(r"\s+", "", hit["title"])
            if normalized in seen_titles:
                continue
            seen_titles.add(normalized)
            entries.append(hit)
    mapped = []
    for entry in entries:
        position = _find_body_title(fulltext, entry["title"], entry["end"])
        if position is not None:
            mapped.append({"title": entry["title"], "pos": position})
    return mapped


def build_chapters(fulltext: str, bookmarks: list[dict]) -> list[dict]:
    markers = find_markers(fulltext)
    candidates = []

    for bookmark in bookmarks:
        position = fulltext.find(f"【第{bookmark['page']}页】")
        if position >= 0:
            candidates.append({"title": bookmark["title"], "pos": position, "source": "bookmark"})

    if not candidates:
        candidates = [{**entry, "source": "toc"} for entry in scan_toc(fulltext)]

    if not candidates:
        candidates = [{**hit, "source": "regex"} for hit in scan_titles(fulltext)]

    if not candidates and len(fulltext) > 20_000:
        size = max(CHUNK, len(fulltext) // 20)
        candidates = [
            {"title": f"片段 {index + 1}", "pos": pos, "source": "fallback"}
            for index, pos in enumerate(range(0, len(fulltext), size))
        ]

    unique: dict[int, dict] = {}
    for candidate in candidates:
        unique.setdefault(int(candidate["pos"]), candidate)
    chapters = sorted(unique.values(), key=lambda candidate: int(candidate["pos"]))
    if len(chapters) > MAX_CHAPTERS:
        raise ExtractionError(f"detected more than {MAX_CHAPTERS} chapters; input is not bounded")
    for index, chapter in enumerate(chapters):
        start = int(chapter["pos"])
        chapter.update(
            no=index + 1,
            start=start,
            end=int(chapters[index + 1]["pos"]) if index + 1 < len(chapters) else len(fulltext),
            start_page=None,
        )
        if markers:
            chapter["start_page"] = markers[marker_index_for_pos(markers, start)][2]
    return chapters


def run(book_path: Path, out_dir: Path) -> dict:
    _check_input_size(book_path)
    kind = detect_format(book_path)
    encoding = None
    if kind == "pdf":
        data = extract_pdf(book_path)
        fulltext = mark_positions(data["pages"], "pdf")
        bookmarks = data["bookmarks"]
    elif kind == "epub":
        data = extract_epub(book_path)
        fulltext = mark_positions(data["blocks"], "epub")
        bookmarks = []
    else:
        fulltext, encoding = read_text_file(book_path)
        bookmarks = []

    chapters = build_chapters(fulltext, bookmarks)
    if not chapters:
        chapters = [
            {
                "no": 1,
                "title": book_path.stem,
                "start": 0,
                "end": len(fulltext),
                "start_page": None,
                "source": "whole-document",
            }
        ]

    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "fulltext.txt").write_text(fulltext, "utf-8")
    payload = {
        "book_title": book_path.stem,
        "format": kind,
        "encoding": encoding,
        "stats": {
            "chars": len(fulltext),
            "pages_or_blocks": len(find_markers(fulltext)),
            "chapters": len(chapters),
        },
        "chapters": [
            {
                key: chapter.get(key)
                for key in ("no", "title", "start", "end", "start_page", "source")
            }
            for chapter in chapters
        ],
        "bookmark_source": "bookmark" if bookmarks else None,
    }
    (raw_dir / "chapters.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), "utf-8"
    )
    return payload
