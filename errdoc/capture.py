"""Capture command output with bounded memory and without invoking a shell."""

from __future__ import annotations

import math
import os
import signal
import shlex
import subprocess
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TextIO

_MAX_CAPTURE_BYTES_PER_STREAM = 512 * 1024
_MAX_ERROR_FILE_BYTES = 2 * 1024 * 1024
_MAX_STDIN_CHARS = 1_000_000
_MAX_COMMAND_TIMEOUT_SECONDS = 600.0
_READ_CHUNK_BYTES = 64 * 1024


def _kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Stop the command and descendants that may still hold captured pipes open."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    @property
    def output(self) -> str:
        """Combine both streams while retaining their source labels."""
        parts = []
        if self.stdout:
            label = "STDOUT (older output truncated)" if self.stdout_truncated else "STDOUT"
            marker = "\n[earlier stdout output omitted; newest 512 KiB retained]" if self.stdout_truncated else ""
            parts.append(f"{label}:\n{self.stdout.rstrip()}{marker}")
        if self.stderr:
            label = "STDERR (older output truncated)" if self.stderr_truncated else "STDERR"
            marker = "\n[earlier stderr output omitted; newest 512 KiB retained]" if self.stderr_truncated else ""
            parts.append(f"{label}:\n{self.stderr.rstrip()}{marker}")
        return "\n\n".join(parts)


def _read_bounded_tail(stream, max_bytes: int) -> tuple[str, bool]:
    chunks: deque[bytes] = deque()
    retained = 0
    truncated = False
    while True:
        chunk = stream.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        if len(chunk) >= max_bytes:
            truncated = truncated or retained > 0 or len(chunk) > max_bytes
            chunk = chunk[-max_bytes:]
            chunks.clear()
            retained = 0
        else:
            overflow = retained + len(chunk) - max_bytes
            if overflow > 0:
                truncated = True
                while overflow:
                    first = chunks[0]
                    if len(first) <= overflow:
                        chunks.popleft()
                        retained -= len(first)
                        overflow -= len(first)
                    else:
                        chunks[0] = first[overflow:]
                        retained -= overflow
                        overflow = 0
        chunks.append(chunk)
        retained += len(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace"), truncated


def run_command(command: Sequence[str], *, timeout: float = 120.0, cwd: str | None = None) -> CommandResult:
    """Run argv without a shell and retain only the newest 512 KiB from each stream."""
    if not command:
        raise ValueError("A command is required")
    if not math.isfinite(timeout) or not 0 < timeout <= _MAX_COMMAND_TIMEOUT_SECONDS:
        raise ValueError(
            f"timeout must be finite and between 0 and {_MAX_COMMAND_TIMEOUT_SECONDS:g} seconds"
        )
    arguments = list(command)
    try:
        process = subprocess.Popen(
            arguments,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            shell=False,
            start_new_session=os.name != "nt",
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {arguments[0]}") from exc

    with process:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="errdoc-capture") as readers:
            stdout_future = readers.submit(_read_bounded_tail, process.stdout, _MAX_CAPTURE_BYTES_PER_STREAM)
            stderr_future = readers.submit(_read_bounded_tail, process.stderr, _MAX_CAPTURE_BYTES_PER_STREAM)
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _kill_process_tree(process)
                process.wait()
                stdout_future.result()
                stderr_future.result()
                raise RuntimeError(f"Command timed out after {timeout:g} seconds") from exc
            stdout, stdout_truncated = stdout_future.result()
            stderr, stderr_truncated = stderr_future.result()

    return CommandResult(
        tuple(arguments), returncode, stdout, stderr, stdout_truncated, stderr_truncated
    )


def read_error_file(path: str | Path, *, max_bytes: int = _MAX_ERROR_FILE_BYTES) -> str:
    """Read a bounded tail from a log file so huge logs cannot exhaust memory."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be at least 1")
    with Path(path).open("rb") as source:
        source.seek(0, os.SEEK_END)
        size = source.tell()
        start = max(0, size - max_bytes)
        source.seek(start)
        data = source.read(max_bytes)
    text = data.decode("utf-8", errors="replace")
    if start:
        marker = f"[earlier file output omitted; retained final {max_bytes} bytes]"
        return f"{marker}\n{text}\n{marker}"
    return text


def read_error_stream(stream: TextIO, *, max_chars: int = _MAX_STDIN_CHARS) -> str:
    """Read piped input incrementally and keep only its newest characters."""
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")
    tail = ""
    truncated = False
    while True:
        chunk = stream.read(min(_READ_CHUNK_BYTES, max_chars + 1))
        if not chunk:
            break
        if len(tail) + len(chunk) > max_chars:
            truncated = True
        tail = (tail + chunk)[-max_chars:]
    if truncated:
        marker = f"[earlier piped input omitted; retained final {max_chars} characters]"
        return f"{marker}\n{tail}\n{marker}"
    return tail


def recent_history(limit: int = 20) -> list[str]:
    """Read a short list of shell history entries where a common history file exists."""
    if limit <= 0:
        return []
    candidates = [Path.home() / ".bash_history", Path.home() / ".zsh_history"]
    if os.name == "nt":
        candidates.insert(
            0,
            Path(os.environ.get("APPDATA", ""))
            / "Microsoft"
            / "Windows"
            / "PowerShell"
            / "PSReadLine"
            / "ConsoleHost_history.txt",
        )
    for path in candidates:
        try:
            return read_error_file(path).splitlines()[-limit:]
        except OSError:
            continue
    return []


def display_command(command: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)
