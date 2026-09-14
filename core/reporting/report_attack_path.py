"""
Report Attack Path model.

Provides the AttackPathStep and ReportAttackPath dataclasses with
Markdown parsing and rendering of the attack chain / assessment narrative.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.phases import get_phase, normalize_phase_key
from core.reporting.report_finding import ReportFindingItem

PHASE_NAMES_DE: Dict[str, str] = {
    "recon": "Aufklärung & Enumeration",
    "access": "Initialer Zugriff & Exploitation",
    "privesc": "Rechteausweitung (PrivEsc)",
    "postex": "Post-Exploitation & Lateral Movement",
    "scripts": "Eigene Skripte & PoCs",
    "misc": "Sonstiges",
}


@dataclass
class AttackPathStep:
    """Individual step in the attack chain / timeline."""

    step_number: int = 1
    phase: str = "recon"
    title: str = ""
    description: str = ""
    finding_id: Optional[str] = None


@dataclass
class ReportAttackPath:
    """Structured representation of the Attack Path / Assessment Narrative section."""

    title: str = "Angriffspfad / Assessment-Verlauf"
    narrative_intro: str = ""
    steps: List[AttackPathStep] = field(default_factory=list)

    @classmethod
    def from_markdown(cls, markdown: str, language: str = "de") -> "ReportAttackPath":
        default_title = (
            "Angriffspfad / Assessment-Verlauf"
            if language == "de"
            else "Attack Path / Assessment Narrative"
        )
        if not markdown:
            return cls(title=default_title)

        title = default_title
        h2 = re.search(r"^##\s+(.*?)$", markdown, re.MULTILINE)
        if h2:
            title = h2.group(1).strip()

        # Split intro from steps
        first_step = re.search(r"^[ \t]*(\d+)\.\s+", markdown, re.MULTILINE)
        first_h3 = re.search(r"^###\s+", markdown, re.MULTILINE)
        split_pos = None
        if first_h3 and (not first_step or first_h3.start() < first_step.start()):
            split_pos = first_h3.start()
        elif first_step:
            split_pos = first_step.start()

        narrative_intro = ""
        if split_pos is not None:
            start_pos = h2.end() if h2 else 0
            narrative_intro = markdown[start_pos:split_pos].strip()
        elif h2:
            narrative_intro = markdown[h2.end():].strip()

        # Parse steps: handles both detailed bullets and one-line legacy bullets
        steps: List[AttackPathStep] = []
        step_matches = list(
            re.finditer(
                r"^[ \t]*(\d+)\.\s+(.*?)(?=(?:\n[ \t]*\d+\.|\n[ \t]*##|\Z))",
                markdown,
                re.DOTALL | re.MULTILINE,
            )
        )

        for match in step_matches:
            num_str = match.group(1)
            step_body = match.group(2).strip()
            lines = step_body.splitlines()
            if not lines:
                continue

            first_line = lines[0].strip()
            m_header = re.search(r"\*\*(.*?)\*\*[:—\-]?\s*(.*)$", first_line)
            if m_header:
                raw_phase = m_header.group(1).strip()
                step_title = m_header.group(2).strip()
            else:
                raw_phase = "recon"
                step_title = first_line

            step_num = int(num_str) if num_str.isdigit() else (len(steps) + 1)
            norm_phase = normalize_phase_key(raw_phase)
            desc = ""
            fid = None

            for line in lines[1:]:
                clean_line = line.strip()
                m_desc = re.search(
                    r"[-*]\s*[*_]*(?:Beschreibung|Description)[:*_ \t]*\s*(.*)$",
                    clean_line,
                    re.IGNORECASE,
                )
                if m_desc:
                    desc = m_desc.group(1).strip().strip("*_").strip()
                m_find = re.search(
                    r"[-*]\s*[*_]*(?:Finding|Schwachstelle)[:*_ \t]*\s*(.*)$",
                    clean_line,
                    re.IGNORECASE,
                )
                if m_find:
                    raw_val = m_find.group(1).strip().strip("*_").strip()
                    m_id = re.search(r"<!--\s*finding:(.*?)\s*-->", raw_val)
                    if m_id:
                        fid = m_id.group(1).strip()
                    else:
                        fid = raw_val

            steps.append(
                AttackPathStep(
                    step_number=step_num,
                    phase=norm_phase,
                    title=step_title,
                    description=desc,
                    finding_id=fid,
                )
            )

        return cls(title=title, narrative_intro=narrative_intro, steps=steps)

    def to_markdown(
        self,
        findings: Optional[List[ReportFindingItem]] = None,
        language: str = "de",
    ) -> str:
        default_title = (
            "Angriffspfad / Assessment-Verlauf"
            if language == "de"
            else "Attack Path / Assessment Narrative"
        )
        sec_title = self.title or default_title
        lines: List[str] = [f"## {sec_title}", ""]

        if self.narrative_intro.strip():
            lines.append(self.narrative_intro.strip())
            lines.append("")

        if not self.steps:
            empty_msg = (
                "*Kein dokumentierter Angriffspfad vorhanden.*"
                if language == "de"
                else "*No documented attack path is available.*"
            )
            lines.append(empty_msg)
            lines.append("")
            return "\n".join(lines).strip()

        chain_title = "### Angriffskette" if language == "de" else "### Attack Chain"
        lines.append(chain_title)
        lines.append("")

        findings_map = {f.id: f for f in (findings or [])}

        for idx, s in enumerate(self.steps, start=1):
            p_obj = get_phase(s.phase)
            ph_name = PHASE_NAMES_DE.get(p_obj.key, p_obj.long) if language == "de" else p_obj.long
            step_header = f"{idx}. **{ph_name}**: {s.title or p_obj.short}"
            lines.append(step_header)
            if s.description.strip():
                lbl_desc = "Beschreibung" if language == "de" else "Description"
                lines.append(f"   - *{lbl_desc}:* {s.description.strip()}")
            if s.finding_id:
                linked_f = findings_map.get(s.finding_id)
                f_title = linked_f.title if linked_f else s.finding_id
                lbl_find = "Schwachstelle" if language == "de" else "Finding"
                lines.append(f"   - *{lbl_find}:* {f_title} <!-- finding:{s.finding_id} -->")

        lines.append("")
        return "\n".join(lines).strip()
