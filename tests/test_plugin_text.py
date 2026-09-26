from core.export_plugins import PluginText
from ui import plugin_text as plugin_text_module


def test_plugin_owned_translation_precedes_host_catalog(monkeypatch):
    monkeypatch.setattr(plugin_text_module, "get_locale", lambda: "de-DE")
    monkeypatch.setattr(
        plugin_text_module,
        "t",
        lambda key, fallback: f"host:{key}:{fallback}",
    )
    value = PluginText(
        "plugins.sample.name",
        "Sample",
        translations={"de": "Beispiel"},
    )

    assert plugin_text_module.plugin_text(value) == "Beispiel"


def test_plugin_text_falls_back_to_host_translation(monkeypatch):
    monkeypatch.setattr(plugin_text_module, "get_locale", lambda: "fr")
    monkeypatch.setattr(
        plugin_text_module,
        "t",
        lambda key, fallback: f"host:{key}:{fallback}",
    )

    assert (
        plugin_text_module.plugin_text(PluginText("plugins.sample.name", "Sample"))
        == "host:plugins.sample.name:Sample"
    )
