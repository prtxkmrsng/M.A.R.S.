"""Gradio web application for MARS: Multi-Agent Reasoning System."""

import asyncio
import os
from typing import AsyncGenerator, Dict, Tuple
import gradio as gr

from mars.config import API_CONFIGS, check_credentials, reload_env
from mars.pipeline import MARSPipeline


def get_status_markdown() -> str:
    """Generate Markdown summarizing provider credential readiness."""
    creds = check_credentials()
    lines = [
        "| Node Key | Role | Provider | Key Required | Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    ready_count = 0
    for key, info in creds.items():
        status_badge = "✅ Ready" if info["configured"] else "⚠️ Missing Key"
        if info["configured"]:
            ready_count += 1
        lines.append(
            f"| `{key}` | **{info['role']}** | {info['provider']} | `{info['env_var']}` | {status_badge} |"
        )
    header = f"### Provider Health Status ({ready_count}/{len(creds)} Configured)\n\n"
    return header + "\n".join(lines)


async def run_mars_stream(query: str) -> AsyncGenerator[Tuple, None]:
    """Async generator streaming intermediate execution states into Gradio components."""
    if not query.strip():
        yield (
            "Please enter a prompt to begin deliberation.",
            "Awaiting input...",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        )
        return

    pipeline = MARSPipeline()

    status_log = "🚀 Initiating MARS Pipeline...\n"
    route_indicator = "Evaluating complexity..."
    final_output = ""
    contrarian_text = "Deliberating..."
    first_principles_text = "Deliberating..."
    expansionist_text = "Deliberating..."
    outsider_text = "Deliberating..."
    executor_text = "Deliberating..."

    draft_1_text = "Pending Phase 2 completion..."
    critique_text = "Pending Chairman synthesis..."
    resolution_text = "Pending Negativist audit..."
    validator_text = "Pending final resolution..."
    telemetry_summary = "Calculating..."

    # Initial update
    yield (
        final_output,
        route_indicator,
        contrarian_text,
        first_principles_text,
        expansionist_text,
        outsider_text,
        executor_text,
        draft_1_text,
        critique_text,
        resolution_text,
        validator_text,
        telemetry_summary,
    )

    # Event buffer for streaming
    event_queue: asyncio.Queue = asyncio.Queue()

    def callback(event_type: str, data: any):
        event_queue.put_nowait((event_type, data))

    pipeline_task = asyncio.create_task(pipeline.run(query, event_callback=callback))

    while not pipeline_task.done() or not event_queue.empty():
        try:
            event_type, data = await asyncio.wait_for(event_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue

        if event_type == "phase1_start":
            route_indicator = "Phase 1: Gating Router analyzing prompt..."
        elif event_type == "router_classified":
            raw = data.get("raw", "")
            route_indicator = f"Routing Decision: {raw}"
        elif event_type == "direct_start":
            route_indicator = "Routing Decision: [DIRECT] (Fast Single-Model Path)"
        elif event_type == "phase2_start":
            route_indicator = "Routing Decision: [COUNCIL] (Concurrent Fan-out Fired)"
            contrarian_text = "⏳ Generating adversarial critique..."
            first_principles_text = "⏳ Deconstructing foundational physics & logic..."
            expansionist_text = "⏳ Scouting exponential upside & angles..."
            outsider_text = "⏳ Questioning assumptions as an intelligent cynic..."
            executor_text = "⏳ Formulating actionable step-by-step blueprint..."
        elif event_type == "council_member_done":
            node_key = data.node_key
            content = data.content
            latency_s = round(data.latency_ms / 1000.0, 2)
            header = f"**Provider:** {data.provider} | **Model:** `{data.model}` ({latency_s}s)\n\n"
            full_text = header + content
            if node_key == "contrarian":
                contrarian_text = full_text
            elif node_key == "first_principles":
                first_principles_text = full_text
            elif node_key == "expansionist":
                expansionist_text = full_text
            elif node_key == "outsider":
                outsider_text = full_text
            elif node_key == "executor":
                executor_text = full_text
        elif event_type == "chairman_draft_start":
            draft_1_text = "⏳ The Chairman is ingesting all 5 council submissions and drafting initial doctrine..."
        elif event_type == "chairman_draft_done":
            latency_s = round(data.latency_ms / 1000.0, 2)
            draft_1_text = f"**Provider:** {data.provider} | **Model:** `{data.model}` ({latency_s}s)\n\n{data.content}"
        elif event_type == "negativist_audit_start":
            critique_text = "⏳ The Negativist (Red-Team) is actively tearing the Chairman's draft apart..."
        elif event_type == "negativist_audit_done":
            latency_s = round(data.latency_ms / 1000.0, 2)
            critique_text = f"**Provider:** {data.provider} | **Model:** `{data.model}` ({latency_s}s)\n\n{data.content}"
        elif event_type == "chairman_resolution_start":
            resolution_text = "⏳ The Chairman is patching all vulnerabilities into the finalized resolution..."
        elif event_type == "chairman_resolution_done":
            latency_s = round(data.latency_ms / 1000.0, 2)
            resolution_text = f"**Provider:** {data.provider} | **Model:** `{data.model}` ({latency_s}s)\n\n{data.content}"
        elif event_type == "validation_attempt_start":
            attempt = data.get("attempt", 1)
            validator_text = f"⏳ The Validator is inspecting syntax, URLs, and logic (Attempt {attempt})..."
        elif event_type == "validation_passed":
            validator_text = f"✅ **PASS** — Structural and factual integrity confirmed.\n\n`{data.get('verdict')}`"
        elif event_type == "validation_rejected":
            validator_text = f"⚠️ **REJECTED** — Re-looping to Chairman for correction.\n\n`{data.get('verdict')}`"

        yield (
            final_output,
            route_indicator,
            contrarian_text,
            first_principles_text,
            expansionist_text,
            outsider_text,
            executor_text,
            draft_1_text,
            critique_text,
            resolution_text,
            validator_text,
            telemetry_summary,
        )

    result = await pipeline_task
    final_output = result.final_output

    telemetry_summary = (
        f"⏱️ **Total Latency:** {result.telemetry.total_latency_s}s  |  "
        f"🔢 **Tokens Processed:** {result.telemetry.total_tokens:,}  |  "
        f"💰 **Estimated Cost:** ${result.telemetry.cost_usd:.2f} (Free-tier)  |  "
        f"🌐 **Active Providers:** {', '.join(result.telemetry.active_providers) or 'None'}"
    )

    yield (
        final_output,
        f"Routing: {result.route} (Completed)",
        contrarian_text,
        first_principles_text,
        expansionist_text,
        outsider_text,
        executor_text,
        draft_1_text,
        critique_text,
        resolution_text,
        validator_text,
        telemetry_summary,
    )


def create_app() -> gr.Blocks:
    """Build and style the Gradio interface."""
    custom_css = """
    .mars-container { max-width: 1200px; margin: auto; }
    .mars-badge { font-weight: bold; font-size: 1.1em; }
    .telemetry-card { background: #1e1e2e; border-radius: 8px; padding: 12px; margin-top: 10px; }
    """

    with gr.Blocks(title="MARS: Multi-Agent Reasoning System", css=custom_css, theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            """
            # 🪐 MARS: Multi-Agent Reasoning System
            ### Distributed Mixture-of-Agents (MoA) Architecture & Adversarial Red-Teaming Council
            *9 specialized nodes across 6 AI providers working in parallel to eliminate hallucinations and logical blind spots.*
            """
        )

        with gr.Row():
            with gr.Column(scale=4):
                query_input = gr.Textbox(
                    label="Enter Complex Reasoning Query or Strategy Prompt",
                    placeholder="e.g. How should a startup build an autonomous drone delivery business in suburban markets under current regulations?",
                    lines=3,
                )
                with gr.Row():
                    submit_btn = gr.Button("🚀 Convene the Council", variant="primary")
                    clear_btn = gr.Button("🧹 Clear")
            with gr.Column(scale=1):
                route_indicator = gr.Textbox(
                    label="Gating Router Classification",
                    value="Standby",
                    interactive=False,
                )
                refresh_status_btn = gr.Button("🔄 Refresh API Status")

        # Telemetry bar
        telemetry_display = gr.Markdown(
            "⏱️ **Total Latency:** 0.0s | 🔢 **Tokens:** 0 | 💰 **Cost:** $0.00 (Free Tier) | 🌐 **Providers:** Standby",
            elem_classes=["telemetry-card"],
        )

        gr.Markdown("### 🏛️ Final Audited & Validated Synthesis")
        final_output_box = gr.Markdown(
            "The validated, bulletproof doctrine produced by the Council will appear here.",
        )

        # Tabbed Council View
        gr.Markdown("### 👥 The Council (Phase 2: Concurrent Fan-Out)")
        with gr.Tabs():
            with gr.TabItem("1. The Contrarian (Skeptic)"):
                contrarian_box = gr.Markdown("No output yet.")
            with gr.TabItem("2. First Principles (Realist)"):
                first_principles_box = gr.Markdown("No output yet.")
            with gr.TabItem("3. The Expansionist (Optimist)"):
                expansionist_box = gr.Markdown("No output yet.")
            with gr.TabItem("4. The Outsider (Cynic)"):
                outsider_box = gr.Markdown("No output yet.")
            with gr.TabItem("5. The Executor (Practical)"):
                executor_box = gr.Markdown("No output yet.")

        # Audit Log Accordion
        with gr.Accordion("🔍 Executive Tier Audit Log (Phase 3 & 4 Dialectic)", open=False):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Chairman Initial Draft (Pre-Red-Team)")
                    draft_1_box = gr.Markdown("Pending...")
                with gr.Column():
                    gr.Markdown("#### Negativist Red-Team Critique (Vulnerability Audit)")
                    critique_box = gr.Markdown("Pending...")
            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### Chairman Revised Resolution (Patched)")
                    resolution_box = gr.Markdown("Pending...")
                with gr.Column():
                    gr.Markdown("#### Validator Ground-Truth Verdict (Zero-Temp)")
                    validator_box = gr.Markdown("Pending...")

        # System Health Accordion
        with gr.Accordion("⚙️ System Health & API Provider Status", open=False):
            status_markdown = gr.Markdown(value=get_status_markdown())

        refresh_status_btn.click(fn=get_status_markdown, outputs=[status_markdown])

        # Setup event bindings
        submit_btn.click(
            fn=run_mars_stream,
            inputs=[query_input],
            outputs=[
                final_output_box,
                route_indicator,
                contrarian_box,
                first_principles_box,
                expansionist_box,
                outsider_box,
                executor_box,
                draft_1_box,
                critique_box,
                resolution_box,
                validator_box,
                telemetry_display,
            ],
        )

        clear_btn.click(
            fn=lambda: ("", "Standby", "", "", "", "", "", "", "", "", "", "Standby"),
            outputs=[
                query_input,
                route_indicator,
                contrarian_box,
                first_principles_box,
                expansionist_box,
                outsider_box,
                executor_box,
                draft_1_box,
                critique_box,
                resolution_box,
                validator_box,
                telemetry_display,
            ],
        )

    return demo
