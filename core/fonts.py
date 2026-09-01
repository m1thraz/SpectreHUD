"""Neutral font-stack definitions shared by application UI and reporting."""

UI_FONT_STACKS = {
    "segoe_ui": (
        "'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif"
    ),
    "inter": "'Inter', 'Segoe UI', -apple-system, sans-serif",
    "roboto": "'Roboto', 'Segoe UI', -apple-system, sans-serif",
    "open_sans": "'Open Sans', 'Segoe UI', -apple-system, sans-serif",
}
CODE_FONT_STACKS = {
    "consolas": "'Consolas', 'Cascadia Code', 'Fira Code', monospace",
    "cascadia_code": "'Cascadia Code', 'Consolas', 'Fira Code', monospace",
    "fira_code": "'Fira Code', 'Cascadia Code', 'Consolas', monospace",
    "jetbrains_mono": "'JetBrains Mono', 'Consolas', 'Fira Code', monospace",
}
REPORT_FONT_STACKS = {
    "segoe_ui": (
        "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', 'Roboto', "
        "'Helvetica Neue', Arial, sans-serif"
    ),
    "calibri": "'Calibri', 'Segoe UI', Arial, sans-serif",
    "arial": "Arial, 'Helvetica Neue', 'Segoe UI', sans-serif",
    "georgia": "Georgia, 'Times New Roman', serif",
}

UI_FONT_OPTIONS = [
    ("segoe_ui", "Segoe UI"),
    ("inter", "Inter"),
    ("roboto", "Roboto"),
    ("open_sans", "Open Sans"),
]
CODE_FONT_OPTIONS = [
    ("consolas", "Consolas"),
    ("cascadia_code", "Cascadia Code"),
    ("fira_code", "Fira Code"),
    ("jetbrains_mono", "JetBrains Mono"),
]
REPORT_FONT_OPTIONS = [
    ("segoe_ui", "Segoe UI"),
    ("calibri", "Calibri"),
    ("arial", "Arial"),
    ("georgia", "Georgia (Serif)"),
]

FONT_FAMILIES = {
    "segoe_ui": "Segoe UI",
    "inter": "Inter",
    "roboto": "Roboto",
    "open_sans": "Open Sans",
    "consolas": "Consolas",
    "cascadia_code": "Cascadia Code",
    "fira_code": "Fira Code",
    "jetbrains_mono": "JetBrains Mono",
    "calibri": "Calibri",
    "arial": "Arial",
    "georgia": "Georgia",
}


def get_font_family(key: str) -> str:
    """Return the local family whose availability represents a font option."""
    return FONT_FAMILIES.get(key, "")


def get_font_stack(stacks: dict[str, str], key: str, default_key: str) -> str:
    """Return a known stack and safely fall back for invalid persisted keys."""
    return stacks.get(key, stacks[default_key])


def get_ui_font_stack(key: str) -> str:
    return get_font_stack(UI_FONT_STACKS, key, "segoe_ui")


def get_code_font_stack(key: str) -> str:
    return get_font_stack(CODE_FONT_STACKS, key, "consolas")


def get_report_font_stack(key: str) -> str:
    return get_font_stack(REPORT_FONT_STACKS, key, "segoe_ui")
