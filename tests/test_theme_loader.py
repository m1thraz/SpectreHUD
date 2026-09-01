"""Tests for built-in and user-provided application themes."""

import json

from core.theme_loader import ThemeLoader
from ui.styles.palette import CYBER_DARK_PALETTE


def test_builtin_cyber_dark_contains_every_required_token():
    loader = ThemeLoader()

    palette = loader.load_theme("cyber_dark")

    assert set(palette) == loader.get_required_tokens()
    assert palette == CYBER_DARK_PALETTE


def test_all_builtin_themes_are_discovered_and_complete():
    loader = ThemeLoader()
    expected_ids = {
        "cyber_dark",
        "daylight",
        "high_contrast",
        "matrix_terminal",
        "nord",
        "red_team",
        "slate",
        "solarized",
        "warm_night",
    }

    discovered_ids = {theme["id"] for theme in loader.list_themes()}

    assert expected_ids <= discovered_ids
    for theme_id in expected_ids:
        palette = loader.load_theme(theme_id)
        assert set(palette) == loader.get_required_tokens()
        assert loader.validate_palette(palette) == []


def test_builtin_themes_have_distinct_visual_identities():
    loader = ThemeLoader()
    theme_ids = {
        "cyber_dark",
        "daylight",
        "high_contrast",
        "matrix_terminal",
        "nord",
        "red_team",
        "slate",
        "solarized",
        "warm_night",
    }

    identities = {
        (loader.load_theme(theme_id)["BG_DARK"], loader.load_theme(theme_id)["CYBER_CYAN"])
        for theme_id in theme_ids
    }

    assert len(identities) == len(theme_ids)


def test_missing_theme_falls_back_to_cyber_dark():
    assert ThemeLoader().load_theme("does_not_exist") == CYBER_DARK_PALETTE


def test_validate_palette_reports_missing_and_invalid_tokens():
    loader = ThemeLoader()
    incomplete = dict(CYBER_DARK_PALETTE)
    incomplete.pop("BG_DARK")
    incomplete["TEXT_PRIMARY"] = ""

    missing = loader.validate_palette(incomplete)

    assert missing == ["BG_DARK", "TEXT_PRIMARY"]


def test_user_theme_is_discovered(tmp_path, monkeypatch):
    user_dir = tmp_path / "themes"
    user_dir.mkdir()
    definition = {
        "id": "portfolio_light",
        "name": "Portfolio Light",
        "author": "Test Author",
        "version": "1.0",
        "palette": dict(CYBER_DARK_PALETTE),
    }
    definition["palette"]["BG_DARK"] = "#ffffff"
    (user_dir / "portfolio_light.json").write_text(json.dumps(definition), encoding="utf-8")
    monkeypatch.setattr(ThemeLoader, "USER_THEMES_DIR", user_dir)

    loader = ThemeLoader()

    assert "portfolio_light" in {theme["id"] for theme in loader.list_themes()}
    assert loader.load_theme("portfolio_light")["BG_DARK"] == "#ffffff"
