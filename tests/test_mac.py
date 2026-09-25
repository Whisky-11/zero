import pytest
from zero import mac


def test_parse_combo():
    assert mac.parse_combo("cmd+shift+t") == ("t", ["command", "shift"])
    assert mac.parse_combo("Return") == ("return", [])
    assert mac.parse_combo("alt + space") == ("space", ["option"])
    with pytest.raises(ValueError):
        mac.parse_combo("hyper+x")
    with pytest.raises(ValueError):
        mac.parse_combo("")


def test_as_quote_escapes():
    assert mac.as_quote('say "hi" \\ bye') == '"say \\"hi\\" \\\\ bye"'


def test_key_script():
    assert mac.key_script("cmd+c") == \
        'tell application "System Events" to keystroke "c" using {command down}'
    assert mac.key_script("return") == 'tell application "System Events" to key code 36'
    assert mac.key_script("cmd+shift+left").endswith("key code 123 using {command down, shift down}")
    with pytest.raises(ValueError):
        mac.key_script("cmd+nosuchkey")


def test_type_script_handles_newlines_and_quotes():
    s = mac.type_script('line "one"\nline two')
    assert 'keystroke "line \\"one\\""' in s
    assert "key code 36" in s
    assert 'keystroke "line two"' in s


def test_coords_roundtrip():
    c = mac.Coords()
    assert c.to_screen(100, 50) == (100, 50)          # before any screenshot: points
    c.set_from(image_w=1440, screen_w_points=1728)     # Retina downscaled capture
    x, y = c.to_screen(720, 450)
    assert (round(x), round(y)) == (864, 540)
    assert c.to_image(864, 540) == (720, 450)


def test_tools_are_all_named_and_gated():
    from zero.gate import classify, ALLOW, CONFIRM
    assert len(mac.TOOL_NAMES) == len(mac.TOOLS)
    for name in mac.TOOL_NAMES:   # every tool gets a decision, none crash
        assert classify(name, {}, [], [], frontmost="Finder") in (ALLOW, CONFIRM)


@pytest.mark.skipif(mac.IS_MAC, reason="non-mac behaviour")
def test_off_mac_returns_error_not_exception():
    ok, msg = mac.open_app("Safari")
    assert not ok and "macOS" in msg
    ok, data, _ = mac.screenshot()
    assert not ok


def test_sdk_tools_build_and_fail_soft_off_mac():
    pytest.importorskip("claude_agent_sdk")
    import asyncio
    tools = {t.name: t for t in mac.build_tools()}
    assert set(tools) == set(mac.TOOLS)
    assert tools["click"].input_schema["required"] == ["x", "y"]
    if not mac.IS_MAC:
        for name, args in (("open_app", {"name": "Safari"}), ("screenshot", {})):
            r = asyncio.run(tools[name].handler(args))
            assert r["is_error"] and "macOS" in r["content"][0]["text"]
    srv = mac.build_mac_mcp()
    assert srv["name"] == "mac"
