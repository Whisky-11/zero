from zero.gate import classify, ALLOW, CONFIRM, DENY

CONFIRM_P = ["rm ", "git push", "Remove-Item", "shutdown"]
NEVER_P = ["rm -rf /", ":(){", "mkfs"]

def c(tool, inp): return classify(tool, inp, CONFIRM_P, NEVER_P)

def test_reads_are_allowed():
    assert c("Read", {"file_path": "x"}) == ALLOW
    assert c("Bash", {"command": "ls -la"}) == ALLOW
    assert c("Bash", {"command": "git status"}) == ALLOW

def test_destructive_needs_confirm():
    assert c("Bash", {"command": "rm old.log"}) == CONFIRM
    assert c("Bash", {"command": "git push origin main"}) == CONFIRM
    assert c("Write", {"file_path": "C:/x"}) == CONFIRM   # any Write mutates

def test_catastrophic_is_denied():
    assert c("Bash", {"command": "rm -rf /"}) == DENY

def test_unknown_mutating_defaults_confirm():
    assert c("SomeNewTool", {"x": 1}) == CONFIRM


# ── Mac tools ────────────────────────────────────────────────────────────
SENSITIVE = ["Mail", "Terminal", "1Password"]

def m(tool, inp, front="Safari", confirm_input=False):
    return classify(tool, inp, CONFIRM_P, NEVER_P, frontmost=front,
                    sensitive_apps=SENSITIVE, confirm_input=confirm_input)

def test_mac_looking_is_allowed():
    assert m("mcp__mac__screenshot", {}) == ALLOW
    assert m("mcp__mac__ui_elements", {"app": "Mail"}) == ALLOW
    assert m("mcp__mac__open_app", {"name": "Safari"}) == ALLOW

def test_mac_input_allowed_in_ordinary_apps():
    assert m("mcp__mac__click", {"x": 10, "y": 20}) == ALLOW
    assert m("mcp__mac__type_text", {"text": "flights to dubai"}) == ALLOW
    assert m("mcp__mac__press_key", {"combo": "cmd+t"}) == ALLOW

def test_mac_input_confirmed_in_sensitive_apps():
    assert m("mcp__mac__click", {"x": 1, "y": 2}, front="Mail") == CONFIRM
    assert m("mcp__mac__type_text", {"text": "hi"}, front="terminal") == CONFIRM  # case-insensitive
    assert m("mcp__mac__click_element", {"name": "Send"}, front="1Password") == CONFIRM

def test_mac_input_confirmed_when_frontmost_unknown_or_forced():
    assert m("mcp__mac__click", {"x": 1, "y": 2}, front="") == CONFIRM
    assert m("mcp__mac__click", {"x": 1, "y": 2}, confirm_input=True) == CONFIRM

def test_mac_typing_prose_is_not_mistaken_for_shell():
    assert m("mcp__mac__type_text", {"text": "fill the form please, the model is warm"}) == ALLOW
    assert m("mcp__mac__type_text", {"text": "rm old.log"}, front="Terminal") == CONFIRM
    assert m("mcp__mac__type_text", {"text": "rm -rf /"}) == DENY

def test_mac_scripts_and_quit_confirm():
    assert m("mcp__mac__run_applescript", {"script": "beep"}) == CONFIRM
    assert m("mcp__mac__run_shortcut", {"name": "Morning"}) == CONFIRM
    assert m("mcp__mac__quit_app", {"name": "Xcode"}) == CONFIRM

def test_mac_open_urls_and_docs_but_confirm_executables():
    assert m("mcp__mac__open", {"target": "https://example.com"}) == ALLOW
    assert m("mcp__mac__open", {"target": "~/Documents/notes.pdf"}) == ALLOW
    assert m("mcp__mac__open", {"target": "~/Downloads/installer.pkg"}) == CONFIRM
    assert m("mcp__mac__open", {"target": "/Applications/Evil.app/"}) == CONFIRM
    assert m("mcp__mac__open", {"target": "~/run.command"}) == CONFIRM

def test_describe_is_speakable():
    from zero.gate import describe
    assert describe("mcp__mac__click_element", {"name": "Send"}, "Mail") == 'press "Send" in Mail'
    assert describe("Bash", {"command": "rm x"}) == "run: rm x"
