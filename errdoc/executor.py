"""Human-confirmed command execution with conservative safety checks."""

from __future__ import annotations

import ctypes
import io
import math
import os
import re
import shutil
import shlex
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from ctypes import wintypes



_BLOCKED = re.compile(
    r"\brm\s+(?:-[^\s]*r[^\r\n]*|--recursive\b[^\r\n]*)"
    r"|\b(?:rmdir|rd)\s+/s(?:\s|$)"
    r"|\b(?:del|erase)\s+/[^\s]*s[^\s]*(?:\s|$)"
    r"|\bformat(?:\.com|\.exe)?\s+[a-z]:"
    r"|\bmkfs(?:\.|\s)|\bdd\s+if=|:\(\)\s*\{"
    r"|\b(?:sudo\s+)?(?:shutdown|reboot)\b"
    r"|\bgit\s+reset\s+--hard\b"
    r"|\bgit\s+clean\s+-[a-z]*f[a-z]*\b"
    r"|\b(?:Remove-Item|Clear-Disk|Remove-Partition|Remove-Volume|Format-Volume|Stop-Computer|Restart-Computer)\b"
    r"|\bdrop\s+database\b"
    r"|\b(?:shutil\.rmtree|os\.(?:remove|rmdir|unlink))\b"
    r"|\bPath\([^)]*\)\.(?:unlink|rmdir)\b",
    re.I,
)

_DEFAULT_IMAGE = "python:3.11-slim"
_MAX_PROJECT_BYTES = 64 * 1024 * 1024
_MAX_PROJECT_FILES = 10_000
_MAX_PROJECT_ENTRIES = 20_000
_MAX_COMMAND_CHARS = 16_384
_MAX_SANDBOX_TIMEOUT = 600.0
_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".nox", "dist", "build", ".errdoc",
    ".aws", ".ssh", ".config", "credentials", "secrets",
}
_SKIP_NAMES = {
    ".env", ".env.local", ".env.development", ".env.production", ".npmrc",
    ".pypirc", ".netrc", "id_rsa", "id_ed25519", "credentials", "secrets",
}
_SKIP_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".log", ".db", ".sqlite", ".sqlite3", ".dump", ".bak"}

_CONTAINER_BOOTSTRAP = r"""
import os, pathlib, subprocess, sys, tarfile
root = pathlib.Path('/workspace')
with tarfile.open(fileobj=sys.stdin.buffer, mode='r|*') as archive:
    for member in archive:
        name = pathlib.PurePosixPath(member.name)
        if name.is_absolute() or not name.parts or any(part in ('', '.', '..') for part in name.parts):
            raise SystemExit('errdoc sandbox: rejected unsafe project path')
        target = root.joinpath(*name.parts)
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise SystemExit('errdoc sandbox: could not read project file')
            with source, target.open('wb') as destination:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    destination.write(block)
            target.chmod((member.mode & 0o755) | 0o600)
        else:
            raise SystemExit('errdoc sandbox: rejected non-regular project entry')
argv = sys.argv[1:]
if argv and argv[0] == '--':
    argv = argv[1:]
if not argv:
    raise SystemExit('errdoc sandbox: command is empty')
try:
    result = subprocess.run(argv, cwd=root, shell=False, check=False)
except FileNotFoundError:
    print('errdoc sandbox: executable is not installed in the configured image', file=sys.stderr)
    raise SystemExit(127)
raise SystemExit(result.returncode)
""".strip()


def is_safe(command: str) -> bool:
    """Return false for commands matching known high-impact operations."""
    return (
        bool(command.strip())
        and len(command) <= _MAX_COMMAND_CHARS
        and not _BLOCKED.search(command)
    )


def split_command(command: str) -> list[str]:
    """Parse one command line into argv using the host platform's quoting rules."""
    if os.name != "nt":
        return shlex.split(command)

    argc = ctypes.c_int()
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    parse = shell32.CommandLineToArgvW
    parse.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int))
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    free = kernel32.LocalFree
    free.argtypes = (ctypes.c_void_p,)
    free.restype = ctypes.c_void_p

    argv = parse(command, ctypes.byref(argc))
    if not argv:
        raise OSError(ctypes.get_last_error(), "Could not parse command line")
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        free(argv)


@dataclass(frozen=True)
class SnapshotEntry:
    path: str
    size_bytes: int | None
    reason: str | None = None


@dataclass(frozen=True)
class ProjectSnapshot:
    root: Path
    archive: bytes
    included: tuple[SnapshotEntry, ...]
    excluded: tuple[SnapshotEntry, ...]

    @property
    def included_bytes(self) -> int:
        return sum(entry.size_bytes or 0 for entry in self.included)


def build_project_snapshot(root: Path) -> ProjectSnapshot:
    """Create the bounded archive and an inspectable inventory of included/excluded paths."""
    root = root.resolve()
    archive_data = io.BytesIO()
    total_size = 0
    file_count = 0
    entry_count = 0
    included: list[SnapshotEntry] = []
    excluded: list[SnapshotEntry] = []
    with tarfile.open(fileobj=archive_data, mode="w") as archive:
        for directory, dirs, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(directory)
            entry_count += 1 + len(dirs) + len(filenames)
            if entry_count > _MAX_PROJECT_ENTRIES:
                raise ValueError("Project snapshot exceeds the sandbox entry-count limit")
            included_dirs = []
            for name in sorted(dirs):
                path = current / name
                relative_name = path.relative_to(root).as_posix()
                if _is_symlink_or_reparse_point(path):
                    excluded.append(SnapshotEntry(relative_name, None, "symbolic link directory"))
                elif name.casefold() in _SKIP_DIRS:
                    excluded.append(SnapshotEntry(relative_name, None, "excluded directory"))
                elif name.startswith(".") and name.casefold() != ".github":
                    excluded.append(SnapshotEntry(relative_name, None, "hidden directory"))
                else:
                    included_dirs.append(name)
            dirs[:] = included_dirs
            for filename in sorted(filenames):
                path = current / filename
                relative = path.relative_to(root)
                relative_name = relative.as_posix()
                if _is_symlink_or_reparse_point(path):
                    excluded.append(SnapshotEntry(relative_name, None, "symbolic link"))
                    continue
                if any(part.startswith(".") for part in relative.parts[:-1]):
                    excluded.append(SnapshotEntry(relative_name, None, "inside hidden directory"))
                    continue
                lower_name = filename.casefold()
                if lower_name in _SKIP_NAMES:
                    excluded.append(SnapshotEntry(relative_name, None, "sensitive filename"))
                    continue
                if re.search(r"(?:^|[._-])(secret|secrets|credential|credentials|password|passwd|token|tokens)(?:[._-]|$)", lower_name):
                    excluded.append(SnapshotEntry(relative_name, None, "sensitive filename pattern"))
                    continue
                if lower_name.startswith(".env"):
                    excluded.append(SnapshotEntry(relative_name, None, "environment file"))
                    continue
                if lower_name.endswith(tuple(_SKIP_SUFFIXES)):
                    excluded.append(SnapshotEntry(relative_name, None, "excluded file type"))
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    excluded.append(SnapshotEntry(relative_name, None, "unreadable file"))
                    continue
                if not path.is_file():
                    excluded.append(SnapshotEntry(relative_name, None, "not a regular file"))
                    continue
                total_size += stat.st_size
                file_count += 1
                if total_size > _MAX_PROJECT_BYTES or file_count > _MAX_PROJECT_FILES:
                    raise ValueError("Project snapshot exceeds the sandbox size or file-count limit")
                included.append(SnapshotEntry(relative_name, stat.st_size))
                info = tarfile.TarInfo(relative.as_posix())
                info.size = stat.st_size
                info.mode = stat.st_mode & 0o755
                with path.open("rb") as source:
                    archive.addfile(info, source)
    return ProjectSnapshot(
        root=root,
        archive=archive_data.getvalue(),
        included=tuple(included),
        excluded=tuple(excluded),
    )


def _project_snapshot(root: Path) -> bytes:
    """Compatibility helper returning just the bounded archive bytes."""
    return build_project_snapshot(root).archive


def _is_symlink_or_reparse_point(path: Path) -> bool:
    """Exclude symlinks and Windows junctions/other filesystem reparse points."""
    if path.is_symlink():
        return True
    try:
        metadata = path.lstat()
    except OSError:
        return True
    return bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def _runtime() -> str:
    health_check_timed_out = False
    requested = os.environ.get("ERRDOC_CONTAINER_RUNTIME", "").strip().lower()
    if requested and requested not in {"docker", "podman"}:
        raise ValueError("ERRDOC_CONTAINER_RUNTIME must be either 'docker' or 'podman'")
    candidates = (requested,) if requested else ("docker", "podman")
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            try:
                result = subprocess.run(
                    [executable, "info"], capture_output=True, text=True, timeout=8, check=False
                )
            except subprocess.TimeoutExpired:
                health_check_timed_out = True
                continue
            except OSError:
                continue
            if result.returncode == 0:
                return executable
    if health_check_timed_out:
        raise RuntimeError(
            f"{requested or 'Docker or Podman'} was found, but its health check timed out; "
            "host execution is disabled"
        )
    if requested:
        raise RuntimeError(
            f"{requested} was requested but is unavailable or not running; host execution is disabled"
        )
    raise RuntimeError("Docker or Podman is required and must be running; host execution is disabled")


def execute(
    command: str,
    *,
    project_dir: Path | None = None,
    timeout: float = 60.0,
    prepared_snapshot: ProjectSnapshot | None = None,
) -> int:
    """Run one approved command in a disposable, network-disabled container copy."""
    if not command.strip():
        raise ValueError("Cannot execute an empty command")
    if len(command) > _MAX_COMMAND_CHARS:
        raise ValueError(f"Command exceeds the {_MAX_COMMAND_CHARS}-character sandbox limit")
    if not is_safe(command):
        raise ValueError("This command matches errdoc's destructive-command safety blacklist")
    if not math.isfinite(timeout) or timeout <= 0 or timeout > _MAX_SANDBOX_TIMEOUT:
        raise ValueError(
            f"Sandbox timeout must be finite and between 0 and {_MAX_SANDBOX_TIMEOUT:g} seconds"
        )

    runtime = _runtime()
    image = os.environ.get("ERRDOC_SANDBOX_IMAGE", _DEFAULT_IMAGE)
    inspected = subprocess.run(
        [runtime, "image", "inspect", "--format", "{{.Id}}", image],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if inspected.returncode != 0:
        raise RuntimeError(
            f"Sandbox image '{image}' is not available locally. Pull or build it first; "
            "errdoc does not download images automatically."
        )
    image_id = inspected.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{64}", image_id):
        image_id = f"sha256:{image_id}"
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise RuntimeError("Container runtime returned an invalid sandbox image identifier")

    project_root = Path(project_dir or Path.cwd()).resolve()
    snapshot_info = prepared_snapshot or build_project_snapshot(project_root)
    if snapshot_info.root != project_root:
        raise ValueError("Prepared sandbox snapshot belongs to a different project directory")
    argv = split_command(command)
    if not argv:
        raise ValueError("Cannot execute an empty command")

    with tempfile.TemporaryDirectory(prefix="errdoc-sandbox-") as temporary:
        cidfile = Path(temporary) / "container-id"
        container_command = [
            runtime, "run", "--interactive", "--network", "none", "--read-only",
            "--tmpfs", "/workspace:rw,nosuid,nodev,size=512m,mode=1777",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777",
            "--memory", "1g", "--cpus", "1", "--pids-limit", "128",
            "--ulimit", "fsize=104857600:104857600", "--ulimit", "nofile=256:256",
            "--ulimit", "core=0:0",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "65534:65534", "--workdir", "/workspace",
            "--log-driver", "none", "--cidfile", str(cidfile),
            "--entrypoint", "python", image_id, "-c", _CONTAINER_BOOTSTRAP, "--", *argv,
        ]
        try:
            result = subprocess.run(
                container_command, input=snapshot_info.archive, timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Sandbox command exceeded the {timeout:g}-second timeout") from exc
        finally:
            try:
                container_id = cidfile.read_text(encoding="ascii").strip()
            except OSError:
                container_id = ""
            if container_id:
                subprocess.run(
                    [runtime, "rm", "--force", container_id],
                    capture_output=True, timeout=10, check=False,
                )
    return result.returncode
