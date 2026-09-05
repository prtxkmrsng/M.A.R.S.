"""Configuration module for MARS nodes and API providers."""

import os
from typing import Any, Dict
from dotenv import load_dotenv

# Load .env file
load_dotenv()

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()

API_CONFIGS: Dict[str, Dict[str, Any]] = {
    "gating_router": {
        "role_name": "Gating Router",
        "provider": "Cloudflare Workers AI",
        "base_url": f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1" if CLOUDFLARE_ACCOUNT_ID else "https://api.cloudflare.com/client/v4/accounts/NONE/ai/v1",
        "api_key_env": "CLOUDFLARE_API_TOKEN",
        "model": "@cf/meta/llama-3.1-8b-instruct",
        "temperature": 0.0,
        "timeout": 12.0,
        "retries": 2,
    },
    "contrarian": {
        "role_name": "The Contrarian",
        "provider": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.1-8b-instant",
        "temperature": 0.8,
        "timeout": 15.0,
        "retries": 2,
    },
    "first_principles": {
        "role_name": "The First Principle Thinker",
        "provider": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "model": "meta/llama-3.1-8b-instruct",
        "temperature": 0.7,
        "timeout": 20.0,
        "retries": 2,
    },
    "expansionist": {
        "role_name": "The Expansionist",
        "provider": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "temperature": 0.85,
        "timeout": 25.0,
        "retries": 2,
    },
    "outsider": {
        "role_name": "The Outsider",
        "provider": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_env": "MISTRAL_API_KEY",
        "model": "mistral-small-latest",
        "temperature": 0.7,
        "timeout": 20.0,
        "retries": 2,
    },
    "executor": {
        "role_name": "The Executor",
        "provider": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "model": "deepseek-ai/deepseek-r1",
        "temperature": 0.6,
        "timeout": 30.0,
        "retries": 2,
    },
    "chairman": {
        "role_name": "The Chairman",
        "provider": "Google AI Studio",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "model": "gemini-3.8-flash",
        "temperature": 0.7,
        "timeout": 25.0,
        "retries": 2,
    },
    "negativist": {
        "role_name": "The Negativist",
        "provider": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "model": "deepseek-ai/deepseek-v3",
        "temperature": 0.8,
        "timeout": 25.0,
        "retries": 2,
    },
    "validator": {
        "role_name": "The Validator",
        "provider": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
        "temperature": 0.0,
        "timeout": 15.0,
        "retries": 2,
    },
}

def reload_env() -> None:
    """Reload environment variables and refresh dynamic base_urls."""
    global CLOUDFLARE_ACCOUNT_ID
    load_dotenv(override=True)
    CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    if CLOUDFLARE_ACCOUNT_ID:
        API_CONFIGS["gating_router"]["base_url"] = (
            f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1"
        )


def check_credentials() -> Dict[str, Dict[str, Any]]:
    """Check availability of credentials for all configured nodes."""
    reload_env()
    status = {}
    for node_key, conf in API_CONFIGS.items():
        env_var = conf["api_key_env"]
        val = os.getenv(env_var, "").strip()
        is_ready = bool(val)
        if node_key == "gating_router":
            is_ready = bool(val and CLOUDFLARE_ACCOUNT_ID)
        status[node_key] = {
            "role": conf["role_name"],
            "provider": conf["provider"],
            "env_var": env_var,
            "configured": is_ready,
        }
    return status
