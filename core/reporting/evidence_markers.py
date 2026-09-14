"""Lossless metadata markers for evidence embedded in report Markdown."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Optional


_EVIDENCE_BLOCK_RE = re.compile(
    r"^<!--\s*spectre:evidence:start:v1:([A-Za-z0-9_-]{1,4096})\s*-->\r?\n"
    r"(.*?)\r?\n<!--\s*spectre:evidence:end\s*-->",
    re.MULTILINE | re.DOTALL,
)
_EVIDENCE_START_RE = re.compile(
    r"^<!--\s*spectre:evidence:start:v1:[A-Za-z0-9_-]{1,4096}\s*-->\r?\n?",
    re.MULTILINE,
)
_EVIDENCE_END_RE = re.compile(
    r"^<!--\s*spectre:evidence:end\s*-->\r?\n?",
    re.MULTILINE,
)
_EVIDENCE_TYPES = {"terminal", "screenshot", "credential", "code", "text"}


@dataclass(frozen=True)
class EvidenceMarkdownBlock:
    start: int
    end: int
    body: str
    metadata: dict[str, str]


def _encode_metadata(metadata: Mapping[str, Any]) -> str:
    def text_value(key: str, default: str = "") -> str:
        value = metadata.get(key, default)
        return default if value is None else str(value)

    payload = {
        "id": text_value("id")[:128],
        "type": text_value("type", "text")[:32],
        "caption": text_value("caption")[:512],
        "source_loot_id": text_value("source_loot_id")[:128],
        "language": text_value("language")[:32],
    }
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_metadata(token: str) -> Optional[dict[str, str]]:
    try:
        padding = "=" * (-len(token) % 4)
        value = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    evidence_id = str(value.get("id", ""))[:128]
    if not evidence_id:
        return None
    evidence_type = str(value.get("type", "text"))[:32]
    if evidence_type not in _EVIDENCE_TYPES:
        evidence_type = "text"
    return {
        "id": evidence_id,
        "type": evidence_type,
        "caption": str(value.get("caption", ""))[:512],
        "source_loot_id": str(value.get("source_loot_id", ""))[:128],
        "language": str(value.get("language", ""))[:32],
    }


def format_evidence_block(metadata: Mapping[str, Any], visible_markdown: str) -> str:
    """Wrap visible evidence Markdown with an invisible, versioned identity envelope."""
    token = _encode_metadata(metadata)
    return (
        f"<!-- spectre:evidence:start:v1:{token} -->\n"
        f"{visible_markdown.strip()}\n"
        "<!-- spectre:evidence:end -->"
    )


def parse_evidence_blocks(markdown: str) -> tuple[EvidenceMarkdownBlock, ...]:
    blocks = []
    for match in _EVIDENCE_BLOCK_RE.finditer(markdown):
        metadata = _decode_metadata(match.group(1))
        if metadata is None:
            continue
        blocks.append(
            EvidenceMarkdownBlock(
                start=match.start(),
                end=match.end(),
                body=match.group(2),
                metadata=metadata,
            )
        )
    return tuple(blocks)


def remove_evidence_block(markdown: str, evidence_id: str) -> tuple[str, bool]:
    for block in parse_evidence_blocks(markdown):
        if block.metadata["id"] == evidence_id:
            return (markdown[: block.start] + markdown[block.end :]).strip(), True
    return markdown, False


def replace_evidence_block(
    markdown: str,
    evidence_id: str,
    replacement: str,
) -> tuple[str, bool]:
    for block in parse_evidence_blocks(markdown):
        if block.metadata["id"] == evidence_id:
            return markdown[: block.start] + replacement + markdown[block.end :], True
    return markdown, False


def strip_evidence_markers(markdown: str) -> str:
    """Remove only internal evidence envelopes while preserving their visible bodies."""
    return _EVIDENCE_END_RE.sub("", _EVIDENCE_START_RE.sub("", markdown))


def reconcile_evidence_markers(original_markdown: str, current_markdown: str) -> str:
    """Restore envelopes dropped by a rich-text roundtrip when their body remains."""
    original_blocks = parse_evidence_blocks(original_markdown)
    if not original_blocks:
        return current_markdown

    present_ids = {
        block.metadata["id"] for block in parse_evidence_blocks(current_markdown)
    }
    result = current_markdown
    search_start = 0
    for block in original_blocks:
        if block.metadata["id"] in present_ids:
            continue
        body = block.body.strip()
        if not body:
            continue
        index = result.find(body, search_start)
        if index == -1:
            continue
        wrapped = format_evidence_block(block.metadata, body)
        result = result[:index] + wrapped + result[index + len(body) :]
        search_start = index + len(wrapped)
    return result
