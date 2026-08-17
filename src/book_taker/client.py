from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .pipeline import RunOptions

SUPPORTED_SUFFIXES = {".pdf", ".epub", ".txt", ".md"}
LATEST_RELEASE_URL = "https://github.com/zhjbddd/my-codex-box/releases/latest"
CLIENT_ASSET_NAMES = {
    "windows": "book-taker-client-windows-x64.exe",
    "macos": "book-taker-client-macos-arm64",
    "linux": "book-taker-client-linux-x64",
}
_SYSTEM_ALIASES = {
    "windows": "windows",
    "win32": "windows",
    "darwin": "macos",
    "macos": "macos",
    "linux": "linux",
}


@dataclass(frozen=True)
class ClientForm:
    book: str
    output: str = ""
    api_key: str = ""
    model: str = ""
    base_url: str = ""
    dry_run: bool = False
    overwrite: bool = False


def artifact_name(system: str) -> str:
    platform = _SYSTEM_ALIASES.get(system.lower())
    if platform is None:
        raise ValueError(f"unsupported client platform: {system}")
    return CLIENT_ASSET_NAMES[platform]


def download_url(platform: str) -> str:
    return f"{LATEST_RELEASE_URL}/download/{artifact_name(platform)}"


def validate_form(form: ClientForm) -> list[str]:
    errors: list[str] = []
    book = form.book.strip()
    if not book:
        errors.append("请选择一本书籍文件")
    else:
        path = Path(book)
        if not path.is_file():
            errors.append(f"找不到文件：{book}")
        elif path.suffix.lower() not in SUPPORTED_SUFFIXES:
            errors.append("仅支持 PDF、EPUB、TXT 或 Markdown")
    output = form.output.strip()
    if output:
        output_path = Path(output)
        if output_path.exists() and not output_path.is_dir():
            errors.append("输出路径必须是目录")
    if not form.dry_run and not form.api_key.strip() and not os.environ.get("OPENAI_API_KEY"):
        errors.append("调用模型前需要填写 API 密钥，或设置 OPENAI_API_KEY")
    return errors


def form_to_options(form: ClientForm) -> RunOptions:
    errors = validate_form(form)
    if errors:
        raise ValueError("; ".join(errors))
    output = form.output.strip()
    return RunOptions(
        book=Path(form.book.strip()),
        out=Path(output) if output else None,
        base_url=form.base_url.strip() or None,
        model=form.model.strip() or None,
        api_key=form.api_key.strip() or None,
        dry_run=form.dry_run,
        overwrite=form.overwrite,
    )
