import pytest
from zero import permissions as p


def test_settings_urls_point_at_privacy_panes():
    assert p.settings_url("Accessibility").endswith("Privacy_Accessibility")
    assert p.settings_url("Screen Recording").endswith("Privacy_ScreenCapture")


def test_summary_and_missing():
    st = {"Microphone": p.GRANTED, "Accessibility": p.MISSING,
          "Screen Recording": p.MISSING, "Automation": p.UNKNOWN}
    assert p.missing(st) == ["Accessibility", "Screen Recording"]
    assert "Accessibility, Screen Recording" in p.summary(st)
    assert p.summary({"Microphone": p.GRANTED}) == "All permissions granted."


@pytest.mark.skipif(p.IS_MAC, reason="non-mac behaviour")
def test_off_mac_status_is_unknown_not_crash():
    assert set(p.status().values()) == {p.UNKNOWN}
    p.request("Accessibility")   # no-op off mac
