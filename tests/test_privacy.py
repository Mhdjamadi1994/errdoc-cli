import io
import json

from errdoc.compressor import sanitize
from errdoc.config import Config
from errdoc.context import detect_context
from errdoc.llm_engine import diagnose


def test_runtime_context_never_contains_local_directory_or_ip(tmp_path):
    context = detect_context(tmp_path)
    assert "cwd" not in context
    assert all("ip" not in key.casefold() for key in context)
    assert str(tmp_path.resolve()) not in json.dumps(context)


def test_model_request_redacts_ip_addresses_and_user_paths(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["payload"] = json.loads(request.data)
        return io.BytesIO(json.dumps({"message": {"content": "Diagnosis: connection failed."}}).encode())

    monkeypatch.setattr("errdoc.llm_engine.urllib.request.urlopen", fake_urlopen)
    error = (
        r"RuntimeError: failed to connect to 203.0.113.25:8443 from "
        r"C:\Users\alice\work\private-project; IPv6 2001:db8::7"
    )
    diagnose(
        error,
        {"cwd": r"C:\Users\alice\work\private-project", "host": "192.168.10.5"},
        Config(),
    )

    sent_text = seen["payload"]["messages"][1]["content"]
    assert "203.0.113.25" not in sent_text
    assert "2001:db8::7" not in sent_text
    assert "192.168.10.5" not in sent_text
    assert "alice" not in sent_text
    assert "<IP_REDACTED>" in sent_text


def test_home_directory_redaction_is_case_insensitive_for_windows_paths():
    result = sanitize(r"C:\Users\Alice\Projects\private\app.py")
    assert "Alice" not in result
    assert "[HOME]" in result
