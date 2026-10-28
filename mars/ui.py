from __future__ import annotations
import asyncio
import json
import gradio as gr
from mars.pipeline import MARSPipeline
from mars.models import AgentResponse, PipelineResult
from mars.prompts import SYSTEM_PROMPTS

pipeline = MARSPipeline()

CUSTOM_THEME = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="slate",
    neutral_hue="slate",
)

CUSTOM_CSS = """
footer {visibility: hidden}
.gradio-container {max-width: 1400px !important;}
"""


def _format_agent_card(resp: AgentResponse | None) -> str:
    if not resp:
        return "*Skipped (Direct Execution or not triggered).* "
    if not resp.success:
        return f"**Status:** Failed (`{resp.error}`)\n\n**Tried:** `{', '.join(resp.fallback_chain_tried)}`"
    fb_badge = " *(Fallback Used)*" if resp.used_fallback else ""
    header = (
        f"**Provider:** `{resp.provider}` | **Model:** `{resp.model}`{fb_badge} | "
        f"**Latency:** `{resp.latency_ms:.0f} ms` | **Tokens:** `{resp.total_tokens}`\n\n---\n\n"
    )
    body = resp.content
    if resp.reasoning_trace:
        body += f"\n\n<details><summary><b>View Internal Reasoning Trace (&lt;think&gt;)</b></summary>\n\n```text\n{resp.reasoning_trace}\n```\n</details>"
    return header + body


def _build_stepper_html(active_phase: int, status_text: str) -> str:
    phases = [
        (1, "Phase 1: Gating Router"),
        (2, "Phase 2: 5-Agent Council"),
        (3, "Phase 3: Chairman & Negativist"),
        (4, "Phase 4: Validator Check"),
    ]
    items = []
    for idx, label in phases:
        if idx < active_phase:
            color = "#10b981"
            prefix = "✓ "
        elif idx == active_phase:
            color = "#6366f1"
            prefix = "● "
        else:
            color = "#64748b"
            prefix = "○ "
        items.append(
            f"<div style='padding:8px 14px;border-radius:8px;background:{color}22;"
            f"border:1px solid {color};color:{color};font-weight:600;font-size:13px;'>"
            f"{prefix}{label}</div>"
        )
    row = "<div style='display:flex;gap:10px;flex-wrap:wrap;margin-bottom:8px;'>" + "".join(items) + "</div>"
    sub = f"<div style='font-size:13px;color:#94a3b8;'><b>Status:</b> {status_text}</div>"
    return row + sub


async def execute_mars_ui(query: str, force_council: bool, compare_baseline: bool):
    if not query or not query.strip():
        yield (
            _build_stepper_html(1, "Waiting for prompt..."),
            "Please enter a prompt.",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "{}",
        )
        return

    # Run MARS pipeline (and optional single-model baseline concurrently)
    mars_task = asyncio.create_task(pipeline.run(query.strip(), force_council=force_council))
    baseline_task = None
    if compare_baseline:
        baseline_task = asyncio.create_task(
            pipeline.client.execute_node(
                node_id="chairman",
                system_prompt="You are a helpful, rigorous AI assistant. Provide a comprehensive response.",
                user_prompt=query.strip(),
            )
        )

    res: PipelineResult = await mars_task
    baseline_md = "*Enable 'Compare against Single-Model Baseline' to run side-by-side viva evaluation.*"
    if baseline_task:
        base_resp = await baseline_task
        baseline_md = _format_agent_card(base_resp)

    c = res.council_responses
    val_summary = "\n\n".join(
        f"**Attempt {i+1} Verdict:** `[{v.verdict}]` — {v.critique} "
        f"(`{v.response.provider}:{v.response.model}`, `{v.response.latency_ms:.0f} ms`)"
        for i, v in enumerate(res.validation_history)
    ) or "*Not triggered (Direct Execution)*"

    audit_md = (
        f"### 1. Gating Router Decision: `{res.routing_decision}`\n"
        f"{_format_agent_card(res.gating_response)}\n\n---\n\n"
        f"### 2. Chairman Initial Draft\n"
        f"{_format_agent_card(res.chairman_initial_draft)}\n\n---\n\n"
        f"### 3. The Negativist Red-Team Audit\n"
        f"{_format_agent_card(res.negativist_critique)}\n\n---\n\n"
        f"### 4. Validator Ground-Truth Audit\n{val_summary}"
    )

    stepper_done = _build_stepper_html(
        5,
        f"Completed via {res.routing_decision} in {res.telemetry.total_latency_ms/1000:.2f}s "
        f"({res.telemetry.total_tokens} tokens | {res.telemetry.fallbacks_triggered} fallbacks)",
    )

    yield (
        stepper_done,
        res.final_output,
        baseline_md,
        _format_agent_card(c.get("contrarian")),
        _format_agent_card(c.get("first_principles")),
        _format_agent_card(c.get("expansionist")),
        _format_agent_card(c.get("outsider")),
        _format_agent_card(c.get("executor")),
        audit_md,
        json.dumps(res.telemetry.to_dict(), indent=2),
    )


def create_ui() -> gr.Blocks:
    with gr.Blocks(
        title="M.A.R.S. — Multi-Agent Reasoning System",
        theme=CUSTOM_THEME,
        css=CUSTOM_CSS,
    ) as demo:
        gr.Markdown(
            "# M.A.R.S. — Multi-Agent Reasoning System\n"
            "**9-Node Heterogeneous Mixture-of-Agents Council with Adversarial Red-Teaming & Zero-Temperature Validation**"
        )

        stepper_html = gr.HTML(_build_stepper_html(0, "Idle — Ready for query"))

        with gr.Row():
            query_input = gr.Textbox(
                label="Enter Strategic, Technical, or Analytical Query",
                placeholder="e.g., Design a fault-tolerant microservice architecture for a real-time stock exchange on a $0 bootstrap budget...",
                lines=3,
                scale=4,
            )
            with gr.Column(scale=1):
                force_council_chk = gr.Checkbox(
                    label="Force 9-Node Council (Bypass Gating Router)", value=True
                )
                compare_baseline_chk = gr.Checkbox(
                    label="Compare vs. Single Baseline Model (Viva Mode)", value=False
                )
                submit_btn = gr.Button("Execute M.A.R.S. Pipeline", variant="primary")

        with gr.Tabs():
            with gr.TabItem("Final Validated Output"):
                final_output_md = gr.Markdown()

            with gr.TabItem("Viva Side-by-Side: Baseline vs. M.A.R.S."):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Single Baseline Model Output")
                        baseline_output_md = gr.Markdown()
                    with gr.Column():
                        gr.Markdown("### M.A.R.S. 9-Node Council Output")
                        mars_compare_md = gr.Markdown()

            with gr.TabItem("Phase 2: 5-Agent Council Deliberations"):
                with gr.Tabs():
                    with gr.TabItem("1. The Contrarian"):
                        c_contrarian = gr.Markdown()
                    with gr.TabItem("2. 1st Principle Thinker"):
                        c_first = gr.Markdown()
                    with gr.TabItem("3. The Expansionist"):
                        c_expansionist = gr.Markdown()
                    with gr.TabItem("4. The Outsider"):
                        c_outsider = gr.Markdown()
                    with gr.TabItem("5. The Executor"):
                        c_executor = gr.Markdown()

            with gr.TabItem("Phase 3 & 4: Executive & Red-Team Audit Log"):
                audit_log_md = gr.Markdown()

            with gr.TabItem("Telemetry & Cost Savings"):
                telemetry_json = gr.Code(language="json", label="Pipeline Telemetry")

        async def _wrapped(q, fc, cb):
            async for out in execute_mars_ui(q, fc, cb):
                # Mirror final output into the side-by-side comparison column as well
                yield (
                    out[0],
                    out[1],
                    out[2],
                    out[1],
                    out[3],
                    out[4],
                    out[5],
                    out[6],
                    out[7],
                    out[8],
                    out[9],
                )

        submit_btn.click(
            fn=_wrapped,
            inputs=[query_input, force_council_chk, compare_baseline_chk],
            outputs=[
                stepper_html,
                final_output_md,
                baseline_output_md,
                mars_compare_md,
                c_contrarian,
                c_first,
                c_expansionist,
                c_outsider,
                c_executor,
                audit_log_md,
                telemetry_json,
            ],
        )

    return demo


# Backward compatibility alias
create_app = create_ui
