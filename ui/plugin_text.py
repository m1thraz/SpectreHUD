"""Generic presentation of passive plugin-owned text metadata."""

from core.export_plugins import PluginText
from core.i18n import get_locale, t


def plugin_text(value: PluginText) -> str:
    localized = value.localized(get_locale())
    return localized if localized is not None else t(value.translation_key, value.fallback)


__all__ = ["plugin_text"]
