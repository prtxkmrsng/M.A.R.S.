"""Data models for MARS pipeline execution and telemetry."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """Result from an individual node invocation."""

    node_key: str
    role_name: str
    content: str
    latency_ms: float = 0.0
    tokens_used: int = 0
    provider: str
    model: str
    success: bool = True
    error_message: Optional[str] = None


class CouncilResult(BaseModel):
    """Aggregated responses from Phase 2 (The 5 Council Members)."""

    query: str
    responses: Dict[str, AgentResponse] = Field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def compiled_council_text(self) -> str:
        """Format 5 council inputs for Chairman synthesis."""
        sections = []
        for role_key, resp in self.responses.items():
            sections.append(f"### {resp.role_name} Output:\n{resp.content.strip()}\n")
        return "\n".join(sections)


class SynthesisResult(BaseModel):
    """Phase 3 & Phase 4 Audit Trail: Chairman Drafts, Red-Team Critique, and Validator."""

    chairman_draft_1: Optional[AgentResponse] = None
    negativist_critique: Optional[AgentResponse] = None
    chairman_final_resolution: Optional[AgentResponse] = None
    validator_verdict: Optional[AgentResponse] = None
    validation_attempts: int = 1
    validation_passed: bool = True


class TelemetryData(BaseModel):
    """Performance and cost metrics for the entire run."""

    total_latency_s: float = 0.0
    per_node_latency_ms: Dict[str, float] = Field(default_factory=dict)
    total_tokens: int = 0
    cost_usd: float = 0.0
    active_providers: List[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    """Complete output produced by the MARSPipeline."""

    query: str
    route: str  # "[DIRECT]" or "[COUNCIL]"
    final_output: str
    direct_response: Optional[AgentResponse] = None
    council_result: Optional[CouncilResult] = None
    synthesis_result: Optional[SynthesisResult] = None
    telemetry: TelemetryData = Field(default_factory=TelemetryData)
