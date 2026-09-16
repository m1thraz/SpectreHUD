"""Markdown transformations used only by the editable report preview."""

from dataclasses import dataclass
import re

from core.reporting import (
    PAGEBREAK_REGEX,
    SPACER_REGEX,
    build_report_navigation,
)

PREVIEW_PAGEBREAK_TOKEN = "SPECTRE_PAGEBREAK_PREVIEW_TOKEN"
PREVIEW_PAGEBREAK_LABEL = "──────── PAGE BREAK ────────"
PREVIEW_SPACER_TOKENS = {
    size: f"SPECTRE_SPACER_PREVIEW_{size.upper()}" for size in ("small", "medium", "large")
}
PREVIEW_SPACER_LABELS = {
    "small": "──── SPACER · SMALL ────",
    "medium": "──── SPACER · MEDIUM ────",
    "large": "──── SPACER · LARGE ────",
}
PREVIEW_NAV_TOKEN_PREFIX = "SPECTRE_NAV_PREVIEW_"

_PREVIEW_NAV_MARKER_RE = re.compile(
    r"^<!--\s*spectre:(section|finding):start:([A-Za-z0-9_:-]+)\s*-->\s*$",
    re.IGNORECASE,
)
_PREVIEW_SURROGATE_LINE_RE = re.compile(
    rf"(?m)^.*(?:{re.escape(PREVIEW_PAGEBREAK_LABEL)}|"
    + "|".join(re.escape(label) for label in PREVIEW_SPACER_LABELS.values())
    + rf"|{PREVIEW_NAV_TOKEN_PREFIX}\d{{4}}).*(?:\r?\n)?"
)


@dataclass(frozen=True)
class PreparedPreview:
    """Preview Markdown plus the temporary tokens used to index navigation."""

    markdown: str
    landmarks: tuple[tuple[str, str, str], ...]


def prepare_preview_markdown(markdown: str) -> PreparedPreview:
    """Expose layout markers and attach navigation tokens outside code fences."""
    navigable_markdown, landmarks = _with_navigation_tokens(markdown)
    return PreparedPreview(_with_layout_tokens(navigable_markdown), landmarks)


def strip_preview_surrogates(markdown: str) -> str:
    """Remove all visual preview-only lines before reconciling canonical markers."""
    return _PREVIEW_SURROGATE_LINE_RE.sub("", markdown)


def _with_navigation_tokens(
    markdown: str,
) -> tuple[str, tuple[tuple[str, str, str], ...]]:
    navigation = build_report_navigation(markdown)
    indexed_entries = {
        (entry.kind, entry.identity.casefold()): entry.identity
        for entry in (*navigation.sections, *navigation.findings)
    }
    rendered: list[str] = []
    landmarks: list[tuple[str, str, str]] = []
    pending_tokens: list[str] = []
    in_fence = False
    fence_marker = ""

    for line in markdown.splitlines():
        stripped = line.lstrip()
        opening = re.match(r"(`{3,}|~{3,})", stripped)
        if opening:
            marker = opening.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
            elif marker[0] == fence_marker:
                in_fence = False
                fence_marker = ""
            rendered.append(line)
            continue

        marker_match = None if in_fence else _PREVIEW_NAV_MARKER_RE.fullmatch(line.strip())
        if marker_match is None:
            if pending_tokens and line.strip() and not line.strip().startswith("<!--"):
                line = f"{line} {' '.join(pending_tokens)}"
                pending_tokens.clear()
            rendered.append(line)
            continue

        kind, marker_identity = marker_match.groups()
        identity = indexed_entries.get((kind.casefold(), marker_identity.casefold()))
        if identity is None:
            rendered.append(line)
            continue

        token = f"{PREVIEW_NAV_TOKEN_PREFIX}{len(landmarks):04d}"
        pending_tokens.append(token)
        landmarks.append((token, kind.casefold(), identity))

    if pending_tokens:
        rendered.append(" ".join(pending_tokens))
    return "\n".join(rendered), tuple(landmarks)


def _with_layout_tokens(markdown: str) -> str:
    lines = markdown.splitlines()
    in_fence = False
    fence_marker = ""
    rendered: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        opening = re.match(r"(`{3,}|~{3,})", stripped)
        if opening:
            marker = opening.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
            elif marker[0] == fence_marker:
                in_fence = False
                fence_marker = ""
            rendered.append(line)
        elif not in_fence and PAGEBREAK_REGEX.fullmatch(line.strip()):
            rendered.append(PREVIEW_PAGEBREAK_TOKEN)
        elif not in_fence and (spacer_match := SPACER_REGEX.fullmatch(line.strip())):
            rendered.append(PREVIEW_SPACER_TOKENS[spacer_match.group(1).lower()])
        else:
            rendered.append(line)
    return "\n".join(rendered)
