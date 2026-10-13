"""Pydantic contracts shared by the agent, governance layer, and API."""

from typing import Any, Literal

from pydantic import BaseModel, Field

DecisionName = Literal["APPROVE", "HUMAN_APPROVAL", "BLOCK"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
ToolName = Literal[
    "none",
    "read_file",
    "search_documents",
    "send_email",
    "update_record",
    "delete_file",
    "make_payment",
]
AttackType = Literal[
    "none",
    "direct_injection",
    "indirect_injection",
    "jailbreak",
    "data_exfiltration",
    "privilege_escalation",
]
RoleName = Literal["guest", "employee", "manager", "admin", "service"]


class ProposedAction(BaseModel):
    """Tool call proposed by the agent. The agent does not decide safety."""

    tool: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class PromptAnalysis(BaseModel):
    """Injection and sensitive-information findings."""

    injection_score: int = Field(ge=0, le=100)
    sensitive_info_score: int = Field(ge=0, le=100)
    flags: list[str]
    matched_patterns: list[str]
    attack_type: AttackType


class PolicyResult(BaseModel):
    """Deterministic authorization result."""

    authorized: bool
    violations: list[str]
    required_approval: bool
    reasons: list[str]


class RuleRisk(BaseModel):
    """Transparent weighted risk score. Breakdown sums to ``score``."""

    score: int = Field(ge=0, le=100)
    breakdown: dict[str, int]
    level: RiskLevel
    notes: dict[str, str] = Field(default_factory=dict)


class ExecutionPermit(BaseModel):
    """Signed capability required before any simulated tool may run.

    ``decision`` is fixed to APPROVE so a block or hold cannot be passed to the
    executor without constructing a different object and a valid signature.
    """

    request_id: str
    decision: Literal["APPROVE"]
    tool: str
    arguments: dict[str, Any]
    approver: str | None = None
    signature: str


class GovernanceResult(BaseModel):
    """Full governance outcome for one proposed action."""

    decision: DecisionName
    combined_risk: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    rule_risk: RuleRisk
    ml_risk: float
    ml_fallback: bool
    prompt_analysis: PromptAnalysis
    policy_result: PolicyResult
    explanation: str
    reasons: list[str]
    timestamp: str
    request_id: str
    signature: str
    permit: ExecutionPermit | None = None
    phase: Literal["primary", "replan"] = "primary"


class AgentRequest(BaseModel):
    """Natural-language request accepted by ``POST /agent``."""

    request: str = Field(min_length=1, max_length=4000)
    user_role: RoleName = "employee"
    user_id: str = Field(default="demo.employee", max_length=120)
    retrieved_context: str = Field(default="", max_length=8000)


class ManualProposalRequest(BaseModel):
    """Governance request that skips the LLM."""

    request: str = ""
    user_role: RoleName = "employee"
    user_id: str = "demo.employee"
    retrieved_context: str = ""
    tool: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = "operator supplied"


class ScoreRequest(BaseModel):
    """Direct combiner input."""

    rule_risk: float = Field(ge=0, le=100)
    ml_risk: float = Field(ge=0, le=100)


class ApprovalDecision(BaseModel):
    """Human decision on a queued action."""

    approver: str = Field(min_length=1, max_length=120)
    reason: str = ""
