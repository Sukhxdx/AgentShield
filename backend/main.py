"""FastAPI application factory."""

import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.api.routes_agent import router as agent_router
from backend.api.routes_approvals import router as approvals_router
from backend.api.routes_audit import router as audit_router
from backend.api.routes_eval import router as eval_router
from backend.api.routes_test import router as test_router
from backend.config import get_settings
from backend.logging_config import configure_logging
from backend.runtime import build_runtime

logger = logging.getLogger("agentshield")


def create_app() -> FastAPI:
    """Build the API, including middleware, routes, and runtime state."""
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="AgentShield",
        version=__version__,
        description=(
            "Governance layer for tool-using agents. A tool runs only after an "
            "APPROVE decision or a recorded human approval."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.runtime = build_runtime(settings)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        started = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(latency_ms)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response

    @app.get("/health")
    def health() -> dict[str, object]:
        runtime = app.state.runtime
        return {
            "status": "ok",
            "llm_provider": runtime.settings.llm_provider,
            "model_loaded": runtime.model.available,
            "ollama_model": runtime.settings.ollama_model,
        }

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "agentshield", "docs": "/docs", "health": "/health"}

    app.include_router(agent_router)
    app.include_router(test_router)
    app.include_router(approvals_router)
    app.include_router(audit_router)
    app.include_router(eval_router)
    results = Path(settings.results_dir)
    results.mkdir(parents=True, exist_ok=True)
    app.mount("/evaluation/artifacts", StaticFiles(directory=results), name="evaluation-artifacts")
    return app


app = create_app()
