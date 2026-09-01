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
from core.platform.opener import open_path
from core.platform.network import detect_linux_ipv4_address, select_preferred_ipv4

__all__ = [
    "PlatformCapabilities",
    "cache_dir",
    "config_dir",
    "data_dir",
    "detect_platform_capabilities",
    "detect_linux_ipv4_address",
    "legacy_config_dir",
    "open_path",
    "projects_dir",
    "select_preferred_ipv4",
    "user_themes_dir",
]
