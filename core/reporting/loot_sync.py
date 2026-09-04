"""
Pure domain logic for SpectreHUD report loot markers and additive report synchronization.

Features:
- Canonical loot marker formatting (<!-- spectre:loot:{entry_id}:{content_hash} -->)
- Canonical SHA-256 content hashing
- Robust marker parsing and marker stripping
- Report / loot diff status classification (missing, current, stale, orphaned)
- Byte-preserving structural insertion of missing loot into existing Markdown reports
- Rich-preview roundtrip marker reconciliation
"""

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from core.loot_manager import CATEGORIES

# Regex matching SpectreHUD loot markers strictly: <!-- spectre:loot:{id}:{hash} -->
MARKER_REGEX = re.compile(r"<!--\s*spectre:loot:([A-Za-z0-9_-]+):([a-fA-F0-9]+)\s*-->")
STRIP_MARKER_REGEX = re.compile(
    r"<!--\s*spectre:loot:[A-Za-z0-9_-]+:[a-fA-F0-9]+\s*-->\r?\n?"
)

PAGEBREAK_MARKER = "<!-- spectre:pagebreak -->"
PAGEBREAK_HTML = '<div class="spectre-page-break" contenteditable="false"></div>'
PAGEBREAK_REGEX = re.compile(r"<!--\s*spectre:pagebreak\s*-->", re.IGNORECASE)

SECTION_NOTES_PLACEHOLDER_DE = "_Eigene Anmerkungen zu dieser Phase:_"
SECTION_NOTES_PLACEHOLDER_EN = "_Notes & observations for this phase:_"
FALLBACK_SECTION_TITLE_DE = "Neu aus Loot ergänzt"
FALLBACK_SECTION_TITLE_EN = "New Loot Entries"
FALLBACK_SECTION_TITLE = FALLBACK_SECTION_TITLE_DE


def loot_content_hash(entry: Mapping[str, Any]) -> str:
    """Calculates a deterministic 12-hex-character SHA-256 hash for a loot entry.

    Fields hashed: category, content, severity, target_ip, timestamp, title, type.
    Note: position is intentionally omitted so board reordering does not mark a report stale.
    """
    payload = {
        "category": str(entry.get("category", "") or ""),
        "content": str(entry.get("content", "") or ""),
        "severity": str(entry.get("severity", "info") or "info").lower(),
        "target_ip": str(entry.get("target_ip", "") or ""),
        "timestamp": str(entry.get("timestamp", "") or ""),
        "title": str(entry.get("title", "") or ""),
        "type": str(entry.get("type", "note") or "note"),
    }
    canonical_json = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:12]


def format_loot_marker(entry_id: str, content_hash: str) -> str:
    """Formats a canonical SpectreHUD HTML comment marker for a loot entry."""
    return f"<!-- spectre:loot:{entry_id}:{content_hash} -->"


def extract_report_markers(report_text: str) -> Dict[str, str]:
    """Extracts all valid SpectreHUD loot markers from markdown report text.

    Returns a mapping of {entry_id: content_hash_lowercase}.
    If duplicate IDs appear, the last valid marker wins deterministically.
    """
    if not report_text:
        return {}
    markers: Dict[str, str] = {}
    for match in MARKER_REGEX.finditer(report_text):
        entry_id = match.group(1)
        content_hash = match.group(2).lower()
        markers[entry_id] = content_hash
    return markers


def strip_report_markers(text: str) -> str:
    """Strips ONLY SpectreHUD loot markers (<!-- spectre:loot:... -->) from text.

    Preserves Obsidian loot deduplication markers (<!-- spectrehud-entry:... -->)
    and user-authored HTML comments untouched.
    """
    if not text:
        return ""
    return STRIP_MARKER_REGEX.sub("", text)


@dataclass(frozen=True)
class LootReportState:
    """Classified status of project loot entries relative to an existing report."""

    missing: Tuple[Dict[str, Any], ...]
    current: Tuple[Dict[str, Any], ...]
    stale: Tuple[Dict[str, Any], ...]
    orphaned_ids: Tuple[str, ...]


def classify_loot_report_state(
    report_text: str, loot_entries: Iterable[Mapping[str, Any]]
) -> LootReportState:
    """Classifies each loot entry into missing, current, or stale relative to report markers,

    and identifies orphaned markers in the report that no longer correspond to active loot.
    """
    markers = extract_report_markers(report_text)
    entry_dict_list = [dict(e) for e in loot_entries]
    active_ids = {str(e.get("id", "")).strip() for e in entry_dict_list if e.get("id")}

    missing: List[Dict[str, Any]] = []
    current: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []

    for entry in entry_dict_list:
        eid = str(entry.get("id", "")).strip()
        if not eid or eid not in markers:
            missing.append(entry)
        else:
            expected_hash = loot_content_hash(entry)
            if markers[eid] == expected_hash:
                current.append(entry)
            else:
                stale.append(entry)

    orphaned = tuple(sorted(mid for mid in markers.keys() if mid not in active_ids))

    return LootReportState(
        missing=tuple(missing),
        current=tuple(current),
        stale=tuple(stale),
        orphaned_ids=orphaned,
    )


@dataclass(frozen=True)
class AppendResult:
    """Result of an additive loot synchronization into a report."""

    text: str
    added_count: int
    used_fallback: bool
    fallback_categories: Tuple[str, ...]


def _find_h2_sections(
    text: str,
) -> List[Tuple[str, int, int]]:
    """Identifies all H2 (## ) section headings outside of markdown code fences.

    Returns a list of tuples: (heading_title_stripped, line_start_pos, content_start_pos).
    """
    lines = text.splitlines(keepends=True)
    in_code_fence = False
    sections: List[Tuple[str, int, int]] = []
    pos = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_fence = not in_code_fence
        elif not in_code_fence and line.startswith("## ") and not line.startswith("### "):
            title = line[3:].strip()
            content_start = pos + len(line)
            sections.append((title, pos, content_start))
        pos += len(line)

    return sections


def _get_category_heading_map(template: Optional[Any] = None) -> Dict[str, str]:
    """Resolves category_id -> expected H2 section heading from the active template or defaults."""
    heading_map: Dict[str, str] = {}
    if template and hasattr(template, "sections"):
        for sec in template.sections:
            if getattr(sec, "type", None) == "phase_section":
                cat_id = getattr(sec, "category_id", None) or "misc"
                cat_obj = next((c for c in CATEGORIES if c["id"] == cat_id), None)
                default_name = cat_obj["name"] if cat_obj else cat_id.capitalize()
                title = getattr(sec, "title", None) or default_name
                heading_map[cat_id] = title

    for cat in CATEGORIES:
        cid = cat["id"]
        if cid not in heading_map:
            heading_map[cid] = cat["name"]

    return heading_map


def _render_loot_block_text(entry: Mapping[str, Any], lang: str = "de") -> str:
    """Renders a single markdown loot entry block including its canonical marker."""
    from core.reporting.template_engine import _render_loot_entry_block

    lines = _render_loot_entry_block(dict(entry), lang=lang)
    return "\n".join(lines) + "\n"


def _match_section_for_category(
    cat_id: str,
    expected_title: str,
    section_bounds: List[Tuple[str, int, int]],
) -> Optional[Tuple[str, int, int]]:
    """Matches a category to an existing H2 section by title, substring, or standard keywords."""
    # 1. Exact match (case-insensitive)
    for title, c_start, s_end in section_bounds:
        if title.strip().lower() == expected_title.strip().lower():
            return (title, c_start, s_end)

    # 2. Substring match
    for title, c_start, s_end in section_bounds:
        t_clean = title.strip().lower()
        exp_clean = expected_title.strip().lower()
        if exp_clean in t_clean or t_clean in exp_clean:
            return (title, c_start, s_end)

    # 3. Semantic category keyword matching
    keywords: Dict[str, List[str]] = {
        "recon": ["recon", "enumeration", "discovery", "footprint", "information gathering"],
        "access": ["initial access", "exploitation", "access"],
        "privesc": ["privilege escalation", "privesc", "rechteausweitung"],
        "postex": ["post-exploitation", "lateral movement", "postex"],
        "scripts": ["scripts", "pocs", "custom scripts"],
        "misc": ["miscellaneous", "sonstiges", "misc"],
    }
    for kw in keywords.get(cat_id, [cat_id]):
        for title, c_start, s_end in section_bounds:
            if kw in title.strip().lower():
                return (title, c_start, s_end)

    return None


def append_missing_loot_to_text(
    report_text: str,
    loot_entries: Iterable[Mapping[str, Any]],
    template: Optional[Any] = None,
    language: str = "de",
) -> AppendResult:
    """Additively inserts missing loot entries into their matching phase sections.

    Guarantees:
    - Existing report text outside insertion slices is preserved 100% byte-for-byte.
    - Stale entries are NOT touched or duplicated.
    - Entries are inserted before phase note placeholders if present, otherwise at end of phase.
    - Unmatched categories are placed under a single '## Neu aus Loot ergänzt' fallback section at end.
    - Preserves exact reversed(phase_entries) rendering order matching regenerate().
    """
    state = classify_loot_report_state(report_text, loot_entries)
    if not state.missing:
        return AppendResult(
            text=report_text,
            added_count=0,
            used_fallback=False,
            fallback_categories=(),
        )

    # Group missing entries by category preserving source order
    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for entry in state.missing:
        cat = str(entry.get("category", "misc") or "misc")
        by_category.setdefault(cat, []).append(dict(entry))

    heading_map = _get_category_heading_map(template)
    sections = _find_h2_sections(report_text)

    # Build section range bounds: (title, start_pos, end_pos)
    section_bounds: List[Tuple[str, int, int]] = []
    for idx, (title, s_start, c_start) in enumerate(sections):
        s_end = sections[idx + 1][1] if idx + 1 < len(sections) else len(report_text)
        section_bounds.append((title, c_start, s_end))

    # Determine insertion points
    # We collect insertions as (insert_pos, replace_len, insertion_text)
    insertions: List[Tuple[int, int, str]] = []
    fallback_entries: List[Dict[str, Any]] = []
    fallback_categories: List[str] = []

    for cat_id, cat_entries in by_category.items():
        expected_title = heading_map.get(cat_id, cat_id.capitalize())
        matched_section = _match_section_for_category(cat_id, expected_title, section_bounds)

        if matched_section is None:
            fallback_entries.extend(cat_entries)
            if cat_id not in fallback_categories:
                fallback_categories.append(cat_id)
            continue

        sec_title, c_start, s_end = matched_section
        sec_text = report_text[c_start:s_end]

        # Render loot blocks in the canonical phase order (matching template_engine's reversed)
        rendered_blocks = "".join(_render_loot_block_text(e, lang=language) for e in reversed(cat_entries))

        # Check if empty placeholder notice is present to clean up
        empty_notice_de = "*Keine Einträge in dieser Phase.*"
        empty_notice_en = "*No entries captured for this phase.*"
        empty_notice_match = None
        for enotice in (empty_notice_de, empty_notice_en):
            if enotice in sec_text:
                empty_notice_match = enotice
                break

        # Check for notes placeholder
        notes_pos = -1
        for placeholder in (SECTION_NOTES_PLACEHOLDER_DE, SECTION_NOTES_PLACEHOLDER_EN):
            idx = sec_text.find(placeholder)
            if idx != -1:
                notes_pos = idx
                break

        if empty_notice_match is not None:
            # Replace empty notice with rendered blocks
            en_idx = sec_text.find(empty_notice_match)
            # Check for trailing newlines after notice
            en_len = len(empty_notice_match)
            while en_idx + en_len < len(sec_text) and sec_text[en_idx + en_len] in "\r\n":
                en_len += 1
            insert_pos = c_start + en_idx
            insertions.append((insert_pos, en_len, rendered_blocks))
        elif notes_pos != -1:
            # Insert right before notes placeholder
            insert_pos = c_start + notes_pos
            # Ensure proper newline spacing before placeholder
            insert_content = rendered_blocks
            if not insert_content.endswith("\n\n"):
                insert_content += "\n"
            insertions.append((insert_pos, 0, insert_content))
        else:
            # Insert at the end of the section
            insert_pos = s_end
            prefix = ""
            if insert_pos > 0 and not report_text[:insert_pos].endswith("\n\n"):
                prefix = "\n" if report_text[:insert_pos].endswith("\n") else "\n\n"
            insertions.append((insert_pos, 0, prefix + rendered_blocks))

    # Apply insertions from bottom to top so positions remain valid
    insertions.sort(key=lambda x: x[0], reverse=True)
    updated_text = report_text
    for insert_pos, replace_len, insert_content in insertions:
        updated_text = (
            updated_text[:insert_pos]
            + insert_content
            + updated_text[insert_pos + replace_len :]
        )

    # Handle fallback section if any categories were not matched
    used_fallback = False
    if fallback_entries:
        used_fallback = True
        is_de = (language or "").lower().startswith("de")
        fallback_title = FALLBACK_SECTION_TITLE_DE if is_de else FALLBACK_SECTION_TITLE_EN
        fallback_header = f"## {fallback_title}"
        existing_fb_sections = [
            s for s in _find_h2_sections(updated_text)
            if s[0] in (FALLBACK_SECTION_TITLE_DE, FALLBACK_SECTION_TITLE_EN, fallback_title)
        ]
        rendered_fb_blocks = "".join(_render_loot_block_text(e, lang=language) for e in reversed(fallback_entries))

        if existing_fb_sections:
            # Insert at the end of existing fallback section
            all_s = _find_h2_sections(updated_text)
            fb_idx = next(i for i, s in enumerate(all_s) if s[1] == existing_fb_sections[-1][1])
            fb_s_end = all_s[fb_idx + 1][1] if fb_idx + 1 < len(all_s) else len(updated_text)
            prefix = ""
            if not updated_text[:fb_s_end].endswith("\n\n"):
                prefix = "\n" if updated_text[:fb_s_end].endswith("\n") else "\n\n"
            updated_text = updated_text[:fb_s_end] + prefix + rendered_fb_blocks + updated_text[fb_s_end:]
        else:
            # Append new fallback section at document end
            prefix = "\n\n" if not updated_text.endswith("\n\n") else ""
            if not updated_text.endswith("\n") and updated_text:
                prefix = "\n\n"
            updated_text = updated_text + prefix + f"{fallback_header}\n\n" + rendered_fb_blocks

    return AppendResult(
        text=updated_text,
        added_count=len(state.missing),
        used_fallback=used_fallback,
        fallback_categories=tuple(fallback_categories),
    )


def _reconcile_pagebreaks(original_markdown: str, current_markdown: str) -> str:
    """Reconciles pagebreak markers dropped by Qt's QTextDocument.toMarkdown()."""
    original_pb_count = len(PAGEBREAK_REGEX.findall(original_markdown))
    if original_pb_count == 0:
        return current_markdown

    current_pb_count = len(PAGEBREAK_REGEX.findall(current_markdown))
    if current_pb_count >= original_pb_count:
        return current_markdown

    # Extract anchor lines following each page break in original markdown
    pb_anchors: List[str] = []
    for match in PAGEBREAK_REGEX.finditer(original_markdown):
        remaining = original_markdown[match.end():].lstrip("\r\n")
        first_line = remaining.split("\n", 1)[0].strip() if remaining else ""
        pb_anchors.append(first_line)

    result = current_markdown
    search_start = 0
    for anchor in pb_anchors:
        if anchor:
            idx = result.find(anchor, search_start)
            if idx != -1:
                # Check if a pagebreak marker already immediately precedes it
                preceding = result[:idx].rstrip()
                last_line = preceding.splitlines()[-1].strip() if preceding else ""
                if not PAGEBREAK_REGEX.fullmatch(last_line):
                    # Insert page break with clean spacing
                    if idx == 0:
                        insert_text = f"{PAGEBREAK_MARKER}\n\n"
                    elif result[:idx].endswith("\n\n"):
                        insert_text = f"{PAGEBREAK_MARKER}\n\n"
                    elif result[:idx].endswith("\n"):
                        insert_text = f"\n{PAGEBREAK_MARKER}\n\n"
                    else:
                        insert_text = f"\n\n{PAGEBREAK_MARKER}\n\n"

                    result = result[:idx] + insert_text + result[idx:]
                    search_start = idx + len(insert_text) + len(anchor)
                else:
                    search_start = idx + len(anchor)
        else:
            # Pagebreak was at the end of the document
            end_preceding = result.rstrip()
            end_last_line = end_preceding.splitlines()[-1].strip() if end_preceding else ""
            if not PAGEBREAK_REGEX.fullmatch(end_last_line):
                result = result.rstrip() + f"\n\n{PAGEBREAK_MARKER}\n"

    return result


def preserve_markers_in_preview_roundtrip(
    original_markdown: str, converted_markdown: str
) -> str:
    """Reconciles SpectreHUD loot markers and manual pagebreaks dropped by Qt's QTextDocument.toMarkdown().

    Identifies markers and their anchor headings from original_markdown, and inserts them
    before matching headings in converted_markdown if the marker was omitted.
    """
    if not original_markdown or not converted_markdown:
        return converted_markdown

    result_markdown = converted_markdown

    # 1. Reconcile loot markers
    original_markers = extract_report_markers(original_markdown)
    converted_markers = extract_report_markers(result_markdown)
    if original_markers and not set(original_markers.keys()).issubset(set(converted_markers.keys())):
        marker_anchors: List[Tuple[str, str, str]] = []  # (entry_id, content_hash, anchor_line_clean)
        for match in MARKER_REGEX.finditer(original_markdown):
            entry_id = match.group(1)
            content_hash = match.group(2).lower()
            # Find next non-empty line after the marker
            after_pos = match.end()
            remaining = original_markdown[after_pos:].lstrip("\r\n")
            first_line = remaining.split("\n", 1)[0].strip() if remaining else ""
            if first_line:
                marker_anchors.append((entry_id, content_hash, first_line))

        for entry_id, content_hash, anchor_line in marker_anchors:
            marker_str = format_loot_marker(entry_id, content_hash)
            if marker_str in result_markdown:
                continue

            # Look for anchor_line in result_markdown
            # Anchor is typically "### [Badge] [Title]" or "### [Title]"
            idx = result_markdown.find(anchor_line)
            if idx != -1:
                # Check if marker is already preceding it
                prefix = result_markdown[:idx]
                if marker_str not in prefix[-150:]:
                    # Insert marker right before the anchor line
                    result_markdown = result_markdown[:idx] + marker_str + "\n" + result_markdown[idx:]

    # 2. Reconcile manual page breaks
    result_markdown = _reconcile_pagebreaks(original_markdown, result_markdown)

    return result_markdown
