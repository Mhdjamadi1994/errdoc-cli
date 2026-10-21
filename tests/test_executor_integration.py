"""Opt-in integration checks for a locally provisioned Docker or Podman runtime."""

from __future__ import annotations

import os

import pytest

from errdoc.executor import execute


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("ERRDOC_RUN_SANDBOX_INTEGRATION") != "1",
        reason="set ERRDOC_RUN_SANDBOX_INTEGRATION=1 to run container integration checks",
    ),
]


def test_command_can_edit_read_only_source_copy_without_changing_original(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("original", encoding="utf-8")
    sample.chmod(0o444)

    try:
        result = execute(
            "python -c \"from pathlib import Path; Path('sample.txt').write_text('changed')\"",
            project_dir=tmp_path,
            timeout=120,
        )
        assert result == 0
        assert sample.read_text(encoding="utf-8") == "original"
    finally:
        sample.chmod(0o644)


def test_container_denies_root_filesystem_writes_and_external_network(tmp_path):
    unprivileged_result = execute(
        "python -c \"import os; raise SystemExit(os.geteuid() == 0)\"",
        project_dir=tmp_path,
        timeout=120,
    )
    world_writable_probe_dir_result = execute(
        "python -c \"import pathlib, stat; p = pathlib.Path('/var/tmp'); "
        "raise SystemExit(0 if p.is_dir() and p.stat().st_mode & stat.S_IWOTH else 1)\"",
        project_dir=tmp_path,
        timeout=120,
    )
    read_only_result = execute(
        "python -c \"from pathlib import Path; Path('/var/tmp/errdoc-root-write-check').write_text('x')\"",
        project_dir=tmp_path,
        timeout=120,
    )
    network_result = execute(
        "python -c \"import socket; names = {name for _, name in socket.if_nameindex()}; "
        "raise SystemExit(0 if names == {'lo'} else 1)\"",
        project_dir=tmp_path,
        timeout=120,
    )

    assert unprivileged_result == 0
    assert world_writable_probe_dir_result == 0
    assert read_only_result != 0
    assert network_result == 0


def test_container_enforces_process_and_memory_limits(tmp_path):
    command = (
        "python -c \"from pathlib import Path; "
        "read=lambda ps: next((p.read_text().strip() for p in map(Path, ps) if p.is_file()), None); "
        "p=read(['/sys/fs/cgroup/pids.max','/sys/fs/cgroup/pids/pids.limit_in_bytes']); "
        "m=read(['/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory/memory.limit_in_bytes']); "
        "assert p is not None and 0 < int(p) <= 128; "
        "assert m is not None and 0 < int(m) <= 1073741824\""
    )
    assert execute(command, project_dir=tmp_path, timeout=120) == 0
