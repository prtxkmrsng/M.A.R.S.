import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from mars.client import strip_reasoning_tokens, CircuitBreaker, LLMClientManager
from mars.pipeline import MARSPipeline
from mars.models import AgentResponse


class TestMARSSystem(unittest.TestCase):
    def test_strip_reasoning_tokens(self):
        raw = "<think>\nLet me deconstruct this problem.\n</think>\nHere is the final actionable step."
        cleaned, trace = strip_reasoning_tokens(raw)
        self.assertEqual(cleaned, "Here is the final actionable step.")
        self.assertIn("deconstruct", trace)

    def test_circuit_breaker_isolation(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=60.0)
        cb.record_transient_failure("groq")
        self.assertTrue(cb.is_available("groq"))
        cb.record_transient_failure("groq")
        self.assertFalse(cb.is_available("groq"))
        self.assertTrue(cb.is_available("gemini"))

    def test_tag_parsers(self):
        decision, ans = MARSPipeline._parse_gating_output("**[DIRECT_EXECUTION]** Paris is the capital of France.")
        self.assertEqual(decision, "DIRECT_EXECUTION")
        self.assertEqual(ans, "Paris is the capital of France.")

        c_dec, c_body = MARSPipeline._parse_chairman_decision("[REBOOT_COUNCIL] Rethink unit economics.")
        self.assertEqual(c_dec, "REBOOT_COUNCIL")
        self.assertEqual(c_body, "Rethink unit economics.")

        passed, verdict, critique = MARSPipeline._parse_validator_output("[REJECT] Unclosed code block.")
        self.assertFalse(passed)
        self.assertEqual(verdict, "REJECT")
        self.assertEqual(critique, "Unclosed code block.")

    def test_pipeline_direct_execution(self):
        async def _run():
            pipe = MARSPipeline()
            pipe.client.execute_node = AsyncMock(
                return_value=AgentResponse(
                    node_id="gating_router",
                    display_name="Gating Router",
                    provider="cloudflare",
                    model="@cf/meta/llama-3.1-8b-instruct-fp8",
                    content="[DIRECT_EXECUTION] 2 + 2 = 4.",
                    total_tokens=20,
                )
            )
            res = await pipe.run("What is 2 + 2?", force_council=False)
            self.assertEqual(res.routing_decision, "DIRECT_EXECUTION")
            self.assertEqual(res.final_output, "2 + 2 = 4.")
            self.assertEqual(res.telemetry.total_api_calls, 1)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
