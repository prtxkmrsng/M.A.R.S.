from typing import Dict, List, Tuple

# Maps each node_id to an ordered list of (provider, model) fallback pairs
NODE_FALLBACKS: Dict[str, List[Tuple[str, str]]] = {
    "gating_router": [
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-2.5-flash"),
        ("mistral", "mistral-small-latest"),
    ],
    "contrarian": [
        ("groq", "qwen/qwen3.8-27b"),
        ("groq", "openai/gpt-oss-20b"),
        ("cloudflare", "@cf/meta/llama-3.1-8b-instruct-fp8"),
        ("gemini", "gemini-2.5-flash"),
        ("mistral", "mistral-small-latest"),
    ],
    "first_principles": [
        ("groq", "openai/gpt-oss-120b"),
        ("gemini", "gemini-2.5-flash"),
        ("mistral", "mistral-small-latest"),
    ],
    "expansionist": [
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-2.5-flash"),
        ("mistral", "mistral-small-latest"),
        ("openrouter", "meta-llama/llama-3.1-8b-instruct:free"),
    ],
    "outsider": [
        ("cloudflare", "@cf/meta/llama-3.1-8b-instruct-fp8"),
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-2.5-flash"),
    ],
    "executor": [
        ("cloudflare", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
        ("groq", "openai/gpt-oss-120b"),
        ("gemini", "gemini-2.5-flash"),
    ],
    "chairman": [
        ("groq", "openai/gpt-oss-120b"),
        ("cloudflare", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
        ("mistral", "mistral-small-latest"),
    ],
    "negativist": [
        ("gemini", "gemini-2.5-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("cloudflare", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"),
    ],
    "validator": [
        ("groq", "openai/gpt-oss-20b"),
        ("gemini", "gemini-2.5-flash"),
        ("cloudflare", "@cf/meta/llama-3.1-8b-instruct-fp8"),
        ("mistral", "mistral-small-latest"),
    ],
}
