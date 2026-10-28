"""Comprehensive verification and sanity check utility for MARS.

Usage:
    python verify_all.py             # Run all offline verification checks
    python verify_all.py --live      # Run offline checks + live single-query smoke test
    python verify_all.py --env-only  # Inspect API credentials and configuration
"""

import argparse
import asyncio
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(force_terminal=True, legacy_windows=False)


def check_environment_packages() -> bool:
    """Verify required Python packages are installed."""
    required = ["openai", "dotenv", "pydantic", "gradio", "rich", "httpx", "pytest"]
    missing = []
    for pkg in required:
        try:
            if pkg == "dotenv":
                import dotenv
            else:
                __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        console.print(f"[bold red]✗ Missing packages:[/bold red] {', '.join(missing)}")
        console.print("[yellow]Run: pip install -r requirements.txt pytest[/yellow]\n")
        return False
    console.print("[bold green]✓ All core dependency packages are installed.[/bold green]")
    return True


def check_api_credentials() -> dict:
    """Inspect and display API key status for all 9 nodes."""
    from mars.config import check_credentials

    status = check_credentials()
    table = Table(title="MARS Node & Provider Status", header_style="bold magenta")
    table.add_column("Node", style="cyan")
    table.add_column("Role", style="white")
    table.add_column("Provider", style="green")
    table.add_column("Env Var", style="yellow")
    table.add_column("Status", style="bold")

    configured = 0
    for node, info in status.items():
        ready = info["configured"]
        if ready:
            configured += 1
            badge = "[green]✓ Ready[/green]"
        else:
            badge = "[red]✗ Missing[/red]"
        table.add_row(node, info["role"], info["provider"], info["env_var"], badge)

    console.print(table)
    console.print(f"[bold]{configured}/{len(status)}[/bold] nodes configured.\n")
    return status


def run_unit_tests() -> bool:
    """Execute pytest test suite."""
    import pytest

    console.print("[bold cyan]Running automated test suite (pytest)...[/bold cyan]")
    ret_code = pytest.main(["-q", "tests/"])
    if ret_code == 0:
        console.print("[bold green]✓ All unit and mock tests passed successfully.[/bold green]\n")
        return True
    else:
        console.print(f"[bold red]✗ Pytest failed with exit code {ret_code}.[/bold red]\n")
        return False


async def run_live_smoke_test():
    """Execute a live quick query through MARS pipeline to confirm live provider routing."""
    from mars.pipeline import MARSPipeline

    console.print("[bold cyan]Running live smoke test query through MARS...[/bold cyan]")
    pipeline = MARSPipeline()
    test_query = "What is the principle of conservation of energy in physics? Answer in 2 sentences."
    start = time.perf_counter()

    def live_cb(event_type: str, data: any):
        if event_type == "router_classified":
            console.print(f"  [yellow]Phase 1 Gating Decision:[/yellow] {data.get('raw')}")
        elif event_type == "pipeline_complete":
            console.print(f"  [green]Pipeline completed route: {data.get('route')}[/green]")

    result = await pipeline.run(test_query, event_callback=live_cb)
    elapsed = time.perf_counter() - start

    console.print(
        Panel(
            result.final_output[:300] + ("..." if len(result.final_output) > 300 else ""),
            title=f"Live Result ({result.route}) - {elapsed:.2f}s",
            border_style="green",
        )
    )
    console.print(f"Tokens: {result.telemetry.total_tokens} | Providers: {', '.join(result.telemetry.active_providers)}\n")


def main():
    parser = argparse.ArgumentParser(description="MARS Verification & Sanity Runner")
    parser.add_argument("--live", action="store_true", help="Run a live query through MARS providers")
    parser.add_argument("--env-only", action="store_true", help="Only check environment and credentials")
    args = parser.parse_args()

    console.print(Panel.fit("[bold cyan]🪐 MARS System Verification & Diagnostics[/bold cyan]"))

    # Step 1: Package dependencies
    console.print("\n[bold]1. Checking Dependencies:[/bold]")
    deps_ok = check_environment_packages()

    # Step 2: Credentials
    console.print("\n[bold]2. Checking Provider Credentials:[/bold]")
    creds = check_api_credentials()

    if args.env_only:
        return

    # Step 3: Automated Unit Tests
    console.print("\n[bold]3. Running Test Suite:[/bold]")
    tests_ok = run_unit_tests()

    # Step 4: Live smoke test (if requested)
    if args.live:
        console.print("\n[bold]4. Executing Live Smoke Test:[/bold]")
        asyncio.run(run_live_smoke_test())

    summary_status = "READY" if (deps_ok and tests_ok) else "ATTENTION REQUIRED"
    style = "bold green" if summary_status == "READY" else "bold red"
    console.print(Panel(f"[{style}]Verification Summary: {summary_status}[/{style}]", border_style="cyan"))


if __name__ == "__main__":
    main()
