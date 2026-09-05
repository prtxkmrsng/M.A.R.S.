"""CLI debug mode for running queries directly through MARS."""

import argparse
import asyncio
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mars.pipeline import MARSPipeline

console = Console(force_terminal=True, legacy_windows=False)


async def run_cli(query: str):
    pipeline = MARSPipeline()
    console.print(f"[bold cyan]Submitting query to MARS:[/bold cyan] {query}\n")

    def cli_event(event_type: str, data: any):
        if event_type == "router_classified":
            console.print(f"[yellow]→ Phase 1 Gating Decision:[/yellow] {data.get('raw')}")
        elif event_type == "phase2_start":
            console.print("[green]→ Phase 2 Fan-Out: Convening 5 Council Personas simultaneously...[/green]")
        elif event_type == "council_member_done":
            console.print(f"  ✓ {data.role_name} ({data.provider}) finished in {data.latency_ms / 1000.0:.2f}s")
        elif event_type == "chairman_draft_done":
            console.print(f"[magenta]→ Phase 3: Chairman synthesized Initial Draft ({data.latency_ms / 1000.0:.2f}s)[/magenta]")
        elif event_type == "negativist_audit_done":
            console.print(f"[red]→ Phase 3: Negativist completed Red-Team Audit ({data.latency_ms / 1000.0:.2f}s)[/red]")
        elif event_type == "chairman_resolution_done":
            console.print(f"[magenta]→ Phase 3: Chairman delivered Final Resolution ({data.latency_ms / 1000.0:.2f}s)[/magenta]")
        elif event_type == "validation_passed":
            console.print(f"[bold green]→ Phase 4: Validator passed output: {data.get('verdict')}[/bold green]")
        elif event_type == "validation_rejected":
            console.print(f"[bold red]→ Phase 4: Validator rejected output: {data.get('verdict')}[/bold red]")

    result = await pipeline.run(query, event_callback=cli_event)

    console.print("\n" + "=" * 60 + "\n")
    console.print(
        Panel(
            result.final_output,
            title=f"🪐 MARS Final Output ({result.route})",
            border_style="green",
        )
    )

    # Telemetry Table
    t_table = Table(title="Execution Telemetry", header_style="bold blue")
    t_table.add_column("Metric", style="cyan")
    t_table.add_column("Value", style="bold white")
    t_table.add_row("Total Latency", f"{result.telemetry.total_latency_s:.2f}s")
    t_table.add_row("Total Tokens", f"{result.telemetry.total_tokens:,}")
    t_table.add_row("Estimated Cost", f"${result.telemetry.cost_usd:.2f} (Free Tier)")
    t_table.add_row("Active Providers", ", ".join(result.telemetry.active_providers) or "None")
    console.print(t_table)


def main():
    parser = argparse.ArgumentParser(description="Run a query through MARS CLI")
    parser.add_argument("query", nargs="?", default="Explain why scaling drone delivery in suburban neighborhoods is difficult.", help="Prompt to evaluate")
    args = parser.parse_args()

    asyncio.run(run_cli(args.query))


if __name__ == "__main__":
    main()
