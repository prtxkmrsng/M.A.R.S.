"""Mocked unit tests for end-to-end MARS pipeline flows and architectural capabilities."""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from mars.models import AgentResponse
from mars.pipeline import MARSPipeline


def test_pipeline_direct_route():
    async def _test():
        pipe = MARSPipeline()
        router_resp = AgentResponse(
            node_id="gating_router",
            display_name="Gating Router",
            provider="cloudflare",
            model="@cf/meta/llama-3.1-8b-instruct-fp8",
            content="[DIRECT_EXECUTION] Paris is the capital of France.",
            total_tokens=25,
            success=True,
        )
        pipe.client.execute_node = AsyncMock(return_value=router_resp)

        events = []
        result = await pipe.run(
            "What is the capital of France?",
            force_council=False,
            event_callback=lambda evt, data: events.append(evt),
        )

        assert result.routing_decision == "DIRECT_EXECUTION"
        assert result.final_output == "Paris is the capital of France."
        assert result.telemetry.total_api_calls == 1
        assert "phase1_start" in events
        assert "pipeline_complete" in events

    asyncio.run(_test())


def test_pipeline_council_route_pass():
    async def _test():
        pipe = MARSPipeline()

        def make_resp(node_id: str, name: str, content: str):
            return AgentResponse(
                node_id=node_id,
                display_name=name,
                provider="mock_provider",
                model="mock_model",
                content=content,
                total_tokens=50,
                success=True,
            )

        async def mock_execute(node_id, system_prompt, user_prompt, override_config=None):
            if node_id == "gating_router":
                return make_resp("gating_router", "Gating Router", "[COUNCIL_ROUTING]")
            elif node_id == "contrarian":
                return make_resp("contrarian", "The Contrarian", "Contrarian risks")
            elif node_id == "first_principles":
                return make_resp("first_principles", "1st Principles", "First principles basics")
            elif node_id == "expansionist":
                return make_resp("expansionist", "The Expansionist", "Upside scale")
            elif node_id == "outsider":
                return make_resp("outsider", "The Outsider", "Incentive proof")
            elif node_id == "executor":
                return make_resp("executor", "The Executor", "Execution plan")
            elif node_id == "chairman":
                if "Synthesize their competing perspectives" in system_prompt:
                    return make_resp("chairman", "The Chairman", "Draft Strategy")
                elif "Decision Matrix" in system_prompt:
                    return make_resp("chairman", "The Chairman", "[PROCEED] Bulletproof Final Solution")
            elif node_id == "negativist":
                return make_resp("negativist", "The Negativist", "Red team critique on edge cases")
            elif node_id == "validator":
                return make_resp("validator", "The Validator", "[PASS] Verified.")
            return make_resp(node_id, node_id, "default")

        pipe.client.execute_node = AsyncMock(side_effect=mock_execute)
        events = []

        res = await pipe.run(
            "Complex design query",
            force_council=False,
            event_callback=lambda evt, data: events.append(evt),
        )

        assert res.routing_decision == "COUNCIL_ROUTING"
        assert res.final_output == "Bulletproof Final Solution"
        assert len(res.council_responses) == 5
        assert len(res.validation_history) == 1
        assert res.validation_history[0].passed is True
        assert "phase1_start" in events
        assert "phase2_complete" in events
        assert "chairman_draft_done" in events
        assert "negativist_audit_done" in events
        assert "validation_passed" in events

    asyncio.run(_test())


def test_pipeline_reboot_council_loop():
    """Verify Chairman triggering [REBOOT_COUNCIL] restarts council with injected feedback."""
    async def _test():
        pipe = MARSPipeline(max_council_reboots=1)
        reboot_count = 0

        def make_resp(node_id: str, name: str, content: str):
            return AgentResponse(
                node_id=node_id,
                display_name=name,
                provider="mock_provider",
                model="mock_model",
                content=content,
                total_tokens=50,
                success=True,
            )

        async def mock_execute(node_id, system_prompt, user_prompt, override_config=None):
            nonlocal reboot_count
            if node_id == "gating_router":
                return make_resp("gating_router", "Gating Router", "[COUNCIL_ROUTING]")
            elif node_id in ["contrarian", "first_principles", "expansionist", "outsider", "executor"]:
                return make_resp(node_id, node_id, f"Analysis {reboot_count}")
            elif node_id == "chairman":
                if "Synthesize their competing perspectives" in system_prompt:
                    return make_resp("chairman", "The Chairman", f"Draft {reboot_count}")
                elif "Decision Matrix" in system_prompt:
                    if reboot_count == 0:
                        reboot_count += 1
                        return make_resp("chairman", "The Chairman", "[REBOOT_COUNCIL] Fatal flaw in economics.")
                    else:
                        return make_resp("chairman", "The Chairman", "[PROCEED] Re-analyzed robust plan.")
            elif node_id == "negativist":
                return make_resp("negativist", "The Negativist", "Severe vulnerability detected")
            elif node_id == "validator":
                return make_resp("validator", "The Validator", "[PASS] Verified.")
            return make_resp(node_id, node_id, "default")

        pipe.client.execute_node = AsyncMock(side_effect=mock_execute)
        res = await pipe.run("Economics query", force_council=False)

        assert res.routing_decision == "COUNCIL_ROUTING"
        assert res.final_output == "Re-analyzed robust plan."
        assert res.telemetry.council_reboots == 1
        assert len(res.reboot_history) == 1
        assert res.reboot_history[0]["chairman_reboot_directive"] == "Fatal flaw in economics."

    asyncio.run(_test())


def test_pipeline_validator_reject_and_repair():
    """Verify Phase 4 repair loop when validator rejects on first attempt and passes on repair."""
    async def _test():
        pipe = MARSPipeline(max_validator_repairs=2)
        val_attempts = 0

        def make_resp(node_id: str, name: str, content: str):
            return AgentResponse(
                node_id=node_id,
                display_name=name,
                provider="mock_provider",
                model="mock_model",
                content=content,
                total_tokens=50,
                success=True,
            )

        async def mock_execute(node_id, system_prompt, user_prompt, override_config=None):
            nonlocal val_attempts
            if node_id == "gating_router":
                return make_resp("gating_router", "Gating Router", "[COUNCIL_ROUTING]")
            elif node_id in ["contrarian", "first_principles", "expansionist", "outsider", "executor"]:
                return make_resp(node_id, node_id, "Council output")
            elif node_id == "chairman":
                if "audited your previous final response" in system_prompt.lower() or "repair" in system_prompt.lower():
                    return make_resp("chairman", "The Chairman", "[PROCEED] Cleaned repaired response.")
                return make_resp("chairman", "The Chairman", "[PROCEED] Initial response with unclosed `code block")
            elif node_id == "negativist":
                return make_resp("negativist", "The Negativist", "Critique")
            elif node_id == "validator":
                val_attempts += 1
                if val_attempts == 1:
                    return make_resp("validator", "The Validator", "[REJECT] Unclosed markdown code block.")
                return make_resp("validator", "The Validator", "[PASS] Cleaned.")
            return make_resp(node_id, node_id, "default")

        pipe.client.execute_node = AsyncMock(side_effect=mock_execute)
        res = await pipe.run("Code query", force_council=True)

        assert res.final_output == "Cleaned repaired response."
        assert res.telemetry.validator_repairs == 1
        assert len(res.validation_history) == 2
        assert res.validation_history[0].passed is False
        assert res.validation_history[1].passed is True

    asyncio.run(_test())


def test_failed_council_node_filtering():
    """Verify that when some council nodes fail, the remaining succeed and synthesize without crashing."""
    async def _test():
        pipe = MARSPipeline()

        async def mock_execute(node_id, system_prompt, user_prompt, override_config=None):
            if node_id == "contrarian":
                # Simulate failure
                return AgentResponse(
                    node_id="contrarian",
                    display_name="The Contrarian",
                    provider="groq",
                    model="qwen/qwen3-32b",
                    content="",
                    success=False,
                    error="Timeout",
                )
            elif node_id in ["first_principles", "expansionist", "outsider", "executor"]:
                return AgentResponse(
                    node_id=node_id,
                    display_name=node_id,
                    provider="mock",
                    model="mock",
                    content="Valid perspective",
                    success=True,
                )
            elif node_id == "chairman":
                if "Synthesize their competing perspectives" in system_prompt:
                    # Ensure the synthesized prompt noted the missing node gracefully
                    assert "unavailable during deliberation" in user_prompt
                    return AgentResponse(
                        node_id="chairman",
                        display_name="The Chairman",
                        provider="gemini",
                        model="gemini-2.5-flash",
                        content="Synthesized draft despite 1 missing node.",
                        success=True,
                    )
                else:
                    return AgentResponse(
                        node_id="chairman",
                        display_name="The Chairman",
                        provider="gemini",
                        model="gemini-2.5-flash",
                        content="[PROCEED] Synthesized final despite 1 missing node.",
                        success=True,
                    )
            elif node_id == "negativist":
                return AgentResponse(node_id="negativist", display_name="Negativist", provider="mistral", model="mistral", content="OK", success=True)
            elif node_id == "validator":
                return AgentResponse(node_id="validator", display_name="Validator", provider="groq", model="llama", content="[PASS]", success=True)
            return AgentResponse(node_id=node_id, display_name=node_id, provider="mock", model="mock", content="OK", success=True)

        pipe.client.execute_node = AsyncMock(side_effect=mock_execute)
        res = await pipe.run("Robustness query", force_council=True)

        assert res.final_output == "Synthesized final despite 1 missing node."
        assert res.council_responses["contrarian"].success is False
        assert res.council_responses["executor"].success is True

    asyncio.run(_test())
