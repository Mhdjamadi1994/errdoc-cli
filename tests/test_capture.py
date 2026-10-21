import sys
import time

import pytest

from errdoc.capture import display_command, read_error_file, read_error_stream, recent_history, run_command
from errdoc.executor import split_command


def test_run_command_captures_both_streams_and_exit_code():
    result = run_command([
        sys.executable,
        "-c",
        "import sys; print('normal output'); print('error output', file=sys.stderr); sys.exit(7)",
    ])
    assert result.returncode == 7
    assert "normal output" in result.stdout
    assert "error output" in result.stderr
    assert "STDOUT:" in result.output
    assert "STDERR:" in result.output


def test_run_command_timeout_is_actionable():
    with pytest.raises(RuntimeError, match="timed out"):
        run_command([sys.executable, "-c", "import time; time.sleep(1)"], timeout=0.05)


def test_run_command_timeout_kills_child_processes_holding_captured_pipes():
    child = "import time; time.sleep(30)"
    parent = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}]); "
        "print('child started', flush=True); time.sleep(30)"
    )
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        run_command([sys.executable, "-c", parent], timeout=0.5)
    assert time.monotonic() - started < 12


def test_run_command_missing_executable_is_actionable():
    with pytest.raises(RuntimeError, match="Command not found"):
        run_command(["errdoc-command-that-does-not-exist-934821"])


def test_recent_history_zero_limit_returns_empty():
    assert recent_history(0) == []

@pytest.mark.parametrize(
    "command",
    [
        ["python", "-c", "raise ValueError('sample error')"],
        ["tool", "two words", 'quote"inside', r"trailing\\", ""],
    ],
)
def test_displayed_command_round_trips_through_host_parser(command):
    assert split_command(display_command(command)) == command


def test_run_command_bounds_both_streams_and_preserves_their_tails():
    program = (
        "import sys; "
        "sys.stdout.write('o' * 600000 + chr(10) + 'ValueError: stdout-tail'); "
        "sys.stderr.write('e' * 600000 + chr(10) + 'RuntimeError: stderr-tail')"
    )
    result = run_command([sys.executable, "-c", program])
    assert result.returncode == 0
    assert result.stdout_truncated is True
    assert result.stderr_truncated is True
    assert len(result.stdout.encode("utf-8")) <= 512 * 1024
    assert len(result.stderr.encode("utf-8")) <= 512 * 1024
    assert result.stdout.endswith("ValueError: stdout-tail")
    assert result.stderr.endswith("RuntimeError: stderr-tail")
    assert "STDOUT (older output truncated)" in result.output
    assert "STDERR (older output truncated)" in result.output
    assert "[earlier stdout output omitted" in result.output
    assert "[earlier stderr output omitted" in result.output


def test_error_file_reads_bounded_tail_and_marks_truncation(tmp_path):
    path = tmp_path / "large.log"
    path.write_bytes(b"earlier-data-" * 20 + b"ValueError: terminal")
    result = read_error_file(path, max_bytes=32)
    assert result.startswith("[earlier file output omitted")
    assert "ValueError: terminal" in result
    assert result.endswith("[earlier file output omitted; retained final 32 bytes]")
    assert len(result.encode("utf-8")) < 200


def test_piped_input_reads_bounded_tail_and_marks_truncation():
    from io import StringIO

    result = read_error_stream(StringIO("old-" * 20 + "ValueError: terminal"), max_chars=32)
    assert result.startswith("[earlier piped input omitted")
    assert "ValueError: terminal" in result
    assert result.endswith("[earlier piped input omitted; retained final 32 characters]")
    assert len(result) < 200
