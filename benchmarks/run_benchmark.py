"""Benchmark runner comparing Single-Model Baseline vs MARS Multi-Agent Council."""

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table

from mars.client import fetch_agent_response
from mars.pipeline import MARSPipeline

console = Console(force_terminal=True, legacy_windows=False)


async def run_baseline_model(question: str) -> dict:
    """Run a single frontier/standard LLM prompt as baseline."""
    start = time.perf_counter()
    resp = await fetch_agent_response(
        node_key="chairman",
        system_prompt="You are an expert AI advisor. Provide a comprehensive, rigorous, and logically sound response.",
        user_query=question,
    )
    duration_s = round(time.perf_counter() - start, 2)
    return {
        "content": resp.content,
        "latency_s": duration_s,
        "tokens": resp.tokens_used,
        "provider": resp.provider,
        "model": resp.model,
    }


async def main():
    parser = argparse.ArgumentParser(description="Run MARS Benchmark Suite")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions to evaluate")
    parser.add_argument("--output-dir", type=str, default="benchmarks", help="Output directory")
    args = parser.parse_args()

    questions_path = Path(__file__).parent / "questions.json"
    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if args.limit:
        questions = questions[: args.limit]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "benchmark_results.csv"
    report_path = out_dir / "benchmark_report.md"

    pipeline = MARSPipeline()
    results = []

    console.print(f"[bold green]Starting MARS Benchmark Suite ({len(questions)} items)...[/bold green]\n")

    for idx, item in enumerate(questions, 1):
        q_id = item["id"]
        category = item["category"]
        q_text = item["question"]

        console.print(f"[bold cyan]Evaluating Question {idx}/{len(questions)} [ID: {q_id}] ({category})[/bold cyan]")
        console.print(f"[italic]{q_text[:90]}...[/italic]")

        # 1. Baseline Run
        console.print("  → Running Baseline Model...")
        baseline = await run_baseline_model(q_text)

        # 2. MARS Council Run
        console.print("  → Running MARS Council Pipeline...")
        mars_result = await pipeline.run(q_text)

        critique_summary = "N/A"
        if mars_result.synthesis_result and mars_result.synthesis_result.negativist_critique:
            critique_summary = mars_result.synthesis_result.negativist_critique.content[:150].replace("\n", " ")

        row = {
            "id": q_id,
            "category": category,
            "question": q_text,
            "baseline_provider": baseline["provider"],
            "baseline_model": baseline["model"],
            "baseline_latency_s": baseline["latency_s"],
            "baseline_tokens": baseline["tokens"],
            "mars_route": mars_result.route,
            "mars_latency_s": mars_result.telemetry.total_latency_s,
            "mars_tokens": mars_result.telemetry.total_tokens,
            "mars_providers": "|".join(mars_result.telemetry.active_providers),
            "mars_validation_passed": mars_result.synthesis_result.validation_passed if mars_result.synthesis_result else True,
            "redteam_audit_sample": critique_summary,
        }
        results.append(row)
        console.print(f"  ✓ Finished in {mars_result.telemetry.total_latency_s}s (Tokens: {mars_result.telemetry.total_tokens})\n")

    # Write CSV
    if results:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)

    # Write Markdown Report
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# MARS Benchmark Evaluation Report\n\n")
        f.write(f"**Total Evaluated Queries:** {len(results)}\n\n")
        f.write("| ID | Category | Baseline Latency | MARS Latency | Baseline Tokens | MARS Tokens | Red-Team Audit Sample |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            f.write(
                f"| {r['id']} | {r['category']} | {r['baseline_latency_s']}s | {r['mars_latency_s']}s | "
                f"{r['baseline_tokens']} | {r['mars_tokens']} | {r['redteam_audit_sample']}... |\n"
            )

    console.print(f"[bold green]✓ Benchmark completed![/bold green] Results written to [cyan]{csv_path}[/cyan] and [cyan]{report_path}[/cyan]")


if __name__ == "__main__":
    asyncio.run(main())
