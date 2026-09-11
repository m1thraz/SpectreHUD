"""
Snippet domain package for SpectreHUD.

Provides cheatsheet commands, filtering, variable interpolation,
and multi-format snippet import (JSON, Markdown).
"""

from core.snippets.manager import SnippetManager
from core.snippets.interpolator import SMART_PRESETS, TemplateEngine
from core.snippets.filter import (
    filter_and_rank_snippets,
    filter_by_category,
    tokenize_query,
)
from core.snippets.importer import (
    import_snippets_from_file,
    normalize_template_variables,
    parse_snippets_json,
    parse_snippets_markdown,
)

__all__ = [
    "SMART_PRESETS",
    "SnippetManager",
    "TemplateEngine",
    "filter_and_rank_snippets",
    "filter_by_category",
    "import_snippets_from_file",
    "normalize_template_variables",
    "parse_snippets_json",
    "parse_snippets_markdown",
    "tokenize_query",
]
