"""Central, UI-free application path resolution for supported platforms."""

import os
import platform
from pathlib import Path
from typing import Mapping, Optional


APP_NAME = "SpectreHUD"
APP_SLUG = "spectrehud"


def _context(
    system_name: Optional[str],
    environ: Optional[Mapping[str, str]],
    home: Optional[Path],
) -> tuple[str, Mapping[str, str], Path]:
    return (
        (system_name or platform.system()).strip().lower(),
        os.environ if environ is None else environ,
        Path.home() if home is None else Path(home),
    )


def _base_from_env(environment: Mapping[str, str], key: str, fallback: Path) -> Path:
    value = environment.get(key, "").strip()
    return Path(value) if value else fallback


def _standard_config_dir(system: str, environment: Mapping[str, str], home: Path) -> Path:
    if system == "windows":
        return _base_from_env(environment, "APPDATA", home / "AppData" / "Roaming") / APP_NAME
    if system == "darwin":
        return home / "Library" / "Application Support" / APP_NAME
    return _base_from_env(environment, "XDG_CONFIG_HOME", home / ".config") / APP_SLUG


def _has_entries(path: Path) -> bool:
    try:
        return path.is_dir() and next(path.iterdir(), None) is not None
    except OSError:
        return False


def _prefer_legacy(standard: Path, *legacy_candidates: Path) -> Path:
    if _has_entries(standard):
        return standard
    return next((path for path in legacy_candidates if _has_entries(path)), standard)


def legacy_config_dir(*, home: Optional[Path] = None) -> Path:
    """Return the pre-XDG SpectreHUD config location without creating it."""
    return (Path.home() if home is None else Path(home)) / ".ctf_cheatsheet_widget"


def config_dir(
    *,
    system_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return config storage, retaining populated legacy data when needed."""
    system, environment, home_path = _context(system_name, environ, home)
    override = environment.get("SPECTRE_CONFIG_DIR", "").strip()
    if override:
        return Path(override)
    standard = _standard_config_dir(system, environment, home_path)
    return _prefer_legacy(standard, legacy_config_dir(home=home_path))


def data_dir(
    *,
    system_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the platform-standard mutable application-data directory."""
    system, environment, home_path = _context(system_name, environ, home)
    override = environment.get("SPECTRE_DATA_DIR", "").strip()
    if override:
        return Path(override)
    if system == "windows":
        base = _base_from_env(environment, "LOCALAPPDATA", home_path / "AppData" / "Local")
        return base / APP_NAME
    if system == "darwin":
        return home_path / "Library" / "Application Support" / APP_NAME
    return _base_from_env(environment, "XDG_DATA_HOME", home_path / ".local" / "share") / APP_SLUG


def cache_dir(
    *,
    system_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the platform-standard disposable cache directory."""
    system, environment, home_path = _context(system_name, environ, home)
    override = environment.get("SPECTRE_CACHE_DIR", "").strip()
    if override:
        return Path(override)
    if system == "windows":
        base = _base_from_env(environment, "LOCALAPPDATA", home_path / "AppData" / "Local")
        return base / APP_NAME / "Cache"
    if system == "darwin":
        return home_path / "Library" / "Caches" / APP_NAME
    return _base_from_env(environment, "XDG_CACHE_HOME", home_path / ".cache") / APP_SLUG


def projects_dir(
    *,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the user-visible workspace default, preserving its established location."""
    environment = os.environ if environ is None else environ
    override = environment.get("SPECTRE_PROJECTS_DIR", "").strip()
    if override:
        return Path(override)
    return (Path.home() if home is None else Path(home)) / "spectre_projects"


def user_themes_dir(
    *,
    system_name: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return user theme storage with a read-compatible legacy fallback."""
    system, environment, home_path = _context(system_name, environ, home)
    override = environment.get("SPECTRE_CONFIG_DIR", "").strip()
    if override:
        return Path(override) / "themes"
    standard = _standard_config_dir(system, environment, home_path) / "themes"
    old_cross_platform = home_path / ".config" / APP_SLUG / "themes"
    old_config_relative = legacy_config_dir(home=home_path) / "themes"
    return _prefer_legacy(standard, old_cross_platform, old_config_relative)
