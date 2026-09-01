"""Central operating-system facts used by platform-sensitive services."""

from core.platform.capabilities import (
    PlatformCapabilities,
    detect_platform_capabilities,
)
from core.platform.paths import (
    cache_dir,
    config_dir,
    data_dir,
    legacy_config_dir,
    projects_dir,
    user_themes_dir,
)

__all__ = [
    "PlatformCapabilities",
    "cache_dir",
    "config_dir",
    "data_dir",
    "detect_platform_capabilities",
    "legacy_config_dir",
    "projects_dir",
    "user_themes_dir",
]
