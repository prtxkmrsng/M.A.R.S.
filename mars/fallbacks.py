"""Resilience layer: Fallback providers and circuit breaker for MARS."""

import time
from typing import Dict, List, Optional, Tuple

# Fallback chain for each node if primary provider fails
NODE_FALLBACKS: Dict[str, List[Dict[str, str]]] = {
    "gating_router": [
        {
            "provider": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.1-8b-instant",
        },
        {
            "provider": "NVIDIA NIM",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key_env": "NVIDIA_API_KEY",
            "model": "meta/llama-3.1-8b-instruct",
        },
    ],
    "contrarian": [
        {
            "provider": "NVIDIA NIM",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key_env": "NVIDIA_API_KEY",
            "model": "meta/llama-3.1-8b-instruct",
        },
        {
            "provider": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "model": "meta-llama/llama-3.3-70b-instruct:free",
        },
    ],
    "first_principles": [
        {
            "provider": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.1-8b-instant",
        },
        {
            "provider": "Mistral AI",
            "base_url": "https://api.mistral.ai/v1",
            "api_key_env": "MISTRAL_API_KEY",
            "model": "mistral-small-latest",
        },
    ],
    "expansionist": [
        {
            "provider": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.1-8b-instant",
        },
        {
            "provider": "NVIDIA NIM",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key_env": "NVIDIA_API_KEY",
            "model": "meta/llama-3.1-8b-instruct",
        },
    ],
    "outsider": [
        {
            "provider": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "model": "meta-llama/llama-3.3-70b-instruct:free",
        },
        {
            "provider": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.1-8b-instant",
        },
    ],
    "executor": [
        {
            "provider": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.3-70b-versatile",
        },
        {
            "provider": "OpenRouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "model": "meta-llama/llama-3.3-70b-instruct:free",
        },
    ],
    "chairman": [
        {
            "provider": "NVIDIA NIM",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key_env": "NVIDIA_API_KEY",
            "model": "deepseek-ai/deepseek-v3",
        },
        {
            "provider": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.3-70b-versatile",
        },
    ],
    "negativist": [
        {
            "provider": "Groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "model": "llama-3.3-70b-versatile",
        },
        {
            "provider": "Google AI Studio",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key_env": "GEMINI_API_KEY",
            "model": "gemini-2.5-flash",
        },
    ],
    "validator": [
        {
            "provider": "NVIDIA NIM",
            "base_url": "https://integrate.api.nvidia.com/v1",
            "api_key_env": "NVIDIA_API_KEY",
            "model": "meta/llama-3.1-8b-instruct",
        },
        {
            "provider": "Google AI Studio",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "api_key_env": "GEMINI_API_KEY",
            "model": "gemini-2.5-flash",
        },
    ],
}


class CircuitBreaker:
    """Tracks provider failure rates and trips temporary cooldowns."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_counts: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}

    def is_available(self, provider: str) -> bool:
        """Check if a provider is currently out of cooldown."""
        fails = self.failure_counts.get(provider, 0)
        if fails >= self.failure_threshold:
            last_fail = self.last_failure_time.get(provider, 0.0)
            if time.time() - last_fail < self.cooldown_seconds:
                return False
            # Reset after cooldown period expires
            self.failure_counts[provider] = 0
        return True

    def record_success(self, provider: str) -> None:
        """Record a successful call and reset failure tally."""
        self.failure_counts[provider] = 0

    def record_failure(self, provider: str) -> None:
        """Increment failure counter and update timestamp."""
        self.failure_counts[provider] = self.failure_counts.get(provider, 0) + 1
        self.last_failure_time[provider] = time.time()


# Global circuit breaker instance
CIRCUIT_BREAKER = CircuitBreaker()
