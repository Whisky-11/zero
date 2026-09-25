from __future__ import annotations

ALLOW, CONFIRM, DENY = "allow", "confirm", "deny"

# tools that never mutate → always allow
_SAFE_TOOLS = {"Read", "Glob", "Grep", "WebFetch", "WebSearch",
               "mcp__memory__recall",
               # Mac: looking, and low-stakes system niceties
               "mcp__mac__screenshot", "mcp__mac__frontmost_app", "mcp__mac__list_windows",
               "mcp__mac__ui_elements", "mcp__mac__list_shortcuts", "mcp__mac__get_clipboard",
               "mcp__mac__set_clipboard", "mcp__mac__notify", "mcp__mac__set_volume",
               "mcp__mac__open_app", "mcp__mac__activate_app", "mcp__mac__scroll"}
# tools that always mutate → at least confirm
_MUTATING_TOOLS = {"Write", "Edit",
                   # arbitrary scripts / shortcuts can do anything; quitting may lose work
                   "mcp__mac__run_applescript", "mcp__mac__run_shortcut", "mcp__mac__quit_app"}
# Mac input tools: act as Ahmad's hands. Allowed in ordinary apps so Zero is
# usable by voice; confirmed in sensitive apps (or always, if confirm_input).
_INPUT_TOOLS = {"mcp__mac__click", "mcp__mac__click_element",
                "mcp__mac__type_text", "mcp__mac__press_key"}
# `open` runs whatever it is pointed at — a .app/.command/.pkg is code execution.
_RISKY_OPEN = (".app", ".command", ".sh", ".pkg", ".dmg", ".tool", ".workflow", ".terminal")


def _text(tool_input: dict) -> str:
    return " ".join(str(v) for v in tool_input.values())


def is_input_tool(tool_name: str) -> bool:
    return tool_name in _INPUT_TOOLS


def classify(tool_name: str, tool_input: dict,
             confirm_patterns: list[str], never_patterns: list[str], *,
             frontmost: str = "", sensitive_apps: list[str] = (),
             confirm_input: bool = False) -> str:
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
    if tool_name in _INPUT_TOOLS:
        if confirm_input:
            return CONFIRM
        # the frontmost app couldn't be determined → can't prove it's safe
        if not frontmost:
            return CONFIRM
        front = frontmost.lower()
        if any(a.lower() == front for a in sensitive_apps):
            return CONFIRM
        # (shell confirm_patterns are NOT applied to typed text: "form " contains
        # "rm ". Terminals are sensitive apps, so typing there confirms anyway.)
        return ALLOW
    if tool_name == "mcp__mac__open":
        target = str(tool_input.get("target", "")).lower().rstrip("/")
        if target.startswith(("http://", "https://")):
            return ALLOW
        if target.endswith(_RISKY_OPEN) or ".app/" in target:
            return CONFIRM
        return ALLOW            # a document or folder
    if tool_name.startswith("mcp__memory__remember"):
        return ALLOW            # storing a fact is harmless
    return CONFIRM              # unknown/other → conservative


def describe(tool_name: str, tool_input: dict, frontmost: str = "") -> str:
    """A short spoken phrase for the confirmation question."""
    where = f" in {frontmost}" if frontmost else ""
    t = tool_input
    if tool_name == "mcp__mac__click":
        return f"click at {t.get('x')}, {t.get('y')}{where}"
    if tool_name == "mcp__mac__click_element":
        return f"press \"{t.get('name')}\"{where}"
    if tool_name == "mcp__mac__type_text":
        return f"type \"{str(t.get('text', ''))[:80]}\"{where}"
    if tool_name == "mcp__mac__press_key":
        return f"press {t.get('combo')}{where}"
    if tool_name == "mcp__mac__quit_app":
        return f"quit {t.get('name')}"
    if tool_name == "mcp__mac__run_shortcut":
        return f"run the shortcut {t.get('name')}"
    if tool_name == "mcp__mac__run_applescript":
        return "run an AppleScript: " + str(t.get("script", ""))[:120]
    if tool_name == "mcp__mac__open":
        return f"open {t.get('target')}"
    simple = {
        "mcp__mac__screenshot": "look at the screen",
        "mcp__mac__frontmost_app": "check the front app",
        "mcp__mac__list_windows": "list open windows",
        "mcp__mac__ui_elements": f"read the controls in {t.get('app') or 'the front app'}",
        "mcp__mac__open_app": f"open {t.get('name')}",
        "mcp__mac__activate_app": f"switch to {t.get('name')}",
        "mcp__mac__scroll": f"scroll {'up' if (t.get('dy') or 0) > 0 else 'down'}",
        "mcp__mac__list_shortcuts": "list Shortcuts",
        "mcp__mac__get_clipboard": "read the clipboard",
        "mcp__mac__set_clipboard": "copy text to the clipboard",
        "mcp__mac__set_volume": f"set volume to {t.get('level')}%",
        "mcp__mac__notify": f"notify: {str(t.get('text', ''))[:80]}",
        "mcp__memory__recall": f"recall {t.get('query')}",
        "mcp__memory__remember": f"remember {str(t.get('fact', ''))[:80]}",
    }
    if tool_name in simple:
        return simple[tool_name]
    if tool_name == "Bash":
        return "run: " + str(t.get("command", _text(tool_input)))[:160]
    if tool_name in ("Write", "Edit"):
        return f"{tool_name.lower()} {t.get('file_path', '')}"
    return f"use {label(tool_name)}: " + _text(tool_input)[:160]


def label(tool_name: str) -> str:
    """'mcp__mac__click_element' -> 'click_element', 'Bash' -> 'Bash'."""
    return tool_name.rsplit("__", 1)[-1] if tool_name.startswith("mcp__") else tool_name


def build_pretooluse_hook(cfg, confirm_aloud, frontmost_fn=None, on_action=None):
    """confirm_aloud(question:str)->bool : speak the question, listen for yes/no.
    frontmost_fn()->str : current frontmost app (Mac); only called for input tools.
    on_action(event:dict) : told every decision (audit log + HUD activity feed);
      event = {tool, input, app, decision, outcome, summary} where outcome is
      allowed | confirmed | declined | denied."""
    mac = getattr(cfg, "mac", None)
    sensitive = list(getattr(mac, "sensitive_apps", []) or [])
    confirm_input = bool(getattr(mac, "confirm_input", False))

    async def hook(input_data, tool_use_id, context):
        if input_data.get("hook_event_name") != "PreToolUse":
            return {}
        name = input_data["tool_name"]
        tool_input = input_data.get("tool_input", {})
        front = ""
        if is_input_tool(name) and frontmost_fn is not None:
            try:
                front = frontmost_fn() or ""
            except Exception:
                front = ""
        decision = classify(name, tool_input,
                            cfg.gate.confirm_patterns, cfg.gate.never_patterns,
                            frontmost=front, sensitive_apps=sensitive,
                            confirm_input=confirm_input)

        def report(outcome: str) -> None:
            if on_action is None:
                return
            try:
                on_action({"tool": label(name), "input": tool_input, "app": front,
                           "decision": decision, "outcome": outcome,
                           "summary": describe(name, tool_input, front)})
            except Exception:
                pass  # reporting must never block a tool

        if decision == ALLOW:
            report("allowed")
            return {}
        if decision == DENY:
            report("denied")
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                    "permissionDecision": "deny", "permissionDecisionReason": "Refused: catastrophic action."}}
        # CONFIRM → ask Ahmad out loud
        ok = confirm_aloud(f"This will {describe(name, tool_input, front)}. Shall I proceed, Ahmad?")
        report("confirmed" if ok else "declined")
        if ok:
            return {}
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny", "permissionDecisionReason": "Ahmad declined."}}
    return hook
