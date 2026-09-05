"""Core orchestration engine for the 9-node MARS council pipeline."""

import asyncio
import re
import time
from typing import Any, Callable, Dict, List, Optional

from mars.client import fetch_agent_response
from mars.models import (
    AgentResponse,
    CouncilResult,
    PipelineResult,
    SynthesisResult,
    TelemetryData,
)
from mars.prompts import (
    CHAIRMAN_RESOLUTION_PROMPT,
    CHAIRMAN_SYNTHESIS_PROMPT,
    CONTRARIAN_SYSTEM_PROMPT,
    EXECUTOR_SYSTEM_PROMPT,
    EXPANSIONIST_SYSTEM_PROMPT,
    FIRST_PRINCIPLES_SYSTEM_PROMPT,
    NEGATIVIST_SYSTEM_PROMPT,
    OUTSIDER_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
)


class MARSPipeline:
    """Orchestrates Phase 1 (Triage), Phase 2 (Council Fan-out),

    Phase 3 (Synthesis & Red-Team), and Phase 4 (Validation).
    """

    def __init__(self):
        pass

    async def run(
        self,
        query: str,
        event_callback: Optional[Callable[[str, Any], None]] = None,
    ) -> PipelineResult:
        """Execute full MARS reasoning workflow for a query."""
        overall_start = time.perf_counter()
        per_node_latency: Dict[str, float] = {}
        total_tokens = 0
        active_providers: set[str] = set()

        def emit(event_type: str, payload: Any = None):
            if event_callback:
                try:
                    event_callback(event_type, payload)
                except Exception:
                    pass

        # -------------------------------------------------------------
        # PHASE 1: Intake & Triage (Gating Router)
        # -------------------------------------------------------------
        emit("phase1_start", {"query": query})
        router_resp = await fetch_agent_response(
            node_key="gating_router",
            system_prompt=ROUTER_SYSTEM_PROMPT,
            user_query=query,
        )
        per_node_latency["gating_router"] = router_resp.latency_ms
        total_tokens += router_resp.tokens_used
        if router_resp.success:
            active_providers.add(router_resp.provider)

        router_text = router_resp.content.strip().upper()
        emit("router_classified", {"raw": router_text})

        # Check if direct route
        is_direct = "[DIRECT]" in router_text and "[COUNCIL]" not in router_text

        if is_direct:
            emit("direct_start")
            # Fast-path: single fast model execution (Groq / Chairman fallback)
            direct_resp = await fetch_agent_response(
                node_key="contrarian",  # uses fast 8B Groq endpoint
                system_prompt="You are a helpful, direct, and fast AI assistant. Answer the user's question clearly and concisely.",
                user_query=query,
            )
            per_node_latency["direct_agent"] = direct_resp.latency_ms
            total_tokens += direct_resp.tokens_used
            if direct_resp.success:
                active_providers.add(direct_resp.provider)

            total_latency = time.perf_counter() - overall_start
            emit("pipeline_complete", {"route": "[DIRECT]"})

            return PipelineResult(
                query=query,
                route="[DIRECT]",
                final_output=direct_resp.content,
                direct_response=direct_resp,
                telemetry=TelemetryData(
                    total_latency_s=round(total_latency, 2),
                    per_node_latency_ms=per_node_latency,
                    total_tokens=total_tokens,
                    cost_usd=0.0,
                    active_providers=list(active_providers),
                ),
            )

        # -------------------------------------------------------------
        # PHASE 2: Concurrent Fan-Out (The Council)
        # -------------------------------------------------------------
        emit("phase2_start")
        council_start = time.perf_counter()

        council_tasks = [
            fetch_agent_response("contrarian", CONTRARIAN_SYSTEM_PROMPT, query),
            fetch_agent_response("first_principles", FIRST_PRINCIPLES_SYSTEM_PROMPT, query),
            fetch_agent_response("expansionist", EXPANSIONIST_SYSTEM_PROMPT, query),
            fetch_agent_response("outsider", OUTSIDER_SYSTEM_PROMPT, query),
            fetch_agent_response("executor", EXECUTOR_SYSTEM_PROMPT, query),
        ]

        # Execute all 5 council personas simultaneously
        council_responses: List[AgentResponse] = await asyncio.gather(*council_tasks)

        council_map: Dict[str, AgentResponse] = {}
        for resp in council_responses:
            council_map[resp.node_key] = resp
            per_node_latency[resp.node_key] = resp.latency_ms
            total_tokens += resp.tokens_used
            if resp.success:
                active_providers.add(resp.provider)
            emit("council_member_done", resp)

        council_duration_ms = (time.perf_counter() - council_start) * 1000.0
        council_result = CouncilResult(
            query=query,
            responses=council_map,
            duration_ms=round(council_duration_ms, 2),
        )
        emit("phase2_complete", council_result)

        # -------------------------------------------------------------
        # PHASE 3: Synthesis & Adversarial Red-Teaming (Sequential)
        # -------------------------------------------------------------
        emit("phase3_start")

        # 1. Chairman Draft 1
        emit("chairman_draft_start")
        chairman_input = (
            f"Original Query: {query}\n\n"
            f"Here are the perspectives submitted by the 5 council members:\n\n"
            f"{council_result.compiled_council_text}"
        )
        chairman_draft_1 = await fetch_agent_response(
            node_key="chairman",
            system_prompt=CHAIRMAN_SYNTHESIS_PROMPT,
            user_query=chairman_input,
        )
        per_node_latency["chairman_draft_1"] = chairman_draft_1.latency_ms
        total_tokens += chairman_draft_1.tokens_used
        if chairman_draft_1.success:
            active_providers.add(chairman_draft_1.provider)
        emit("chairman_draft_done", chairman_draft_1)

        # 2. Negativist Red-Team Audit (Reads ONLY Chairman's draft)
        emit("negativist_audit_start")
        negativist_input = (
            f"Review this proposed strategy drafted by the Chairman for the query '{query}':\n\n"
            f"{chairman_draft_1.content}\n\n"
            f"Tear this plan apart. Identify every vulnerability, hidden flaw, and logical risk."
        )
        negativist_resp = await fetch_agent_response(
            node_key="negativist",
            system_prompt=NEGATIVIST_SYSTEM_PROMPT,
            user_query=negativist_input,
        )
        per_node_latency["negativist"] = negativist_resp.latency_ms
        total_tokens += negativist_resp.tokens_used
        if negativist_resp.success:
            active_providers.add(negativist_resp.provider)
        emit("negativist_audit_done", negativist_resp)

        # 3. Chairman Final Resolution (Patches vulnerabilities)
        emit("chairman_resolution_start")
        resolution_input = (
            f"Your Initial Draft Strategy:\n{chairman_draft_1.content}\n\n"
            f"Adversarial Audit from the Negativist:\n{negativist_resp.content}\n\n"
            f"Rewrite the final strategic plan to completely patch these vulnerabilities."
        )
        chairman_resolution = await fetch_agent_response(
            node_key="chairman",
            system_prompt=CHAIRMAN_RESOLUTION_PROMPT,
            user_query=resolution_input,
            override_temperature=0.5,
        )
        per_node_latency["chairman_resolution"] = chairman_resolution.latency_ms
        total_tokens += chairman_resolution.tokens_used
        if chairman_resolution.success:
            active_providers.add(chairman_resolution.provider)
        emit("chairman_resolution_done", chairman_resolution)

        # -------------------------------------------------------------
        # PHASE 4: Final Validation (Zero-Temperature Ground Truth)
        # -------------------------------------------------------------
        emit("phase4_start")
        max_validation_retries = 2
        validation_attempts = 0
        validator_verdict = None
        validation_passed = False
        current_final_text = chairman_resolution.content

        for attempt in range(max_validation_retries):
            validation_attempts += 1
            emit("validation_attempt_start", {"attempt": validation_attempts})

            validator_input = f"Response to validate:\n\n{current_final_text}"
            validator_verdict = await fetch_agent_response(
                node_key="validator",
                system_prompt=VALIDATOR_SYSTEM_PROMPT,
                user_query=validator_input,
                override_temperature=0.0,
            )
            node_key_str = f"validator_attempt_{validation_attempts}"
            per_node_latency[node_key_str] = validator_verdict.latency_ms
            total_tokens += validator_verdict.tokens_used
            if validator_verdict.success:
                active_providers.add(validator_verdict.provider)

            verdict_text = validator_verdict.content.strip()
            if "[PASS]" in verdict_text:
                validation_passed = True
                emit("validation_passed", {"verdict": verdict_text})
                break

            # If rejected and we have retries left, prompt Chairman to fix
            emit("validation_rejected", {"verdict": verdict_text, "attempt": validation_attempts})
            if attempt < max_validation_retries - 1:
                correction_prompt = (
                    f"The Validator found issues with your response:\n{verdict_text}\n\n"
                    f"Current draft:\n{current_final_text}\n\n"
                    f"Fix the formatting, links, and logical errors immediately."
                )
                repaired = await fetch_agent_response(
                    node_key="chairman",
                    system_prompt="Fix all structural and factual errors flagged by the validator.",
                    user_query=correction_prompt,
                    override_temperature=0.3,
                )
                per_node_latency[f"chairman_repair_{attempt+1}"] = repaired.latency_ms
                total_tokens += repaired.tokens_used
                current_final_text = repaired.content

        synthesis_result = SynthesisResult(
            chairman_draft_1=chairman_draft_1,
            negativist_critique=negativist_resp,
            chairman_final_resolution=chairman_resolution,
            validator_verdict=validator_verdict,
            validation_attempts=validation_attempts,
            validation_passed=validation_passed,
        )

        total_latency = time.perf_counter() - overall_start
        emit("pipeline_complete", {"route": "[COUNCIL]"})

        return PipelineResult(
            query=query,
            route="[COUNCIL]",
            final_output=current_final_text,
            council_result=council_result,
            synthesis_result=synthesis_result,
            telemetry=TelemetryData(
                total_latency_s=round(total_latency, 2),
                per_node_latency_ms=per_node_latency,
                total_tokens=total_tokens,
                cost_usd=0.0,
                active_providers=list(active_providers),
            ),
        )
