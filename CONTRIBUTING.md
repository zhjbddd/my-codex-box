# Contributing

Thank you for improving My Codex Box. The project welcomes focused bug fixes, tests, format
compatibility improvements, documentation corrections, and security hardening.

## Before opening a pull request

1. Open an issue first for large features or changes to output formats.
2. Do not commit copyrighted books, generated notes derived from non-public books, API keys,
   credentials, `.env` files, binaries, or real personal documents.
3. Use synthetic fixtures that reproduce the structure needed by the test.
4. Add a regression test for changes to extraction, path handling, model boundaries, quotation
   verification, or filtering.
5. Keep Skill instructions concise and review their effect on shell, file, network, and credential
   behavior.

## Local checks

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m pytest
```

If you changed `skills/book-taker`, also run the Skill validator documented in the README.
The distributable Plugin mirrors the root `skills/book-taker` source. Maintainers regenerate it
before release, and the test suite rejects out-of-sync files.

By submitting a contribution, you agree that it is licensed under the Apache License 2.0.
