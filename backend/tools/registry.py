"""JSON schemas and descriptions for the six simulated tools.

Implementations live in the executor and are not callable from this module.
"""

from typing import Any

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "read_file": {
        "description": "Read a file inside the simulated document sandbox.",
        "base_impact": "low-medium",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {"path": {"type": "string"}},
        },
    },
    "search_documents": {
        "description": "Search simulated documents by keyword.",
        "base_impact": "low",
        "parameters": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}},
        },
    },
    "send_email": {
        "description": "Send a simulated email. Nothing leaves the sandbox mailbox.",
        "base_impact": "medium",
        "parameters": {
            "type": "object",
            "required": ["to", "subject", "body"],
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
        },
    },
    "update_record": {
        "description": "Update fields on a simulated employee record.",
        "base_impact": "medium-high",
        "parameters": {
            "type": "object",
            "required": ["record_id", "fields"],
            "properties": {
                "record_id": {"type": "string"},
                "fields": {"type": "object"},
            },
        },
    },
    "delete_file": {
        "description": "Delete a file from the simulated sandbox. Irreversible inside the demo session.",
        "base_impact": "high",
        "parameters": {
            "type": "object",
            "required": ["path"],
            "properties": {"path": {"type": "string"}},
        },
    },
    "make_payment": {
        "description": "Record a simulated payment. No money moves.",
        "base_impact": "high",
        "parameters": {
            "type": "object",
            "required": ["payee", "amount", "currency"],
            "properties": {
                "payee": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string"},
            },
        },
    },
}

TOOL_NAMES = list(TOOL_SCHEMAS)
