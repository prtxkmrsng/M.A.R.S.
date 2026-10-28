# 🪐 MARS: Comprehensive Run & Verification Guide

This guide provides end-to-end instructions for setting up, running, testing, and verifying the **MARS (Multi-Agent Reasoning System)** pipeline, web interface, CLI, automated tests, and benchmarking suite.

---

## 📑 Table of Contents

1. [System Architecture & 9-Node Topology](#1-system-architecture--9-node-topology)
2. [Prerequisites & Environment Setup](#2-prerequisites--environment-setup)
3. [API Keys & Configuration (`.env`)](#3-api-keys--configuration-env)
4. [Step-by-Step Run Instructions](#4-step-by-step-run-instructions)
   - [Mode A: Unified Verification Runner](#mode-a-unified-verification-runner-recommended-first-step)
   - [Mode B: Interactive Web Interface (Gradio)](#mode-b-interactive-web-interface-gradio)
   - [Mode C: Command-Line Deliberation (CLI)](#mode-c-command-line-deliberation-cli)
   - [Mode D: Quantitative Benchmarking Suite](#mode-d-quantitative-benchmarking-suite)
5. [Testing & Quality Assurance](#5-testing--quality-assurance)
   - [Automated Unit & Mock Tests (`pytest`)](#automated-unit--mock-tests-pytest)
   - [Pipeline Mock Verification](#pipeline-mock-verification)
   - [Failover & Circuit Breaker Verification](#failover--circuit-breaker-verification)
6. [Component-by-Component Verification Checklist](#6-component-by-component-verification-checklist)
7. [Troubleshooting & FAQs](#7-troubleshooting--faqs)

---

## 1. System Architecture & 9-Node Topology

MARS executes an adversarial 4-phase Mixture-of-Agents (MoA) pipeline across 6 free-tier AI providers:

```
[User Query]
     │
     ▼
[Phase 1: Gating Router] ──(Simple)──► [Direct Fast Model] ──► [Output]
     │
     │ (Complex Reasoning)
     ▼
[Phase 2: Concurrent Fan-Out (5 Personas in Parallel)]
     ├── The Contrarian (Groq)
     ├── The First Principle Thinker (SambaNova)
     ├── The Expansionist (OpenRouter)
     ├── The Outsider (Mistral AI)
     └── The Executor (SambaNova)
     │
     ▼
[Phase 3: Executive Tier (Sequential Adversarial Loop)]
     ├── Chairman Synthesis Draft 1 (Google AI Studio / Gemini)
     ├── Negativist Red-Team Audit (SambaNova)
     └── Chairman Final Resolution (Google AI Studio / Gemini)
     │
     ▼
[Phase 4: Ground-Truth Validation]
     └── The Validator (Groq: 0.0 Temp) ──[PASS]──► [Delivered Output]
                                         ──[REJECT]─► [Chairman Repair Loop]
```

### Node Topology & Default Endpoints

| Phase | Node | Role Name | Provider | Default Model | Temp | Key Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Phase 1** | 1 | `gating_router` | Cloudflare Workers AI | `@cf/meta/llama-3.1-8b-instruct` | 0.0 | Edge triage: `[DIRECT]` vs `[COUNCIL]` |
| **Phase 2** | 2 | `contrarian` | Groq | `llama-3.1-8b-instant` | 0.8 | Skeptic: Catches fatal flaws & failure points |
| **Phase 2** | 3 | `first_principles` | SambaNova | `Meta-Llama-3.3-70B-Instruct` | 0.7 | Realist: Strips buzzwords to physics/math |
| **Phase 2** | 4 | `expansionist` | OpenRouter | `meta-llama/llama-3.3-70b-instruct:free` | 0.85 | Optimist: Spots exponential scaling leverage |
| **Phase 2** | 5 | `outsider` | Mistral AI | `mistral-small-latest` | 0.7 | Cynic: Demands proof and questions motives |
| **Phase 2** | 6 | `executor` | SambaNova | `DeepSeek-R1` | 0.6 | Practical: Formulates step-by-step roadmap |
| **Phase 3** | 7 | `chairman` | Google AI Studio | `gemini-3.5-flash` | 0.7 | Idealist: Synthesizes 5 outputs into strategy |
| **Phase 3** | 8 | `negativist` | SambaNova | `DeepSeek-V3-0324` | 0.8 | Red-Team: Ruthlessly attacks Chairman draft |
| **Phase 4** | 9 | `validator` | Groq | `llama-3.3-70b-versatile` | 0.0 | Logic auditor: Validates syntax, links, facts |

---

## 2. Prerequisites & Environment Setup

### Environment Activation
Always activate the target conda environment:

```bash
conda deactivate
conda activate AIML
```

### Dependency Installation
Install all necessary packages via `requirements.txt`:

```bash
pip install -r requirements.txt
```

Verify installed packages:
```bash
python -c "import openai, gradio, pydantic, rich, httpx, dotenv, pytest; print('All dependencies present!')"
```

---

## 3. API Keys & Configuration (`.env`)

Create your local `.env` configuration by copying `.env.example`:

```bash
cp .env.example .env
```

### Required Variables & Free-Tier Providers

| Env Variable | Provider | How to Obtain | Free Tier Limits |
| :--- | :--- | :--- | :--- |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare | [dash.cloudflare.com](https://dash.cloudflare.com) (Sidebar) | Generous daily Neurons allowance |
| `CLOUDFLARE_API_TOKEN` | Cloudflare | [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) (`Workers AI: Read`) | Included in Free Tier |
| `GROQ_API_KEY` | Groq | [console.groq.com/keys](https://console.groq.com/keys) | 30 RPM, 14.4k RPD (8B), 1k RPD (70B) |
| `SAMBANOVA_API_KEY` | SambaNova Cloud | [cloud.sambanova.ai](https://cloud.sambanova.ai) (API Keys) | Generous free rate limits |
| `OPENROUTER_API_KEY` | OpenRouter | [openrouter.ai/keys](https://openrouter.ai/keys) | 20 RPM, 50 RPD (Free models `:free`) |
| `MISTRAL_API_KEY` | Mistral AI | [console.mistral.ai/api-keys](https://console.mistral.ai/api-keys) (Enable "Experiment" tier) | 30 RPM, 1 RPS |
| `GEMINI_API_KEY` | Google AI Studio | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | 15 RPM (Gemini Flash) |

### Auditing Configured Credentials

Run the built-in credential audit command anytime:

```bash
python main.py --check-env
```

Expected output:
```text
🪐 Initializing MARS (Multi-Agent Reasoning System)...
                         MARS Provider & API Key Status                         
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Node          ┃ Role          ┃ Provider      ┃ Env Variable  ┃ Status       ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ gating_router │ Gating Router │ Cloudflare... │ CLOUDFLARE... │ ✓ Configured │
│ contrarian    │ The Contrarian│ Groq          │ GROQ_API_KEY  │ ✓ Configured │
│ ...           │ ...           │ ...           │ ...           │ ✓ Configured │
└───────────────┴───────────────┴───────────────┴───────────────┴──────────────┘
9/9 nodes ready.
```

---

## 4. Step-by-Step Run Instructions

### Mode A: Unified Verification Runner (Recommended First Step)

A dedicated script `verify_all.py` executes dependencies check, credential audit, automated test suite, and optional live smoke testing in one command:

```bash
# Offline verification (dependencies + credential status + 9 unit & mock tests)
python verify_all.py

# Live smoke test (runs real prompt through MARS pipeline)
python verify_all.py --live

# Quick credential check only
python verify_all.py --env-only
```

---

### Mode B: Interactive Web Interface (Gradio)

Launch the full-featured web dashboard:

```bash
# Local execution on default port (http://127.0.0.1:7860)
python main.py

# Specify custom port or bind address
python main.py --port 8080 --host 0.0.0.0

# Generate a public shareable link
python main.py --share
```

#### How to Use the Web UI:
1. Open your browser at `http://127.0.0.1:7860`.
2. Enter a prompt in the text box.
   - **Simple test (Direct Route):** `"What is the capital of Spain?"`
   - **Complex test (Council Route):** `"How should an enterprise build an autonomous agentic customer support fleet with local SLA compliance?"`
3. Click **🚀 Convene the Council**.
4. Observe:
   - **Gating Router Classification:** Real-time badge changes to `[DIRECT]` or `[COUNCIL]`.
   - **The Council Tabs:** Watch 5 tabs populate concurrently (The Contrarian, First Principle Thinker, The Expansionist, The Outsider, The Executor).
   - **Executive Tier Audit Log Accordion:** Expand to view Chairman Draft 1, Negativist Red-Team Critique, Chairman Revised Resolution, and Validator Verdict.
   - **Final Audited & Validated Synthesis:** The validated resolution.
   - **Telemetry Bar:** View Total Latency, Tokens Processed, Cost ($0.00), and Active Providers.

---

### Mode C: Command-Line Deliberation (CLI)

Run queries directly from the terminal with full streaming event logs:

```bash
# Default sample query
python cli.py

# Custom query
python cli.py "How can a solo developer scale an open-source AI infrastructure tool to 100k users?"
```

#### CLI Output Structure:
- Real-time Phase 1 Gating decision.
- Phase 2 parallel member completions with latencies.
- Phase 3 Chairman draft, Negativist audit, and Chairman resolution notifications.
- Phase 4 Validator verification (`[PASS]` / `[REJECT]`).
- Formatted output panel with complete strategic doctrine.
- Detailed execution telemetry table.

---

### Mode D: Quantitative Benchmarking Suite

Compare single frontier baseline responses against the MARS multi-agent council:

```bash
# Run benchmark on first 3 questions
python benchmarks/run_benchmark.py --limit 3

# Run benchmark on all questions in questions.json
python benchmarks/run_benchmark.py
```

#### Outputs Generated:
- `benchmarks/benchmark_results.csv`: Latency, token usage, providers, and audit samples per query.
- `benchmarks/benchmark_report.md`: Formatted comparison table for documentation and academic evaluation.

---

## 5. Testing & Quality Assurance

### Automated Unit & Mock Tests (`pytest`)

Run the automated test suite anytime without consuming API tokens:

```bash
python -m pytest tests/
```

Verbose test output:
```bash
python -m pytest -v tests/
```

### Test Suite Coverage:

1. `tests/test_mars.py`:
   - `test_api_configs_completeness`: Confirms all 9 nodes have defined configurations, models, base URLs, and environment variables.
   - `test_prompts_completeness`: Validates that system prompts exist for all nodes and meet minimum length constraints.
   - `test_circuit_breaker`: Tests failure counting, threshold tripping, cooldown mechanics, and success resets.
   - `test_models_compiled_council_text`: Validates compilation of council perspectives for Chairman synthesis.
   - `test_check_credentials`: Confirms credential dictionary inspection.

2. `tests/test_pipeline_mock.py`:
   - `test_pipeline_direct_route`: Tests Phase 1 direct fast-path routing and result structure.
   - `test_pipeline_council_route_pass`: Tests full 4-phase council deliberation, fan-out, synthesis, red-teaming, and validation pass.
   - `test_pipeline_validator_reject_and_repair`: Tests Phase 4 validation rejection, Chairman correction prompt loop, and subsequent validation pass.
   - `test_fetch_agent_response_fallback`: Tests automatic failover to secondary provider when primary encounters errors (e.g., Groq rate limits failing over to SambaNova).

---

## 6. Component-by-Component Verification Checklist

Use this checklist to confirm full system health:

- [ ] **Python Environment**: `python --version` returns Python 3.10 or higher.
- [ ] **Package Dependencies**: `python verify_all.py` reports `✓ All core dependency packages are installed`.
- [ ] **Configuration Status**: `python main.py --check-env` reports `9/9 nodes ready`.
- [ ] **Unit Tests**: `python -m pytest tests/` passes 9/9 tests.
- [ ] **Fast Path Route**: Query `"What is 15 * 4?"` in CLI routes to `[DIRECT]`.
- [ ] **Council Route**: Query `"Explain the architectural trade-offs of microservices vs monoliths for fintech"` routes to `[COUNCIL]`.
- [ ] **Concurrent Fan-Out**: Web UI shows 5 council persona tabs populating simultaneously.
- [ ] **Red-Team Dialectic**: Phase 3 audit shows Negativist critique challenging Chairman Draft 1.
- [ ] **Validation Integrity**: Phase 4 shows `[PASS]` verdict from zero-temperature validator.
- [ ] **Telemetry Reporting**: Total latency, token count, cost ($0.00), and active provider list displayed in UI/CLI.
- [ ] **Benchmark Export**: `python benchmarks/run_benchmark.py --limit 1` writes CSV and Markdown reports.

---

## 7. Troubleshooting & FAQs

### 1. `429 Rate Limit Exceeded`
- **Cause:** Free tier quotas momentarily reached on a provider (e.g. Groq 8B 30 RPM or OpenRouter 20 RPM).
- **Resolution:** MARS has built-in fallback chains in `mars/fallbacks.py`. If Groq fails, it automatically reroutes to SambaNova or OpenRouter. The circuit breaker prevents repeated retries to failing endpoints.

### 2. `Cloudflare Workers AI: 401 / 403 Authentication Error`
- **Cause:** Incorrect `CLOUDFLARE_ACCOUNT_ID` or missing token permissions.
- **Resolution:**
  1. Verify `CLOUDFLARE_ACCOUNT_ID` matches your Cloudflare dashboard URL (`dash.cloudflare.com/<ACCOUNT_ID>`).
  2. Create an API Token with **Workers AI: Read** permission at [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens).

### 3. Windows Terminal Unicode / UTF-8 Warnings
- **Cause:** Windows default `cp1252` encoding encountering emoji or box-drawing characters.
- **Resolution:** `main.py`, `cli.py`, and `verify_all.py` automatically call `sys.stdout.reconfigure(encoding="utf-8")`. If running external scripts, execute `chcp 65001` in your command prompt.

### 4. OpenRouter `:free` Model Availability
- **Cause:** OpenRouter free model variants (e.g., `meta-llama/llama-3.3-70b-instruct:free`) may experience high traffic surges.
- **Resolution:** MARS fallback chains automatically fail over to Groq or SambaNova if the OpenRouter endpoint times out.

---

## Summary of Verification Commands

```bash
# 1. Activate Environment
conda deactivate
conda activate AIML

# 2. Complete Health & Test Verification
python verify_all.py

# 3. Launch Web UI
python main.py

# 4. Run CLI Query
python cli.py "How can a startup build a zero-emission logistics network?"

# 5. Run Benchmark
python benchmarks/run_benchmark.py --limit 3
```
