import pytest

from errdoc.compressor import compress_log, sanitize


def test_sanitize_redacts_secrets_and_ansi():
    assert sanitize("\x1b[31mAPI_KEY=abc123\x1b[0m") == "API_KEY=[REDACTED]"


def test_sanitize_redacts_quoted_multiword_credentials():
    result = sanitize("""password="private phrase"; token='second private phrase'""")
    assert result == "password=[REDACTED]; token=[REDACTED]"
    assert "private phrase" not in result


def test_sanitize_redacts_bearer_credentials():
    assert sanitize("Authorization: Bearer abc.def_123") == "Authorization: Bearer [REDACTED]"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("AWS_SECRET_ACCESS_KEY=synthetic-private-value", "AWS_SECRET_ACCESS_KEY=[REDACTED]"),
        (
            "DATABASE_URL=postgres://alice:synthetic-password@db.example/path",
            "DATABASE_URL=postgres://[REDACTED]@db.example/path",
        ),
        (
            "Authorization: Basic synthetic-private-value",
            "Authorization: Basic [REDACTED]",
        ),
        (
            '{"api_key":"synthetic-json-secret"}',
            '{"api_key":[REDACTED]}',
        ),
        (
            "-----BEGIN PRIVATE KEY-----\nsynthetic-pem-secret\n-----END PRIVATE KEY-----",
            "[REDACTED_PRIVATE_KEY]",
        ),
    ],
)
def test_sanitize_redacts_cloud_credentials_database_urls_and_basic_auth(source, expected):
    result = sanitize(source)
    assert result == expected
    assert "synthetic-private-value" not in result
    assert "synthetic-password" not in result
    assert "synthetic-json-secret" not in result
    assert "synthetic-pem-secret" not in result


@pytest.mark.parametrize(
    "address",
    ["203.0.113.8", "192.168.1.17", "127.0.0.1", "2001:db8::7", "[2001:db8::7]"],
)
def test_sanitize_redacts_ipv4_and_ipv6_addresses(address):
    result = sanitize(f"connection failed to {address}:8443")
    assert address not in result
    assert "<IP_REDACTED>" in result


@pytest.mark.parametrize(
    "symbol",
    ["std::fmt::Display", "TelemetryClient::flush()", "Counter::increment", "foo::bar::Baz"],
)
def test_sanitize_preserves_namespaced_symbols_that_contain_ipv6_like_fragments(symbol):
    assert sanitize(symbol) == symbol


@pytest.mark.parametrize(
    "path",
    [r"C:\\Users\\alice\\project\\app.py", "/home/alice/project/app.py", "/Users/alice/project/app.py"],
)
def test_sanitize_redacts_common_user_home_paths(path):
    result = sanitize(f"Traceback in {path}")
    assert "alice" not in result
    assert "[HOME]" in result


def test_compressor_keeps_error_and_omits_dependency_frames():
    log = "Traceback (most recent call last):\n  File 'x', in run\n  File '/lib/site-packages/pkg.py', in call\nValueError: bad input"
    result = compress_log(log)
    assert "ValueError: bad input" in result
    assert "dependency frame(s) omitted" in result


@pytest.mark.parametrize("limit", [1, 10, 40])
def test_compressor_respects_small_character_limits(limit):
    result = compress_log("x" * 100, max_chars=limit)
    assert len(result) <= limit


def test_truncation_boundary_preserves_terminal_exception_and_redacts_secret():
    log = "old output\n" * 100 + "API_KEY=boundary-secret\nValueError: terminal failure"
    result = compress_log(log, max_chars=96)
    assert len(result) <= 96
    assert "boundary-secret" not in result
    assert "ValueError: terminal failure" in result


def test_compressor_rejects_nonpositive_limits():
    with pytest.raises(ValueError, match="max_chars"):
        compress_log("log", max_chars=0)
    with pytest.raises(ValueError, match="max_lines"):
        compress_log("log", max_lines=0)

def test_compressor_collapses_repeated_log_lines():
    log = "heartbeat unchanged\n" * 100
    result = compress_log(log, max_lines=200)
    assert result.count("heartbeat unchanged") == 1
    assert "repeated line omitted 99 times" in result
    assert len(result) < len(log) * 0.1
