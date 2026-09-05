"""Asynchronous LLM client engine for MARS with fallback and timeout handling."""

import asyncio
import os
import time
from typing import Dict, List, Optional, Tuple
from openai import AsyncOpenAI

from mars.config import API_CONFIGS
from mars.fallbacks import CIRCUIT_BREAKER, NODE_FALLBACKS
from mars.models import AgentResponse


def _create_client(base_url: str, api_key: str, provider: str) -> AsyncOpenAI:
    """Build an AsyncOpenAI instance configured with appropriate headers."""
    default_headers = {}
    if "openrouter" in base_url.lower():
        default_headers["HTTP-Referer"] = "https://github.com/prtxkmrsng/M.A.R.S."
        default_headers["X-Title"] = "MARS: Multi-Agent Reasoning System"

    return AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers=default_headers or None,
    )


async def execute_llm_call(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    timeout: float = 20.0,
    provider: str = "Unknown",
) -> Tuple[str, int]:
    """Execute a single async OpenAI-compatible chat completion."""
    client = _create_client(base_url, api_key, provider)
    start_time = time.perf_counter()
    
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        ),
        timeout=timeout,
    )
    content = response.choices[0].message.content or ""
    tokens = 0
    if response.usage:
        tokens = (response.usage.prompt_tokens or 0) + (response.usage.completion_tokens or 0)
    return content, tokens


async def fetch_agent_response(
    node_key: str,
    system_prompt: str,
    user_query: str,
    override_temperature: Optional[float] = None,
    custom_messages: Optional[List[Dict[str, str]]] = None,
) -> AgentResponse:
    """Fetch response for a given MARS node with automatic retry and fallback chains."""
    primary_conf = API_CONFIGS[node_key]
    role_name = primary_conf["role_name"]
    temp = override_temperature if override_temperature is not None else primary_conf["temperature"]
    timeout = primary_conf["timeout"]
    retries = primary_conf.get("retries", 2)

    messages = custom_messages or [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    # Build list of targets: primary first, then fallbacks
    targets = [
        {
            "provider": primary_conf["provider"],
            "base_url": primary_conf["base_url"],
            "api_key_env": primary_conf["api_key_env"],
            "model": primary_conf["model"],
        }
    ]
    if node_key in NODE_FALLBACKS:
        targets.extend(NODE_FALLBACKS[node_key])

    start_perf = time.perf_counter()
    last_error = "No credentials or providers available."

    for target in targets:
        provider = target["provider"]
        api_key = os.getenv(target["api_key_env"], "").strip()

        # Skip if no API key configured
        if not api_key:
            continue

        # Skip if provider circuit breaker is tripped
        if not CIRCUIT_BREAKER.is_available(provider):
            continue

        base_url = target["base_url"]
        model = target["model"]

        for attempt in range(retries):
            try:
                content, tokens = await execute_llm_call(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    temperature=temp,
                    timeout=timeout,
                    provider=provider,
                )
                CIRCUIT_BREAKER.record_success(provider)
                elapsed_ms = (time.perf_counter() - start_perf) * 1000.0
                return AgentResponse(
                    node_key=node_key,
                    role_name=role_name,
                    content=content,
                    latency_ms=elapsed_ms,
                    tokens_used=tokens,
                    provider=provider,
                    model=model,
                    success=True,
                )
            except Exception as exc:
                last_error = f"{provider} ({model}) Error: {str(exc)}"
                CIRCUIT_BREAKER.record_failure(provider)
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

    # If all providers failed or were unconfigured:
    elapsed_ms = (time.perf_counter() - start_perf) * 1000.0
    return AgentResponse(
        node_key=node_key,
        role_name=role_name,
        content=f"[{role_name} Unavailable: {last_error}]",
        latency_ms=elapsed_ms,
        tokens_used=0,
        provider=primary_conf["provider"],
        model=primary_conf["model"],
        success=False,
        error_message=last_error,
    )
