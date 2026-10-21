import json

import pytest

from errdoc.config import load_config


def _clear_config_env(monkeypatch):
    for name in (
        "ERRDOC_CONFIG",
        "ERRDOC_PROVIDER",
        "ERRDOC_MODEL",
        "ERRDOC_BASE_URL",
        "ERRDOC_API_KEY",
        "ERRDOC_TIMEOUT",
        "ERRDOC_MAX_INPUT_CHARS",
        "ERRDOC_MAX_OUTPUT_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_config_reads_json_and_environment_overrides(tmp_path, monkeypatch):
    _clear_config_env(monkeypatch)
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"provider": "ollama", "model": "from-file", "timeout": 10}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ERRDOC_CONFIG", str(config_file))
    monkeypatch.setenv("ERRDOC_MODEL", "from-env")
    result = load_config()
    assert result.provider == "ollama"
    assert result.model == "from-env"
    assert result.timeout == 10


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider", "unknown", "provider"),
        ("provider", ["ollama"], "provider"),
        ("base_url", ["http://localhost"], "base_url"),
        ("base_url", "https://alice:private-token@example.invalid/v1", "base_url"),
        ("model", "", "model"),
        ("base_url", "not-a-url", "base_url"),
        ("timeout", 0, "timeout"),
        ("timeout", float("nan"), "timeout"),
        ("timeout", 601, "timeout"),
        ("max_input_chars", 0, "max_input_chars"),
        ("max_input_chars", 1_000_001, "max_input_chars"),
        ("max_output_tokens", 63, "max_output_tokens"),
        ("max_output_tokens", 4097, "max_output_tokens"),
    ],
)
def test_config_rejects_invalid_values(tmp_path, monkeypatch, field, value, message):
    _clear_config_env(monkeypatch)
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({field: value}), encoding="utf-8")
    monkeypatch.setenv("ERRDOC_CONFIG", str(config_file))
    with pytest.raises(ValueError, match=message):
        load_config()


def test_config_rejects_malformed_json(tmp_path, monkeypatch):
    _clear_config_env(monkeypatch)
    config_file = tmp_path / "config.json"
    config_file.write_text("{", encoding="utf-8")
    monkeypatch.setenv("ERRDOC_CONFIG", str(config_file))
    with pytest.raises(ValueError, match="Cannot read configuration"):
        load_config()
