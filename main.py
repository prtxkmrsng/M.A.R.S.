"""Main entry point for MARS (Multi-Agent Reasoning System)."""

import argparse
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.table import Table

from mars.config import check_credentials, reload_env
from mars.ui import create_app

console = Console(force_terminal=True, legacy_windows=False)


def print_env_status():
    """Print an attractive summary table of provider credentials."""
    reload_env()
    status = check_credentials()
    table = Table(title="MARS Provider & API Key Status", header_style="bold magenta")
    table.add_column("Node", style="cyan")
    table.add_column("Role", style="white")
    table.add_column("Provider", style="green")
    table.add_column("Env Variable", style="yellow")
    table.add_column("Status", style="bold")

    configured_count = 0
    for node, info in status.items():
        is_ready = info["configured"]
        if is_ready:
            configured_count += 1
            badge = "[green]✓ Configured[/green]"
        else:
            badge = "[red]✗ Missing[/red]"
        table.add_row(node, info["role"], info["provider"], info["env_var"], badge)

    console.print(table)
    console.print(
        f"\n[bold]{configured_count}/{len(status)}[/bold] nodes ready. "
        "Edit [bold cyan].env[/bold cyan] to configure missing keys.\n"
    )


def main():
    parser = argparse.ArgumentParser(description="MARS: Multi-Agent Reasoning System")
    parser.add_argument("--port", type=int, default=7860, help="Port to run Gradio server on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address to bind")
    parser.add_argument("--share", action="store_true", help="Generate public Gradio share link")
    parser.add_argument("--check-env", action="store_true", help="Check .env credentials and exit")

    args = parser.parse_args()

    console.print("[bold cyan]🪐 Initializing MARS (Multi-Agent Reasoning System)...[/bold cyan]")
    print_env_status()

    if args.check_env:
        sys.exit(0)

    app = create_app()
    console.print(f"[bold green]Starting Gradio web server at http://{args.host}:{args.port}[/bold green]")
    app.queue().launch(server_name=args.host, server_port=args.port, share=args.share)


if __name__ == "__main__":
    main()
