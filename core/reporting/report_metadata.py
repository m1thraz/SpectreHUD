"""
Report Metadata model.

Provides the ReportMetadata dataclass with bidirectional Markdown table
serialization and multi-language field alias resolution.
"""

import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

_METADATA_ROW_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|$")

_CLIENT_ALIASES = (
    "auftraggeber / client",
    "client / organization",
    "client",
    "auftraggeber",
    "kunde",
    "customer",
    "organisation",
    "organization",
    "company",
    "unternehmen",
)
_TESTER_ALIASES = (
    "tester",
    "lead tester",
    "prüfer",
    "pentester",
    "analyst",
    "author",
    "autor",
)
_TARGET_ALIASES = (
    "ziel(e) / scope",
    "scope / target",
    "target",
    "scope",
    "ziel",
    "ziele",
    "ziel(e)",
    "target_ip",
    "ip",
    "domain",
    "netzwerk",
    "network",
)
_TIMEFRAME_ALIASES = (
    "testzeitraum",
    "assessment period",
    "zeitraum",
    "timeframe",
    "period",
)
_DATE_ALIASES = (
    "berichtsdatum",
    "report date",
    "datum",
    "date",
    "stand",
    "assessment date",
    "erstellungsdatum",
)
_CLASSIFICATION_ALIASES = (
    "klassifizierung",
    "classification",
    "vertraulichkeit",
    "confidentiality",
    "tlp",
    "traffic light protocol",
)
_VERSION_ALIASES = (
    "report-version",
    "report version",
    "version",
    "revision",
)


def _clean_md_val(val: str) -> str:
    cleaned = val.strip().strip("`").strip()
    cleaned = re.sub(r"[*_]", "", cleaned)
    return html.unescape(cleaned).strip()


def _first_match(data: Dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        norm = alias.strip().lower()
        if norm in data and data[norm]:
            return data[norm]
        clean = re.sub(r"[\s/()_-]+", " ", norm).strip()
        if clean in data and data[clean]:
            return data[clean]
    return ""


@dataclass
class ReportMetadata:
    title: str = ""
    client: str = ""
    tester: str = ""
    target_scope: str = ""
    timeframe: str = ""
    date: str = ""
    classification: str = ""
    version: str = "v1.0"
    custom_fields: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_markdown_table(cls, markdown: str) -> "ReportMetadata":
        title = ""
        kv: Dict[str, str] = {}
        for line in markdown.splitlines():
            line_str = line.strip()
            if line_str.startswith("# "):
                title = line_str[2:].strip()
                continue
            match = _METADATA_ROW_RE.match(line_str)
            if match:
                raw_k = match.group(1).strip().lower()
                val = _clean_md_val(match.group(2))
                kv[raw_k] = val
                norm_k = re.sub(r"[\s/()_-]+", " ", raw_k).strip()
                kv[norm_k] = val

        client = _first_match(kv, _CLIENT_ALIASES)
        tester = _first_match(kv, _TESTER_ALIASES)
        target = _first_match(kv, _TARGET_ALIASES)
        timeframe = _first_match(kv, _TIMEFRAME_ALIASES)
        date = _first_match(kv, _DATE_ALIASES)
        classification = _first_match(kv, _CLASSIFICATION_ALIASES)
        version = _first_match(kv, _VERSION_ALIASES) or "v1.0"

        # Capture any unmapped custom keys
        standard_keys = {
            *_CLIENT_ALIASES,
            *_TESTER_ALIASES,
            *_TARGET_ALIASES,
            *_TIMEFRAME_ALIASES,
            *_DATE_ALIASES,
            *_CLASSIFICATION_ALIASES,
            *_VERSION_ALIASES,
        }
        normalized_standard_keys = {
            re.sub(r"[\s/()_-]+", " ", key).strip() for key in standard_keys
        }
        custom = {
            k: v
            for k, v in kv.items()
            if k not in standard_keys
            and re.sub(r"[\s/()_-]+", " ", k).strip() not in normalized_standard_keys
        }

        return cls(
            title=title,
            client=client,
            tester=tester,
            target_scope=target,
            timeframe=timeframe,
            date=date,
            classification=classification,
            version=version,
            custom_fields=custom,
        )

    def to_markdown_table(self, language: str = "de") -> str:
        date_str = self.date or datetime.now().strftime("%Y-%m-%d")
        title = self.title or ("Security Assessment Report" if language != "de" else "Sicherheitsbericht")
        lines = [f"# {title}", ""]
        if language == "de":
            lines.extend([
                "| Eigenschaft | Wert |",
                "|---|---|",
                f"| **Auftraggeber / Client** | `{self.client}` |",
                f"| **Tester** | `{self.tester}` |",
                f"| **Ziel(e) / Scope** | `{self.target_scope}` |",
                f"| **Testzeitraum** | `{self.timeframe}` |",
                f"| **Berichtsdatum** | `{date_str}` |",
                f"| **Klassifizierung** | `{self.classification or 'Vertraulich – Nur für internen Gebrauch'}` |",
                f"| **Report-Version** | `{self.version or 'v1.0'}` |",
            ])
        else:
            lines.extend([
                "| Property | Value |",
                "|---|---|",
                f"| **Client / Organization** | `{self.client}` |",
                f"| **Lead Tester** | `{self.tester}` |",
                f"| **Scope / Target** | `{self.target_scope}` |",
                f"| **Assessment Period** | `{self.timeframe}` |",
                f"| **Report Date** | `{date_str}` |",
                f"| **Classification** | `{self.classification or 'Confidential – Internal Use Only'}` |",
                f"| **Report Version** | `{self.version or 'v1.0'}` |",
            ])
        for k, v in self.custom_fields.items():
            lines.append(f"| **{k.capitalize()}** | `{v}` |")
        lines.append("")
        return "\n".join(lines)
