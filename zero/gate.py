from __future__ import annotations

ALLOW, CONFIRM, DENY = "allow", "confirm", "deny"

# tools that never mutate → always allow
_SAFE_TOOLS = {"Read", "Glob", "Grep", "WebFetch", "WebSearch",
               "mcp__memory__recall"}
# tools that always mutate → at least confirm
_MUTATING_TOOLS = {"Write", "Edit"}


def _text(tool_input: dict) -> str:
    return " ".join(str(v) for v in tool_input.values())


def classify(tool_name: str, tool_input: dict,
             confirm_patterns: list[str], never_patterns: list[str]) -> str:
    blob = _text(tool_input)
    if any(p in blob for p in never_patterns):
        return DENY
    if tool_name in _SAFE_TOOLS:
        return ALLOW
    if tool_name == "Bash":
        if any(p in blob for p in confirm_patterns):
            return CONFIRM
        return ALLOW            # non-mutating shell (ls, cat, git status, etc.)
    if tool_name in _MUTATING_TOOLS:
        return CONFIRM
    if tool_name.startswith("mcp__memory__remember"):
        return ALLOW            # storing a fact is harmless
    return CONFIRM              # unknown/other → conservative


def build_pretooluse_hook(cfg, confirm_aloud):
    """confirm_aloud(question:str)->bool : speak the question, listen for yes/no."""
    async def hook(input_data, tool_use_id, context):
        if input_data.get("hook_event_name") != "PreToolUse":
            return {}
        decision = classify(input_data["tool_name"], input_data.get("tool_input", {}),
                            cfg.gate.confirm_patterns, cfg.gate.never_patterns)
        if decision == ALLOW:
            return {}
        if decision == DENY:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                    "permissionDecision": "deny", "permissionDecisionReason": "Refused: catastrophic action."}}
        # CONFIRM → ask Ahmad out loud
        summary = _text(input_data.get("tool_input", {}))[:160]
        ok = confirm_aloud(f"This will run: {summary}. Shall I proceed, Ahmad?")
        if ok:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny", "permissionDecisionReason": "Ahmad declined."}}
    return hook
