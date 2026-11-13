"""
Interactive Premium CLI for Problem 2: Linux Hardware Assistant.
Run with:
    python -m problem2_linux_hardware_assistant.cli
"""
import sys
from rich.prompt import Prompt
from .assistant import HardwareAssistant
from .ui_components import (
    console,
    render_banner,
    render_quick_suggestions,
    render_tool_execution,
    render_assistant_response
)


def run_cli():
    render_banner()
    render_quick_suggestions()

    assistant = HardwareAssistant(use_mock=True)

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]User Query[/bold cyan]").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                console.print("\n[bold yellow]Session finished. Have a great day![/bold yellow]\n")
                break

            response = assistant.ask(user_input)

            # Display safe tool execution telemetry
            if response["tools_invoked"]:
                for tool in response["tools_invoked"]:
                    render_tool_execution(tool, details="System DMI/Sysfs/PCI bus")

            # Check if anti-hallucination refusal was triggered
            is_refusal = "I cannot determine" in response["answer"]
            render_assistant_response(response["answer"], is_warning=is_refusal)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Session closed.[/bold yellow]\n")
            break


if __name__ == "__main__":
    run_cli()
