"""Neutral font-stack definitions shared by application UI and reporting."""

UI_FONT_STACKS = {
    "segoe_ui": (
        "'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, Roboto, sans-serif"
    ),
    "inter": "'Inter', 'Segoe UI', -apple-system, sans-serif",
    "ibm_plex_sans": (
        "'IBM Plex Sans', 'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif"
    ),
    "manrope": "'Manrope', 'Inter', 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
    "roboto": "'Roboto', 'Segoe UI', -apple-system, sans-serif",
    "open_sans": "'Open Sans', 'Segoe UI', -apple-system, sans-serif",
}
CODE_FONT_STACKS = {
    "consolas": "'Consolas', 'Cascadia Code', 'Fira Code', monospace",
    "cascadia_code": "'Cascadia Code', 'Consolas', 'Fira Code', monospace",
    "fira_code": "'Fira Code', 'Cascadia Code', 'Consolas', monospace",
    "jetbrains_mono": "'JetBrains Mono', 'Consolas', 'Fira Code', monospace",
    "ibm_plex_mono": "'IBM Plex Mono', 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace",
    "iosevka": "'Iosevka', 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace",
    "hack": "'Hack', 'JetBrains Mono', 'DejaVu Sans Mono', 'Consolas', monospace",
}
REPORT_FONT_STACKS = {
    "segoe_ui": (
        "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', 'Roboto', "
        "'Helvetica Neue', Arial, sans-serif"
    ),
    "calibri": "'Calibri', 'Segoe UI', Arial, sans-serif",
    "arial": "Arial, 'Helvetica Neue', 'Segoe UI', sans-serif",
    "lato": "'Lato', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
    "source_serif": "'Source Serif 4', 'Source Serif Pro', 'Georgia', 'Times New Roman', serif",
    "georgia": "Georgia, 'Times New Roman', serif",
    "cambria": "'Cambria', 'Georgia', 'Times New Roman', serif",
}

UI_FONT_OPTIONS = [
    ("segoe_ui", "Segoe UI"),
    ("inter", "Inter"),
    ("ibm_plex_sans", "IBM Plex Sans"),
    ("manrope", "Manrope"),
    ("roboto", "Roboto"),
    ("open_sans", "Open Sans"),
]
CODE_FONT_OPTIONS = [
    ("consolas", "Consolas"),
    ("cascadia_code", "Cascadia Code"),
    ("fira_code", "Fira Code"),
    ("jetbrains_mono", "JetBrains Mono"),
    ("ibm_plex_mono", "IBM Plex Mono"),
    ("iosevka", "Iosevka (Condensed)"),
    ("hack", "Hack"),
]
REPORT_FONT_OPTIONS = [
    ("segoe_ui", "Segoe UI"),
    ("calibri", "Calibri"),
    ("arial", "Arial"),
    ("georgia", "Georgia (Serif)"),
    ("lato", "Lato"),
    ("source_serif", "Source Serif Pro"),
    ("cambria", "Cambria (Serif)"),
]

FONT_FAMILIES = {
    "segoe_ui": "Segoe UI",
    "inter": "Inter",
    "ibm_plex_sans": "IBM Plex Sans",
    "manrope": "Manrope",
    "roboto": "Roboto",
    "open_sans": "Open Sans",
    "consolas": "Consolas",
    "cascadia_code": "Cascadia Code",
    "fira_code": "Fira Code",
    "jetbrains_mono": "JetBrains Mono",
    "ibm_plex_mono": "IBM Plex Mono",
    "iosevka": "Iosevka",
    "hack": "Hack",
    "calibri": "Calibri",
    "arial": "Arial",
    "lato": "Lato",
    "source_serif": "Source Serif Pro",
    "georgia": "Georgia",
    "cambria": "Cambria",
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
