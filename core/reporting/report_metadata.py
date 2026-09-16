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

CLIENT_ALIASES: tuple[str, ...] = (
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
TESTER_ALIASES: tuple[str, ...] = (
    "lead tester / analyst",
    "lead tester",
    "tester",
    "prüfer",
    "pentester",
    "auditor",
    "analyst",
    "author",
    "autor",
    "erstellt von",
    "created by",
)
TARGET_ALIASES: tuple[str, ...] = (
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
TIMEFRAME_ALIASES: tuple[str, ...] = (
    "assessment period",
    "testzeitraum",
    "zeitraum",
    "period",
    "timeframe",
    "testing period",
)
DATE_ALIASES: tuple[str, ...] = (
    "berichtsdatum",
    "report date",
    "datum",
    "date",
    "stand",
    "assessment date",
    "erstellungsdatum",
)
CLASSIFICATION_ALIASES: tuple[str, ...] = (
    "klassifizierung",
    "classification",
    "vertraulichkeit",
    "confidentiality",
    "tlp",
    "traffic light protocol",
)
VERSION_ALIASES: tuple[str, ...] = (
    "report-version",
    "report version",
    "version",
    "revision",
)

ALL_METADATA_ALIASES: frozenset[str] = frozenset(
    alias.strip().lower()
    for group in (
        CLIENT_ALIASES,
        TARGET_ALIASES,
        TESTER_ALIASES,
        TIMEFRAME_ALIASES,
        DATE_ALIASES,
        CLASSIFICATION_ALIASES,
        VERSION_ALIASES,
    )
    for alias in group
)

_CLIENT_ALIASES = CLIENT_ALIASES
_TESTER_ALIASES = TESTER_ALIASES
_TARGET_ALIASES = TARGET_ALIASES
_TIMEFRAME_ALIASES = TIMEFRAME_ALIASES
_DATE_ALIASES = DATE_ALIASES
_CLASSIFICATION_ALIASES = CLASSIFICATION_ALIASES
_VERSION_ALIASES = VERSION_ALIASES
_ALL_METADATA_ALIASES = ALL_METADATA_ALIASES


def clean_metadata_value(val: str) -> str:
    cleaned = val.strip().strip("`").strip()
    cleaned = re.sub(r"[*_]", "", cleaned).strip()
    if cleaned in ("-", "–", "—", "n/a", "N/A"):
        return ""
    return html.unescape(cleaned).strip()


_clean_md_val = clean_metadata_value


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
        standard_keys = ALL_METADATA_ALIASES
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
        title = self.title or (
            "Security Assessment Report" if language != "de" else "Sicherheitsbericht"
        )
        lines = [f"# {title}", ""]
        if language == "de":
            lines.extend(
                [
                    "| Eigenschaft | Wert |",
                    "|---|---|",
                    f"| **Auftraggeber / Client** | `{self.client}` |",
                    f"| **Tester** | `{self.tester}` |",
                    f"| **Ziel(e) / Scope** | `{self.target_scope}` |",
                    f"| **Testzeitraum** | `{self.timeframe}` |",
                    f"| **Berichtsdatum** | `{date_str}` |",
                    f"| **Klassifizierung** | `{self.classification or 'Vertraulich – Nur für internen Gebrauch'}` |",
                    f"| **Report-Version** | `{self.version or 'v1.0'}` |",
                ]
            )
        else:
            lines.extend(
                [
                    "| Property | Value |",
                    "|---|---|",
                    f"| **Client / Organization** | `{self.client}` |",
                    f"| **Lead Tester** | `{self.tester}` |",
                    f"| **Scope / Target** | `{self.target_scope}` |",
                    f"| **Assessment Period** | `{self.timeframe}` |",
                    f"| **Report Date** | `{date_str}` |",
                    f"| **Classification** | `{self.classification or 'Confidential – Internal Use Only'}` |",
                    f"| **Report Version** | `{self.version or 'v1.0'}` |",
                ]
            )
        for k, v in self.custom_fields.items():
            lines.append(f"| **{k.capitalize()}** | `{v}` |")
        lines.append("")
        return "\n".join(lines)
