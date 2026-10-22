import io
import json
import threading
import urllib.error
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from errdoc.config import Config
from errdoc.llm_engine import SYSTEM_PROMPT, diagnose, needs_llm, sanitize_model_response


def test_system_prompt_covers_reviewed_failure_modes_without_unsupported_fixes():
    assert "main-module guard" in SYSTEM_PROMPT
    assert "instance keys must be known during planning" in SYSTEM_PROMPT
    assert "state still references the missing provider configuration" in SYSTEM_PROMPT
    assert "status alone does not identify the cause" in SYSTEM_PROMPT
    assert "do not blame Java version unless the error is UnsupportedClassVersionError" in SYSTEM_PROMPT
    assert "do not describe it as rate limiting" in SYSTEM_PROMPT
    assert "distinguish a transaction timing out while waiting for a lock from a detected deadlock" in SYSTEM_PROMPT
    assert "Do not treat this as a missing package version" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    ("error", "expected", "forbidden"),
    [
        (
            "ZeroDivisionError: division by zero in billing.py:74",
            "denominator",
            "line 74 is not verified",
        ),
        (
            "verifying example.com/ledger@v1.8.2: checksum mismatch\ndownloaded: h1:aaaa\ngo.sum: h1:bbbb",
            "differs from the value recorded in go.sum",
            "go mod verify",
        ),
        (
            "RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase.",
            "__main__",
            "python.ini",
        ),
        (
            "Error: Invalid for_each argument\nfor_each = local.service_accounts depends on values known only after apply.",
            "keys must be known during planning",
            "values variable",
        ),
        (
            "Error: Provider configuration not present\nmodule.storage requires provider registry.terraform.io/hashicorp/aws.west, but it has been removed.",
            "state still references provider configuration",
            "removed from the state",
        ),
        (
            "Pod api-5f94 State Waiting Reason ImagePullBackOff\nBack-off pulling image registry.example.invalid/team/api:v7",
            "does not identify the cause",
            "failure in the registry",
        ),
        (
            "Error response from daemon: Bind for 0.0.0.0:8080 failed: port is already allocated",
            "host port 8080",
            "netstat",
        ),
        (
            "System.TypeLoadException: Method 'GetInvoiceTotal' in type 'Contoso.Billing.InvoiceService' from assembly 'Contoso.Billing, Version=4.1.0.0' does not have an implementation.",
            "has no implementation",
            "runtime classpath",
        ),
        (
            "AttributeError: module 'datetime' has no attribute 'UTC'\nPython runtime: 3.10.14",
            "added in Python 3.11",
            "introduced in Python 3.7",
        ),
    ],
)
def test_reviewed_failure_modes_use_deterministic_evidence_based_diagnosis(error, expected, forbidden):
    result = diagnose(error, {}, Config(provider="ollama", model="unused", base_url="http://127.0.0.1:1"))

    assert expected.casefold() in result.casefold()
    assert forbidden.casefold() not in result.casefold()
    assert needs_llm(error) is False


@pytest.mark.parametrize(
    ("error", "expected", "forbidden"),
    [
        ("UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 12: invalid start byte", "could not decode byte 0xff", "corrupted"),
        ("UnicodeEncodeError: 'ascii' codec can't encode character in position 4: ordinal not in range(128)", "could not encode a character", "input-data issue"),
        ("AttributeError: Can't pickle local object 'build.<locals>.worker'", "could not pickle the local object", "binary linkage"),
        ("java.lang.ClassNotFoundException: com.example.ReportClient", "could not load class com.example.ReportClient", "binary linkage incompatibility"),
        ("java.lang.ClassCastException: class java.lang.String cannot be cast to class java.lang.Integer", "could not cast", "missing class"),
        ("Readiness probe failed: HTTP probe failed with statuscode: 503", "readiness probe received HTTP 503", "image pull failure"),
        ("Liveness probe failed: HTTP probe failed with statuscode: 500", "liveness probe received HTTP 500", "authentication and authorization"),
        ("ERROR 1205 (HY000): Lock wait timeout exceeded; try restarting transaction", "waited too long to acquire a lock", "detected deadlock"),
        ("System.IO.FileNotFoundException: Could not load file or assembly 'Contoso.Data, Version=2.1.0.0, Culture=neutral, PublicKeyToken=null'. The system cannot find the file specified.", "could not resolve assembly Contoso.Data", "IP address"),
    ],
)
def test_additional_reviewed_diagnostics_are_deterministic(error, expected, forbidden):
    result = diagnose(error, {}, Config(provider="ollama", model="unused", base_url="http://127.0.0.1:1"))
    assert expected.casefold() in result.casefold()
    assert forbidden.casefold() not in result.casefold()
    assert needs_llm(error) is False


def test_inline_bundle_command_is_removed_from_model_response():
    cleaned, removed = sanitize_model_response("Run `bundle config set --local platform x86_64-linux` to fix it.")
    assert removed is True
    assert "bundle config" not in cleaned
    assert "[command example omitted]" in cleaned


@contextmanager
def _openai_compatible_http_server(response_body):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request_body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append((self.path, dict(self.headers), json.loads(request_body)))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            try:
                self.wfile.write(response_body)
            except BrokenPipeError:
                pass

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_openai_compatible_local_http_endpoint_works_without_credentials():
    response_body = json.dumps(
        {"choices": [{"message": {"content": "Diagnosis: local response."}}]}
    ).encode()
    with _openai_compatible_http_server(response_body) as (base_url, requests):
        config = Config(
            provider="openai", model="local-test", base_url=base_url,
            api_key=None, timeout=3, max_output_tokens=384,
        )
        result = diagnose(
            "ValueError: api_key=private-fixture-value\n"
            "AWS_SECRET_ACCESS_KEY=synthetic-aws-value\n"
            "DATABASE_URL=postgres://alice:synthetic-db-password@db.example/path\n"
            "Authorization: Basic synthetic-basic-value\n"
            "-----BEGIN PRIVATE KEY-----\nsynthetic-pem-value\n-----END PRIVATE KEY-----",
            {"project": "Python"}, config,
        )

    assert result == "Diagnosis: local response."
    assert len(requests) == 1
    path, headers, payload = requests[0]
    assert path == "/v1/chat/completions"
    assert not any(name.casefold() == "authorization" for name in headers)
    assert payload["model"] == "local-test"
    assert payload["max_tokens"] == 384
    sent_content = payload["messages"][1]["content"]
    assert "api_key=[REDACTED]" in sent_content
    for secret in (
        "private-fixture-value", "synthetic-aws-value", "synthetic-db-password",
        "synthetic-basic-value", "synthetic-pem-value",
    ):
        assert secret not in sent_content


def test_openai_compatible_local_http_endpoint_rejects_oversized_response():
    response_body = b"{" + (b" " * (1_048_576)) + b"}"
    with _openai_compatible_http_server(response_body) as (base_url, _requests):
        config = Config(provider="openai", model="local-test", base_url=base_url, timeout=3)
        with pytest.raises(RuntimeError, match="exceeds the 1048576-byte limit"):
            diagnose("ValueError: example", {}, config)


def test_module_not_found_is_diagnosed_without_guessing_a_package(monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("standard ModuleNotFoundError should not call an LLM")

    monkeypatch.setattr("errdoc.llm_engine.urllib.request.urlopen", unexpected_request)
    result = diagnose(
        "ModuleNotFoundError: No module named 'sample_module'",
        {"project": "Python"},
        Config(),
    )
    assert "could not import sample_module" in result
    assert "No install command was generated" in result
    assert "pip install sample_module" not in result


def test_git_no_upstream_error_uses_evidence_only_deterministic_diagnosis(monkeypatch):
    from errdoc.llm_engine import needs_llm

    monkeypatch.setattr(
        "errdoc.llm_engine.urllib.request.urlopen",
        lambda *args, **kwargs: pytest.fail("Git upstream errors should not call an LLM"),
    )
    error = "fatal: The current branch feature/cleanup has no upstream branch."
    result = diagnose(error, {}, Config())
    assert needs_llm(error) is False
    assert "feature/cleanup" in result
    assert "no upstream branch" in result
    assert "detached HEAD" not in result
    assert "git checkout" not in result


def test_java_class_version_mismatch_uses_logged_versions_deterministically(monkeypatch):
    from errdoc.llm_engine import needs_llm

    monkeypatch.setattr(
        "errdoc.llm_engine.urllib.request.urlopen",
        lambda *args, **kwargs: pytest.fail("class version mismatch should not call an LLM"),
    )
    error = (
        "java.lang.UnsupportedClassVersionError: ReportClient has been compiled by a more recent "
        "Java Runtime (class file version 65.0), this runtime only recognizes class file versions up to 61.0"
    )
    result = diagnose(error, {}, Config())
    assert needs_llm(error) is False
    assert "version 65.0" in result
    assert "up to 61.0" in result
    assert "pom.xml" not in result


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            "You are in 'detached HEAD' state. Commits made here are not attached to a branch.",
            ("detached head", "branch", "retained"),
        ),
        (
            "! [rejected] feature/report -> feature/report (non-fast-forward)\nerror: failed to push some refs",
            ("feature/report", "remote", "integrate"),
        ),
    ],
)
def test_git_state_errors_use_deterministic_command_free_diagnoses(monkeypatch, error, expected):
    from errdoc.llm_engine import needs_llm

    monkeypatch.setattr(
        "errdoc.llm_engine.urllib.request.urlopen",
        lambda *args, **kwargs: pytest.fail("recognized Git state errors should not call an LLM"),
    )
    result = diagnose(error, {}, Config())
    assert needs_llm(error) is False
    assert all(term in result.casefold() for term in expected)
    assert "`" not in result
    assert "git checkout" not in result.casefold()


def test_ollama_request_uses_chat_api_and_parses_response(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["body"] = json.loads(request.data)
        return io.BytesIO(json.dumps({"message": {"content": "Diagnosis text"}}).encode())

    monkeypatch.setattr("errdoc.llm_engine.urllib.request.urlopen", fake_urlopen)
    result = diagnose("ValueError: bad value", {"os": "Windows"}, Config())
    assert result == "Diagnosis text"
    assert seen["url"] == "http://localhost:11434/api/chat"
    assert seen["body"]["model"] == "llama3.2"
    assert seen["body"]["stream"] is False
    assert seen["body"]["options"]["num_predict"] == 256
    assert seen["body"]["options"]["temperature"] == 0.2


def test_openai_compatible_base_url_with_v1_is_not_duplicated(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["authorization"] = request.get_header("Authorization")
        seen["body"] = request.data.decode("utf-8")
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "API diagnosis"}}]}).encode())

    monkeypatch.setattr("errdoc.llm_engine.urllib.request.urlopen", fake_urlopen)
    config = Config(
        provider="openai",
        model="test-model",
        base_url="https://example.invalid/v1/",
        api_key="secret",
    )
    assert diagnose("ValueError", {}, config) == "API diagnosis"
    assert seen["url"] == "https://example.invalid/v1/chat/completions"
    assert seen["authorization"] == "Bearer secret"
    assert json.loads(seen["body"])["max_tokens"] == 256
    assert json.loads(seen["body"])["temperature"] == 0.2


def test_ollama_missing_model_http_error_is_actionable(monkeypatch):
    def fake_urlopen(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost:11434/api/chat",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"error":"model llama3.2 not found, try pulling it first"}'),
        )

    monkeypatch.setattr("errdoc.llm_engine.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="ollama pull llama3.2"):
        diagnose("ValueError", {}, Config())


def test_provider_http_error_redacts_api_key_for_direct_python_call(monkeypatch):
    api_key = "unusual-private-credential-value"

    def fake_urlopen(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://example.invalid/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            io.BytesIO(json.dumps({"error": f"credential rejected: {api_key}"}).encode()),
        )

    monkeypatch.setattr("errdoc.llm_engine.urllib.request.urlopen", fake_urlopen)
    config = Config(provider="openai", base_url="https://example.invalid/v1", api_key=api_key)
    with pytest.raises(RuntimeError) as raised:
        diagnose("ValueError: sample", {}, config)

    assert "credential rejected: [REDACTED]" in str(raised.value)
    assert api_key not in str(raised.value)


def test_llm_timeout_is_actionable(monkeypatch):
    monkeypatch.setattr(
        "errdoc.llm_engine.urllib.request.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()),
    )
    with pytest.raises(RuntimeError, match="timed out after 180"):
        diagnose("ValueError", {}, Config())

def test_common_module_error_is_handled_without_llm():
    assert needs_llm("ModuleNotFoundError: No module named 'missing_module'") is False
    assert needs_llm("ValueError: invalid value") is True


def test_model_command_section_is_removed_from_display_text():
    raw = "Diagnosis: cause.\n\nSteps:\n1. Inspect the failing expression.\n\n**Suggested command**\n```bash\nkill $(pgrep node)\n```"
    cleaned, removed = sanitize_model_response(raw)
    assert removed is True
    assert "Diagnosis: cause." in cleaned
    assert "Suggested command" not in cleaned
    assert "pgrep" not in cleaned


def test_model_fenced_code_is_removed_even_without_command_heading():
    cleaned, removed = sanitize_model_response("Cause found.\n```bash\nsudo example\n```")
    assert removed is True
    assert cleaned == "Cause found."


def test_model_inline_shell_command_and_environment_assignment_are_removed():
    cleaned, removed = sanitize_model_response(
        "Set it with `export DJANGO_SETTINGS_MODULE=myproject.settings` or run `python manage.py check`."
    )
    assert removed is True
    assert "export DJANGO_SETTINGS_MODULE" not in cleaned
    assert "python manage.py check" not in cleaned
    assert cleaned.count("[command example omitted]") == 2


def test_model_inline_identifiers_are_preserved():
    cleaned, removed = sanitize_model_response("The setting `DJANGO_SETTINGS_MODULE` must be configured.")
    assert removed is False
    assert "`DJANGO_SETTINGS_MODULE`" in cleaned


def test_model_retry_instruction_is_removed_when_its_command_is_filtered():
    raw = (
        "Steps:\n"
        "1. Verify network connectivity.\n"
        "2. Check internet connectivity and try running `npm` again to see if the issue persists."
    )
    cleaned, removed = sanitize_model_response(raw)
    assert removed is True
    assert "Verify network connectivity" in cleaned
    assert "Check internet connectivity" in cleaned
    assert "command example omitted" not in cleaned
    assert "again" not in cleaned


def test_model_inline_python_ini_filename_is_not_mistaken_for_a_command():
    raw = "Inspect the `python.ini` or `pyvenv.cfg` file for the interpreter setting."
    cleaned, removed = sanitize_model_response(raw)
    assert removed is False
    assert cleaned == raw


def test_model_bare_tool_reference_is_preserved_but_a_runnable_command_is_filtered():
    mention = "Check the endpoint with a tool like `curl` or a web browser."
    cleaned_mention, mention_removed = sanitize_model_response(mention)
    assert mention_removed is False
    assert cleaned_mention == mention

    command = "Run `curl` to check the endpoint."
    cleaned_command, command_removed = sanitize_model_response(command)
    assert command_removed is True
    assert "curl" not in cleaned_command


def test_model_inline_go_sum_filename_is_not_removed_as_a_command():
    cleaned, removed = sanitize_model_response("The `go.sum` file contains the expected module checksum.")
    assert removed is False
    assert "`go.sum`" in cleaned


@pytest.mark.parametrize(
    "advice",
    [
        "Print the record dictionary to inspect it.",
        "Print the environment variables before retrying.",
        "Use `print(record)` to see the current input.",
    ],
)
def test_model_advice_to_dump_potentially_sensitive_data_is_removed(advice):
    cleaned, removed = sanitize_model_response("**Steps**\n\n1. " + advice)
    assert removed is True
    assert "record dictionary" not in cleaned.casefold()
    assert "environment variables" not in cleaned.casefold()
    assert "print(record)" not in cleaned


def test_model_inline_database_commands_are_removed():
    cleaned, removed = sanitize_model_response(
        "Run `dbshell -c \"CREATE TABLE orders_invoice (id int);\"` to create it."
    )
    assert removed is True
    assert "dbshell" not in cleaned
    assert "CREATE TABLE" not in cleaned


def test_model_risky_advice_steps_are_removed_with_continuations():
    raw = (
        "Steps:\n"
        "1. Check the current execution policy.\n"
        "2. Change the Execution Policy: run Set-ExecutionPolicy RemoteSigned.\n"
        "   This enables scripts for the current user.\n"
        "3. Use the project's documented activation method."
    )
    cleaned, removed = sanitize_model_response(raw)
    assert removed is True
    assert "Check the current execution policy" in cleaned
    assert "Change the Execution Policy" not in cleaned
    assert "enables scripts" not in cleaned
    assert "documented activation method" in cleaned


def test_oversized_llm_response_is_rejected_before_json_parsing(monkeypatch):
    monkeypatch.setattr("errdoc.llm_engine._MAX_RESPONSE_BYTES", 32)
    monkeypatch.setattr(
        "errdoc.llm_engine.urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(b"x" * 33),
    )
    with pytest.raises(RuntimeError, match="exceeds the 32-byte limit"):
        diagnose("ValueError", {}, Config())
