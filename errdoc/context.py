"""Lightweight project and operating-system context detection."""

from __future__ import annotations

import platform
from pathlib import Path


def detect_context(cwd: str | Path = ".") -> dict[str, str]:
    root = Path(cwd).resolve()
    markers = {
        "Django": ("manage.py",),
        "Node.js": ("package.json", "node_modules"),
        "Git": (".git",),
        "Python": ("pyproject.toml", "requirements.txt", "setup.py"),
    }
    frameworks: list[str] = []
    for name, files in markers.items():
        if any((root / file).exists() for file in files):
            frameworks.append(name)
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "python": platform.python_version(),
        "project": ", ".join(frameworks) or "Unknown",
    }
