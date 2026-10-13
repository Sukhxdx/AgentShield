"""Process-wide objects built once per application."""

from dataclasses import dataclass
from typing import Any

from backend.agent.graph import build_graph
from backend.agent.llm import LLMClient, build_llm
from backend.agentshield.audit import AuditStore
from backend.agentshield.risk_ml import RiskModel
from backend.agentshield.service import GovernanceService
from backend.config import Settings, get_settings
from backend.tools.sandbox_store import SandboxStore


@dataclass
class Runtime:
    """Dependencies for routes and the LangGraph workflow."""

    settings: Settings
    store: SandboxStore
    audit: AuditStore
    model: RiskModel
    service: GovernanceService
    llm: LLMClient
    graph: Any


def build_runtime(settings: Settings | None = None) -> Runtime:
    """Construct the sandbox, model, governance service, and graph."""
    settings = settings or get_settings()
    store = SandboxStore(settings.sandbox_db_path)
    audit = AuditStore(settings.audit_db_path)
    model = RiskModel(settings.resolved_model_path())
    service = GovernanceService(settings, store, model, audit)
    llm = build_llm(settings)
    graph = build_graph(settings=settings, llm=llm, service=service, store=store, audit=audit)
    return Runtime(
        settings=settings,
        store=store,
        audit=audit,
        model=model,
        service=service,
        llm=llm,
        graph=graph,
    )
