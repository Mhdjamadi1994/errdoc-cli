import json
import sys

from click.testing import CliRunner

from errdoc.cli import _extract_command, main


def test_no_llm_command_shows_both_streams_and_preserves_exit_code():
    result = CliRunner().invoke(
        main,
        [
            "--no-llm",
            sys.executable,
            "-c",
            "import sys; print('normal output'); print('error output', file=sys.stderr); sys.exit(6)",
        ],
    )
    assert result.exit_code == 6
    assert "normal output" in result.output
    assert "error output" in result.output
    assert "STDOUT:" in result.output
    assert "STDERR:" in result.output


def test_file_input_can_be_analyzed_without_llm(tmp_path):
    error_file = tmp_path / "error.log"
    error_file.write_text("ValueError: bad value", encoding="utf-8")
    result = CliRunner().invoke(main, ["--no-llm", "--file", str(error_file)])
    assert result.exit_code == 0
    assert "ValueError: bad value" in result.output


def test_config_init_writes_default_config_to_requested_path(tmp_path):
    target = tmp_path / "config.json"
    result = CliRunner().invoke(main, ["--config-init"], env={"ERRDOC_CONFIG": str(target)})
    assert result.exit_code == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["provider"] == "ollama"
    assert data["timeout"] == 180.0


def test_extract_command_supports_fenced_and_labeled_commands():
    fence = chr(96) * 3
    assert _extract_command("Suggested command:\n" + fence + "bash\npython --version\n" + fence) == "python --version"
    tick = chr(96)
    assert _extract_command("Suggested command: " + tick + "python --version" + tick) == "python --version"
    assert _extract_command("No command here.") is None
    assert _extract_command("Suggested command:\n" + fence + "bash\npython -m pdb your_script.py\n" + fence) is None

def test_config_init_reports_filesystem_errors_cleanly(tmp_path, monkeypatch):
    from errdoc import cli

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    monkeypatch.setattr(cli, "config_path", lambda: blocker / "config.json")
    result = CliRunner().invoke(main, ["--config-init"])
    assert result.exit_code == 1
    assert "could not create configuration" in result.output
    assert "Traceback" not in result.output

def test_history_file_is_opt_in_and_sanitized(tmp_path):
    error_file = tmp_path / "error.log"
    error_file.write_text("ValueError: bad value", encoding="utf-8")
    history_file = tmp_path / "history.txt"
    history_file.write_text("password=hunter2\necho safe-history", encoding="utf-8")
    result = CliRunner().invoke(
        main,
        ["--no-llm", "--file", str(error_file), "--history-file", str(history_file)],
    )
    assert result.exit_code == 0
    assert "safe-history" in result.output
    assert "[REDACTED]" in result.output
    assert "hunter2" not in result.output


def test_recent_history_is_not_read_without_history_option(tmp_path, monkeypatch):
    from errdoc import cli

    error_file = tmp_path / "error.log"
    error_file.write_text("ValueError: bad value", encoding="utf-8")
    monkeypatch.setattr(cli, "recent_history", lambda: (_ for _ in ()).throw(AssertionError("history read")))
    result = CliRunner().invoke(main, ["--no-llm", "--file", str(error_file)])
    assert result.exit_code == 0

def test_model_request_prints_wait_message(tmp_path, monkeypatch):
    from errdoc import cli

    error_file = tmp_path / "error.log"
    error_file.write_text("ValueError: sample", encoding="utf-8")
    monkeypatch.setattr(cli, "diagnose", lambda *args: "A concise diagnosis.")
    result = CliRunner().invoke(main, ["--file", str(error_file)])
    assert result.exit_code == 0
    assert "Generating diagnosis with ollama (llama3.2)" in result.output
    assert "AI diagnosis is unverified advice" in result.output
    assert "A concise diagnosis." in result.output


def test_common_secret_is_redacted_before_model_request(tmp_path, monkeypatch):
    error_file = tmp_path / "error.log"
    error_file.write_text("ValueError: sample\nAPI_KEY=private-value", encoding="utf-8")
    received = {}

    def capture_request(error, *args):
        received["error"] = error
        return "A concise diagnosis."

    monkeypatch.setattr("errdoc.cli.diagnose", capture_request)
    result = CliRunner().invoke(main, ["--file", str(error_file)])
    assert result.exit_code == 0
    assert "private-value" not in received["error"]
    assert "API_KEY=[REDACTED]" in received["error"]


def test_deterministic_module_error_does_not_claim_to_wait_for_model(tmp_path):
    error_file = tmp_path / "error.log"
    error_file.write_text("ModuleNotFoundError: No module named 'sample_mod'", encoding="utf-8")
    result = CliRunner().invoke(main, ["--file", str(error_file)])
    assert result.exit_code == 0
    assert "could not import sample_mod" in result.output
    assert "Generating diagnosis with" not in result.output


def test_model_suggested_command_is_hidden_and_never_executed(tmp_path, monkeypatch):
    error_file = tmp_path / "error.log"
    error_file.write_text("UnclassifiedError: sample", encoding="utf-8")
    monkeypatch.setattr("errdoc.cli.diagnose", lambda *args: "Suggested command: python --version")
    monkeypatch.setattr("errdoc.cli.execute", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("executed without consent")))
    result = CliRunner().invoke(main, ["--file", str(error_file), "--execute-fix"], input="\n")
    assert result.exit_code == 0
    assert "Model-generated commands or potentially unsafe advice were hidden" in result.output
    assert "python --version" not in result.output


def test_manual_command_requires_explicit_sandbox_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    error_file = tmp_path / "error.txt"
    error_file.write_text("UnclassifiedError: sample", encoding="utf-8")
    monkeypatch.setattr("errdoc.cli.diagnose", lambda *args: "Diagnosis: inspect the environment.")
    executed = []
    monkeypatch.setattr("errdoc.cli.execute", lambda command, **kwargs: executed.append((command, kwargs)) or 0)
    result = CliRunner().invoke(main, ["--file", str(error_file), "--execute-fix"], input="python --version\ny\n")
    assert result.exit_code == 0
    assert executed[0][0] == "python --version"
    assert executed[0][1]["timeout"] == 120.0
    assert executed[0][1]["project_dir"] == tmp_path.resolve()
    assert executed[0][1]["prepared_snapshot"].included
    assert "original project" in result.output
    manifest_files = list((tmp_path / ".errdoc").glob("sandbox-snapshot-preview-*.json"))
    assert len(manifest_files) == 1
    manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    assert any(item["path"] == "error.txt" for item in manifest["included"])


def test_manual_command_is_not_executed_without_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    error_file = tmp_path / "error.log"
    error_file.write_text("UnclassifiedError: sample", encoding="utf-8")
    monkeypatch.setattr("errdoc.cli.diagnose", lambda *args: "Diagnosis: inspect the environment.")
    monkeypatch.setattr("errdoc.cli.execute", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("executed without consent")))
    result = CliRunner().invoke(main, ["--file", str(error_file), "--execute-fix"], input="python --version\nn\n")
    assert result.exit_code == 0
    assert "Sandbox execution cancelled" in result.output


def test_confirmed_command_uses_the_exact_snapshot_shown_before_confirmation(tmp_path, monkeypatch):
    import io
    import tarfile

    from errdoc import cli

    monkeypatch.chdir(tmp_path)
    source = tmp_path / "app.py"
    source.write_text("before confirmation", encoding="utf-8")
    received = {}

    def confirm_after_edit(*_args, **_kwargs):
        source.write_text("after preview", encoding="utf-8")
        return True

    def fake_execute(command, **kwargs):
        received["command"] = command
        received["snapshot"] = kwargs["prepared_snapshot"]
        return 0

    monkeypatch.setattr(cli.click, "confirm", confirm_after_edit)
    monkeypatch.setattr(cli, "execute", fake_execute)
    assert cli._confirm_and_execute("python app.py", 30.0) == 0

    with tarfile.open(fileobj=io.BytesIO(received["snapshot"].archive), mode="r:") as archive:
        archived = archive.extractfile("app.py").read().decode("utf-8")
    assert archived == "before confirmation"
    assert source.read_text(encoding="utf-8") == "after preview"


def test_model_output_is_sanitized_before_display(tmp_path, monkeypatch):
    error_file = tmp_path / "error.log"
    error_file.write_text("UnclassifiedError: sample", encoding="utf-8")
    monkeypatch.setattr(
        "errdoc.cli.diagnose",
        lambda *args: 'Diagnosis: password="private phrase" in /home/alice/project',
    )
    result = CliRunner().invoke(
        main,
        ["--file", str(error_file)],
        env={"ERRDOC_CONFIG": str(tmp_path / "missing-config.json")},
    )
    assert result.exit_code == 0
    assert "private phrase" not in result.output
    assert "/home/alice" not in result.output
    assert "[REDACTED]" in result.output
    assert "[HOME]" in result.output


def test_provider_error_does_not_display_configured_api_key(tmp_path, monkeypatch):
    from errdoc import cli
    from errdoc.config import Config

    error_file = tmp_path / "error.log"
    error_file.write_text("UnclassifiedError: sample", encoding="utf-8")
    monkeypatch.setattr(cli, "load_config", lambda: Config(provider="openai", api_key="private-token"))
    monkeypatch.setattr(
        cli,
        "diagnose",
        lambda *args: (_ for _ in ()).throw(RuntimeError("provider echoed private-token")),
    )

    result = CliRunner().invoke(main, ["--file", str(error_file)])

    assert result.exit_code == 1
    assert "provider echoed [REDACTED]" in result.output
    assert "private-token" not in result.output
