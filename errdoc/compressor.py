"""Reduce common traceback noise while preserving actionable error context."""

from __future__ import annotations

import ipaddress
import os
import re
from itertools import groupby
from pathlib import Path

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_SECRET = re.compile(
    r"(?i)((?:api[_-]?key|access[_-]?key|secret(?:[_-]?(?:access[_-]?)?key)?|"
    r"client[_-]?secret|token|password|passwd|pwd|private[_-]?key)[\"']?)"
    r"(\s*[=:]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_BEARER = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
_AUTHORIZATION = re.compile(
    r"(?i)(\bAuthorization[\"']?\s*[:=]\s*[\"']?)(Bearer|Basic|Token)"
    r"\s+([^\"'\s,;]+)([\"']?)"
)
_URL_CREDENTIALS = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^/@\s?#]+)@")
_PRIVATE_KEY_BLOCK = re.compile(
    r"(?is)-----BEGIN ([A-Z0-9 ]*PRIVATE KEY)-----.*?-----END \1-----"
)
_SITE_PACKAGES = re.compile(r"(?:^|[/\\])(?:site-packages|dist-packages)(?:[/\\]|$)", re.I)
_TRACE_START = re.compile(r"Traceback \(most recent call last\):")
_IPV4_CANDIDATE = re.compile(r"(?<![0-9A-Za-z_.])(?:\d{1,3}\.){3}\d{1,3}(?![0-9A-Za-z_.])")
_IPV6_CANDIDATE = re.compile(
    r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}"
    r"(?:%[A-Za-z0-9_.-]+)?(?![0-9A-Fa-f:])"
)
_VERSION_VALUE_CONTEXT = re.compile(r"(?i)(?:\bversion|\bclass file version)\s*[=:]\s*$")
_WINDOWS_USER_HOME = re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s:'\"]+")
_UNIX_USER_HOME = re.compile(r"/(?:home|Users)/[^/\\\s:'\"]+")


def sanitize(text: str) -> str:
    """Remove terminal colors and redact credentials, IPs, and common home paths."""
    text = _ANSI.sub("", text)
    text = _PRIVATE_KEY_BLOCK.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _SECRET.sub(r"\1\2[REDACTED]", text)
    text = _AUTHORIZATION.sub(r"\1\2 [REDACTED]\4", text)
    text = _BEARER.sub(r"\1[REDACTED]", text)
    text = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", text)

    home = str(Path.home())
    if home and home not in {".", os.path.abspath(os.sep)}:
        text = re.sub(re.escape(home), "[HOME]", text, flags=re.I if os.name == "nt" else 0)
        if os.name == "nt":
            text = re.sub(re.escape(home.replace("\\", "/")), "[HOME]", text, flags=re.I)
    text = _WINDOWS_USER_HOME.sub("[HOME]", text)
    text = _UNIX_USER_HOME.sub("[HOME]", text)

    def redact_ip(match: re.Match[str]) -> str:
        candidate = match.group(0).split("%", 1)[0]
        # Four-part assembly versions look exactly like IPv4 literals. Preserve
        # them only when explicitly labeled as versions so diagnostics retain
        # useful metadata without broadly weakening address redaction.
        if match.re is _IPV4_CANDIDATE and _VERSION_VALUE_CONTEXT.search(text[:match.start()]):
            return match.group(0)
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            return match.group(0)
        return "<IP_REDACTED>"

    text = _IPV6_CANDIDATE.sub(redact_ip, text)
    return _IPV4_CANDIDATE.sub(redact_ip, text)


def compress_log(text: str, *, max_chars: int = 12_000, max_lines: int = 100) -> str:
    """Drop repetitive dependency frames and retain the traceback's useful edges."""
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")
    if max_lines < 1:
        raise ValueError("max_lines must be at least 1")

    lines = sanitize(text).splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    trace_indexes = [i for i, line in enumerate(lines) if _TRACE_START.search(line)]
    if trace_indexes:
        start = trace_indexes[-1]
        lines = lines[start:]

    kept: list[str] = []
    skipped = 0
    for line in lines:
        if _SITE_PACKAGES.search(line) and line.lstrip().startswith("File "):
            skipped += 1
            continue
        if skipped and line.lstrip().startswith("File "):
            kept.append(f"... {skipped} dependency frame(s) omitted ...")
            skipped = 0
        kept.append(line)
    if skipped:
        kept.append(f"... {skipped} dependency frame(s) omitted ...")

    collapsed: list[str] = []
    for line, group in groupby(kept):
        count = sum(1 for _ in group)
        if count > 3:
            collapsed.extend((line, f"... repeated line omitted {count - 1} times ..."))
        else:
            collapsed.extend([line] * count)
    result = "\n".join(collapsed).strip()
    if len(result) > max_chars:
        marker = "... earlier output truncated ...\n"
        if max_chars <= len(marker):
            return result[-max_chars:]
        result = marker + result[-(max_chars - len(marker)):]
    return result
