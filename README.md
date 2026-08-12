# My Codex Box

[![CI](https://github.com/zhjbddd/my-codex-box/actions/workflows/ci.yml/badge.svg)](https://github.com/zhjbddd/my-codex-box/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

My Codex Box currently ships **Book Taker**: a Python CLI and reusable Agent Skill that turns
one local text-based PDF, EPUB, TXT, or Markdown book into structured chapter notes. Its central
quality control is deterministic quotation verification: generated quotations and RIA source
passages must be found in the extracted source before they enter the final report.

This repository is an independent open-source project maintained by
[@zhjbddd](https://github.com/zhjbddd). It is not an official OpenAI product.

## Why this exists

Long documents do not fit cleanly into one model context, and generated reading notes can contain
convincing but fabricated quotations or page numbers. Book Taker separates deterministic work from
model work:

1. detect the real file format and extract text locally;
2. identify chapters from PDF bookmarks, table-of-contents mappings, headings, or a visible fallback;
3. process bounded chapter chunks through an OpenAI-compatible API;
4. assign PDF physical-page anchors in code, not in the model response;
5. verify every quoted source passage against the extracted text;
6. omit unverifiable quotations from `out/final.md` while keeping an audit record.

## Current scope

- One local text PDF, EPUB, TXT, or Markdown file
- PDF bookmark and physical-page support
- BSD-licensed `pypdf` extraction backend
- EPUB spine parsing without an EPUB framework dependency
- UTF-8, GB18030, and Big5 text input
- JSON intermediate artifacts and a Markdown report
- OpenAI-compatible Chat Completions endpoint
- Standalone CLI plus Agent Skill packaging

Not supported: OCR for scanned PDFs, DRM removal, batch processing, GUI, or a claim that generated
notes replace the original work.

## Install the CLI

Python 3.10 or newer is required.

```bash
git clone https://github.com/zhjbddd/my-codex-box.git
cd my-codex-box
python -m venv .venv
```

Activate the virtual environment, then install:

```bash
python -m pip install -e .
```

First inspect extraction without making any network request:

```bash
book-taker path/to/book.pdf --dry-run
```

Book Taker refuses to reuse a non-empty output directory by default. Pass `--overwrite` only to
replace a prior run for the same source; directories containing unrelated files are never cleared.

For model-backed notes, set credentials in the environment. Do not put secrets in shell history,
the repository, or command arguments.

PowerShell:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "your-model"       # optional
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"  # optional
book-taker .\book.pdf
```

Bash:

```bash
export OPENAI_API_KEY="your-key"
export OPENAI_MODEL="your-model"       # optional
export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional
book-taker ./book.pdf
```

The CLI displays a rough request-size estimate and asks for confirmation. In a trusted automated
environment, `--yes` explicitly approves the model calls.

## Output

```text
book-taker-output/
  raw/fulltext.txt          # extracted source with page/block markers
  raw/chapters.json         # chapter boundaries, source, and statistics
  struct/outline.json       # generated global outline
  struct/chapter-*.json     # generated chapter cards
  struct/warnings.json      # quotation-verification audit log
  out/final.md              # final notes with verified quotations only
```

PDF page anchors are physical document pages. They may differ from page labels printed in the book.

## Install the Skill

The reusable Skill source is in [`skills/book-taker`](skills/book-taker), and a validated
distributable Plugin is generated under `plugins/my-codex-box/`. It follows the open Agent Skills
layout and includes Codex-facing metadata. Install the packaged plugin where supported, or copy the
`book-taker` directory into the Skills location used by your agent host. The Skill keeps its
deterministic extraction and verification code under `scripts/` and does not require the CLI package
to be installed.

OpenCode users can copy the same directory to `.opencode/skills/book-taker/`.

Before installing third-party Skills, review their instructions and scripts. A Skill can influence
an agent's file, shell, network, and credential behavior.

## Security and privacy

- Book content is untrusted input. The program does not execute book contents or embedded scripts.
- EPUBs are inspected for unsafe paths, excessive member counts, oversized files, and suspicious
  compression ratios before parsing.
- The full extracted text is written under the chosen output directory; treat it as copyrighted or
  sensitive data and do not commit it.
- Model-backed operation sends selected book text to the configured API provider. `--dry-run` stays
  local and makes no model request.
- Verification proves only that quoted text appears in the extracted source. It does not prove that
  summaries are correct or that a file is harmless.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and the maintained threat boundary.

## Development

```bash
python -m pip install -e ".[dev]"
python tools/sync_plugin.py
python -m ruff check .
python -m pytest
```

Maintainers should additionally validate `skills/book-taker` and `plugins/my-codex-box` with the
current Codex Skill and Plugin validators before release.

Tests use synthetic text and generated EPUB fixtures; copyrighted books and live API keys are not
required. See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change.

## Project status

The project is an early public MVP. Deterministic extraction, input limits, quote verification,
cross-platform tests, CLI packaging, and Skill metadata are implemented. Accuracy still depends on
book layout and the configured model; complex multi-column PDFs and scanned pages remain known gaps.

## License

Licensed under the [Apache License 2.0](LICENSE).
