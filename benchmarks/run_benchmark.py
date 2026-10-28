import asyncio
import json
from pathlib import Path
from mars.pipeline import MARSPipeline

JUDGE_SYSTEM_PROMPT = (
    "You are an impartial academic benchmark judge. You will be given a complex User Query, "
    "Response A (Single-Model Baseline), and Response B (MARS 9-Node Council). "
    "Evaluate both responses on a 1-10 scale across three criteria:\n"
    "1. Factuality & Logical Rigor\n"
    "2. Blind-Spot & Risk Detection\n"
    "3. Practical Actionability\n"
    "Output strict JSON with keys: "
    '{"baseline_score": float, "mars_score": float, "winner": "MARS"|"BASELINE"|"TIE", "rationale": str}'
)


async def run_benchmarks() -> None:
    questions_path = Path(__file__).parent / "questions.json"
    if not questions_path.exists():
        questions = [
            "Design a zero-budget distributed rate limiter for an API gateway handling 10,000 req/sec across 3 regions.",
            "A SaaS startup wants to replace its entire customer support team with an autonomous LLM agent tomorrow. Analyze this strategy and provide an execution plan.",
        ]
    else:
        with open(questions_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            questions = [q["question"] if isinstance(q, dict) else str(q) for q in data]

    pipeline = MARSPipeline()
    results = []

    for idx, q in enumerate(questions, 1):
        print(f"\n[{idx}/{len(questions)}] Running benchmark query: {q[:80]}...")
        mars_res = await pipeline.run(q, force_council=True)
        baseline_resp = await pipeline.client.execute_node(
            node_id="chairman",
            system_prompt="You are a helpful, rigorous AI assistant.",
            user_prompt=q,
        )

        judge_prompt = (
            f"### USER QUERY:\n{q}\n\n"
            f"### RESPONSE A (Baseline):\n{baseline_resp.content}\n\n"
            f"### RESPONSE B (MARS Council):\n{mars_res.final_output}"
        )
        judge_resp = await pipeline.client.execute_node(
            node_id="validator",
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_prompt=judge_prompt,
        )

        results.append(
            {
                "query": q,
                "baseline_latency_ms": round(baseline_resp.latency_ms, 1),
                "mars_latency_ms": round(mars_res.telemetry.total_latency_ms, 1),
                "mars_total_tokens": mars_res.telemetry.total_tokens,
                "fallbacks_triggered": mars_res.telemetry.fallbacks_triggered,
                "judge_evaluation": judge_resp.content,
            }
        )

    out_path = Path(__file__).parent / "benchmark_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nBenchmark complete! Saved results to {out_path}")
    await pipeline.client.close()


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
