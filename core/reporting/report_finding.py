"""
Report Finding model.

Provides the ReportFindingItem dataclass with full Markdown parsing,
evidence attachment/detachment, and Markdown rendering.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from core.phases import normalize_phase_key
from core.reporting.charts import render_severity_badge
from core.reporting.evidence_markers import (
    parse_evidence_blocks,
    remove_evidence_block,
    replace_evidence_block,
)
from core.reporting.findings import (
    FINDING_END_RE,
    finding_end_marker,
    finding_start_marker,
)
from core.reporting.report_evidence import (
    CODE_BLOCK_RE,
    IMAGE_MD_RE,
    ReportEvidenceItem,
)
from core.reporting.report_metadata import _clean_md_val

_LOOT_MARKER_RE = re.compile(
    r"^<!-- spectre:loot:([A-Za-z0-9_-]+):([a-fA-F0-9]+) -->", re.MULTILINE
)
_SEVERITY_CLEAN_RE = re.compile(r"\[?(CRITICAL|HIGH|MEDIUM|LOW|INFO)\]?", re.IGNORECASE)


@dataclass
class ReportFindingItem:
    id: str
    title: str = ""
    severity: str = "medium"
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    status: str = "open"  # "open", "in_progress", "resolved", "accepted_risk"
    phase: str = "recon"
    targets: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    description: str = ""
    evidence_items: List[ReportEvidenceItem] = field(default_factory=list)
    recommendation: str = ""
    references: List[str] = field(default_factory=list)
    loot_marker: Optional[str] = None
    raw_extra: str = ""

    def __post_init__(self) -> None:
        self.phase = normalize_phase_key(self.phase)

    @classmethod
    def from_markdown(
        cls, markdown: str, entry_id: str, language: str = "de"
    ) -> "ReportFindingItem":
        loot_match = _LOOT_MARKER_RE.search(markdown)
        loot_marker = loot_match.group(0) if loot_match else None

        title = ""
        heading_match = re.search(r"^###\s+(.*?)$", markdown, re.MULTILINE)
        if heading_match:
            title = heading_match.group(1).strip()

        severity = "medium"
        sev_match = re.search(r"\*\*Severity:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if sev_match:
            clean_sev = _SEVERITY_CLEAN_RE.search(sev_match.group(1))
            if clean_sev:
                severity = clean_sev.group(1).lower()

        cvss_score = None
        score_match = re.search(
            r"\*\*CVSS Score:\*\*\s*`?([0-9]+(?:\.[0-9]+)?)`?",
            markdown,
            re.IGNORECASE,
        )
        if score_match:
            candidate = float(score_match.group(1))
            if 0.0 <= candidate <= 10.0:
                cvss_score = candidate

        vector_match = re.search(
            r"\*\*CVSS Vector:\*\*\s*`([^`]+)`",
            markdown,
            re.IGNORECASE,
        )
        cvss_vector = vector_match.group(1).strip() if vector_match else None

        targets: List[str] = []
        target_match = re.search(r"\*\*Target:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if target_match:
            val = _clean_md_val(target_match.group(1))
            if val:
                targets = [t.strip() for t in val.split(",") if t.strip()]

        phase = "recon"
        phase_match = re.search(r"\*\*Phase:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if phase_match:
            phase = normalize_phase_key(_clean_md_val(phase_match.group(1)))

        timestamp = None
        time_match = re.search(
            r"\*\*(?:Observed|Beobachtet):\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE
        )
        if time_match:
            timestamp = _clean_md_val(time_match.group(1))

        status = "open"
        status_match = re.search(r"\*\*Status:\*\*\s*(.*?)(?:  |$)", markdown, re.MULTILINE)
        if status_match:
            raw_status = _clean_md_val(status_match.group(1)).lower()
            if raw_status in ("offen", "open"):
                status = "open"
            elif raw_status in ("behoben", "resolved", "closed"):
                status = "resolved"
            elif raw_status in ("in arbeit", "in_progress", "in progress", "progress"):
                status = "in_progress"
            elif raw_status in ("akzeptiert", "accepted_risk", "accepted risk", "accepted"):
                status = "accepted_risk"

        # Split description and recommendation sections
        desc_header = re.search(
            r"^####\s+(?:Beschreibung|Description)\s*$", markdown, re.MULTILINE | re.IGNORECASE
        )
        rec_header = re.search(
            r"^####\s+(?:Empfehlung|Recommendation)\s*$", markdown, re.MULTILINE | re.IGNORECASE
        )
        ref_header = re.search(
            r"^####\s+(?:Referenzen|References)\s*$", markdown, re.MULTILINE | re.IGNORECASE
        )

        description = ""
        recommendation = ""
        references: List[str] = []

        if desc_header:
            desc_start = desc_header.end()
            desc_end = len(markdown)
            for next_h in (rec_header, ref_header):
                if next_h and next_h.start() > desc_start:
                    desc_end = min(desc_end, next_h.start())
            desc_text = markdown[desc_start:desc_end]
            end_m = FINDING_END_RE.search(desc_text)
            if end_m:
                desc_text = desc_text[: end_m.start()]
            description = desc_text.strip()

        if rec_header:
            rec_start = rec_header.end()
            rec_end = len(markdown)
            if ref_header and ref_header.start() > rec_start:
                rec_end = ref_header.start()
            rec_text = markdown[rec_start:rec_end]
            end_m = FINDING_END_RE.search(rec_text)
            if end_m:
                rec_text = rec_text[: end_m.start()]
            recommendation = rec_text.strip()

        if ref_header:
            ref_block = markdown[ref_header.end() :]
            end_m = FINDING_END_RE.search(ref_block)
            if end_m:
                ref_block = ref_block[: end_m.start()]
            for line in ref_block.strip().splitlines():
                line_str = line.strip().lstrip("-* ").strip()
                if line_str and not line_str.startswith("<!--"):
                    references.append(line_str)

        # Versioned envelopes preserve exact evidence identity and provenance.
        # Legacy reports still use the visible image/code heuristics below.
        evidence_items: List[ReportEvidenceItem] = []
        ev_idx = 1
        evidence_blocks = parse_evidence_blocks(description)
        for block in evidence_blocks:
            metadata = block.metadata
            evidence_type = metadata["type"]
            content = block.body.strip()
            caption = metadata["caption"]
            language_value = metadata["language"]
            if evidence_type == "screenshot":
                image_match = IMAGE_MD_RE.search(block.body)
                if image_match:
                    caption = caption or image_match.group(1)
                    content = image_match.group(2)
            elif evidence_type in ("terminal", "credential", "code"):
                code_match = CODE_BLOCK_RE.search(block.body)
                if code_match:
                    language_value = language_value or code_match.group(2)
                    content = code_match.group(3)
            evidence_items.append(
                ReportEvidenceItem(
                    id=metadata["id"],
                    type=evidence_type,
                    caption=caption,
                    content=content,
                    source_loot_id=metadata["source_loot_id"] or None,
                    language=language_value,
                )
            )

        legacy_description = list(description)
        for block in evidence_blocks:
            for index in range(block.start, block.end):
                if legacy_description[index] not in "\r\n":
                    legacy_description[index] = " "
        legacy_markdown = "".join(legacy_description)

        for img_match in IMAGE_MD_RE.finditer(legacy_markdown):
            evidence_items.append(
                ReportEvidenceItem(
                    id=f"{entry_id}-img-{ev_idx}",
                    type="screenshot",
                    caption=img_match.group(1),
                    content=img_match.group(2),
                    source_loot_id=entry_id,
                )
            )
            ev_idx += 1

        for code_match in CODE_BLOCK_RE.finditer(legacy_markdown):
            lang = (code_match.group(2) or "").strip().lower()
            ev_type = (
                "terminal"
                if lang in ("bash", "sh", "terminal", "console")
                else (
                    "credential"
                    if lang in ("credential", "credentials", "loot", "creds")
                    else "code"
                )
            )
            evidence_items.append(
                ReportEvidenceItem(
                    id=f"{entry_id}-code-{ev_idx}",
                    type=ev_type,
                    content=code_match.group(3),
                    source_loot_id=entry_id,
                )
            )
            ev_idx += 1

        return cls(
            id=entry_id,
            title=title,
            severity=severity,
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            status=status,
            phase=phase,
            targets=targets,
            timestamp=timestamp,
            description=description,
            evidence_items=evidence_items,
            recommendation=recommendation,
            references=references,
            loot_marker=loot_marker,
        )

    def attach_evidence(
        self,
        item: ReportEvidenceItem,
        insert_into_description: bool = True,
    ) -> None:
        """Attaches an evidence item and optionally appends its Markdown to the description."""
        existing_idx = next((i for i, ev in enumerate(self.evidence_items) if ev.id == item.id), -1)
        if existing_idx >= 0:
            self.evidence_items[existing_idx] = item
        else:
            self.evidence_items.append(item)

        if insert_into_description:
            md = item.to_persisted_markdown()
            clean_content = item.content.strip()
            if clean_content and clean_content not in self.description:
                if self.description and not self.description.endswith("\n\n"):
                    if not self.description.endswith("\n"):
                        self.description += "\n\n"
                    else:
                        self.description += "\n"
                self.description += f"{md}\n"

    def detach_evidence(
        self,
        evidence_id: str,
        remove_from_description: bool = True,
    ) -> Optional[ReportEvidenceItem]:
        """Removes an evidence item and optionally strips its Markdown from the description."""
        found_idx = next(
            (i for i, ev in enumerate(self.evidence_items) if ev.id == evidence_id), -1
        )
        if found_idx == -1:
            return None
        removed = self.evidence_items.pop(found_idx)
        if remove_from_description:
            self.description, removed_block = remove_evidence_block(
                self.description,
                evidence_id,
            )
            if removed_block:
                return removed
        if remove_from_description and removed.content:
            if removed.type == "screenshot":
                pattern = rf"!\[.*?\]\({re.escape(removed.content)}\)\r?\n?"
                self.description = re.sub(pattern, "", self.description).strip()
            else:
                block_pattern = rf"```[a-zA-Z0-9_-]*\r?\n{re.escape(removed.content)}\r?\n```\r?\n?"
                self.description = re.sub(block_pattern, "", self.description).strip()
        return removed

    def update_evidence(
        self,
        evidence_id: str,
        caption: Optional[str] = None,
        content: Optional[str] = None,
    ) -> bool:
        """Updates caption or content for an evidence item, synchronizing Markdown in description."""
        found = next((ev for ev in self.evidence_items if ev.id == evidence_id), None)
        if not found:
            return False

        old_caption = found.caption
        old_content = found.content

        if caption is not None:
            found.caption = caption
        if content is not None:
            found.content = content

        replacement = found.to_persisted_markdown()
        self.description, replaced_block = replace_evidence_block(
            self.description,
            evidence_id,
            replacement,
        )
        if replaced_block:
            return True

        if found.type == "screenshot":
            old_tag = f"![{old_caption}]({old_content})"
            new_tag = f"![{found.caption}]({found.content})"
            if old_tag in self.description:
                self.description = self.description.replace(old_tag, new_tag)
            elif old_content in self.description:
                pattern = rf"!\[.*?\]\({re.escape(old_content)}\)"
                self.description = re.sub(pattern, new_tag, self.description)
        elif old_content and old_content in self.description:
            self.description = self.description.replace(old_content, found.content)

        return True

    def to_markdown(self, language: str = "de", include_phase: bool = False) -> str:
        lines = [finding_start_marker(self.id)]
        if self.loot_marker:
            lines.append(self.loot_marker)

        title = self.title or ("Unbenannter Eintrag" if language == "de" else "Unnamed Entry")
        lines.append(f"### {title}")
        lines.append("")

        meta_parts = [f"**Severity:** {render_severity_badge(self.severity, include_emoji=False)}"]
        if self.cvss_score is not None:
            meta_parts.append(f"**CVSS Score:** `{self.cvss_score:.1f}`")
        if self.cvss_vector:
            meta_parts.append(f"**CVSS Vector:** `{self.cvss_vector}`")
        if self.targets:
            meta_parts.append(f"**Target:** `{', '.join(self.targets)}`")
        if include_phase and self.phase:
            phase_label = "**Phase:**"
            meta_parts.append(f"{phase_label} {self.phase.capitalize()}")
        if self.timestamp:
            time_label = "**Beobachtet:**" if language == "de" else "**Observed:**"
            meta_parts.append(f"{time_label} `{self.timestamp}`")

        status_text = (
            "Offen"
            if self.status == "open"
            else (
                "Behoben"
                if self.status == "resolved"
                else ("In Arbeit" if self.status == "in_progress" else "Akzeptiert")
            )
        )
        if language != "de":
            status_text = (
                "Open"
                if self.status == "open"
                else (
                    "Resolved"
                    if self.status == "resolved"
                    else ("In Progress" if self.status == "in_progress" else "Accepted Risk")
                )
            )
        meta_parts.append(f"**Status:** {status_text}")

        lines.append("  \n".join(meta_parts))
        lines.append("")

        if self.description:
            lines.append("#### Beschreibung" if language == "de" else "#### Description")
            lines.append("")
            lines.append(self.description)
            lines.append("")

        if self.recommendation:
            lines.append("#### Empfehlung" if language == "de" else "#### Recommendation")
            lines.append("")
            lines.append(self.recommendation)
            lines.append("")

        if self.references:
            lines.append("#### Referenzen" if language == "de" else "#### References")
            lines.append("")
            for ref in self.references:
                lines.append(f"- {ref}")
            lines.append("")

        if self.raw_extra:
            lines.append(self.raw_extra)
            lines.append("")

        lines.append(finding_end_marker(self.id))
        return "\n".join(lines)
