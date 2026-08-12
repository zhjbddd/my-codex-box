#!/usr/bin/env python3
"""Regenerate vendored Skill code and the distributable Plugin tree."""

from __future__ import annotations

import shutil
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised by the Python 3.10 CI jobs
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SOURCE = ROOT / "src" / "book_taker"
SKILL_SOURCE = ROOT / "skills" / "book-taker"
PLUGIN_SKILL = ROOT / "plugins" / "my-codex-box" / "skills" / "book-taker"
RUNTIME_FILES = ("__init__.py", "extract.py", "verify.py")
PLUGIN_MANIFEST = ROOT / "plugins" / "my-codex-box" / ".codex-plugin" / "plugin.json"


def versions() -> tuple[str, str, str]:
    import json

    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    package_version = project["project"]["version"]
    init_namespace: dict[str, str] = {}
    exec(PACKAGE_SOURCE.joinpath("__init__.py").read_text("utf-8"), init_namespace)
    manifest_version = json.loads(PLUGIN_MANIFEST.read_text("utf-8"))["version"]
    return package_version, init_namespace["__version__"], manifest_version


def main() -> None:
    discovered_versions = versions()
    if len(set(discovered_versions)) != 1:
        raise RuntimeError(f"version mismatch: {discovered_versions}")
    skill_runtime = SKILL_SOURCE / "src" / "book_taker"
    skill_runtime.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_FILES:
        shutil.copy2(PACKAGE_SOURCE / name, skill_runtime / name)
    plugin_root = (ROOT / "plugins" / "my-codex-box").resolve()
    if not PLUGIN_SKILL.resolve().is_relative_to(plugin_root):
        raise RuntimeError("refusing to synchronize outside the plugin root")
    is_junction = getattr(PLUGIN_SKILL, "is_junction", lambda: False)
    if PLUGIN_SKILL.is_symlink() or is_junction():
        raise RuntimeError("refusing to replace a linked plugin skill directory")
    if PLUGIN_SKILL.exists():
        shutil.rmtree(PLUGIN_SKILL)
    shutil.copytree(SKILL_SOURCE, PLUGIN_SKILL)
    print(f"synchronized Skill runtime and Plugin at {PLUGIN_SKILL.parent.parent}")


if __name__ == "__main__":
    main()
