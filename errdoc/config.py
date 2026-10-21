"""Configuration loading for errdoc."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_TIMEOUT_SECONDS = 600.0
MAX_INPUT_CHARS = 1_000_000


@dataclass(frozen=True)
class Config:
    provider: str = "ollama"
    model: str = "llama3.2"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    timeout: float = 180.0
    max_input_chars: int = 12_000
    max_output_tokens: int = 256


def config_path() -> Path:
    override = os.environ.get("ERRDOC_CONFIG")
    return Path(override).expanduser() if override else Path.home() / ".errdoc" / "config.json"


def load_config() -> Config:
    """Load JSON defaults, then apply ERRDOC_* environment overrides."""
    path = config_path()
    raw: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("Configuration root must be a JSON object")
            raw = loaded
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Cannot read configuration at {path}: {exc}") from exc

    fields: dict[str, Any] = {}
    for key in Config.__dataclass_fields__:
        env_key = f"ERRDOC_{key.upper()}"
        value = os.environ.get(env_key, raw.get(key))
        if value is not None:
            fields[key] = value
    for key in ("timeout", "max_input_chars", "max_output_tokens"):
        if key in fields:
            try:
                fields[key] = float(fields[key]) if key == "timeout" else int(fields[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric") from exc

    result = Config(**fields)
    if not isinstance(result.provider, str) or result.provider not in {"ollama", "openai"}:
        raise ValueError("provider must be 'ollama' or 'openai'")
    if not isinstance(result.model, str) or not result.model.strip():
        raise ValueError("model must be a non-empty string")
    if not isinstance(result.base_url, str):
        raise ValueError("base_url must be a string")
    parsed_url = urlparse(result.base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("base_url must be an absolute HTTP or HTTPS URL")
    if parsed_url.username is not None or parsed_url.password is not None:
        raise ValueError("base_url must not contain embedded credentials; configure api_key separately")
    if not math.isfinite(result.timeout) or not 0 < result.timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout must be finite and between 0 and {MAX_TIMEOUT_SECONDS:g} seconds")
    if not 1 <= result.max_input_chars <= MAX_INPUT_CHARS:
        raise ValueError(f"max_input_chars must be between 1 and {MAX_INPUT_CHARS}")
    if not 64 <= result.max_output_tokens <= 4096:
        raise ValueError("max_output_tokens must be between 64 and 4096")
    if result.api_key is not None and not isinstance(result.api_key, str):
        raise ValueError("api_key must be a string or null")
    return result
