from __future__ import annotations
import asyncio
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

from mars.client import LLMClientManager
from mars.config import COUNCIL_NODE_IDS
from mars.models import (
    AgentResponse,
    CouncilResult,
    PipelineResult,
    PipelineTelemetry,
    SynthesisResult,
    ValidationResult,
)
from mars.prompts import SYSTEM_PROMPTS

logger = logging.getLogger("mars.pipeline")

StatusCallback = Optional[Callable[[int, str], None]]
EventCallback = Optional[Callable[[str, Any], None]]


class MARSPipeline:
    """9-Node, 4-Phase Adversarial Mixture-of-Agents Reasoning Pipeline."""

    def __init__(
        self,
        client_manager: Optional[LLMClientManager] = None,
        max_council_reboots: int = 1,
        max_validator_repairs: int = 2,
    ) -> None:
        self.client = client_manager or LLMClientManager()
        self.max_council_reboots = max_council_reboots
        self.max_validator_repairs = max_validator_repairs

    @staticmethod
    def _notify(
        status_cb: StatusCallback,
        event_cb: EventCallback,
        phase: int,
        message: str,
        event_name: Optional[str] = None,
        payload: Any = None,
    ) -> None:
        if status_cb:
            try:
                status_cb(phase, message)
            except Exception:
                pass
        if event_cb and event_name:
            try:
                event_cb(event_name, payload)
            except Exception:
                pass

    @staticmethod
    def _parse_gating_output(text: str) -> tuple[str, str]:
        """Returns (decision, direct_answer_if_any)."""
        if not text:
            return "COUNCIL_ROUTING", ""
        upper = text.upper()
        if "COUNCIL_ROUTING" in upper and "DIRECT_EXECUTION" not in upper:
            return "COUNCIL_ROUTING", ""
        if "DIRECT_EXECUTION" in upper:
            cleaned = re.sub(
                r"^.*?[*`_]*\[?DIRECT_EXECUTION\]?[*`_]*:?\s*",
                "",
                text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            return "DIRECT_EXECUTION", cleaned
        return "COUNCIL_ROUTING", ""

    @staticmethod
    def _parse_chairman_decision(text: str) -> tuple[str, str]:
        """Parses [REBOOT_COUNCIL] vs [PROCEED] from Chairman resolution."""
        if not text:
            return "PROCEED", ""
        if re.search(r"\[?\bREBOOT_COUNCIL\b\]?", text, flags=re.IGNORECASE):
            cleaned = re.sub(
                r"^.*?[*`_]*\[?REBOOT_COUNCIL\]?[*`_]*:?\s*",
                "",
                text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            return "REBOOT_COUNCIL", cleaned
        cleaned = re.sub(
            r"^.*?[*`_]*\[?PROCEED\]?[*`_]*:?\s*",
            "",
            text,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        return "PROCEED", cleaned

    @staticmethod
    def _parse_validator_output(text: str) -> tuple[bool, str, str]:
        """Returns (passed, verdict_str, critique)."""
        if not text:
            return True, "PASS", "Validator unavailable; auto-passed."
        if re.search(r"\[?\bREJECT\b\]?", text, flags=re.IGNORECASE):
            critique = re.sub(
                r"^.*?[*`_]*\[?REJECT\]?[*`_]*:?\s*",
                "",
                text,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            return False, "REJECT", critique or text
        critique = re.sub(
            r"^.*?[*`_]*\[?PASS\]?[*`_]*:?\s*",
            "",
            text,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        ).strip()
        return True, "PASS", critique or "Verified."

    @staticmethod
    def _format_council_for_chairman(
        user_query: str, council_responses: Dict[str, AgentResponse]
    ) -> str:
        sections = [f"### ORIGINAL USER QUERY:\n{user_query}\n\n### COUNCIL DELIBERATIONS:"]
        for node_id, resp in council_responses.items():
            if resp.success and resp.content.strip():
                sections.append(f"#### [{resp.display_name}]\n{resp.content.strip()}")
            else:
                sections.append(
                    f"#### [{resp.display_name}]\n(Node unavailable during deliberation; synthesize from remaining perspectives.)"
                )
        return "\n\n".join(sections)

    async def _run_council_fanout(
        self,
        user_query: str,
        reboot_feedback: Optional[str] = None,
        event_cb: EventCallback = None,
    ) -> Dict[str, AgentResponse]:
        prompt = user_query
        if reboot_feedback:
            prompt = (
                f"{user_query}\n\n"
                f"--- CRITICAL RE-EVALUATION DIRECTIVE FROM THE CHAIRMAN ---\n"
                f"A previous council draft was rejected due to fundamental flaws:\n"
                f"{reboot_feedback}\n"
                f"Re-analyze the user query from your persona's perspective while directly addressing these flaws."
            )

        async def _exec_and_emit(node_id: str) -> AgentResponse:
            resp = await self.client.execute_node(
                node_id=node_id,
                system_prompt=SYSTEM_PROMPTS[node_id],
                user_prompt=prompt,
            )
            if event_cb:
                try:
                    event_cb("council_member_done", resp)
                except Exception:
                    pass
            return resp

        tasks = [_exec_and_emit(node_id) for node_id in COUNCIL_NODE_IDS]
        results = await asyncio.gather(*tasks)
        return {resp.node_id: resp for resp in results}

    async def run(
        self,
        query: str,
        force_council: bool = False,
        status_callback: StatusCallback = None,
        event_callback: EventCallback = None,
    ) -> PipelineResult:
        pipeline_start = time.perf_counter()
        telemetry = PipelineTelemetry()

        # =====================================================================
        # PHASE 1: GATING ROUTER
        # =====================================================================
        self._notify(
            status_callback,
            event_callback,
            1,
            "Phase 1: Gating Router evaluating query complexity...",
            "phase1_start",
            {"query": query},
        )
        p1_start = time.perf_counter()

        if force_council:
            routing_decision = "COUNCIL_ROUTING"
            gating_resp = None
            self._notify(
                status_callback,
                event_callback,
                1,
                "Forcing Council Routing (Router bypassed).",
                "router_classified",
                {"raw": "[COUNCIL_ROUTING] (Forced)"},
            )
        else:
            gating_resp = await self.client.execute_node(
                node_id="gating_router",
                system_prompt=SYSTEM_PROMPTS["gating_router"],
                user_prompt=query,
            )
            telemetry.record(gating_resp)
            if gating_resp.success:
                routing_decision, direct_answer = self._parse_gating_output(gating_resp.content)
            else:
                routing_decision, direct_answer = "COUNCIL_ROUTING", ""

            self._notify(
                status_callback,
                event_callback,
                1,
                f"Router Decision: {routing_decision}",
                "router_classified",
                {"raw": f"[{routing_decision}]"},
            )

            if routing_decision == "DIRECT_EXECUTION" and direct_answer:
                telemetry.phase1_latency_ms = (time.perf_counter() - p1_start) * 1000.0
                telemetry.total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0
                self._notify(
                    status_callback,
                    event_callback,
                    4,
                    "Completed via Direct Execution (Gating Router).",
                    "pipeline_complete",
                    {"route": "[DIRECT_EXECUTION]"},
                )
                return PipelineResult(
                    query=query,
                    routing_decision="DIRECT_EXECUTION",
                    final_output=direct_answer,
                    gating_response=gating_resp,
                    direct_response=gating_resp,
                    telemetry=telemetry,
                )

        telemetry.phase1_latency_ms = (time.perf_counter() - p1_start) * 1000.0

        # =====================================================================
        # PHASE 2 & PHASE 3: PARALLEL COUNCIL + CHAIRMAN / NEGATIVIST LOOP
        # =====================================================================
        reboot_feedback: Optional[str] = None
        reboot_count = 0
        reboot_history: List[Dict[str, Any]] = []
        council_responses: Dict[str, AgentResponse] = {}
        chairman_draft: Optional[AgentResponse] = None
        negativist_resp: Optional[AgentResponse] = None
        chairman_resolution: Optional[AgentResponse] = None
        final_candidate_text = ""

        while True:
            # --- PHASE 2: 5-Agent Concurrent Fan-Out ---
            self._notify(
                status_callback,
                event_callback,
                2,
                f"Phase 2: Firing 5-Agent Parallel Council (Cycle {reboot_count + 1})...",
                "phase2_start",
            )
            p2_start = time.perf_counter()
            council_responses = await self._run_council_fanout(
                query, reboot_feedback=reboot_feedback, event_cb=event_callback
            )
            council_elapsed = (time.perf_counter() - p2_start) * 1000.0
            telemetry.phase2_latency_ms += council_elapsed
            for resp in council_responses.values():
                telemetry.record(resp)

            self._notify(
                status_callback,
                event_callback,
                2,
                "Phase 2: Council Fan-Out completed.",
                "phase2_complete",
                CouncilResult(query=query, responses=council_responses, duration_ms=council_elapsed),
            )

            # Check if all council nodes failed
            if not any(r.success and r.content.strip() for r in council_responses.values()):
                telemetry.total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0
                return PipelineResult(
                    query=query,
                    routing_decision="COUNCIL_ROUTING",
                    final_output="Error: All 5 Council providers failed or are unconfigured. Please check your API keys in `.env`.",
                    gating_response=gating_resp,
                    council_responses=council_responses,
                    telemetry=telemetry,
                )

            # --- PHASE 3A: Chairman Initial Synthesis ---
            self._notify(
                status_callback,
                event_callback,
                3,
                "Phase 3: Chairman synthesizing 5 Council perspectives...",
                "chairman_draft_start",
            )
            p3_start = time.perf_counter()
            compiled_council = self._format_council_for_chairman(query, council_responses)
            chairman_draft = await self.client.execute_node(
                node_id="chairman",
                system_prompt=SYSTEM_PROMPTS["chairman_draft"],
                user_prompt=compiled_council,
            )
            telemetry.record(chairman_draft)
            self._notify(
                status_callback,
                event_callback,
                3,
                "Phase 3: Chairman synthesized Initial Draft.",
                "chairman_draft_done",
                chairman_draft,
            )

            # --- PHASE 3B: Negativist Red-Team Audit ---
            self._notify(
                status_callback,
                event_callback,
                3,
                "Phase 3: The Negativist red-teaming Chairman's draft...",
                "negativist_audit_start",
            )
            negativist_input = (
                f"### ORIGINAL USER QUERY:\n{query}\n\n"
                f"### CHAIRMAN'S INITIAL DRAFT STRATEGY:\n{chairman_draft.content}"
            )
            negativist_resp = await self.client.execute_node(
                node_id="negativist",
                system_prompt=SYSTEM_PROMPTS["negativist"],
                user_prompt=negativist_input,
            )
            telemetry.record(negativist_resp)
            self._notify(
                status_callback,
                event_callback,
                3,
                "Phase 3: Negativist completed Red-Team Audit.",
                "negativist_audit_done",
                negativist_resp,
            )

            # --- PHASE 3C: Chairman Resolution & Decision Matrix ---
            self._notify(
                status_callback,
                event_callback,
                3,
                "Phase 3: Chairman resolving vulnerabilities...",
                "chairman_resolution_start",
            )
            resolution_input = (
                f"### ORIGINAL USER QUERY:\n{query}\n\n"
                f"### CHAIRMAN'S INITIAL DRAFT:\n{chairman_draft.content}\n\n"
                f"### THE NEGATIVIST'S ADVERSARIAL CRITIQUE:\n{negativist_resp.content}\n\n"
                f"Note: Council reboots used so far = {reboot_count} (Max allowed = {self.max_council_reboots})."
            )
            chairman_resolution = await self.client.execute_node(
                node_id="chairman",
                system_prompt=SYSTEM_PROMPTS["chairman_resolution"],
                user_prompt=resolution_input,
            )
            telemetry.record(chairman_resolution)
            telemetry.phase3_latency_ms += (time.perf_counter() - p3_start) * 1000.0

            decision, cleaned_resolution = self._parse_chairman_decision(chairman_resolution.content)
            chairman_resolution.content = cleaned_resolution
            final_candidate_text = cleaned_resolution or chairman_draft.content
            self._notify(
                status_callback,
                event_callback,
                3,
                f"Phase 3: Chairman Resolution decision: {decision}.",
                "chairman_resolution_done",
                chairman_resolution,
            )

            if decision == "REBOOT_COUNCIL" and reboot_count < self.max_council_reboots:
                reboot_count += 1
                telemetry.council_reboots += 1
                reboot_feedback = cleaned_resolution
                reboot_history.append(
                    {
                        "cycle": reboot_count,
                        "negativist_critique": negativist_resp.content,
                        "chairman_reboot_directive": reboot_feedback,
                    }
                )
                logger.info(f"Chairman triggered [REBOOT_COUNCIL] (Cycle {reboot_count}).")
                continue
            break

        # =====================================================================
        # PHASE 4: ZERO-TEMPERATURE VALIDATOR & REPAIR LOOP
        # =====================================================================
        p4_start = time.perf_counter()
        validation_history: List[ValidationResult] = []
        repairs_used = 0
        last_val_resp: Optional[AgentResponse] = None

        while True:
            self._notify(
                status_callback,
                event_callback,
                4,
                f"Phase 4: Validator auditing final output (Check {repairs_used + 1})...",
                "validation_attempt_start",
                {"attempt": repairs_used + 1},
            )
            validator_input = (
                f"### ORIGINAL USER QUERY:\n{query}\n\n"
                f"### CHAIRMAN FINAL RESPONSE TO AUDIT:\n{final_candidate_text}"
            )
            val_resp = await self.client.execute_node(
                node_id="validator",
                system_prompt=SYSTEM_PROMPTS["validator"],
                user_prompt=validator_input,
            )
            telemetry.record(val_resp)
            last_val_resp = val_resp

            passed, verdict, critique = self._parse_validator_output(val_resp.content)
            validation_history.append(
                ValidationResult(
                    passed=passed,
                    verdict=verdict,
                    critique=critique,
                    response=val_resp,
                )
            )

            if passed:
                self._notify(
                    status_callback,
                    event_callback,
                    4,
                    f"Phase 4: Validator passed [{verdict}].",
                    "validation_passed",
                    {"verdict": verdict, "critique": critique},
                )
                break

            if repairs_used >= self.max_validator_repairs:
                self._notify(
                    status_callback,
                    event_callback,
                    4,
                    f"Phase 4: Validator rejected [{verdict}] (Max repairs exhausted).",
                    "validation_rejected",
                    {"verdict": verdict, "critique": critique},
                )
                break

            # Trigger repair back to Chairman with full context preserved
            repairs_used += 1
            telemetry.validator_repairs += 1
            self._notify(
                status_callback,
                event_callback,
                4,
                f"Phase 4: Validator issued [REJECT]. Chairman repairing (Attempt {repairs_used})...",
                "validation_rejected",
                {"verdict": verdict, "critique": critique, "attempt": repairs_used},
            )
            repair_input = (
                f"### ORIGINAL USER QUERY:\n{query}\n\n"
                f"### KEY ADVERSARIAL CONSTRAINTS TO PRESERVE:\n{negativist_resp.content if negativist_resp else ''}\n\n"
                f"### PREVIOUS REJECTED RESPONSE:\n{final_candidate_text}\n\n"
                f"### VALIDATOR REJECTION REASON:\n{critique}\n\n"
                f"Provide the complete, corrected final response now."
            )
            repair_resp = await self.client.execute_node(
                node_id="chairman",
                system_prompt=SYSTEM_PROMPTS["chairman_repair"],
                user_prompt=repair_input,
            )
            telemetry.record(repair_resp)
            if repair_resp.success and repair_resp.content.strip():
                _, cleaned_repair = self._parse_chairman_decision(repair_resp.content)
                final_candidate_text = cleaned_repair or repair_resp.content.strip()
                chairman_resolution = repair_resp

        telemetry.phase4_latency_ms = (time.perf_counter() - p4_start) * 1000.0
        telemetry.total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0
        self._notify(
            status_callback,
            event_callback,
            4,
            "Pipeline execution complete.",
            "pipeline_complete",
            {"route": "[COUNCIL_ROUTING]"},
        )

        council_result_obj = CouncilResult(
            query=query,
            responses=council_responses,
            duration_ms=telemetry.phase2_latency_ms,
        )
        synthesis_result_obj = SynthesisResult(
            chairman_draft_1=chairman_draft,
            negativist_critique=negativist_resp,
            chairman_final_resolution=chairman_resolution,
            validator_verdict=last_val_resp,
            validation_attempts=len(validation_history),
            validation_passed=any(v.passed for v in validation_history),
        )

        return PipelineResult(
            query=query,
            routing_decision=routing_decision,
            final_output=final_candidate_text,
            gating_response=gating_resp,
            council_responses=council_responses,
            chairman_initial_draft=chairman_draft,
            negativist_critique=negativist_resp,
            chairman_resolution=chairman_resolution,
            validation_history=validation_history,
            reboot_history=reboot_history,
            telemetry=telemetry,
            council_result=council_result_obj,
            synthesis_result=synthesis_result_obj,
        )
