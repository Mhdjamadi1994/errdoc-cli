import pytest

from pathlib import Path
from types import SimpleNamespace

from errdoc import executor


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf ./important",
        "rm -r ./important",
        "rm --recursive ./important",
        "python -c \"import shutil; shutil.rmtree('important')\"",
        "rmdir /s /q C:\\important",
        "del /s /q C:\\important\\*",
        "git reset --hard",
        "git clean -fd",
        "Remove-Item -Recurse -Force C:\\important",
        "Format-Volume -DriveLetter D",
        "DROP DATABASE customer_data",
    ],
)
def test_destructive_commands_are_blocked(command):
    assert executor.is_safe(command) is False


def test_regular_command_is_not_blacklisted():
    assert executor.is_safe("python -m pip show rich")


def test_snapshot_filter_recognizes_windows_reparse_points():
    from types import SimpleNamespace

    class ReparsePath:
        def is_symlink(self):
            return False

        def lstat(self):
            return SimpleNamespace(st_file_attributes=0x400)

    assert executor._is_symlink_or_reparse_point(ReparsePath()) is True


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ('python -c "print(1)"', ["python", "-c", "print(1)"]),
        ('tool "two words" tail', ["tool", "two words", "tail"]),
        ("tool ''", ["tool", ""]),
    ],
)
def test_split_command_respects_quoted_arguments(command, expected):
    import os
    if os.name != "nt":
        assert executor.split_command(command) == expected


@pytest.mark.parametrize("image_id", ["sha256:" + "a" * 64, "a" * 64])
def test_command_runs_in_restricted_container_with_disposable_snapshot(tmp_path, monkeypatch, image_id):
    import io
    import tarfile

    (tmp_path / "app.py").write_text("print('sample')", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=private", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "input.txt").write_text("safe input", encoding="utf-8")
    monkeypatch.setattr(executor, "_runtime", lambda: "docker")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=image_id + "\n", stderr="")
        if command[1] == "run":
            cidfile = command[command.index("--cidfile") + 1]
            with open(cidfile, "w", encoding="ascii") as handle:
                handle.write("container123\n")
            return SimpleNamespace(returncode=0)
        assert command[1:3] == ["rm", "--force"]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(executor.subprocess, "run", fake_run)
    assert executor.execute('python -c "print(1)"', project_dir=tmp_path) == 0

    run_command, run_options = next(
        (command, options) for command, options in calls if command[1] == "run"
    )
    assert run_command[run_command.index("--network") + 1] == "none"
    assert "--read-only" in run_command
    assert run_command[run_command.index("--cap-drop") + 1] == "ALL"
    assert run_command[run_command.index("--memory") + 1] == "1g"
    assert run_command[run_command.index("--cpus") + 1] == "1"
    assert run_command[run_command.index("--pids-limit") + 1] == "128"
    assert "--ulimit" in run_command
    assert run_options["timeout"] == 60.0
    assert run_command[-3:] == ["python", "-c", "print(1)"]
    with tarfile.open(fileobj=io.BytesIO(run_options["input"]), mode="r:") as archive:
        names = set(archive.getnames())
    assert "app.py" in names and "nested/input.txt" in names
    assert ".env" not in names
    assert calls[-1][0][1:3] == ["rm", "--force"]


def test_missing_container_runtime_disables_execution(monkeypatch):
    monkeypatch.setattr(executor.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Docker or Podman is required"):
        executor._runtime()


def test_runtime_health_probe_uses_bounded_timeout(monkeypatch):
    calls = []
    monkeypatch.setattr(
        executor.shutil, "which", lambda name: "docker.exe" if name == "docker" else None
    )
    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda command, **kwargs: (
            calls.append((command, kwargs)) or SimpleNamespace(returncode=0)
        ),
    )

    assert executor._runtime() == "docker.exe"
    assert calls[0][1]["timeout"] == 8


def test_explicit_podman_runtime_is_selected_even_when_docker_is_available(monkeypatch):
    monkeypatch.setenv("ERRDOC_CONTAINER_RUNTIME", "podman")
    monkeypatch.setattr(
        executor.shutil, "which", lambda name: f"{name}.exe"
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(executor.subprocess, "run", fake_run)
    assert executor._runtime() == "podman.exe"
    assert calls == [["podman.exe", "info"]]


def test_unknown_explicit_runtime_fails_closed(monkeypatch):
    monkeypatch.setenv("ERRDOC_CONTAINER_RUNTIME", "runc")
    with pytest.raises(ValueError, match="ERRDOC_CONTAINER_RUNTIME"):
        executor._runtime()


def test_runtime_health_timeout_has_a_specific_error(monkeypatch):
    monkeypatch.setattr(
        executor.shutil, "which", lambda name: "docker.exe" if name == "docker" else None
    )
    monkeypatch.setattr(
        executor.subprocess, "run",
        lambda command, **kwargs: (_ for _ in ()).throw(
            executor.subprocess.TimeoutExpired(command, kwargs["timeout"])
        ),
    )

    with pytest.raises(RuntimeError, match="health check timed out"):
        executor._runtime()


def test_unavailable_image_fails_without_running_command(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, "_runtime", lambda: "docker")
    monkeypatch.setattr(
        executor.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="not found"),
    )
    with pytest.raises(RuntimeError, match="not available locally"):
        executor.execute("python --version", project_dir=tmp_path)


def test_snapshot_omits_secret_named_files_logs_databases_and_hidden_dirs(tmp_path):
    import io
    import tarfile

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "api_token.json").write_text("secret", encoding="utf-8")
    (tmp_path / "app.log").write_text("private log", encoding="utf-8")
    (tmp_path / "cache.db").write_text("private data", encoding="utf-8")
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local" / "private.py").write_text("secret", encoding="utf-8")
    snapshot = executor.build_project_snapshot(tmp_path)
    with tarfile.open(fileobj=io.BytesIO(snapshot.archive), mode="r:") as archive:
        names = set(archive.getnames())
    assert names == {"src/app.py"}
    assert {item.path for item in snapshot.included} == {"src/app.py"}
    filtered = {item.path: item.reason for item in snapshot.excluded}
    assert filtered["api_token.json"] == "sensitive filename pattern"
    assert filtered["app.log"] == "excluded file type"
    assert filtered[".local"] == "hidden directory"


def test_snapshot_enforces_size_limit(tmp_path, monkeypatch):
    (tmp_path / "large.py").write_text("x" * 32, encoding="utf-8")
    monkeypatch.setattr(executor, "_MAX_PROJECT_BYTES", 16)
    with pytest.raises(ValueError, match="size or file-count limit"):
        executor._project_snapshot(tmp_path)


def test_snapshot_enforces_entry_limit_for_empty_directories(tmp_path, monkeypatch):
    for name in ("one", "two", "three"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(executor, "_MAX_PROJECT_ENTRIES", 3)
    with pytest.raises(ValueError, match="entry-count limit"):
        executor._project_snapshot(tmp_path)


def test_snapshot_enforces_regular_file_limit(tmp_path, monkeypatch):
    for name in ("one.py", "two.py", "three.py"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    monkeypatch.setattr(executor, "_MAX_PROJECT_FILES", 2)
    with pytest.raises(ValueError, match="size or file-count limit"):
        executor._project_snapshot(tmp_path)


def test_oversized_command_is_rejected_before_runtime_lookup(monkeypatch):
    monkeypatch.setattr(
        executor, "_runtime", lambda: pytest.fail("runtime must not be inspected")
    )
    command = "x" * (executor._MAX_COMMAND_CHARS + 1)
    assert executor.is_safe(command) is False
    with pytest.raises(ValueError, match="character sandbox limit"):
        executor.execute(command)


@pytest.mark.parametrize("member_name", ["../escaped.txt", "/absolute.txt", "nested/../../escaped.txt"])
def test_container_bootstrap_rejects_path_traversal_members(tmp_path, member_name):
    import io
    import subprocess
    import sys
    import tarfile

    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w") as archive:
        data = b"must not be written"
        member = tarfile.TarInfo(member_name)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))

    bootstrap = executor._CONTAINER_BOOTSTRAP.replace(
        "pathlib.Path('/workspace')", f"pathlib.Path({str(tmp_path)!r})"
    )
    result = subprocess.run(
        [sys.executable, "-c", bootstrap, "--", sys.executable, "-c", "pass"],
        input=archive_bytes.getvalue(), capture_output=True, timeout=5, check=False,
    )
    assert result.returncode != 0
    assert b"rejected unsafe project path" in result.stderr
    assert not (tmp_path.parent / "escaped.txt").exists()


@pytest.mark.parametrize("member_type", ["symlink", "hardlink"])
def test_container_bootstrap_rejects_link_entries(tmp_path, member_type):
    import io
    import subprocess
    import sys
    import tarfile

    archive_bytes = io.BytesIO()
    with tarfile.open(fileobj=archive_bytes, mode="w") as archive:
        member = tarfile.TarInfo("linked.txt")
        member.type = tarfile.SYMTYPE if member_type == "symlink" else tarfile.LNKTYPE
        member.linkname = "../../outside.txt"
        archive.addfile(member)

    bootstrap = executor._CONTAINER_BOOTSTRAP.replace(
        "pathlib.Path('/workspace')", f"pathlib.Path({str(tmp_path)!r})"
    )
    result = subprocess.run(
        [sys.executable, "-c", bootstrap, "--", sys.executable, "-c", "pass"],
        input=archive_bytes.getvalue(), capture_output=True, timeout=5, check=False,
    )
    assert result.returncode != 0
    assert b"rejected non-regular project entry" in result.stderr
    assert not (tmp_path.parent / "outside.txt").exists()


def test_snapshot_excludes_symlinks_to_files_outside_the_project(tmp_path, monkeypatch):
    import io
    import tarfile

    project = tmp_path / "project"
    project.mkdir()
    link = project / "leak.txt"
    link.write_text("external data must not be archived", encoding="utf-8")
    link_dir = project / "linked-directory"
    link_dir.mkdir()
    (link_dir / "private.txt").write_text("private", encoding="utf-8")
    symlink_paths = {link, link_dir}
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path in symlink_paths or original_is_symlink(path),
    )
    (project / "safe.txt").write_text("safe", encoding="utf-8")

    with tarfile.open(fileobj=io.BytesIO(executor._project_snapshot(project)), mode="r:") as archive:
        names = set(archive.getnames())
    assert names == {"safe.txt"}


def test_shell_operators_are_parsed_as_arguments_not_executed_by_a_shell():
    parsed = executor.split_command("python -c \"print('safe')\" && whoami")
    assert parsed == ["python", "-c", "print('safe')", "&&", "whoami"]


def test_container_timeout_still_removes_disposable_container(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, "_runtime", lambda: "docker")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1:3] == ["image", "inspect"]:
            return SimpleNamespace(returncode=0, stdout="sha256:" + "b" * 64 + "\n", stderr="")
        if command[1] == "run":
            with open(command[command.index("--cidfile") + 1], "w", encoding="ascii") as handle:
                handle.write("timedout123\n")
            raise executor.subprocess.TimeoutExpired(command, 1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(executor.subprocess, "run", fake_run)
    (tmp_path / "app.py").write_text("pass", encoding="utf-8")
    with pytest.raises(RuntimeError, match="exceeded the 1-second timeout"):
        executor.execute("python app.py", project_dir=tmp_path, timeout=1)
    assert calls[-1][1:3] == ["rm", "--force"]


def test_destructive_command_is_rejected_before_container_execution():
    with pytest.raises(ValueError, match="safety blacklist"):
        executor.execute("rm -rf important")


def test_empty_command_is_rejected():
    with pytest.raises(ValueError, match="empty command"):
        executor.execute("")


def test_invalid_timeout_is_rejected():
    with pytest.raises(ValueError, match="timeout must be finite"):
        executor.execute("python --version", timeout=0)


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 601])
def test_nonfinite_or_unbounded_timeout_is_rejected(timeout):
    with pytest.raises(ValueError, match="timeout must be finite"):
        executor.execute("python --version", timeout=timeout)
