from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

from book_taker import extract


def test_txt_gb18030_detection_and_chapters(tmp_path: Path) -> None:
    book = tmp_path / "book.txt"
    book.write_bytes("第一章 开始\n正文一\n第二章 继续\n正文二".encode("gb18030"))

    payload = extract.run(book, tmp_path / "out")

    assert payload["format"] == "txt"
    assert payload["encoding"] == "gb18030"
    assert [chapter["title"] for chapter in payload["chapters"]] == [
        "第一章 开始",
        "第二章 继续",
    ]


def test_plain_text_without_headings_becomes_one_chapter(tmp_path: Path) -> None:
    book = tmp_path / "notes.md"
    book.write_text("没有标题的短文本。", "utf-8")

    payload = extract.run(book, tmp_path / "out")

    assert payload["chapters"] == [
        {
            "no": 1,
            "title": "notes",
            "start": 0,
            "end": 9,
            "start_page": None,
            "source": "whole-document",
        }
    ]


def test_toc_entries_map_to_body_headings() -> None:
    text = (
        "目录\n第一章 开始\n第二章 继续\n" + "x" * 5100 + "\n第一章 开始\n正文\n第二章 继续\n正文"
    )

    chapters = extract.build_chapters(text, [])

    body_start = text.rfind("第一章 开始")
    assert chapters[0]["source"] == "toc"
    assert chapters[0]["pos"] == body_start
    assert chapters[0]["pos"] > 5000


def test_short_toc_entries_are_not_used_as_body_chapters() -> None:
    text = "目录\n第一章 开始\n第二章 继续\n\n第一章 开始\n正文\n第二章 继续\n正文"

    chapters = extract.build_chapters(text, [])

    first_body_position = text.find("第一章 开始", text.find("第一章 开始") + 1)
    assert chapters[0]["source"] == "toc"
    assert chapters[0]["pos"] == first_body_position


def _write_epub(path: Path, *, unsafe: bool = False) -> None:
    container = """<?xml version='1.0'?>
    <container xmlns='urn:oasis:names:tc:opendocument:xmlns:container'>
      <rootfiles><rootfile full-path='OPS/package.opf'/></rootfiles>
    </container>"""
    opf = """<?xml version='1.0'?>
    <package xmlns='http://www.idpf.org/2007/opf'>
      <manifest><item id='c1' href='chapter.xhtml'/></manifest>
      <spine><itemref idref='c1'/></spine>
    </package>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OPS/package.opf", opf)
        archive.writestr("OPS/chapter.xhtml", "<h1>第一章 开始</h1><p>正文</p>")
        if unsafe:
            archive.writestr("../escape.txt", "bad")


def test_epub_uses_spine_order(tmp_path: Path) -> None:
    book = tmp_path / "book.epub"
    _write_epub(book)

    payload = extract.run(book, tmp_path / "out")

    assert payload["format"] == "epub"
    assert payload["chapters"][0]["title"] == "第一章 开始"


def test_epub_rejects_path_traversal(tmp_path: Path) -> None:
    book = tmp_path / "bad.epub"
    _write_epub(book, unsafe=True)

    with pytest.raises(extract.ExtractionError, match="unsafe EPUB member path"):
        extract.run(book, tmp_path / "out")


def test_zip_masquerading_as_text_is_rejected(tmp_path: Path) -> None:
    book = tmp_path / "book.txt"
    with zipfile.ZipFile(book, "w") as archive:
        archive.writestr("a.txt", "hello")

    with pytest.raises(extract.ExtractionError, match="only accepted"):
        extract.detect_format(book)


def test_pdf_bookmark_pages_are_one_based(tmp_path: Path, monkeypatch) -> None:
    book = tmp_path / "book.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_outline_item("第一章 开始", 0)
    with book.open("wb") as stream:
        writer.write(stream)

    original = extract.PdfReader

    class ReaderWithText:
        def __new__(cls, *args, **kwargs):
            reader = original(*args, **kwargs)
            monkeypatch.setattr(reader.pages[0], "extract_text", lambda: "第一章 开始")
            return reader

    monkeypatch.setattr(extract, "PdfReader", ReaderWithText)
    data = extract.extract_pdf(book)

    assert data["bookmarks"] == [{"title": "第一章 开始", "page": 1}]


def test_pdf_without_text_requests_ocr(tmp_path: Path) -> None:
    book = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with book.open("wb") as stream:
        writer.write(stream)

    with pytest.raises(extract.ExtractionError, match="scanned PDFs require OCR"):
        extract.extract_pdf(book)


def test_output_overwrite_refuses_unrelated_directory(tmp_path: Path) -> None:
    book = tmp_path / "book.txt"
    book.write_text("text", "utf-8")
    output = tmp_path / "out"
    output.mkdir()
    output.joinpath("keep.txt").write_text("do not delete", "utf-8")

    with pytest.raises(extract.ExtractionError, match="not created by Book Taker"):
        extract.prepare_output(book, output, overwrite=True)

    assert output.joinpath("keep.txt").read_text("utf-8") == "do not delete"


def test_output_overwrite_only_clears_generated_entries(tmp_path: Path) -> None:
    book = tmp_path / "book.txt"
    book.write_text("text", "utf-8")
    output = tmp_path / "out"
    extract.prepare_output(book, output)
    output.joinpath("raw").mkdir()
    output.joinpath("raw", "old.txt").write_text("old", "utf-8")

    extract.prepare_output(book, output, overwrite=True)

    assert not output.joinpath("raw").exists()
    assert output.joinpath(extract.OUTPUT_MARKER).is_file()


def test_overwrite_flag_requires_prior_output(tmp_path: Path) -> None:
    book = tmp_path / "book.txt"
    book.write_text("text", "utf-8")

    with pytest.raises(extract.ExtractionError, match="prior Book Taker run"):
        extract.prepare_output(book, tmp_path / "new-output", overwrite=True)
