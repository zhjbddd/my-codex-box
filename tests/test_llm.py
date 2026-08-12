from __future__ import annotations

import json

import pytest
import requests

from book_taker import llm


class FakeResponse:
    def __init__(self, payload: dict, *, content_length: int | None = None) -> None:
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield self.content

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def test_chat_rejects_oversized_response_before_json_parsing(monkeypatch) -> None:
    response = FakeResponse({}, content_length=llm.MAX_API_RESPONSE_BYTES + 1)
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: response)
    config = llm.LLMConfig("https://example.com/v1", "model", "secret")

    with pytest.raises(RuntimeError, match="5 MiB"):
        llm.chat(config, "system", "user", max_retries=0)


def test_chat_parses_structured_json(monkeypatch) -> None:
    response = FakeResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: response)
    config = llm.LLMConfig("https://example.com/v1", "model", "secret")

    assert llm.chat(config, "system", "user") == {"ok": True}


def test_nonlocal_api_requires_https() -> None:
    with pytest.raises(ValueError, match="require HTTPS"):
        llm.resolve_config("http://example.com/v1", "model")


def test_local_api_can_use_http() -> None:
    config = llm.resolve_config("http://localhost:8000/v1", "model")

    assert config.base_url == "http://localhost:8000/v1"


def test_base_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="must not include credentials"):
        llm.resolve_config("https://user:password@example.com/v1", "model")


def test_chat_enforces_streamed_body_limit(monkeypatch) -> None:
    response = FakeResponse({})
    response.content = b"x" * (llm.MAX_API_RESPONSE_BYTES + 1)
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: response)
    config = llm.LLMConfig("https://example.com/v1", "model", "secret")

    with pytest.raises(RuntimeError, match="5 MiB"):
        llm.chat(config, "system", "user", max_retries=0)
