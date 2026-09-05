"""Unit tests for MARS modules and data structures."""

import pytest
from mars.config import API_CONFIGS, check_credentials
from mars.fallbacks import CircuitBreaker, NODE_FALLBACKS
from mars.models import AgentResponse, CouncilResult, PipelineResult, TelemetryData
from mars.prompts import PROMPTS_BY_NODE


def test_api_configs_completeness():
    expected_nodes = [
        "gating_router",
        "contrarian",
        "first_principles",
        "expansionist",
        "outsider",
        "executor",
        "chairman",
        "negativist",
        "validator",
    ]
    for node in expected_nodes:
        assert node in API_CONFIGS, f"Missing config for {node}"
        assert "base_url" in API_CONFIGS[node]
        assert "api_key_env" in API_CONFIGS[node]
        assert "model" in API_CONFIGS[node]


def test_prompts_completeness():
    expected_prompt_keys = [
        "gating_router",
        "contrarian",
        "first_principles",
        "expansionist",
        "outsider",
        "executor",
        "chairman_synthesis",
        "negativist",
        "chairman_resolution",
        "validator",
    ]
    for key in expected_prompt_keys:
        assert key in PROMPTS_BY_NODE, f"Missing prompt for {key}"
        assert len(PROMPTS_BY_NODE[key]) > 10


def test_circuit_breaker():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.5)
    provider = "MockProvider"

    assert cb.is_available(provider) is True
    cb.record_failure(provider)
    assert cb.is_available(provider) is True

    cb.record_failure(provider)
    # Tripped
    assert cb.is_available(provider) is False

    # Success resets
    cb.record_success(provider)
    assert cb.is_available(provider) is True


def test_models_compiled_council_text():
    resp1 = AgentResponse(
        node_key="contrarian",
        role_name="The Contrarian",
        content="Critique A",
        provider="Groq",
        model="llama-3.1-8b-instant",
    )
    resp2 = AgentResponse(
        node_key="executor",
        role_name="The Executor",
        content="Action Plan B",
        provider="NVIDIA NIM",
        model="deepseek-ai/deepseek-r1",
    )
    council = CouncilResult(
        query="Test query",
        responses={"contrarian": resp1, "executor": resp2},
    )
    compiled = council.compiled_council_text
    assert "The Contrarian Output:" in compiled
    assert "Critique A" in compiled
    assert "The Executor Output:" in compiled
    assert "Action Plan B" in compiled


def test_check_credentials():
    status = check_credentials()
    assert isinstance(status, dict)
    assert "gating_router" in status
    assert "chairman" in status
