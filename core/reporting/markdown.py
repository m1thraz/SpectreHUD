"""
Markdown Parsing and HTML Conversion Engine for SpectreHUD Reports.
"""

import html
import re
from pathlib import Path
from typing import Optional, List, Union, Iterable

from core.reporting.assets import encode_image_base64, ImageEmbeddingBudget
from core.reporting.loot_sync import (
    PAGEBREAK_HTML,
    PAGEBREAK_REGEX,
    SPACER_REGEX,
    strip_report_markers,
)
from core.logger import get_logger

logger = get_logger(__name__)


def sanitize_url(url: str, is_image: bool = False) -> str:
    """
    Sanitizes URLs for href or src attributes.
    Blocks 'javascript:', 'vbscript:', 'data:' (non-image), unapproved schemes,
    and protocol-relative URLs ('//...', '\\\\...') to prevent XSS and SSRF.
    """
    clean = url.strip()
    lower = clean.lower()

    # Remove control characters and whitespace tricks
    lower_no_spaces = re.sub(r"[\s\x00-\x1f\x7f-\x9f]", "", lower)

    # Explicitly block dangerous script URI schemes
    if lower_no_spaces.startswith(("javascript:", "vbscript:", "livescript:")):
        return "#unsafe-scheme-blocked"

    # Explicitly block protocol-relative URLs
    if lower_no_spaces.startswith(("//", "\\\\")):
        return "#unsafe-protocol-relative-blocked"

    if is_image:
        # Images: allow http, https, approved data:image/ mime types, and safe relative paths
        if lower_no_spaces.startswith(("http://", "https://")):
            return html.escape(clean, quote=True)
        if lower_no_spaces.startswith(
            (
                "data:image/png",
                "data:image/jpeg",
                "data:image/jpg",
                "data:image/gif",
                "data:image/webp",
            )
        ):
            return html.escape(clean, quote=True)
        if lower_no_spaces.startswith("data:"):
            return "#unsafe-data-uri-blocked"
        # Block any unapproved scheme
        if ":" in clean.split("/")[0]:
            return "#unsafe-image-scheme-blocked"
        return html.escape(clean, quote=True)
    else:
        # Links: allow http, https, mailto, and relative / anchor links
        if lower_no_spaces.startswith(("http://", "https://", "mailto:", "#")):
            return html.escape(clean, quote=True)
        if lower_no_spaces.startswith("data:"):
            return "#unsafe-data-link-blocked"
        # Block any unapproved scheme
        if ":" in clean.split("/")[0]:
            return "#unsafe-link-scheme-blocked"
        return html.escape(clean, quote=True)


def resolve_and_embed_images(
    md_text: str, project_dir: Optional[Path], budget: Optional[ImageEmbeddingBudget] = None
) -> str:
    """Finds all ![alt](src) in markdown and embeds local images as base64 data URIs within limits."""
    if not project_dir:
        return md_text

    proj_resolved = project_dir.resolve()
    active_budget = budget or ImageEmbeddingBudget()

    def _replace_img(match: re.Match) -> str:
        alt_text = match.group(1)
        raw_src = match.group(2).strip()

        # Skip data URIs or external URLs
        if (
            raw_src.startswith("data:")
            or raw_src.startswith("http://")
            or raw_src.startswith("https://")
        ):
            return match.group(0)

        clean_src = raw_src
        if clean_src.startswith("file:///"):
            clean_src = clean_src[8:]
        elif clean_src.startswith("file://"):
            clean_src = clean_src[7:]

        p = Path(clean_src)
        candidate_paths = []
        if p.is_absolute():
            candidate_paths.append(p)
        else:
            candidate_paths.append(project_dir / p)
            candidate_paths.append(project_dir / "loot" / p.name)

        for candidate in candidate_paths:
            try:
                cand_resolved = candidate.resolve()
                if (
                    cand_resolved.is_relative_to(proj_resolved)
                    and cand_resolved.exists()
                    and cand_resolved.is_file()
                ):
                    file_size = cand_resolved.stat().st_size
                    if not active_budget.can_embed(file_size):
                        logger.warning(
                            f"Image embedding budget exceeded (embedded={active_budget.embedded_count}/{active_budget.max_images} imgs, "
                            f"bytes={active_budget.embedded_bytes}/{active_budget.max_total_bytes} bytes). Skipping {cand_resolved.name}"
                        )
                        return f"*[Embedded image limit reached: {alt_text or cand_resolved.name}]*"

                    b64_uri = encode_image_base64(cand_resolved)
                    if b64_uri:
                        active_budget.record(file_size)
                        return f"![{alt_text}]({b64_uri})"
            except (OSError, RuntimeError):
                continue

        return match.group(0)

    img_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
    return img_pattern.sub(_replace_img, md_text)


def format_inline(text: str) -> str:
    """Formats inline markdown: bold, italic, inline code, links, images."""
    if not text:
        return ""

    code_tokens: List[str] = []

    def _code_sub(m: re.Match) -> str:
        token = f"@@SPECTRE_CODETOKEN{len(code_tokens)}@@"
        code_tokens.append(f"<code>{html.escape(m.group(1))}</code>")
        return token

    res = re.sub(r"`([^`]+)`", _code_sub, text)

    img_tokens: List[str] = []

    def _img_sub(m: re.Match) -> str:
        token = f"@@SPECTRE_IMGTOKEN{len(img_tokens)}@@"
        alt = html.escape(m.group(1), quote=True)
        src = sanitize_url(m.group(2), is_image=True)
        img_tokens.append(f'<img src="{src}" alt="{alt}" class="inline-img">')
        return token

    res = re.sub(r"!\[(.*?)\]\((.*?)\)", _img_sub, res)

    link_tokens: List[str] = []

    def _link_sub(m: re.Match) -> str:
        token = f"@@SPECTRE_LINKTOKEN{len(link_tokens)}@@"
        ltext = html.escape(m.group(1))
        url = sanitize_url(m.group(2), is_image=False)
        link_tokens.append(f'<a href="{url}" target="_blank" rel="noopener noreferrer">{ltext}</a>')
        return token

    res = re.sub(r"\[(.*?)\]\((.*?)\)", _link_sub, res)

    badge_tokens: List[str] = []

    def _badge_sub(m: re.Match) -> str:
        classes = m.group(1).strip()
        inner = m.group(2)
        class_list = classes.split()
        if "severity-pill" in class_list and all(
            re.match(r"^[a-zA-Z0-9_-]+$", c) for c in class_list
        ):
            safe_classes = " ".join(class_list)
            safe_inner = html.escape(html.unescape(inner))
            token = f"@@SPECTRE_BADGETOKEN{len(badge_tokens)}@@"
            badge_tokens.append(f'<span class="{safe_classes}">{safe_inner}</span>')
            return token
        return m.group(0)

    res = re.sub(
        r'<span\s+class=["\']([^"\']+)["\']>([\s\S]*?)</span>',
        _badge_sub,
        res,
        flags=re.IGNORECASE,
    )

    res = html.escape(res)
    res = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", res)
    res = re.sub(r"__(.*?)__", r"<strong>\1</strong>", res)
    res = re.sub(r"\*(.*?)\*", r"<em>\1</em>", res)
    res = re.sub(r"\b_(.*?)_\b", r"<em>\1</em>", res)

    for i, token_html in enumerate(link_tokens):
        res = res.replace(f"@@SPECTRE_LINKTOKEN{i}@@", token_html)

    for i, token_html in enumerate(img_tokens):
        res = res.replace(f"@@SPECTRE_IMGTOKEN{i}@@", token_html)

    for i, token_html in enumerate(code_tokens):
        res = res.replace(f"@@SPECTRE_CODETOKEN{i}@@", token_html)

    for i, token_html in enumerate(badge_tokens):
        res = res.replace(f"@@SPECTRE_BADGETOKEN{i}@@", token_html)

    return res


def _render_html_table(table_rows: List[List[str]]) -> List[str]:
    """Renders a parsed markdown table (header + body rows) to HTML lines."""
    if not table_rows:
        return []
    lines = ['<div class="table-container"><table>', "<thead><tr>"]
    header = table_rows[0]
    for cell in header:
        lines.append(f"<th>{format_inline(cell)}</th>")
    lines.append("</tr></thead>")
    if len(table_rows) > 1:
        lines.append("<tbody>")
        for row in table_rows[1:]:
            lines.append("<tr>")
            for cell in row:
                lines.append(f"<td>{format_inline(cell)}</td>")
            lines.append("</tr>")
        lines.append("</tbody>")
    lines.append("</table></div>")
    return lines


class _MarkdownHtmlParser:
    """Line-oriented state machine converting SpectreHUD markdown subset into HTML.

    Preserves code block precedence, delayed inline escaping, and export-safety invariants.
    """

    def __init__(self) -> None:
        self.html_lines: List[str] = []
        self.in_code_block: bool = False
        self.code_block_lang: str = ""
        self.code_block_lines: List[str] = []
        self.in_list: bool = False
        self.list_type: str = "ul"
        self.in_table: bool = False
        self.table_rows: List[List[str]] = []
        self.in_blockquote: bool = False
        self.blockquote_lines: List[str] = []

    def flush_list(self) -> None:
        if self.in_list:
            self.html_lines.append(f"</{self.list_type}>")
            self.in_list = False

    def flush_table(self) -> None:
        if self.in_table and self.table_rows:
            self.html_lines.extend(_render_html_table(self.table_rows))
            self.in_table = False
            self.table_rows = []

    def flush_blockquote(self) -> None:
        if self.in_blockquote and self.blockquote_lines:
            inner_text = "<br>".join([format_inline(bl) for bl in self.blockquote_lines])
            self.html_lines.append(f"<blockquote>{inner_text}</blockquote>")
            self.in_blockquote = False
            self.blockquote_lines = []

    def flush_open_containers(self) -> None:
        self.flush_list()
        self.flush_table()
        self.flush_blockquote()

    def _handle_code_block_fence(self, stripped: str) -> None:
        if self.in_code_block:
            raw_code = "\n".join(self.code_block_lines)
            escaped_code = html.escape(raw_code)
            safe_lang = re.sub(r"[^a-zA-Z0-9_+-]", "", self.code_block_lang)
            safe_lang = html.escape(safe_lang, quote=True)
            lang_class = f' class="language-{safe_lang}"' if safe_lang else ""
            self.html_lines.append(f"<pre><code{lang_class}>{escaped_code}</code></pre>")
            self.in_code_block = False
            self.code_block_lines = []
            self.code_block_lang = ""
        else:
            self.flush_open_containers()
            self.in_code_block = True
            self.code_block_lang = stripped.lstrip("`").strip()
            self.code_block_lines = []

    def _handle_pagebreak_or_spacer(self, stripped: str) -> bool:
        if PAGEBREAK_REGEX.fullmatch(stripped):
            self.flush_open_containers()
            self.html_lines.append(PAGEBREAK_HTML)
            return True

        spacer_match = SPACER_REGEX.fullmatch(stripped)
        if spacer_match:
            self.flush_open_containers()
            size = spacer_match.group(1).lower()
            self.html_lines.append(
                f'<div class="spectre-spacer spacer-{size}" aria-hidden="true"></div>'
            )
            return True
        return False

    def _handle_blockquote(self, stripped: str) -> bool:
        if stripped.startswith(">"):
            self.flush_list()
            self.flush_table()
            self.in_blockquote = True
            self.blockquote_lines.append(stripped.lstrip(">").strip())
            return True
        if self.in_blockquote:
            self.flush_blockquote()
        return False

    def _handle_table_row(self, stripped: str) -> bool:
        if stripped.startswith("|") and stripped.endswith("|"):
            self.flush_list()
            self.flush_blockquote()
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                return True
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not self.in_table:
                self.in_table = True
                self.table_rows = [cells]
            else:
                self.table_rows.append(cells)
            return True
        if self.in_table:
            self.flush_table()
        return False

    def _handle_list_item(self, stripped: str) -> bool:
        unordered_match = re.match(r"^[-*]\s+(.*)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)

        if unordered_match or ordered_match:
            self.flush_blockquote()
            self.flush_table()
            target_type = "ul" if unordered_match else "ol"
            item_text = (
                unordered_match.group(1) if unordered_match else ordered_match.group(1)  # type: ignore[union-attr]
            )

            if not self.in_list or self.list_type != target_type:
                self.flush_list()
                self.html_lines.append(f"<{target_type}>")
                self.in_list = True
                self.list_type = target_type
            self.html_lines.append(f"<li>{format_inline(item_text)}</li>")
            return True
        if self.in_list:
            self.flush_list()
        return False

    def _handle_heading(self, stripped: str) -> bool:
        for prefix, tag in (
            ("#### ", "h4"),
            ("### ", "h3"),
            ("## ", "h2"),
            ("# ", "h1"),
        ):
            if stripped.startswith(prefix):
                self.html_lines.append(
                    f"<{tag}>{format_inline(stripped[len(prefix):])}</{tag}>"
                )
                return True
        return False

    def _handle_image(self, stripped: str) -> bool:
        img_match = re.match(r"^!\[(.*?)\]\((.*?)\)$", stripped)
        if img_match:
            alt = html.escape(img_match.group(1), quote=True)
            raw_src = img_match.group(2)
            src = sanitize_url(raw_src, is_image=True)
            self.html_lines.append(
                f'<div class="screenshot-container"><img src="{src}" alt="{alt}" class="screenshot-img"><p class="screenshot-caption">{alt}</p></div>'
            )
            return True
        return False

    def _handle_horizontal_rule(self, stripped: str) -> bool:
        if stripped in ("---", "***", "___"):
            self.html_lines.append("<hr>")
            return True
        return False

    def process_line(self, line: str) -> None:
        stripped = line.strip()

        if stripped.startswith("```"):
            self._handle_code_block_fence(stripped)
            return

        if self.in_code_block:
            self.code_block_lines.append(line)
            return

        if self._handle_pagebreak_or_spacer(stripped):
            return

        if self._handle_blockquote(stripped):
            return

        if self._handle_table_row(stripped):
            return

        if self._handle_list_item(stripped):
            return

        if not stripped:
            return

        if self._handle_horizontal_rule(stripped):
            return

        if self._handle_heading(stripped):
            return

        if self._handle_image(stripped):
            return

        self.html_lines.append(f"<p>{format_inline(stripped)}</p>")

    def finalize(self) -> str:
        self.flush_open_containers()
        if self.in_code_block and self.code_block_lines:
            raw_code = "\n".join(self.code_block_lines)
            escaped_code = html.escape(raw_code)
            safe_lang = re.sub(r"[^a-zA-Z0-9_+-]", "", self.code_block_lang)
            safe_lang = html.escape(safe_lang, quote=True)
            lang_class = f' class="language-{safe_lang}"' if safe_lang else ""
            self.html_lines.append(f"<pre><code{lang_class}>{escaped_code}</code></pre>")
        return "\n".join(self.html_lines)

    def parse(self, content: Union[str, Iterable[str]]) -> str:
        self.html_lines = []
        self.in_code_block = False
        self.code_block_lang = ""
        self.code_block_lines = []
        self.in_list = False
        self.list_type = "ul"
        self.in_table = False
        self.table_rows = []
        self.in_blockquote = False
        self.blockquote_lines = []
        line_list = content.splitlines() if isinstance(content, str) else content
        for line in line_list:
            self.process_line(line)
        return self.finalize()


def convert_markdown_to_html(md_text: str, project_dir: Optional[Path] = None) -> str:
    """Convert the line-oriented report subset after loot-marker stripping and image resolution.

    Block precedence and delayed inline escaping are structural and export-safety invariants,
    not interchangeable parsing stages.
    """
    clean_md = strip_report_markers(md_text)
    processed_md = resolve_and_embed_images(clean_md, project_dir)
    return _MarkdownHtmlParser().parse(processed_md.splitlines())
