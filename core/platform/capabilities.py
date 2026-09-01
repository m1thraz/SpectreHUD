"""UI-free desktop capability detection for supported operating systems."""

from dataclasses import dataclass
import os
import platform
from typing import Mapping, Optional


@dataclass(frozen=True)
class PlatformCapabilities:
    """Capabilities expected from the current OS and desktop session."""

    system: str
    global_hotkeys: bool
    screen_capture: bool
    wayland: bool
    x11: bool


def detect_platform_capabilities(
    *,
    system_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> PlatformCapabilities:
    """Return conservative capability facts without importing Qt or UI code.

    Optional inputs make the decision deterministic in tests and keep it
    independent from the developer machine's actual desktop session.
    """
    environment = os.environ if environ is None else environ
    system = (system_name or platform.system()).strip().lower()
    session_type = environment.get("XDG_SESSION_TYPE", "").strip().lower()

    is_linux = system == "linux"
    wayland = is_linux and (
        session_type == "wayland" or bool(environment.get("WAYLAND_DISPLAY"))
    )
    x11 = is_linux and not wayland and (
        session_type == "x11" or bool(environment.get("DISPLAY"))
    )

    # Windows is the fully verified desktop path. Linux capabilities are only
    # advertised for an explicit X11 session. macOS remains an unsupported,
    # conservative fallback until it receives its own implementation/smoke test.
    verified_desktop = system == "windows" or x11
    return PlatformCapabilities(
        system=system,
        global_hotkeys=verified_desktop,
        screen_capture=verified_desktop,
        wayland=wayland,
        x11=x11,
    )
