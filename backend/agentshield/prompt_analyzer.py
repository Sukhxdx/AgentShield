"""Layered prompt analysis for injection and sensitive information.

Scores are sums of the weights in ``patterns.yml``, capped at 100. Each pattern
id contributes at most once. Leetspeak patterns run on a normalized copy of the
text. Base64-looking blobs are decoded and scanned with the same user-scope
patterns, which catches trivial encoded instruction smuggling.

Weights (injection, see the YAML for the full catalog):

- ignore-previous instructions: 48
- jailbreak / persona switch: 40
- system-prompt override: 46
- delimiter smuggling: 36
- leetspeak ignore-previous: 42
- indirect "when you read this... forward": 62
- exfiltration phrasing: 44
- privilege escalation: 40

Sensitive-information weights: email 30, phone 25, Aadhaar 50, PAN 50,
API secret 45, employee-database phrasing 40, payroll/salary keywords 28.
Card-like numbers add 55 only when they pass the Luhn check.
"""

import base64
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.agentshield.models import AttackType, PromptAnalysis

_PATTERN_PATH = Path(__file__).with_name("patterns.yml")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"})
_B64 = re.compile(r"(?<![A-Za-z0-9+/])(?:[A-Za-z0-9+/]{16,}={0,2})(?![A-Za-z0-9+/])")
_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_ATTACK_PRIORITY = {
    "privilege_escalation": 5,
    "data_exfiltration": 4,
    "jailbreak": 3,
    "direct_injection": 2,
    "indirect_injection": 1,
    "none": 0,
}


@lru_cache
def _catalog() -> dict[str, Any]:
    raw = yaml.safe_load(_PATTERN_PATH.read_text(encoding="utf-8"))
    compiled: dict[str, list[dict[str, Any]]] = {"injection": [], "sensitive": []}
    for kind in ("injection", "sensitive"):
        for item in raw.get(kind, []):
            compiled[kind].append({**item, "cregex": re.compile(item["regex"])})
    return compiled


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(digits[::-1]):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0 and len(digits) >= 13


def _blob(user_request: str, retrieved_context: str, arguments: dict[str, Any]) -> dict[str, str]:
    arg_text = " ".join(str(value) for value in arguments.values())
    return {
        "user": user_request or "",
        "retrieved": retrieved_context or "",
        "arguments": arg_text,
        "any": "\n".join([user_request or "", retrieved_context or "", arg_text]),
    }


def _normalize(text: str, mode: str | None) -> str:
    if mode == "leet":
        return text.translate(_LEET)
    return text


def _scope_text(scope: str, texts: dict[str, str], mode: str | None) -> str:
    return _normalize(texts.get(scope, texts["any"]), mode)


def _decode_base64(text: str) -> str:
    found: list[str] = []
    for match in _B64.findall(text):
        padded = match + ("=" * ((4 - len(match) % 4) % 4))
        try:
            decoded = base64.b64decode(padded, validate=True)
        except (ValueError, base64.binascii.Error):
            continue
        if not decoded:
            continue
        try:
            found.append(decoded.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    return "\n".join(found)


def _card_hits(text: str) -> bool:
    for match in _CARD.findall(text):
        digits = re.sub(r"\D", "", match)
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return True
    return False


def analyze_prompt(
    user_request: str,
    retrieved_context: str = "",
    arguments: dict[str, Any] | None = None,
) -> PromptAnalysis:
    """Score a request, its retrieved context, and the proposed arguments."""
    texts = _blob(user_request, retrieved_context, arguments or {})
    catalog = _catalog()
    matched: list[str] = []
    flags: list[str] = []
    injection_score = 0
    best_type: AttackType = "none"
    best_weight = -1

    decoded = _decode_base64(texts["any"])
    if decoded:
        texts = {**texts, "user": texts["user"] + "\n" + decoded, "any": texts["any"] + "\n" + decoded}
        matched.append("base64_decoded")
        flags.append("encoded_payload")

    for item in catalog["injection"]:
        haystack = _scope_text(item.get("scope", "any"), texts, item.get("normalize"))
        if not item["cregex"].search(haystack):
            continue
        matched.append(item["id"])
        injection_score += int(item["weight"])
        attack = item["attack_type"]
        weight = int(item["weight"])
        priority = _ATTACK_PRIORITY.get(attack, 0)
        best_priority = _ATTACK_PRIORITY.get(best_type, 0)
        if weight > best_weight or (weight == best_weight and priority > best_priority):
            best_weight = weight
            best_type = attack

    sensitive_score = 0
    sensitive_haystack = texts["any"]
    for item in catalog["sensitive"]:
        if item["cregex"].search(sensitive_haystack):
            matched.append(item["id"])
            sensitive_score += int(item["weight"])
    if _card_hits(sensitive_haystack):
        matched.append("payment_card_luhn")
        sensitive_score += 55

    injection_score = max(0, min(100, injection_score))
    sensitive_score = max(0, min(100, sensitive_score))
    if injection_score:
        flags.append("prompt_injection")
    if best_type == "indirect_injection":
        flags.append("indirect_injection")
    if best_type == "jailbreak":
        flags.append("jailbreak")
    if best_type == "data_exfiltration":
        flags.append("data_exfiltration")
    if best_type == "privilege_escalation":
        flags.append("privilege_escalation")
    if sensitive_score:
        flags.append("sensitive_information")

    return PromptAnalysis(
        injection_score=injection_score,
        sensitive_info_score=sensitive_score,
        flags=flags,
        matched_patterns=matched,
        attack_type=best_type,
    )
