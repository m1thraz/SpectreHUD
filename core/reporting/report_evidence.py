"""
Report Evidence model.

Provides the ReportEvidenceItem dataclass for structured representation
of evidence artifacts (screenshots, terminal output, code, credentials)
with Markdown serialization and provenance-preserving persistence.
"""

import re
from dataclasses import dataclass
from typing import Optional

from core.reporting.evidence_markers import (
    format_evidence_block,
)

# Shared regex for image and code-block detection in Markdown.
IMAGE_MD_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)$", re.MULTILINE)
CODE_BLOCK_RE = re.compile(
    r"^(`{3,})([a-zA-Z0-9_-]*)\r?\n(.*?)\r?\n\1$",
    re.DOTALL | re.MULTILINE,
)


@dataclass
class ReportEvidenceItem:
    id: str
    type: str  # "terminal", "screenshot", "credential", "code", "text"
    caption: str = ""
    content: str = ""
    source_loot_id: Optional[str] = None
    language: str = ""

    def to_markdown(self) -> str:
        if self.type == "screenshot":
            caption = self.caption or "Screenshot"
            return f"![{caption}]({self.content})"
        if self.type in ("terminal", "credential", "code"):
            if self.type == "credential" and self.language in {
                "credential",
                "credentials",
                "hash",
                "flag",
            }:
                # The subtype is persistence metadata, not a Markdown language.
                lang = ""
            else:
                lang = self.language or ("bash" if self.type == "terminal" else ("text" if self.type == "credential" else ""))
            backtick_runs = re.findall(r"`+", self.content)
            fence_length = max(3, max((len(run) for run in backtick_runs), default=0) + 1)
            fence = "`" * fence_length
            return f"{fence}{lang}\n{self.content}\n{fence}"
        return self.content

    def to_persisted_markdown(self) -> str:
        """Keep provenance invisible while leaving the rendered evidence unchanged."""
        return format_evidence_block(
            {
                "id": self.id,
                "type": self.type,
                "caption": self.caption,
                "source_loot_id": self.source_loot_id,
                "language": self.language,
            },
            self.to_markdown(),
        )
