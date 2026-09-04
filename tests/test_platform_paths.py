"""Platform path resolution without dependence on the developer's home."""

from core.platform.paths import (
    cache_dir,
    config_dir,
    data_dir,
    projects_dir,
    user_themes_dir,
)


def test_linux_uses_explicit_xdg_roots(tmp_path):
    environment = {
        "XDG_CONFIG_HOME": str(tmp_path / "xdg-config"),
        "XDG_DATA_HOME": str(tmp_path / "xdg-data"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg-cache"),
    }

    assert config_dir(system_name="Linux", environ=environment, home=tmp_path) == tmp_path / "xdg-config" / "spectrehud"
    assert data_dir(system_name="Linux", environ=environment, home=tmp_path) == tmp_path / "xdg-data" / "spectrehud"
    assert cache_dir(system_name="Linux", environ=environment, home=tmp_path) == tmp_path / "xdg-cache" / "spectrehud"


def test_linux_uses_xdg_fallbacks_when_environment_is_absent(tmp_path):
    assert config_dir(system_name="Linux", environ={}, home=tmp_path) == tmp_path / ".config" / "spectrehud"
    assert data_dir(system_name="Linux", environ={}, home=tmp_path) == tmp_path / ".local" / "share" / "spectrehud"
    assert cache_dir(system_name="Linux", environ={}, home=tmp_path) == tmp_path / ".cache" / "spectrehud"


def test_windows_uses_roaming_config_and_local_data(tmp_path):
    environment = {
        "APPDATA": str(tmp_path / "Roaming"),
        "LOCALAPPDATA": str(tmp_path / "Local"),
    }

    assert config_dir(system_name="Windows", environ=environment, home=tmp_path) == tmp_path / "Roaming" / "SpectreHUD"
    assert data_dir(system_name="Windows", environ=environment, home=tmp_path) == tmp_path / "Local" / "SpectreHUD"
    assert cache_dir(system_name="Windows", environ=environment, home=tmp_path) == tmp_path / "Local" / "SpectreHUD" / "Cache"


def test_explicit_spectre_overrides_have_highest_priority(tmp_path):
    environment = {
        "SPECTRE_CONFIG_DIR": str(tmp_path / "config-override"),
        "SPECTRE_DATA_DIR": str(tmp_path / "data-override"),
        "SPECTRE_CACHE_DIR": str(tmp_path / "cache-override"),
        "SPECTRE_PROJECTS_DIR": str(tmp_path / "projects-override"),
    }

    assert config_dir(system_name="Linux", environ=environment, home=tmp_path) == tmp_path / "config-override"
    assert data_dir(system_name="Linux", environ=environment, home=tmp_path) == tmp_path / "data-override"
    assert cache_dir(system_name="Linux", environ=environment, home=tmp_path) == tmp_path / "cache-override"
    assert projects_dir(environ=environment, home=tmp_path) == tmp_path / "projects-override"
    assert user_themes_dir(system_name="Linux", environ=environment, home=tmp_path) == tmp_path / "config-override" / "themes"


def test_windows_user_themes_retain_old_cross_platform_location(tmp_path):
    old_themes = tmp_path / ".config" / "spectrehud" / "themes"
    old_themes.mkdir(parents=True)
    (old_themes / "custom.json").write_text("{}", encoding="utf-8")

    resolved = user_themes_dir(
        system_name="Windows",
        environ={"APPDATA": str(tmp_path / "Roaming")},
        home=tmp_path,
    )

    assert resolved == old_themes
