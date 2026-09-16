"""
Report Appendix model.

Provides the ReportAppendix dataclass with structured representation
of the Appendix & Evidence section (commands, screenshots, notes)
and bidirectional Markdown serialization.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from core.reporting.report_evidence import ReportEvidenceItem


@dataclass
class ReportAppendix:
    """Structured representation of the Appendix & Evidence section."""

    title: str = "Anhang"
    commands_markdown: str = ""
    screenshots_markdown: str = ""
    raw_content: str = ""
    command_snippets: List[ReportEvidenceItem] = field(default_factory=list)
    screenshots: List[ReportEvidenceItem] = field(default_factory=list)
    custom_notes: str = ""

    @classmethod
    def from_markdown(cls, markdown: str, language: str = "de") -> "ReportAppendix":
        default_title = "Anhang" if language == "de" else "Appendix"
        if not markdown:
            return cls(title=default_title)

        title = default_title
        h2 = re.search(r"^##\s+(.*?)$", markdown, re.MULTILINE)
        if h2:
            title = h2.group(1).strip()

        command_snippets: List[ReportEvidenceItem] = []
        screenshots: List[ReportEvidenceItem] = []
        notes_lines: List[str] = []

        has_subsections = bool(re.search(r"^###\s+", markdown, re.MULTILINE))
        if has_subsections:
            sections = re.split(r"^###\s+", markdown, flags=re.MULTILINE)
            preamble = sections[0]
            preamble_lines = [
                line_text for line_text in preamble.splitlines() if not line_text.startswith("## ")
            ]
            if any(line_text.strip() for line_text in preamble_lines):
                notes_lines.append("\n".join(preamble_lines).strip())

            for sec in sections[1:]:
                sec_lines = sec.strip().splitlines()
                if not sec_lines:
                    continue
                header = sec_lines[0].lower()
                sec_body = "\n".join(sec_lines[1:]).strip()

                if any(k in header for k in ("anhang a", "appendix a", "befehl", "command")):
                    code_matches = list(
                        re.finditer(r"```([a-zA-Z0-9_-]*)\r?\n(.*?)\r?\n```", sec_body, re.DOTALL)
                    )
                    last_idx = 0
                    for idx, m in enumerate(code_matches, start=1):
                        preceding = sec_body[last_idx : m.start()].strip()
                        last_idx = m.end()
                        caption = ""
                        if preceding:
                            lines_prec = [
                                line_text.strip()
                                for line_text in preceding.splitlines()
                                if line_text.strip()
                            ]
                            if lines_prec:
                                last_line = lines_prec[-1]
                                m_cap = re.match(
                                    r"^(?:####|\*\*|#+)\s*(.+?)(?:\*\*|#*)?$", last_line
                                )
                                if m_cap:
                                    caption = m_cap.group(1).strip()
                                elif (
                                    not last_line.startswith(("-", "*", "|"))
                                    and len(last_line) < 80
                                ):
                                    caption = last_line.strip("*_#`").strip()
                        lang = m.group(1) or ""
                        code = m.group(2) or ""
                        t_type = (
                            "terminal"
                            if (
                                not lang
                                or lang
                                in ("bash", "sh", "shell", "powershell", "cmd", "batch", "zsh")
                            )
                            else "code"
                        )
                        command_snippets.append(
                            ReportEvidenceItem(
                                id=f"cmd_{idx}",
                                type=t_type,
                                caption=caption,
                                content=code.strip(),
                                language=lang.strip() or "bash",
                            )
                        )

                elif any(
                    k in header
                    for k in (
                        "anhang b",
                        "appendix b",
                        "screenshot",
                        "nachweis",
                        "evidence",
                        "bild",
                    )
                ):
                    imgs = re.findall(r"!\[(.*?)\]\((.*?)\)", sec_body)
                    for idx, (cap, path) in enumerate(imgs, start=1):
                        screenshots.append(
                            ReportEvidenceItem(
                                id=f"sc_{idx}",
                                type="screenshot",
                                caption=cap.strip(),
                                content=path.strip(),
                            )
                        )

                elif any(
                    k in header
                    for k in (
                        "anhang c",
                        "appendix c",
                        "rohdaten",
                        "notiz",
                        "raw",
                        "note",
                        "ergänzend",
                    )
                ):
                    if sec_body:
                        notes_lines.append(sec_body)
                else:
                    notes_lines.append(f"### {sec_lines[0]}\n\n{sec_body}")

        else:
            imgs = re.findall(r"!\[(.*?)\]\((.*?)\)", markdown)
            for idx, (cap, path) in enumerate(imgs, start=1):
                screenshots.append(
                    ReportEvidenceItem(
                        id=f"sc_{idx}",
                        type="screenshot",
                        caption=cap.strip(),
                        content=path.strip(),
                    )
                )

            code_matches = list(
                re.finditer(r"```([a-zA-Z0-9_-]*)\r?\n(.*?)\r?\n```", markdown, re.DOTALL)
            )
            for idx, m in enumerate(code_matches, start=1):
                lang = m.group(1) or ""
                code = m.group(2) or ""
                t_type = (
                    "terminal"
                    if (
                        not lang
                        or lang in ("bash", "sh", "shell", "powershell", "cmd", "batch", "zsh")
                    )
                    else "code"
                )
                command_snippets.append(
                    ReportEvidenceItem(
                        id=f"cmd_{idx}",
                        type=t_type,
                        caption="",
                        content=code.strip(),
                        language=lang.strip() or "bash",
                    )
                )

            clean_text = re.sub(r"^##\s+.*$", "", markdown, flags=re.MULTILINE)
            clean_text = re.sub(r"!\[.*?\]\(.*?\)", "", clean_text)
            clean_text = re.sub(
                r"```[a-zA-Z0-9_-]*\r?\n.*?\r?\n```", "", clean_text, flags=re.DOTALL
            )
            if clean_text.strip():
                notes_lines.append(clean_text.strip())

        return cls(
            title=title,
            raw_content=markdown if not (command_snippets or screenshots or notes_lines) else "",
            command_snippets=command_snippets,
            screenshots=screenshots,
            custom_notes="\n\n".join(notes_lines).strip(),
        )

    def to_markdown(self, title: Optional[str] = None, language: str = "de") -> str:
        default_title = "Anhang" if language == "de" else "Appendix"
        sec_title = title or self.title or default_title
        lines: List[str] = [f"## {sec_title}", ""]

        if not self.command_snippets and not self.screenshots and not self.custom_notes.strip():
            if self.raw_content.strip():
                return self.raw_content.strip()
            if self.commands_markdown or self.screenshots_markdown:
                if self.commands_markdown:
                    lines.append(
                        "### Anhang A: Ausgeführte Befehle"
                        if language == "de"
                        else "### Appendix A: Command History"
                    )
                    lines.append("")
                    lines.append(self.commands_markdown.strip())
                    lines.append("")
                if self.screenshots_markdown:
                    lines.append(
                        "### Anhang B: Screenshots & Nachweise"
                        if language == "de"
                        else "### Appendix B: Screenshots & Evidence"
                    )
                    lines.append("")
                    lines.append(self.screenshots_markdown.strip())
                    lines.append("")
                return "\n".join(lines).strip()
            empty_msg = (
                "*Keine Anhänge oder Nachweise erfasst.*"
                if language == "de"
                else "*No appendices or evidence recorded.*"
            )
            lines.append(empty_msg)
            lines.append("")
            return "\n".join(lines).strip()

        # Section A: Commands
        title_a = (
            "### Anhang A: Ausgeführte Befehle"
            if language == "de"
            else "### Appendix A: Executed Commands"
        )
        lines.append(title_a)
        lines.append("")
        if self.command_snippets:
            for item in self.command_snippets:
                if item.caption:
                    lines.append(f"#### {item.caption}")
                lang = getattr(item, "language", "") or ("bash" if item.type == "terminal" else "")
                lines.append(f"```{lang}\n{item.content.strip()}\n```")
                lines.append("")
        else:
            msg = (
                "*Keine Befehlsprotokolle hinterlegt.*"
                if language == "de"
                else "*No command logs recorded.*"
            )
            lines.append(msg)
            lines.append("")

        # Section B: Screenshots
        title_b = (
            "### Anhang B: Screenshots & Nachweise"
            if language == "de"
            else "### Appendix B: Screenshots & Evidence"
        )
        lines.append(title_b)
        lines.append("")
        if self.screenshots:
            for item in self.screenshots:
                cap = item.caption or ("Nachweis" if language == "de" else "Evidence")
                lines.append(f"![{cap}]({item.content})")
                lines.append("")
        else:
            msg = (
                "*Keine Screenshots oder Nachweise hinterlegt.*"
                if language == "de"
                else "*No screenshots or evidence recorded.*"
            )
            lines.append(msg)
            lines.append("")

        # Section C: Notes / Raw Data
        if self.custom_notes.strip():
            title_c = (
                "### Anhang C: Ergänzende Rohdaten & Notizen"
                if language == "de"
                else "### Appendix C: Supplementary Raw Data & Notes"
            )
            lines.append(title_c)
            lines.append("")
            lines.append(self.custom_notes.strip())
            lines.append("")

        return "\n".join(lines).strip()
