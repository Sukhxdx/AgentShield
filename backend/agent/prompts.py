"""System prompt and the JSON-only tool contract shown to the agent.

The agent never sees AgentShield scores, thresholds, or policy text.
"""

from backend.tools.registry import TOOL_SCHEMAS

SYSTEM_PROMPT = """/no_think
You are an operations assistant for Northwind. You propose exactly one tool call
as JSON. You do not decide whether the call is safe or authorized.

Return only a JSON object with this shape:
{{"tool": "<one of the tools below or none>", "arguments": {{}}, "reasoning": "short"}}

Tools:
{tools}

If the request cannot be done with one of these tools, use "none".
Do not wrap the JSON in markdown.
"""


def render_system_prompt() -> str:
    """Fill the tool list into the system prompt."""
    lines = []
    for name, spec in TOOL_SCHEMAS.items():
        required = ", ".join(spec["parameters"]["required"])
        lines.append(f"- {name}({required}): {spec['description']}")
    return SYSTEM_PROMPT.format(tools="\n".join(lines))


def render_user_prompt(user_request: str, retrieved_context: str, replan: bool) -> str:
    """Build the user turn, including any retrieved document text."""
    context = retrieved_context.strip() or "(none)"
    replan_note = ""
    if replan:
        replan_note = (
            "\nThe previous proposal was refused. Propose a safer alternative "
            "that still helps, or use tool none.\n"
        )
    return (
        f"User request:\n{user_request}\n"
        f"{replan_note}\n"
        f"Retrieved document content:\n{context}\n"
    )
