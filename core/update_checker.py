"""Headless GitHub release checks for SpectreHUD."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import sys
from typing import Any, Callable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.cli import APP_VERSION


LATEST_RELEASE_API = "https://api.github.com/repos/m1thraz/SpectreHUD/releases/latest"
MAX_RESPONSE_BYTES = 1_000_000
_VERSION_PATTERN = re.compile(
    r"^[vV]?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:[-+][0-9A-Za-z.-]+)?$"
)


class UpdateCheckError(RuntimeError):
    """Raised when release information cannot be safely evaluated."""


@dataclass(frozen=True)
class UpdateCheckResult:
    current_version: str
    latest_version: str
    release_url: str
    published_at: str
    update_available: bool
    asset_url: Optional[str] = None


def _version_tuple(version: str) -> tuple[int, int, int]:
    match = _VERSION_PATTERN.fullmatch(str(version).strip())
    if match is None:
        raise UpdateCheckError(f"Unsupported release version: {version!r}")
    return (int(match.group("major")), int(match.group("minor")), int(match.group("patch")))



def _preferred_asset_url(release: Mapping[str, Any], platform_name: str) -> Optional[str]:
    suffix = ".exe" if platform_name == "win32" else ".deb" if platform_name.startswith("linux") else ""
    if not suffix:
        return None
    for asset in release.get("assets", []):
        if not isinstance(asset, Mapping):
            continue
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if name.lower().endswith(suffix) and url.startswith("https://github.com/"):
            return url
    return None


def check_for_updates(
    current_version: str = APP_VERSION,
    *,
    timeout: float = 5.0,
    platform_name: Optional[str] = None,
    opener: Callable[..., Any] = urlopen,
) -> UpdateCheckResult:
    """Return the latest stable GitHub release without downloading or installing it."""
    request = Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"SpectreHUD/{current_version}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise UpdateCheckError("GitHub release information is currently unavailable") from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise UpdateCheckError("GitHub release response exceeded the safety limit")
    try:
        release = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateCheckError("GitHub returned invalid release information") from exc
    if not isinstance(release, Mapping) or release.get("draft") or release.get("prerelease"):
        raise UpdateCheckError("GitHub did not return a stable release")

    latest_version = str(release.get("tag_name", "")).strip().removeprefix("v")
    release_url = str(release.get("html_url", ""))
    if not release_url.startswith("https://github.com/m1thraz/SpectreHUD/releases/"):
        raise UpdateCheckError("GitHub returned an unexpected release URL")

    return UpdateCheckResult(
        current_version=current_version,
        latest_version=latest_version,
        release_url=release_url,
        published_at=str(release.get("published_at", "")),
        update_available=_version_tuple(latest_version) > _version_tuple(current_version),
        asset_url=_preferred_asset_url(release, platform_name or sys.platform),
    )
