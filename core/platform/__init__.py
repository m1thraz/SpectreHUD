"""Central operating-system facts used by platform-sensitive services."""

from core.platform.capabilities import (
    PlatformCapabilities,
    detect_platform_capabilities,
)

__all__ = ["PlatformCapabilities", "detect_platform_capabilities"]
