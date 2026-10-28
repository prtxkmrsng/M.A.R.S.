import os
from typing import Any, Dict
from dotenv import load_dotenv
from mars.models import AgentConfig

load_dotenv()

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()

PROVIDER_CONFIGS: Dict[str, Dict[str, str]] = {
    "cloudflare": {
        "base_url": f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
        "api_key": os.getenv("CLOUDFLARE_API_TOKEN", "").strip(),
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", "").strip(),
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "api_key": os.getenv("MISTRAL_API_KEY", "").strip(),
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": os.getenv("GEMINI_API_KEY", "").strip(),
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_API_KEY", "").strip(),
    },
}

# Reference commercial pricing per 1M tokens (used to show theoretical value saved by $0 free-tier routing)
MODEL_PRICING_PER_1M: Dict[str, tuple[float, float]] = {
    "@cf/meta/llama-3.1-8b-instruct-fp8": (0.05, 0.08),
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": (0.29, 2.25),
    "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b": (0.50, 4.88),
    "qwen/qwen3-32b": (0.29, 0.59),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "mistral-small-latest": (0.10, 0.30),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
}

# 9-Node Topology across 4 Execution Phases
NODE_CONFIGS: Dict[str, AgentConfig] = {
    # Phase 1: Intake Gatekeeper
    "gating_router": AgentConfig(
        node_id="gating_router",
        display_name="Gating Router (The Pragmatist)",
        phase=1,
        provider="cloudflare",
        model="@cf/meta/llama-3.1-8b-instruct-fp8",
        temperature=0.0,
        max_tokens=256,
        timeout=12.0,
    ),
    # Phase 2: The 5-Agent Parallel Council
    "contrarian": AgentConfig(
        node_id="contrarian",
        display_name="The Contrarian (Skeptic/Pessimist)",
        phase=2,
        provider="groq",
        model="qwen/qwen3.8-27b",
        temperature=0.6,
        max_tokens=1200,
        timeout=25.0,
    ),
    "first_principles": AgentConfig(
        node_id="first_principles",
        display_name="1st Principle Thinker (Realist)",
        phase=2,
        provider="cloudflare",
        model="@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        temperature=0.5,
        max_tokens=1024,
        timeout=30.0,
    ),
    "expansionist": AgentConfig(
        node_id="expansionist",
        display_name="The Expansionist (Optimist/Opportunist)",
        phase=2,
        provider="groq",
        model="openai/gpt-oss-120b",
        temperature=0.8,
        max_tokens=1024,
        timeout=25.0,
    ),
    "outsider": AgentConfig(
        node_id="outsider",
        display_name="The Outsider (The Cynic)",
        phase=2,
        provider="mistral",
        model="mistral-small-latest",
        temperature=0.7,
        max_tokens=1024,
        timeout=25.0,
    ),
    "executor": AgentConfig(
        node_id="executor",
        display_name="The Executor (Practical Realist)",
        phase=2,
        provider="cloudflare",
        model="@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
        temperature=0.5,
        max_tokens=2048,  # Increased so <think> trace doesn't truncate the final output
        timeout=35.0,
    ),
    # Phase 3: Executive Synthesis & Adversarial Red-Teaming
    "chairman": AgentConfig(
        node_id="chairman",
        display_name="The Chairman (Idealist Synthesizer)",
        phase=3,
        provider="gemini",
        model="gemini-2.5-flash",  # Fixed from invalid gemini-3.5-flash
        temperature=0.5,
        max_tokens=2500,
        timeout=40.0,
    ),
    "negativist": AgentConfig(
        node_id="negativist",
        display_name="The Negativist (Adversarial Red-Teamer)",
        phase=3,
        provider="mistral",  # Decoupled from Chairman to eliminate self-bias & Gemini RPM contention
        model="mistral-small-latest",
        temperature=0.7,
        max_tokens=1500,
        timeout=30.0,
    ),
    # Phase 4: Zero-Temperature Ground-Truth Auditor
    "validator": AgentConfig(
        node_id="validator",
        display_name="The Validator (Ground-Truth Auditor)",
        phase=4,
        provider="groq",
        model="openai/gpt-oss-120b",
        temperature=0.0,
        max_tokens=800,
        timeout=20.0,
    ),
}

COUNCIL_NODE_IDS = [
    "contrarian",
    "first_principles",
    "expansionist",
    "outsider",
    "executor",
]


def is_provider_configured(provider: str) -> bool:
    cfg = PROVIDER_CONFIGS.get(provider, {})
    if not cfg.get("api_key"):
        return False
    if provider == "cloudflare" and not CLOUDFLARE_ACCOUNT_ID:
        return False
    return True


def reload_env() -> None:
    """Reload environment variables and refresh dynamic base_urls and keys."""
    global CLOUDFLARE_ACCOUNT_ID
    load_dotenv(override=True)
    CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    PROVIDER_CONFIGS["cloudflare"]["api_key"] = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    PROVIDER_CONFIGS["cloudflare"]["base_url"] = (
        f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1"
        if CLOUDFLARE_ACCOUNT_ID
        else "https://api.cloudflare.com/client/v4/accounts/NONE/ai/v1"
    )
    PROVIDER_CONFIGS["groq"]["api_key"] = os.getenv("GROQ_API_KEY", "").strip()
    PROVIDER_CONFIGS["mistral"]["api_key"] = os.getenv("MISTRAL_API_KEY", "").strip()
    PROVIDER_CONFIGS["gemini"]["api_key"] = os.getenv("GEMINI_API_KEY", "").strip()
    PROVIDER_CONFIGS["openrouter"]["api_key"] = os.getenv("OPENROUTER_API_KEY", "").strip()


def check_credentials() -> Dict[str, Dict[str, Any]]:
    """Check availability of credentials for all configured nodes."""
    reload_env()
    provider_env_keys = {
        "cloudflare": "CLOUDFLARE_API_TOKEN",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    status = {}
    for node_id, cfg in NODE_CONFIGS.items():
        is_ready = is_provider_configured(cfg.provider)
        status[node_id] = {
            "role": cfg.display_name,
            "provider": cfg.provider,
            "env_var": provider_env_keys.get(cfg.provider, ""),
            "configured": is_ready,
        }
    return status


# Backward-compatible API_CONFIGS dictionary
API_CONFIGS: Dict[str, Dict[str, Any]] = {
    node_id: {
        "role_name": cfg.display_name,
        "provider": cfg.provider,
        "base_url": PROVIDER_CONFIGS[cfg.provider]["base_url"],
        "api_key_env": {
            "cloudflare": "CLOUDFLARE_API_TOKEN",
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }[cfg.provider],
        "model": cfg.model,
        "temperature": cfg.temperature,
        "timeout": cfg.timeout,
        "retries": 2,
    }
    for node_id, cfg in NODE_CONFIGS.items()
}
