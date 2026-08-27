"""
Markdown Parsing and HTML Conversion Engine for SpectreHUD Reports.
"""

import html
import re
from pathlib import Path
from typing import Optional, List

from core.reporting.assets import encode_image_base64
from core.logger import get_logger

logger = get_logger(__name__)


def sanitize_url(url: str, is_image: bool = False) -> str:
    """
    Sanitizes URLs for href or src attributes.
    Blocks 'javascript:', 'vbscript:', 'data:' (non-image), and unapproved schemes to prevent XSS.
    """
    clean = url.strip()
    lower = clean.lower()

    # Remove control characters and whitespace tricks
    lower_no_spaces = re.sub(r'[\s\x00-\x1f\x7f-\x9f]', '', lower)

    # Explicitly block dangerous script URI schemes
    if lower_no_spaces.startswith(("javascript:", "vbscript:", "livescript:")):
        return "#unsafe-scheme-blocked"

    if is_image:
        # Images: allow http, https, approved data:image/ mime types, and safe relative paths
        if lower_no_spaces.startswith(("http://", "https://")):
            return html.escape(clean, quote=True)
        if lower_no_spaces.startswith(("data:image/png", "data:image/jpeg", "data:image/jpg", "data:image/gif", "data:image/webp")):
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


def resolve_and_embed_images(md_text: str, project_dir: Optional[Path]) -> str:
    """Finds all ![alt](src) in markdown and embeds local images as base64 data URIs."""
    if not project_dir:
        return md_text

    proj_resolved = project_dir.resolve()

    def _replace_img(match: re.Match) -> str:
        alt_text = match.group(1)
        raw_src = match.group(2).strip()

        # Skip data URIs or external URLs
        if raw_src.startswith("data:") or raw_src.startswith("http://") or raw_src.startswith("https://"):
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
                if cand_resolved.is_relative_to(proj_resolved) and cand_resolved.exists() and cand_resolved.is_file():
                    b64_uri = encode_image_base64(cand_resolved)
                    if b64_uri:
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

    return res


def convert_markdown_to_html(md_text: str, project_dir: Optional[Path] = None) -> str:
    """Converts Markdown text to HTML body structure."""
    processed_md = resolve_and_embed_images(md_text, project_dir)

    lines = processed_md.splitlines()
    html_lines: List[str] = []
    in_code_block = False
    code_block_lang = ""
    code_block_lines: List[str] = []
    in_list = False
    list_type = "ul"
    in_table = False
    table_rows: List[List[str]] = []
    in_blockquote = False
    blockquote_lines: List[str] = []

    def _flush_list():
        nonlocal in_list
        if in_list:
            html_lines.append(f"</{list_type}>")
            in_list = False

    def _flush_table():
        nonlocal in_table, table_rows
        if in_table and table_rows:
            html_lines.append('<div class="table-container"><table>')
            header = table_rows[0]
            html_lines.append("<thead><tr>")
            for cell in header:
                html_lines.append(f"<th>{format_inline(cell)}</th>")
            html_lines.append("</tr></thead>")
            if len(table_rows) > 1:
                html_lines.append("<tbody>")
                for row in table_rows[1:]:
                    html_lines.append("<tr>")
                    for cell in row:
                        html_lines.append(f"<td>{format_inline(cell)}</td>")
                    html_lines.append("</tr>")
                html_lines.append("</tbody>")
            html_lines.append("</table></div>")
            in_table = False
            table_rows = []

    def _flush_blockquote():
        nonlocal in_blockquote, blockquote_lines
        if in_blockquote and blockquote_lines:
            inner_text = "<br>".join([format_inline(bl) for bl in blockquote_lines])
            html_lines.append(f"<blockquote>{inner_text}</blockquote>")
            in_blockquote = False
            blockquote_lines = []

    for line in lines:
        stripped = line.strip()

        # Code Fences ```
        if stripped.startswith("```"):
            if in_code_block:
                raw_code = "\n".join(code_block_lines)
                escaped_code = html.escape(raw_code)
                lang_class = f' class="language-{code_block_lang}"' if code_block_lang else ""
                html_lines.append(f'<pre><code{lang_class}>{escaped_code}</code></pre>')
                in_code_block = False
                code_block_lines = []
                code_block_lang = ""
            else:
                _flush_list()
                _flush_table()
                _flush_blockquote()
                in_code_block = True
                code_block_lang = stripped.lstrip("`").strip()
                code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # Blockquotes >
        if stripped.startswith(">"):
            _flush_list()
            _flush_table()
            in_blockquote = True
            blockquote_lines.append(stripped.lstrip(">").strip())
            continue
        elif in_blockquote:
            _flush_blockquote()

        # Table Rows |
        if stripped.startswith("|") and stripped.endswith("|"):
            _flush_list()
            _flush_blockquote()
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not in_table:
                in_table = True
                table_rows = [cells]
            else:
                table_rows.append(cells)
            continue
        elif in_table:
            _flush_table()

        # Lists (- or * or 1.)
        unordered_match = re.match(r"^[-*]\s+(.*)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)

        if unordered_match:
            _flush_blockquote()
            _flush_table()
            if not in_list or list_type != "ul":
                _flush_list()
                html_lines.append("<ul>")
                in_list = True
                list_type = "ul"
            html_lines.append(f"<li>{format_inline(unordered_match.group(1))}</li>")
            continue
        elif ordered_match:
            _flush_blockquote()
            _flush_table()
            if not in_list or list_type != "ol":
                _flush_list()
                html_lines.append("<ol>")
                in_list = True
                list_type = "ol"
            html_lines.append(f"<li>{format_inline(ordered_match.group(1))}</li>")
            continue
        elif in_list:
            _flush_list()

        if not stripped:
            continue

        if stripped in ("---", "***", "___"):
            html_lines.append("<hr>")
            continue

        if stripped.startswith("#### "):
            html_lines.append(f"<h4>{format_inline(stripped[5:])}</h4>")
            continue
        elif stripped.startswith("### "):
            html_lines.append(f"<h3>{format_inline(stripped[4:])}</h3>")
            continue
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{format_inline(stripped[3:])}</h2>")
            continue
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{format_inline(stripped[2:])}</h1>")
            continue

        img_match = re.match(r"^!\[(.*?)\]\((.*?)\)$", stripped)
        if img_match:
            alt = html.escape(img_match.group(1), quote=True)
            raw_src = img_match.group(2)
            src = sanitize_url(raw_src, is_image=True)
            html_lines.append(f'<div class="screenshot-container"><img src="{src}" alt="{alt}" class="screenshot-img"><p class="screenshot-caption">{alt}</p></div>')
            continue

        html_lines.append(f"<p>{format_inline(stripped)}</p>")

    _flush_list()
    _flush_table()
    _flush_blockquote()

    if in_code_block and code_block_lines:
        raw_code = "\n".join(code_block_lines)
        escaped_code = html.escape(raw_code)
        html_lines.append(f'<pre><code>{escaped_code}</code></pre>')

    return "\n".join(html_lines)
