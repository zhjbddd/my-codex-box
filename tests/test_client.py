from __future__ import annotations

from pathlib import Path

from book_taker import client, llm
from book_taker.pipeline import RunOptions, run_book_taker


def test_download_urls_point_at_latest_release_assets() -> None:
    assert client.download_url("windows").endswith(
        "/releases/latest/download/book-taker-client-windows-x64.exe"
    )
    assert client.download_url("macos").endswith(
        "/releases/latest/download/book-taker-client-macos-arm64"
    )
    assert client.download_url("linux").endswith(
        "/releases/latest/download/book-taker-client-linux-x64"
    )


def test_validate_form_requires_supported_book(tmp_path: Path) -> None:
    missing = client.validate_form(client.ClientForm(book=""))
    assert "请选择一本书籍文件" in missing

    book = tmp_path / "notes.docx"
    book.write_text("nope", "utf-8")
    unsupported = client.validate_form(client.ClientForm(book=str(book), dry_run=True))
    assert any("仅支持" in item for item in unsupported)


def test_form_to_options_keeps_api_key_in_memory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    book = tmp_path / "book.txt"
    book.write_text("第一章 开始\n正文", "utf-8")
    form = client.ClientForm(
        book=str(book),
        output=str(tmp_path / "out"),
        api_key="session-secret",
        model="demo-model",
        dry_run=True,
    )

    options = client.form_to_options(form)

    assert options.api_key == "session-secret"
    assert not any(
        "session-secret" in path.read_text("utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    )


def test_model_run_requires_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    book = tmp_path / "book.txt"
    book.write_text("第一章 开始\n正文", "utf-8")

    errors = client.validate_form(client.ClientForm(book=str(book), dry_run=False))

    assert any("API 密钥" in item for item in errors)


def test_client_dry_run_uses_shared_pipeline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    book = tmp_path / "book.txt"
    book.write_text("第一章 开始\n这是正文内容。", "utf-8")
    options = client.form_to_options(
        client.ClientForm(book=str(book), output=str(tmp_path / "out"), dry_run=True)
    )

    code = run_book_taker(options)

    assert code == 0
    assert (tmp_path / "out" / "raw" / "chapters.json").is_file()


def test_resolve_config_accepts_session_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = llm.resolve_config("https://api.openai.com/v1", "demo-model", "session-secret")

    assert config.api_key == "session-secret"


def test_pipeline_aborts_without_confirmation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unused")
    book = tmp_path / "book.txt"
    book.write_text("第一章 开始\n正文", "utf-8")
    messages: list[str] = []

    code = run_book_taker(
        RunOptions(book=book, out=tmp_path / "out"),
        progress=messages.append,
        confirm=lambda: False,
    )

    assert code == 0
    assert any("aborted" in message for message in messages)


def test_artifact_names_match_download_assets() -> None:
    assert client.artifact_name("windows") == client.CLIENT_ASSET_NAMES["windows"]
    assert client.artifact_name("darwin") == client.CLIENT_ASSET_NAMES["macos"]
    assert client.artifact_name("linux") == client.CLIENT_ASSET_NAMES["linux"]


def test_download_page_lists_release_assets() -> None:
    page = Path(__file__).resolve().parents[1].joinpath("docs", "download.html").read_text("utf-8")
    for name in client.CLIENT_ASSET_NAMES.values():
        assert name in page
        assert f"/releases/latest/download/{name}" in page
