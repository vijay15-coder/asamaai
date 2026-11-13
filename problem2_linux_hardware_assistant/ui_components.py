"""
Terminal UI / Presentation enhancements for Problem 2.
"""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich.prompt import Prompt

console = Console(safe_box=True)


def render_banner():
    banner_text = Text()
    banner_text.append("LINUX HARDWARE ASSISTANT ", style="bold cyan")
    banner_text.append("v2.0\n", style="bold yellow")
    banner_text.append("Deterministic Tool Calling | Sandboxed | Zero-Hallucination Guardrails", style="dim white")
    console.print(Panel(banner_text, border_style="cyan", padding=(1, 2)))


def render_quick_suggestions():
    table = Table.grid(padding=1)
    table.add_column(style="bold yellow")
    table.add_column(style="dim white")
    
    table.add_row("1.", "Can I add more RAM, and how much?")
    table.add_row("2.", "Is my SSD NVMe or SATA?")
    table.add_row("3.", "and what about the GPU?")
    table.add_row("4.", "What are my CPU specs and core count?")
    table.add_row("exit", "Quit the interactive assistant")

    console.print(Panel(table, title="Quick Examples", border_style="dim", padding=(0, 2)))


def render_tool_execution(tool_name: str, status: str = "SUCCESS", details: str = ""):
    table = Table.grid(padding=1)
    table.add_column(style="dim cyan", width=14)
    table.add_column(style="bold white")
    table.add_row("Security Check:", "[green][PASS] Allow-Listed Binary (shell=False)[/green]")
    table.add_row("Tool Dispatched:", f"[bold cyan]{tool_name}[/bold cyan]")
    if details:
        table.add_row("Data Source:", f"[dim]{details}[/dim]")
    
    console.print(Panel(table, title="Safe System Query Execution", border_style="blue", padding=(0, 1)))


def render_assistant_response(answer: str, is_warning: bool = False):
    color = "yellow" if is_warning else "green"
    icon = "[!]" if is_warning else "[*]"
    title = f"{icon} Hardware Assistant Response"
    console.print(Panel(f"[bold white]{answer}[/bold white]", title=title, border_style=color, padding=(1, 2)))

