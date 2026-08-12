from __future__ import annotations

import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
SYNCED_FILES = ("__init__.py", "extract.py", "verify.py")


def test_plugin_manifest_points_to_existing_skill() -> None:
    plugin_root = ROOT / "plugins" / "my-codex-box"
    manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text("utf-8"))

    assert manifest["name"] == "my-codex-box"
    assert (plugin_root / manifest["skills"] / "book-taker" / "SKILL.md").is_file()


def test_release_versions_match() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    package_namespace: dict[str, str] = {}
    exec((ROOT / "src" / "book_taker" / "__init__.py").read_text("utf-8"), package_namespace)
    manifest = json.loads(
        (ROOT / "plugins" / "my-codex-box" / ".codex-plugin" / "plugin.json").read_text("utf-8")
    )

    assert project["project"]["version"] == package_namespace["__version__"]
    assert manifest["version"] == package_namespace["__version__"]


def test_skill_has_only_supported_frontmatter_fields() -> None:
    text = (ROOT / "skills" / "book-taker" / "SKILL.md").read_text("utf-8")
    frontmatter = text.split("---", 2)[1]
    keys = {line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line}

    assert keys == {"name", "description"}


def test_skill_runtime_matches_package_sources() -> None:
    package = ROOT / "src" / "book_taker"
    skill_package = ROOT / "skills" / "book-taker" / "src" / "book_taker"

    for name in SYNCED_FILES:
        assert skill_package.joinpath(name).read_bytes() == package.joinpath(name).read_bytes()


def test_distributable_plugin_skill_matches_source_skill() -> None:
    source = ROOT / "skills" / "book-taker"
    packaged = ROOT / "plugins" / "my-codex-box" / "skills" / "book-taker"
    source_files = {
        path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()
    }
    packaged_files = {
        path.relative_to(packaged): path.read_bytes()
        for path in packaged.rglob("*")
        if path.is_file()
    }

    assert packaged_files == source_files
