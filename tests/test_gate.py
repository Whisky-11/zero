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
