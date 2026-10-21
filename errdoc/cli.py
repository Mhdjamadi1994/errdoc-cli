"""Command-line interface for errdoc and its fix alias."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.prompt import Prompt

from . import __version__
from .capture import display_command, read_error_file, read_error_stream, recent_history, run_command
from .compressor import compress_log, sanitize
from .config import Config, config_path, load_config
from .context import detect_context
from .executor import build_project_snapshot, execute
from .llm_engine import diagnose, needs_llm, sanitize_model_response
from .ui import console, error_console, show_diagnosis, show_error, show_fix


@click.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True, "allow_interspersed_args": False})
@click.version_option(__version__)
@click.option("--file", "error_file", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Analyze an existing log file.")
@click.option("--no-llm", is_flag=True, help="Capture and compress output without contacting an LLM.")
@click.option("--history", "include_history", is_flag=True, help="Include recent shell history in the analysis.")
@click.option("--history-file", type=click.Path(exists=True, dir_okay=False, path_type=Path), help="Include commands from an exported history file.")
@click.option("--execute-fix", is_flag=True, help="Ask before running a proposed command in a disposable Docker/Podman copy; changes are discarded.")
@click.option("--config-init", "initialize_config", is_flag=True, help="Create the default per-user configuration file.")
@click.option("--timeout", type=click.FloatRange(min=0.1, max=600.0), default=120.0, show_default=True, help="Command timeout in seconds (maximum 600).")
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def main(
    ctx: click.Context,
    error_file: Path | None,
    no_llm: bool,
    include_history: bool,
    history_file: Path | None,
    execute_fix: bool,
    initialize_config: bool,
    timeout: float,
    command: tuple[str, ...],
) -> int:
    """Analyze a command's failure, a log file, or piped input."""
    if initialize_config:
        if error_file or command or history_file:
            raise click.UsageError("--config-init cannot be combined with a file or command.")
        try:
            path = config_path()
            if path.exists():
                raise click.ClickException(f"Configuration already exists: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(Config()), indent=2) + "\n", encoding="utf-8")
            console.print(f"Created [green]{path}[/green]")
            return 0
        except OSError as exc:
            error_console.print(f"[red]errdoc: could not create configuration: {exc}[/red]")
            raise SystemExit(1) from exc

    command_exit_code: int | None = None
    fix_exit_code: int | None = None
    config: Config | None = None
    try:
        if error_file:
            raw = read_error_file(error_file)
            title = sanitize(str(error_file))
        elif command:
            result = run_command(command, timeout=timeout)
            title = sanitize(display_command(result.command))
            raw = result.output
            command_exit_code = result.returncode
            if result.returncode == 0:
                console.print("[green]Command completed successfully.[/green]")
                return 0
        elif not sys.stdin.isatty():
            raw = read_error_stream(sys.stdin)
            title = "Piped input"
        else:
            raise click.UsageError("Provide a command, --file PATH, or pipe error text to stdin.")

        history_entries = recent_history() if include_history else []
        if history_file:
            history_entries.extend(read_error_file(history_file).splitlines()[-20:])
        if history_entries:
            raw += "\n\nRecent shell history:\n" + "\n".join(history_entries)

        config = load_config()
        compressed = compress_log(raw, max_chars=config.max_input_chars)
        show_error(title, compressed)
        if no_llm:
            if command_exit_code:
                ctx.exit(command_exit_code)
            return 0

        model_used = needs_llm(compressed)
        if model_used:
            console.print(f"[yellow]Generating diagnosis with {config.provider} ({config.model}); waiting for the local/API response...[/yellow]")
            console.print("[yellow]AI diagnosis is unverified advice. Check it against the traceback and project before acting.[/yellow]")
            with console.status("Analyzing error...", spinner="dots"):
                result_text = diagnose(compressed, detect_context(), config)
            result_text, commands_removed = sanitize_model_response(result_text)
            if commands_removed:
                console.print("[yellow]Model-generated commands or potentially unsafe advice were hidden because their safety and accuracy have not passed the release gate.[/yellow]")
        else:
            result_text = diagnose(compressed, detect_context(), config)
        result_text = sanitize(result_text)
        show_diagnosis(result_text)
        proposed = None if model_used else _extract_command(result_text)
        if proposed:
            show_fix(proposed)
            if execute_fix:
                fix_exit_code = _confirm_and_execute(proposed, timeout)
        elif execute_fix:
            candidate = Prompt.ask("No command was proposed. Enter a command to run, or leave blank", default="")
            if candidate:
                show_fix(candidate)
                fix_exit_code = _confirm_and_execute(candidate, timeout)

        final_code = fix_exit_code if fix_exit_code is not None else command_exit_code or 0
        if final_code:
            ctx.exit(final_code)
        return 0
    except click.exceptions.Exit:
        raise
    except (RuntimeError, ValueError, OSError) as exc:
        message = sanitize(str(exc))
        if config is not None and config.api_key:
            message = message.replace(config.api_key, "[REDACTED]")
        error_console.print(f"[red]errdoc: {message}[/red]")
        raise SystemExit(1) from exc


def _extract_command(text: str) -> str | None:
    """Extract one concrete command and reject examples or placeholders."""
    fenced = re.search(r"(?:\x60){3}(?:bash|sh|shell|powershell|cmd|python|py|text)?\s*\n(.*?)\n(?:\x60){3}", text, re.I | re.S)
    if fenced:
        lines = [line.strip() for line in fenced.group(1).splitlines() if line.strip()]
        candidate = lines[0] if len(lines) == 1 else None
    else:
        labeled = re.search(r"(?im)^Suggested command:\s*(?:\x60)?(.+?)(?:\x60)?\s*$", text)
        candidate = labeled.group(1).strip() if labeled else None
    if candidate and candidate.startswith("#"):
        return None
    if candidate and re.search(r"(?i)\byour_[a-z0-9_.-]+|\bplaceholder\b|\bTODO\b|<[^>]+>|\b(?:replace|insert)_me\b", candidate):
        return None
    return candidate


def _confirm_and_execute(command: str, timeout: float) -> int | None:
    project_root = Path.cwd().resolve()
    snapshot = build_project_snapshot(project_root)
    manifest_dir = project_root / ".errdoc"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    if not manifest_dir.resolve().is_relative_to(project_root):
        raise OSError("Snapshot preview directory resolves outside the project")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest_path = manifest_dir / f"sandbox-snapshot-preview-{stamp}.json"
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": ".",
        "archive_bytes": len(snapshot.archive),
        "included_file_bytes": snapshot.included_bytes,
        "limits": {
            "max_file_bytes": 64 * 1024 * 1024,
            "max_files": 10_000,
            "max_entries": 20_000,
        },
        "included": [asdict(entry) for entry in snapshot.included],
        "excluded": [asdict(entry) for entry in snapshot.excluded],
    }
    with manifest_path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(manifest, indent=2) + "\n")
    relative_manifest = manifest_path.relative_to(project_root).as_posix()
    console.print(
        f"[bold]Sandbox snapshot preview[/bold]: {len(snapshot.included)} files, "
        f"{snapshot.included_bytes} source bytes; {len(snapshot.excluded)} paths filtered."
    )
    for entry in snapshot.included[:100]:
        console.print(f"  + {entry.path} ({entry.size_bytes} bytes)", markup=False)
    if len(snapshot.included) > 100:
        console.print(f"  ... {len(snapshot.included) - 100} more included files")
    reasons: dict[str, int] = {}
    for entry in snapshot.excluded:
        reason = entry.reason or "excluded"
        reasons[reason] = reasons.get(reason, 0) + 1
    for reason, count in sorted(reasons.items()):
        console.print(f"  - filtered {count}: {reason}")
    console.print(
        f"Full path-by-path manifest (names and sizes only): {relative_manifest}. "
        "Review it before answering yes; the command will use this exact snapshot."
    )
    if not click.confirm("Run this command in the disposable sandbox?", default=False):
        console.print("Sandbox execution cancelled.")
        return None
    console.print(
        "[yellow]Running in a disposable container copy. It has no network and cannot modify the original project.[/yellow]"
    )
    return execute(command, timeout=timeout, project_dir=project_root, prepared_snapshot=snapshot)

def fix() -> None:
    """Entry point for the fix executable alias."""
    main(prog_name="fix")
