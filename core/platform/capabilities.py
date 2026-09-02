from dataclasses import dataclass
from enum import Enum
import os
import platform
from typing import Mapping, Optional


class ScreenCaptureStatus(str, Enum):
    """Explicit availability states for desktop screen capture."""

    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class PlatformCapabilities:
    """Capabilities expected from the current OS and desktop session."""

    system: str
    global_hotkeys: bool
    screen_capture: bool
    wayland: bool
    x11: bool
    compositor: bool = True

    @property
    def screen_capture_status(self) -> ScreenCaptureStatus:
        if self.screen_capture:
            return ScreenCaptureStatus.AVAILABLE
        if self.wayland:
            return ScreenCaptureStatus.LIMITED
        return ScreenCaptureStatus.UNAVAILABLE

    def is_screen_capture_available(self) -> bool:
        return self.screen_capture


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

    # Detect compositor presence
    compositor = True
    override_comp = environment.get("SPECTREHUD_COMPOSITOR", "").strip().lower()
    if override_comp in ("0", "false", "no", "off", "disable", "disabled"):
        compositor = False
    elif override_comp in ("1", "true", "yes", "on", "enable", "enabled"):
        compositor = True
    elif x11:
        import shutil

        xprop = shutil.which("xprop")
        if xprop:
            try:
                import subprocess

                res = subprocess.run(
                    [xprop, "-root", "-len", "1", "_NET_WM_CM_S0"],
                    capture_output=True,
                    text=True,
                    timeout=0.5,
                )
                compositor = res.returncode == 0 and "window id" in res.stdout.lower()
            except Exception:
                compositor = True

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
        compositor=compositor,
    )
