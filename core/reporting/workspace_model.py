"""
SpectreHUD Report Workspace Data Model.

Provides pure-Python, headless, structured representations of pentest/CTF
reports (metadata, findings, evidence, narrative sections, and appendices)
with lossless bidirectional Markdown synchronization.

Individual section models have been extracted into dedicated modules;
this module retains the orchestrating ReportWorkspaceDocument,
the lightweight ReportNarrativeSection container, and re-exports
all public symbols for backward compatibility.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.phases import normalize_phase_key
from core.reporting.findings import (
    FINDING_END_RE,
    FINDING_START_RE,
)
from core.reporting.section_markers import (
    segment_report_markdown,
    wrap_section_markdown,
)

# --- Re-exports from extracted modules (backward compatibility) -----------
from core.reporting.report_metadata import ReportMetadata  # noqa: F401
from core.reporting.report_evidence import ReportEvidenceItem  # noqa: F401
from core.reporting.report_finding import ReportFindingItem  # noqa: F401
from core.reporting.report_appendix import ReportAppendix  # noqa: F401
from core.reporting.report_executive_summary import (  # noqa: F401
    PHASE_NAMES_DE,
    ReportExecutiveSummary,
)
from core.reporting.report_remediation import (  # noqa: F401
    SEVERITY_ORDER,
    STATUS_LABELS_DE,
    STATUS_LABELS_EN,
    ReportRemediationPlan,
)
from core.reporting.report_attack_path import (  # noqa: F401
    AttackPathStep,
    ReportAttackPath,
)
from core.reporting.report_scope import (  # noqa: F401
    ScopeExclusionItem,
    ScopeTargetItem,
    normalize_environment,
    normalize_target_type,
    ReportScopeMethodology,
)

_LOOT_MARKER_RE = re.compile(
    r"^<!-- spectre:loot:([A-Za-z0-9_-]+):([a-fA-F0-9]+) -->", re.MULTILINE
)


@dataclass
class ReportNarrativeSection:
    identity: str
    section_type: str
    title: str = ""
    content: str = ""
    options: Dict[str, Any] = field(default_factory=dict)
    page_break_before: bool = False

    def to_markdown(self) -> str:
        text = self.content.strip()
        if self.page_break_before:
            text = f"<!-- spectre:pagebreak -->\n\n{text}"
        return wrap_section_markdown(text, self.identity)


def _is_meaningful_unstructured_block(markdown: str, branding_footer: str = "") -> bool:
    stripped = markdown.strip()
    if not stripped:
        return False
    if branding_footer and stripped == branding_footer:
        return False
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if all(line in ("---", "***", "___") for line in lines):
        return False
    return True


@dataclass
class ReportWorkspaceDocument:
    metadata: ReportMetadata = field(default_factory=ReportMetadata)
    narratives: List[ReportNarrativeSection] = field(default_factory=list)
    findings: List[ReportFindingItem] = field(default_factory=list)
    appendix: Optional[ReportAppendix] = None
    language: str = "de"
    footer: str = ""
    unstructured_blocks: List[str] = field(default_factory=list)

    # --- Finding Operations ---

    def add_finding(self, finding: ReportFindingItem) -> None:
        self.findings.append(finding)

    def remove_finding(self, finding_id: str) -> bool:
        initial_len = len(self.findings)
        self.findings = [f for f in self.findings if f.id != finding_id]
        return len(self.findings) < initial_len

    def get_finding(self, finding_id: str) -> Optional[ReportFindingItem]:
        for f in self.findings:
            if f.id == finding_id:
                return f
        return None

    def update_finding(self, finding: ReportFindingItem) -> bool:
        for idx, f in enumerate(self.findings):
            if f.id == finding.id:
                self.findings[idx] = finding
                return True
        return False

    def reorder_findings(self, ordered_ids: List[str]) -> None:
        id_map = {f.id: f for f in self.findings}
        reordered: List[ReportFindingItem] = []
        for fid in ordered_ids:
            if fid in id_map:
                reordered.append(id_map[fid])
        # Append any unmentioned findings
        for f in self.findings:
            if f.id not in ordered_ids:
                reordered.append(f)
        self.findings = reordered

    def get_findings_by_severity(self) -> Dict[str, List[ReportFindingItem]]:
        buckets: Dict[str, List[ReportFindingItem]] = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": [],
        }
        for f in self.findings:
            sev = f.severity.lower()
            if sev in buckets:
                buckets[sev].append(f)
            else:
                buckets.setdefault("info", []).append(f)
        return buckets

    def get_findings_by_phase(self) -> Dict[str, List[ReportFindingItem]]:
        buckets: Dict[str, List[ReportFindingItem]] = {}
        for f in self.findings:
            phase = normalize_phase_key(f.phase)
            buckets.setdefault(phase, []).append(f)
        return buckets

    # --- Bidirectional Markdown Synchronisation ---

    @classmethod
    def from_markdown(
        cls, markdown_text: str, default_language: str = "de"
    ) -> "ReportWorkspaceDocument":
        if not markdown_text:
            return cls(language=default_language)

        # Detect language
        is_de = (
            "auftraggeber" in markdown_text.lower()
            or "beschreibung" in markdown_text.lower()
            or "erstellt mit" in markdown_text.lower()
        )
        language = (
            "de"
            if is_de
            else (
                "en"
                if "client" in markdown_text.lower() or "description" in markdown_text.lower()
                else default_language
            )
        )

        segments = segment_report_markdown(markdown_text)
        metadata = ReportMetadata()
        narratives: List[ReportNarrativeSection] = []
        findings: List[ReportFindingItem] = []
        appendix: Optional[ReportAppendix] = None
        unstructured: List[str] = []
        footer = ""

        # Check for legacy generated branding footer and strip it
        footer_match = re.search(
            r"\n*---\s*\n+_(?:Generated with|Erstellt mit) "
            r"SpectreHUD Pentest & CTF Companion\b[^_\n]*_\s*$",
            markdown_text,
            re.IGNORECASE,
        )
        branding_footer = footer_match.group(0).strip() if footer_match else ""

        for seg in segments:
            if seg.section_type == "header_metadata":
                metadata = ReportMetadata.from_markdown_table(seg.markdown)
            elif seg.section_type in ("finding_section", "phase_section"):
                # Parse all finding items inside this section
                cursor = 0
                while start := FINDING_START_RE.search(seg.markdown, cursor):
                    entry_id = start.group(1)
                    end = next(
                        (
                            m
                            for m in FINDING_END_RE.finditer(seg.markdown, start.end())
                            if m.group(1) == entry_id
                        ),
                        None,
                    )
                    if end is None:
                        break
                    block = seg.markdown[start.start() : end.end()]
                    finding = ReportFindingItem.from_markdown(block, entry_id, language=language)
                    if seg.category_id:
                        finding.phase = normalize_phase_key(seg.category_id)
                    findings.append(finding)
                    cursor = end.end()

                # Clean finding blocks from section to retain narrative notes/custom text
                clean_sec_md = FINDING_START_RE.sub("", seg.markdown)
                clean_sec_md = FINDING_END_RE.sub("", clean_sec_md)
                clean_sec_md = _LOOT_MARKER_RE.sub("", clean_sec_md)
                # Keep narrative section container
                sec_title = ""
                h2 = re.search(r"^##\s+(.*?)$", seg.markdown, re.MULTILINE)
                if h2:
                    sec_title = h2.group(1).strip()
                narratives.append(
                    ReportNarrativeSection(
                        identity=seg.identity or seg.section_type,
                        section_type=seg.section_type,
                        title=sec_title,
                        content=clean_sec_md.strip(),
                    )
                )
            elif seg.section_type == "appendix":
                appendix = ReportAppendix.from_markdown(seg.markdown, language=language)
                narratives.append(
                    ReportNarrativeSection(
                        identity=seg.identity or "appendix",
                        section_type="appendix",
                        title=appendix.title or ("Appendix" if language != "de" else "Anhang"),
                        content=seg.markdown,
                    )
                )
            elif seg.is_structured:
                sec_title = ""
                h2 = re.search(r"^##\s+(.*?)$", seg.markdown, re.MULTILINE)
                if h2:
                    sec_title = h2.group(1).strip()
                narratives.append(
                    ReportNarrativeSection(
                        identity=seg.identity or seg.section_type,
                        section_type=seg.section_type,
                        title=sec_title,
                        content=seg.markdown,
                    )
                )
            else:
                if _is_meaningful_unstructured_block(seg.markdown, branding_footer):
                    unstructured.append(seg.markdown.strip())

        return cls(
            metadata=metadata,
            narratives=narratives,
            findings=findings,
            appendix=appendix,
            language=language,
            footer=footer,
            unstructured_blocks=unstructured,
        )

    def get_executive_summary(self) -> ReportExecutiveSummary:
        narr = next(
            (
                n
                for n in self.narratives
                if n.identity == "executive_summary" or n.section_type == "executive_summary"
            ),
            None,
        )
        content = narr.content if narr else ""
        summary = ReportExecutiveSummary.from_markdown(content, language=self.language)
        if narr and narr.title:
            summary.title = narr.title
        return summary

    def set_executive_summary(self, summary: ReportExecutiveSummary) -> None:
        md = summary.to_markdown(self.findings, language=self.language)
        for n in self.narratives:
            if n.identity == "executive_summary" or n.section_type == "executive_summary":
                n.title = summary.title
                n.content = md
                return
        self.narratives.insert(
            0,
            ReportNarrativeSection(
                identity="executive_summary",
                section_type="executive_summary",
                title=summary.title,
                content=md,
            ),
        )

    def get_remediation_plan(self) -> ReportRemediationPlan:
        narrative = next(
            (
                n
                for n in self.narratives
                if n.identity == "remediation_table" or n.section_type == "remediation_table"
            ),
            None,
        )
        content = narrative.content if narrative else ""
        return ReportRemediationPlan.from_markdown(content, language=self.language)

    def set_remediation_plan(self, plan: ReportRemediationPlan) -> None:
        md = plan.to_markdown(self.findings, language=self.language)
        for n in self.narratives:
            if n.identity == "remediation_table" or n.section_type == "remediation_table":
                n.title = plan.title
                n.content = md
                return
        self.narratives.append(
            ReportNarrativeSection(
                identity="remediation_table",
                section_type="remediation_table",
                title=plan.title,
                content=md,
            ),
        )

    def get_attack_path(self) -> ReportAttackPath:
        narrative = next(
            (
                n
                for n in self.narratives
                if n.identity == "attack_path"
                or n.section_type in ("attack_path", "attack_narrative")
            ),
            None,
        )
        content = narrative.content if narrative else ""
        return ReportAttackPath.from_markdown(content, language=self.language)

    def set_attack_path(self, path: ReportAttackPath) -> None:
        md = path.to_markdown(self.findings, language=self.language)
        for n in self.narratives:
            if n.identity == "attack_path" or n.section_type in ("attack_path", "attack_narrative"):
                n.title = path.title
                n.content = md
                return
        self.narratives.append(
            ReportNarrativeSection(
                identity="attack_path",
                section_type="attack_path",
                title=path.title,
                content=md,
            ),
        )

    def get_scope_methodology(self) -> ReportScopeMethodology:
        narrative = next(
            (
                n
                for n in self.narratives
                if n.identity == "scope_limitations"
                or n.section_type in ("scope_limitations", "scope")
            ),
            None,
        )
        content = narrative.content if narrative else ""
        return ReportScopeMethodology.from_markdown(content, language=self.language)

    def set_scope_methodology(self, scope: ReportScopeMethodology) -> None:
        md = scope.to_markdown(language=self.language)
        for n in self.narratives:
            if n.identity == "scope_limitations" or n.section_type in (
                "scope_limitations",
                "scope",
            ):
                n.title = scope.title
                n.content = md
                return
        self.narratives.append(
            ReportNarrativeSection(
                identity="scope_limitations",
                section_type="scope_limitations",
                title=scope.title,
                content=md,
            ),
        )

    def get_appendix(self) -> ReportAppendix:
        narrative = next(
            (
                n
                for n in self.narratives
                if n.identity == "appendix" or n.section_type == "appendix"
            ),
            None,
        )
        content = narrative.content if narrative else ""
        if self.appendix is not None:
            if not self.appendix.title and narrative and narrative.title:
                self.appendix.title = narrative.title
            return self.appendix
        app = ReportAppendix.from_markdown(content, language=self.language)
        if narrative and narrative.title:
            app.title = narrative.title
        self.appendix = app
        return app

    def set_appendix(self, appendix: ReportAppendix) -> None:
        self.appendix = appendix
        md = appendix.to_markdown(title=appendix.title, language=self.language)
        for n in self.narratives:
            if n.identity == "appendix" or n.section_type == "appendix":
                n.title = appendix.title
                n.content = md
                return
        self.narratives.append(
            ReportNarrativeSection(
                identity="appendix",
                section_type="appendix",
                title=appendix.title,
                content=md,
            ),
        )

    def _render_executive_summary_content(self, narrative: ReportNarrativeSection) -> str:
        """Regenerates findings matrix inside executive summary while preserving highlights and intro."""
        summary = ReportExecutiveSummary.from_markdown(narrative.content, language=self.language)
        if narrative.title:
            summary.title = narrative.title
        return summary.to_markdown(self.findings, language=self.language)

    def _render_remediation_table_content(self, narrative: ReportNarrativeSection) -> str:
        """Regenerates remediation table rows from current findings."""
        plan = ReportRemediationPlan.from_markdown(narrative.content, language=self.language)
        if narrative.title:
            plan.title = narrative.title
        return plan.to_markdown(self.findings, language=self.language)

    def _render_attack_path_content(self, narrative: ReportNarrativeSection) -> str:
        """Regenerates attack path content."""
        path = ReportAttackPath.from_markdown(narrative.content, language=self.language)
        if narrative.title:
            path.title = narrative.title
        return path.to_markdown(self.findings, language=self.language)

    def _render_scope_methodology_content(self, narrative: ReportNarrativeSection) -> str:
        """Regenerates scope and methodology content."""
        scope = ReportScopeMethodology.from_markdown(narrative.content, language=self.language)
        if narrative.title:
            scope.title = narrative.title
        return scope.to_markdown(language=self.language)

    def to_markdown(self, regenerate_matrices: bool = True) -> str:
        parts: List[str] = []

        # 1. Header Metadata
        header_text = self.metadata.to_markdown_table(language=self.language)
        parts.append(wrap_section_markdown(header_text.strip(), "header_metadata"))

        # Group findings by phase
        findings_by_phase = self.get_findings_by_phase()
        phase_findings_emitted: set[str] = set()

        # 2. Iterate narratives in defined order
        for narr in self.narratives:
            if narr.section_type == "header_metadata":
                continue  # already handled

            if narr.section_type == "executive_summary":
                content = (
                    self._render_executive_summary_content(narr)
                    if regenerate_matrices
                    else narr.content
                )
                parts.append(wrap_section_markdown(content.strip(), narr.identity))

            elif narr.section_type == "remediation_table":
                content = (
                    self._render_remediation_table_content(narr)
                    if regenerate_matrices
                    else narr.content
                )
                parts.append(wrap_section_markdown(content.strip(), narr.identity))

            elif narr.section_type in ("attack_path", "attack_narrative"):
                content = (
                    self._render_attack_path_content(narr) if regenerate_matrices else narr.content
                )
                parts.append(wrap_section_markdown(content.strip(), narr.identity))

            elif narr.identity == "scope_limitations" or narr.section_type in (
                "scope_limitations",
                "scope",
            ):
                content = (
                    self._render_scope_methodology_content(narr)
                    if regenerate_matrices
                    else narr.content
                )
                parts.append(wrap_section_markdown(content.strip(), narr.identity))

            elif narr.section_type == "finding_section":
                # Unified findings section: render all findings
                sec_lines = [f"## {narr.title or 'Technische Findings'}", ""]
                for f in self.findings:
                    sec_lines.append(f.to_markdown(language=self.language, include_phase=True))
                    sec_lines.append("")
                phase_findings_emitted.update(f.id for f in self.findings)
                parts.append(wrap_section_markdown("\n".join(sec_lines).strip(), narr.identity))

            elif narr.section_type == "phase_section":
                cat_id = narr.identity.split(":")[-1] if ":" in narr.identity else "misc"
                phase_findings = findings_by_phase.get(cat_id, [])
                sec_lines = [f"## {narr.title or cat_id.capitalize()}", ""]
                if not phase_findings:
                    no_entries = (
                        "*Keine Einträge in dieser Phase.*"
                        if self.language == "de"
                        else "*No entries captured for this phase.*"
                    )
                    sec_lines.append(no_entries)
                    sec_lines.append("")
                else:
                    for f in phase_findings:
                        sec_lines.append(f.to_markdown(language=self.language, include_phase=False))
                        sec_lines.append("")
                        phase_findings_emitted.add(f.id)

                # Keep any user notes from narrative
                notes_lines = [
                    line
                    for line in narr.content.splitlines()
                    if not line.strip().startswith("## ")
                    and not line.strip().startswith("*Keine Einträge")
                ]
                if notes_lines:
                    sec_lines.append("\n".join(notes_lines).strip())
                    sec_lines.append("")

                parts.append(wrap_section_markdown("\n".join(sec_lines).strip(), narr.identity))

            elif narr.section_type == "appendix":
                app = self.get_appendix()
                app_content = app.to_markdown(title=narr.title or app.title, language=self.language)
                parts.append(wrap_section_markdown(app_content.strip(), narr.identity))

            else:
                # Custom / Scope / Attack path narrative
                parts.append(wrap_section_markdown(narr.content.strip(), narr.identity))

        # Check if there are unassigned findings not yet emitted
        remaining_findings = [f for f in self.findings if f.id not in phase_findings_emitted]
        if remaining_findings and not any(
            n.section_type == "finding_section" for n in self.narratives
        ):
            extra_lines = ["## Technische Findings", ""]
            for f in remaining_findings:
                extra_lines.append(f.to_markdown(language=self.language, include_phase=True))
                extra_lines.append("")
            parts.append(wrap_section_markdown("\n".join(extra_lines).strip(), "finding_section"))

        # Append unstructured preamble/extra blocks if any
        for unstr in self.unstructured_blocks:
            if _is_meaningful_unstructured_block(unstr):
                parts.append(unstr.strip())

        body = "\n\n---\n\n".join(p for p in parts if p)

        # Footer
        footer = self.footer
        if footer:
            if not footer.startswith("\n"):
                footer = f"\n\n---\n\n{footer}"
            return body + footer

        return body
