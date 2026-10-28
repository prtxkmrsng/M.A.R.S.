from __future__ import annotations
import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from openai import AsyncOpenAI, APIStatusError, APITimeoutError, APIConnectionError

from mars.config import (
    NODE_CONFIGS,
    PROVIDER_CONFIGS,
    MODEL_PRICING_PER_1M,
    is_provider_configured,
)
from mars.fallbacks import NODE_FALLBACKS
from mars.models import AgentConfig, AgentResponse

logger = logging.getLogger("mars.client")

THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
UNCLOSED_THINK_RE = re.compile(r"<think>.*$", re.DOTALL | re.IGNORECASE)


def strip_reasoning_tokens(text: str) -> Tuple[str, str]:
    """Extracts <think>...</think> blocks from reasoning models (DeepSeek-R1 / Qwen3)
    and returns (cleaned_content, reasoning_trace)."""
    if not text:
        return "", ""
    traces = THINK_TAG_RE.findall(text)
    cleaned = THINK_TAG_RE.sub("", text).strip()
    if "<think>" in cleaned.lower():
        # Handle truncated unclosed <think> block
        unclosed = UNCLOSED_THINK_RE.findall(cleaned)
        traces.extend(unclosed)
        cleaned = UNCLOSED_THINK_RE.sub("", cleaned).strip()
    return cleaned, "\n".join(traces).strip()


class CircuitBreaker:
    """Tracks transient provider failures (429/5xx/timeouts) and enforces cooldown."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 45.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures: Dict[str, int] = {}
        self.opened_at: Dict[str, float] = {}

    def is_available(self, key: str, *args, **kwargs) -> bool:
        if key not in self.opened_at:
            return True
        elapsed = time.monotonic() - self.opened_at[key]
        if elapsed >= self.cooldown_seconds:
            # Half-open: allow retry
            del self.opened_at[key]
            self.failures[key] = 0
            return True
        return False

    def record_success(self, key: str, *args, **kwargs) -> None:
        self.failures[key] = 0
        self.opened_at.pop(key, None)

    def record_transient_failure(self, key: str) -> None:
        count = self.failures.get(key, 0) + 1
        self.failures[key] = count
        if count >= self.failure_threshold:
            self.opened_at[key] = time.monotonic()
            logger.warning(
                f"CircuitBreaker OPEN for '{key}' after {count} transient failures "
                f"(cooldown={self.cooldown_seconds}s)."
            )

    # Compatibility alias
    def record_failure(self, key: str, *args, **kwargs) -> None:
        self.record_transient_failure(key)


class LLMClientManager:
    """Manages pooled AsyncOpenAI clients, circuit breakers, and multi-provider fallbacks."""

    def __init__(self) -> None:
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=45.0)
        self._clients: Dict[str, AsyncOpenAI] = {}

    def _get_client(self, provider: str) -> AsyncOpenAI:
        if provider not in self._clients:
            cfg = PROVIDER_CONFIGS.get(provider)
            if not cfg or not is_provider_configured(provider):
                raise ValueError(f"Provider '{provider}' is not configured in .env")
            default_headers = {}
            if provider == "openrouter":
                default_headers["HTTP-Referer"] = "https://github.com/prtxkmrsng/M.A.R.S."
                default_headers["X-Title"] = "MARS: Multi-Agent Reasoning System"
            self._clients[provider] = AsyncOpenAI(
                base_url=cfg["base_url"],
                api_key=cfg["api_key"],
                default_headers=default_headers or None,
                max_retries=0,  # Retries and fallbacks are managed explicitly by MARS
            )
        return self._clients[provider]

    @staticmethod
    def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        in_rate, out_rate = MODEL_PRICING_PER_1M.get(model, (0.15, 0.60))
        return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000.0

    async def _call_single(
        self,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
    ) -> Tuple[str, str, int, int]:
        client = self._get_client(provider)
        coro = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        completion = await asyncio.wait_for(coro, timeout=timeout)
        raw_text = (completion.choices[0].message.content or "").strip()
        cleaned_text, reasoning_trace = strip_reasoning_tokens(raw_text)

        # If model spent all tokens inside <think>, salvage reasoning trace rather than returning empty string
        if not cleaned_text and reasoning_trace:
            cleaned_text = re.sub(r"</?think>", "", reasoning_trace, flags=re.IGNORECASE).strip()

        usage = getattr(completion, "usage", None)
        if usage and getattr(usage, "total_tokens", 0):
            p_tok = getattr(usage, "prompt_tokens", 0) or 0
            c_tok = getattr(usage, "completion_tokens", 0) or 0
        else:
            # Fallback token estimation (~4 chars/token)
            p_tok = max(1, (len(system_prompt) + len(user_prompt)) // 4)
            c_tok = max(1, len(raw_text) // 4)

        return cleaned_text, reasoning_trace, p_tok, c_tok

    async def execute_node(
        self,
        node_id: str,
        system_prompt: str,
        user_prompt: str,
        override_config: Optional[AgentConfig] = None,
    ) -> AgentResponse:
        cfg = override_config or NODE_CONFIGS[node_id]
        candidates: List[Tuple[str, str]] = [(cfg.provider, cfg.model)] + NODE_FALLBACKS.get(node_id, [])

        tried_chain: List[str] = []
        start_t = time.perf_counter()
        last_error = "No configured providers available."

        for idx, (provider, model) in enumerate(candidates):
            endpoint_key = f"{provider}:{model}"
            if not is_provider_configured(provider):
                tried_chain.append(f"{endpoint_key} (unconfigured)")
                continue

            if not self.circuit_breaker.is_available(provider):
                tried_chain.append(f"{endpoint_key} (circuit_open)")
                continue

            try:
                call_start = time.perf_counter()
                cleaned_text, reasoning_trace, p_tok, c_tok = await self._call_single(
                    provider=provider,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=cfg.temperature,
                    max_tokens=cfg.max_tokens,
                    timeout=cfg.timeout,
                )
                latency_ms = (time.perf_counter() - call_start) * 1000.0
                self.circuit_breaker.record_success(provider)
                tried_chain.append(endpoint_key)

                return AgentResponse(
                    node_id=node_id,
                    display_name=cfg.display_name,
                    provider=provider,
                    model=model,
                    content=cleaned_text,
                    raw_content=cleaned_text,
                    reasoning_trace=reasoning_trace,
                    latency_ms=latency_ms,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    total_tokens=p_tok + c_tok,
                    estimated_cost_usd=self._estimate_cost(model, p_tok, c_tok),
                    used_fallback=(idx > 0),
                    fallback_chain_tried=tried_chain,
                    success=True,
                )

            except APIStatusError as exc:
                last_error = f"HTTP {exc.status_code} on {endpoint_key}: {exc.message}"
                tried_chain.append(f"{endpoint_key} (HTTP_{exc.status_code})")
                # Only trip provider circuit breaker on rate limit (429) or server errors (5xx),
                # NOT on 400/404 model name errors.
                if exc.status_code == 429 or exc.status_code >= 500:
                    self.circuit_breaker.record_transient_failure(provider)
                logger.warning(f"[{node_id}] {last_error} -> trying next fallback.")

            except (APITimeoutError, APIConnectionError, asyncio.TimeoutError) as exc:
                last_error = f"Timeout/Connection error on {endpoint_key}: {type(exc).__name__}"
                tried_chain.append(f"{endpoint_key} (timeout)")
                self.circuit_breaker.record_transient_failure(provider)
                logger.warning(f"[{node_id}] {last_error} -> trying next fallback.")

            except Exception as exc:
                last_error = f"Unexpected error on {endpoint_key}: {exc}"
                tried_chain.append(f"{endpoint_key} (error)")
                logger.warning(f"[{node_id}] {last_error} -> trying next fallback.")

        total_latency = (time.perf_counter() - start_t) * 1000.0
        return AgentResponse(
            node_id=node_id,
            display_name=cfg.display_name,
            provider=cfg.provider,
            model=cfg.model,
            content="",
            latency_ms=total_latency,
            used_fallback=True,
            fallback_chain_tried=tried_chain,
            success=False,
            error=last_error,
        )

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()
        self._clients.clear()


_DEFAULT_MANAGER: Optional[LLMClientManager] = None


def get_default_client_manager() -> LLMClientManager:
    global _DEFAULT_MANAGER
    if _DEFAULT_MANAGER is None:
        _DEFAULT_MANAGER = LLMClientManager()
    return _DEFAULT_MANAGER


async def fetch_agent_response(
    node_key: str,
    system_prompt: str,
    user_query: str,
    override_temperature: Optional[float] = None,
    custom_messages: Optional[List[Dict[str, str]]] = None,
) -> AgentResponse:
    manager = get_default_client_manager()
    cfg = NODE_CONFIGS.get(node_key)
    if cfg and override_temperature is not None:
        import copy
        cfg = copy.copy(cfg)
        cfg.temperature = override_temperature
    return await manager.execute_node(
        node_id=node_key,
        system_prompt=system_prompt,
        user_prompt=user_query,
        override_config=cfg,
    )
