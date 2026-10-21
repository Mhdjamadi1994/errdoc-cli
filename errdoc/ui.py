"""Three-color terminal output."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
error_console = Console(stderr=True)


def show_error(title: str, detail: str) -> None:
    console.print(Panel(Text(detail or "No error output captured.", style="red"), title=title, border_style="red"))


def show_diagnosis(text: str) -> None:
    console.print(Panel(Text(text, style="yellow"), title="Diagnosis", border_style="yellow"))


def show_fix(command: str) -> None:
    console.print(Panel(Text(command, style="green"), title="Suggested fix", border_style="green"))
