from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5-mini"
MAX_API_RESPONSE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str | None


def resolve_config(
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> LLMConfig:
    resolved_base = base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL
    resolved_base = resolved_base.rstrip("/")
    if not resolved_base.endswith("/v1"):
        resolved_base += "/v1"
    parsed = urlparse(resolved_base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("OPENAI_BASE_URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(
            "OPENAI_BASE_URL must not include credentials, query parameters, or fragments"
        )
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("API credentials require HTTPS unless the endpoint is local")
    return LLMConfig(
        base_url=resolved_base,
        model=model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL,
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
    )


def chat(
    config: LLMConfig,
    system: str,
    user: str,
    *,
    timeout: int = 180,
    max_retries: int = 2,
) -> dict:
    if not config.api_key:
        raise RuntimeError("set OPENAI_API_KEY before using LLM features")
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with requests.post(
                f"{config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json=payload,
                stream=True,
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_API_RESPONSE_BYTES:
                    raise RuntimeError("LLM response exceeds the 5 MiB safety limit")
                body = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    body.extend(chunk)
                    if len(body) > MAX_API_RESPONSE_BYTES:
                        raise RuntimeError("LLM response exceeds the 5 MiB safety limit")
            data = json.loads(body)
            return json.loads(data["choices"][0]["message"]["content"])
        except RuntimeError:
            raise
        except (requests.RequestException, KeyError, TypeError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {max_retries + 1} attempts: {last_error}")
