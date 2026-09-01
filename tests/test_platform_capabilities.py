"""Deterministic tests for OS and desktop-session capability facts."""

import pytest

from core.platform import detect_platform_capabilities


@pytest.mark.parametrize(
    ("system", "environment", "hotkeys", "capture", "wayland", "x11"),
    [
        ("Windows", {}, True, True, False, False),
        ("Linux", {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, True, True, False, True),
        ("Linux", {"DISPLAY": ":1"}, True, True, False, True),
        ("Linux", {"XDG_SESSION_TYPE": "wayland", "WAYLAND_DISPLAY": "wayland-0"}, False, False, True, False),
        ("Linux", {"WAYLAND_DISPLAY": "wayland-1", "DISPLAY": ":0"}, False, False, True, False),
        ("Linux", {}, False, False, False, False),
        ("Darwin", {}, False, False, False, False),
    ],
)
def test_detect_platform_capabilities(
    system,
    environment,
    hotkeys,
    capture,
    wayland,
    x11,
):
    capabilities = detect_platform_capabilities(
        system_name=system,
        environ=environment,
    )

    assert capabilities.system == system.lower()
    assert capabilities.global_hotkeys is hotkeys
    assert capabilities.screen_capture is capture
    assert capabilities.is_screen_capture_available() is capture
    assert capabilities.wayland is wayland
    assert capabilities.x11 is x11

    if capture:
        assert capabilities.screen_capture_status == "available"
    elif wayland:
        assert capabilities.screen_capture_status == "limited"
    else:
        assert capabilities.screen_capture_status == "unavailable"

