from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time


@dataclass
class AgentConfig:
    node_id: str
    display_name: str
    phase: int
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: float = 25.0


@dataclass
class AgentResponse:
    node_id: str
    display_name: str
    provider: str
    model: str
    content: str
    raw_content: str = ""
    reasoning_trace: str = ""
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    used_fallback: bool = False
    fallback_chain_tried: List[str] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None

    # Backward compatibility properties
    @property
    def node_key(self) -> str:
        return self.node_id

    @property
    def role_name(self) -> str:
        return self.display_name

    @property
    def tokens_used(self) -> int:
        return self.total_tokens

    @property
    def error_message(self) -> Optional[str]:
        return self.error


@dataclass
class ValidationResult:
    passed: bool
    verdict: str  # "PASS" or "REJECT"
    critique: str
    response: AgentResponse


@dataclass
class PipelineTelemetry:
    total_latency_ms: float = 0.0
    phase1_latency_ms: float = 0.0
    phase2_latency_ms: float = 0.0
    phase3_latency_ms: float = 0.0
    phase4_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_estimated_cost_usd: float = 0.0
    total_api_calls: int = 0
    fallbacks_triggered: int = 0
    council_reboots: int = 0
    validator_repairs: int = 0
    node_calls: List[AgentResponse] = field(default_factory=list)

    @property
    def total_latency_s(self) -> float:
        return round(self.total_latency_ms / 1000.0, 2)

    @property
    def cost_usd(self) -> float:
        return round(self.total_estimated_cost_usd, 6)

    @property
    def active_providers(self) -> List[str]:
        return sorted(list({r.provider for r in self.node_calls if r.success and r.provider}))

    def record(self, resp: AgentResponse) -> None:
        self.node_calls.append(resp)
        self.total_api_calls += 1
        self.total_prompt_tokens += resp.prompt_tokens
        self.total_completion_tokens += resp.completion_tokens
        self.total_tokens += resp.total_tokens
        self.total_estimated_cost_usd += resp.estimated_cost_usd
        if resp.used_fallback:
            self.fallbacks_triggered += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_latency_ms": round(self.total_latency_ms, 1),
            "phase_latencies_ms": {
                "phase1_gating": round(self.phase1_latency_ms, 1),
                "phase2_council_parallel": round(self.phase2_latency_ms, 1),
                "phase3_synthesis_redteam": round(self.phase3_latency_ms, 1),
                "phase4_validation": round(self.phase4_latency_ms, 1),
            },
            "tokens": {
                "prompt": self.total_prompt_tokens,
                "completion": self.total_completion_tokens,
                "total": self.total_tokens,
            },
            "estimated_cost_usd": round(self.total_estimated_cost_usd, 6),
            "total_api_calls": self.total_api_calls,
            "fallbacks_triggered": self.fallbacks_triggered,
            "council_reboots": self.council_reboots,
            "validator_repairs": self.validator_repairs,
        }


# Compatibility alias
TelemetryData = PipelineTelemetry


@dataclass
class CouncilResult:
    query: str
    responses: Dict[str, AgentResponse] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def compiled_council_text(self) -> str:
        lines = []
        for key, resp in self.responses.items():
            lines.append(f"### {resp.display_name} Output:\n{resp.content}\n")
        return "\n".join(lines)


@dataclass
class SynthesisResult:
    chairman_draft_1: Optional[AgentResponse] = None
    negativist_critique: Optional[AgentResponse] = None
    chairman_final_resolution: Optional[AgentResponse] = None
    validator_verdict: Optional[AgentResponse] = None
    validation_attempts: int = 1
    validation_passed: bool = True


@dataclass
class PipelineResult:
    query: str
    routing_decision: str  # "DIRECT_EXECUTION" or "COUNCIL_ROUTING"
    final_output: str
    gating_response: Optional[AgentResponse] = None
    council_responses: Dict[str, AgentResponse] = field(default_factory=dict)
    chairman_initial_draft: Optional[AgentResponse] = None
    negativist_critique: Optional[AgentResponse] = None
    chairman_resolution: Optional[AgentResponse] = None
    validation_history: List[ValidationResult] = field(default_factory=list)
    reboot_history: List[Dict[str, Any]] = field(default_factory=list)
    telemetry: PipelineTelemetry = field(default_factory=PipelineTelemetry)

    # Compatibility attributes
    direct_response: Optional[AgentResponse] = None
    council_result: Optional[CouncilResult] = None
    synthesis_result: Optional[SynthesisResult] = None

    @property
    def route(self) -> str:
        return self.routing_decision
