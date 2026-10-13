"""Path checks shared by policy and the executor."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PathCheck:
    """Result of normalizing a sandbox-relative path."""

    ok: bool
    normalized: str
    reason: str = ""


ALLOWED_PREFIXES = ("guidelines", "docs", "confidential", "finance", "restricted", "inbox")


def check_path(path: object) -> PathCheck:
    """Reject absolute paths, traversal, and locations outside the sandbox tree."""
    if not isinstance(path, str) or not path.strip():
        return PathCheck(False, "", "path_required")
    raw = path.strip().replace("\\", "/")
    if raw.startswith("/") or raw.startswith("~"):
        return PathCheck(False, "", "absolute_path")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return PathCheck(False, "", "path_traversal")
    if not parts:
        return PathCheck(False, "", "path_required")
    if parts[0] not in ALLOWED_PREFIXES:
        return PathCheck(False, "", "path_outside_sandbox")
    return PathCheck(True, "/".join(parts))
