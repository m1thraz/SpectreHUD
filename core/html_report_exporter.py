import base64
import html
import mimetypes
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from core.logger import get_logger
from core.atomic_write import atomic_write_text

logger = get_logger("html_report_exporter")

MAX_EMBED_IMAGE_FILE_SIZE: int = 15 * 1024 * 1024  # 15 MB


class HtmlReportExporter:
    """Exports markdown reports to standalone, professionally styled HTML with base64 embedded images."""

    @staticmethod
    def _encode_image_base64(image_path: Path) -> Optional[str]:
        """Encodes an image file to a base64 data URI."""
        try:
            if not image_path.exists() or not image_path.is_file():
                return None
            if image_path.stat().st_size > MAX_EMBED_IMAGE_FILE_SIZE:
                logger.warning(f"Image too large to embed as base64 ({image_path.stat().st_size} bytes): {image_path}")
                return None

            mime_type, _ = mimetypes.guess_type(str(image_path))
            if not mime_type or not mime_type.startswith("image/"):
                mime_type = "image/png"

            img_bytes = image_path.read_bytes()
            b64_str = base64.b64encode(img_bytes).decode("ascii")
            return f"data:{mime_type};base64,{b64_str}"
        except OSError as e:
            logger.warning(f"Failed to read image for base64 embedding {image_path}: {e}")
            return None

    @classmethod
    def _resolve_and_embed_images(cls, md_text: str, project_dir: Optional[Path]) -> str:
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
                        b64_uri = cls._encode_image_base64(cand_resolved)
                        if b64_uri:
                            return f"![{alt_text}]({b64_uri})"
                except (OSError, RuntimeError):
                    continue

            return match.group(0)

        img_pattern = re.compile(r"!\[(.*?)\]\((.*?)\)")
        return img_pattern.sub(_replace_img, md_text)

    @staticmethod
    def _sanitize_url(url: str, is_image: bool = False) -> str:
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

    @classmethod
    def markdown_to_html(cls, md_text: str, project_dir: Optional[Path] = None) -> str:
        """Converts Markdown text to HTML body structure."""
        processed_md = cls._resolve_and_embed_images(md_text, project_dir)

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
            nonlocal in_list, list_type
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
                    html_lines.append(f"<th>{cls._format_inline(cell)}</th>")
                html_lines.append("</tr></thead>")
                if len(table_rows) > 1:
                    html_lines.append("<tbody>")
                    for row in table_rows[1:]:
                        html_lines.append("<tr>")
                        for cell in row:
                            html_lines.append(f"<td>{cls._format_inline(cell)}</td>")
                        html_lines.append("</tr>")
                    html_lines.append("</tbody>")
                html_lines.append("</table></div>")
                in_table = False
                table_rows = []

        def _flush_blockquote():
            nonlocal in_blockquote, blockquote_lines
            if in_blockquote and blockquote_lines:
                inner_text = "<br>".join([cls._format_inline(bl) for bl in blockquote_lines])
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
                html_lines.append(f"<li>{cls._format_inline(unordered_match.group(1))}</li>")
                continue
            elif ordered_match:
                _flush_blockquote()
                _flush_table()
                if not in_list or list_type != "ol":
                    _flush_list()
                    html_lines.append("<ol>")
                    in_list = True
                    list_type = "ol"
                html_lines.append(f"<li>{cls._format_inline(ordered_match.group(1))}</li>")
                continue
            elif in_list:
                _flush_list()

            if not stripped:
                continue

            if stripped in ("---", "***", "___"):
                html_lines.append("<hr>")
                continue

            if stripped.startswith("#### "):
                html_lines.append(f"<h4>{cls._format_inline(stripped[5:])}</h4>")
                continue
            elif stripped.startswith("### "):
                html_lines.append(f"<h3>{cls._format_inline(stripped[4:])}</h3>")
                continue
            elif stripped.startswith("## "):
                html_lines.append(f"<h2>{cls._format_inline(stripped[3:])}</h2>")
                continue
            elif stripped.startswith("# "):
                html_lines.append(f"<h1>{cls._format_inline(stripped[2:])}</h1>")
                continue

            img_match = re.match(r"^!\[(.*?)\]\((.*?)\)$", stripped)
            if img_match:
                alt = html.escape(img_match.group(1), quote=True)
                raw_src = img_match.group(2)
                src = cls._sanitize_url(raw_src, is_image=True)
                html_lines.append(f'<div class="screenshot-container"><img src="{src}" alt="{alt}" class="screenshot-img"><p class="screenshot-caption">{alt}</p></div>')
                continue

            html_lines.append(f"<p>{cls._format_inline(stripped)}</p>")

        _flush_list()
        _flush_table()
        _flush_blockquote()

        if in_code_block and code_block_lines:
            raw_code = "\n".join(code_block_lines)
            escaped_code = html.escape(raw_code)
            html_lines.append(f'<pre><code>{escaped_code}</code></pre>')

        return "\n".join(html_lines)

    @classmethod
    def _format_inline(cls, text: str) -> str:
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
            src = cls._sanitize_url(m.group(2), is_image=True)
            img_tokens.append(f'<img src="{src}" alt="{alt}" class="inline-img">')
            return token

        res = re.sub(r"!\[(.*?)\]\((.*?)\)", _img_sub, res)

        link_tokens: List[str] = []
        def _link_sub(m: re.Match) -> str:
            token = f"@@SPECTRE_LINKTOKEN{len(link_tokens)}@@"
            ltext = html.escape(m.group(1))
            url = cls._sanitize_url(m.group(2), is_image=False)
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

    @classmethod
    def build_full_html(
        cls, 
        markdown_content: str, 
        project_dir: Optional[Path] = None, 
        project_name: Optional[str] = None,
        target_ip: Optional[str] = None
    ) -> str:
        """Generates the full, styled HTML document ready for export."""
        body_html = cls.markdown_to_html(markdown_content, project_dir=project_dir)
        pname = project_name or (project_dir.name if project_dir else "Target")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target_str = target_ip if target_ip and target_ip != "all" else "N/A"

        return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SpectreHUD // Pentest Report - {html.escape(pname)}</title>
    <style>
        :root {{
            --bg-color: #090d12;
            --container-bg: #0d1117;
            --card-bg: #161b22;
            --border-color: #30363d;
            --accent-blue: #58a6ff;
            --accent-cyan: #00e5ff;
            --accent-green: #39d353;
            --accent-gold: #e3b341;
            --text-main: #e6edf3;
            --text-muted: #8b949e;
            --code-bg: #040d14;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Inter', 'Roboto', 'Helvetica Neue', Arial, sans-serif;
            font-size: 14px;
            line-height: 1.6;
            padding: 24px 16px;
        }}

        .report-wrapper {{
            max-width: 980px;
            margin: 0 auto;
            background-color: var(--container-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
            overflow: hidden;
        }}

        .report-header {{
            background: linear-gradient(135deg, #161b22 0%, #0d1926 100%);
            border-bottom: 2px solid var(--accent-cyan);
            padding: 24px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .brand-title {{
            font-size: 22px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: 1.5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .brand-badge {{
            background: linear-gradient(90deg, #00e5ff, #388bfd);
            color: #040d14;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }}

        .header-meta {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            font-size: 12px;
            color: var(--text-muted);
        }}

        .meta-item {{
            background-color: rgba(22, 27, 34, 0.8);
            border: 1px solid var(--border-color);
            border-radius: 5px;
            padding: 4px 10px;
        }}

        .meta-item strong {{
            color: var(--accent-blue);
        }}

        .action-bar {{
            background-color: #121820;
            border-bottom: 1px solid var(--border-color);
            padding: 10px 32px;
            display: flex;
            justify-content: flex-end;
            gap: 12px;
        }}

        .btn-action {{
            background-color: var(--card-bg);
            color: var(--text-main);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .btn-action:hover {{
            background-color: var(--accent-blue);
            color: #040d14;
            border-color: var(--accent-blue);
        }}

        .report-body {{
            padding: 32px;
        }}

        h1, h2, h3, h4 {{
            font-weight: 700;
            line-height: 1.3;
        }}

        h1 {{
            color: #ffffff;
            font-size: 24px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            margin-top: 10px;
            margin-bottom: 16px;
        }}

        h2 {{
            color: var(--accent-cyan);
            font-size: 18px;
            border-bottom: 1px solid rgba(48, 54, 61, 0.6);
            padding-bottom: 6px;
            margin-top: 28px;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        h3 {{
            color: var(--accent-blue);
            font-size: 15px;
            margin-top: 20px;
            margin-bottom: 8px;
        }}

        h4 {{
            color: #a5d6ff;
            font-size: 14px;
            margin-top: 16px;
            margin-bottom: 6px;
        }}

        p {{
            margin-bottom: 12px;
            color: var(--text-main);
        }}

        hr {{
            border: 0;
            border-top: 1px solid var(--border-color);
            margin: 24px 0;
        }}

        pre {{
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            border-left: 3px solid var(--accent-green);
            border-radius: 6px;
            padding: 12px 16px;
            margin: 12px 0;
            overflow-x: auto;
        }}

        code {{
            font-family: 'Consolas', 'Cascadia Code', 'Fira Code', monospace;
            font-size: 12.5px;
            color: var(--accent-green);
        }}

        p code, li code, blockquote code, td code {{
            background-color: rgba(22, 27, 34, 0.9);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 2px 5px;
            font-size: 12px;
            color: var(--accent-gold);
        }}

        blockquote {{
            background-color: rgba(22, 27, 34, 0.6);
            border-left: 4px solid var(--accent-blue);
            border-radius: 0 6px 6px 0;
            padding: 10px 16px;
            margin: 14px 0;
            color: var(--text-muted);
            font-style: italic;
        }}

        ul, ol {{
            padding-left: 24px;
            margin-bottom: 14px;
        }}

        li {{
            margin-bottom: 4px;
        }}

        a {{
            color: var(--accent-blue);
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
            color: var(--accent-cyan);
        }}

        .screenshot-container {{
            margin: 18px 0;
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 8px;
            text-align: center;
        }}

        .screenshot-img {{
            max-width: 100%;
            height: auto;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            display: block;
            margin: 0 auto;
        }}

        .screenshot-caption {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 6px;
            font-style: italic;
        }}

        .table-container {{
            overflow-x: auto;
            margin: 14px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            border: 1px solid var(--border-color);
            font-size: 13px;
        }}

        th, td {{
            padding: 8px 12px;
            text-align: left;
            border: 1px solid var(--border-color);
        }}

        th {{
            background-color: #1c2128;
            color: var(--accent-cyan);
            font-weight: 600;
        }}

        tr:nth-child(even) {{
            background-color: rgba(22, 27, 34, 0.5);
        }}

        .report-footer {{
            border-top: 1px solid var(--border-color);
            padding: 16px 32px;
            background-color: #090d12;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: var(--text-muted);
        }}

        @media print {{
            body {{
                background-color: #ffffff;
                color: #1f2328;
                padding: 0;
            }}

            .report-wrapper {{
                border: none;
                box-shadow: none;
                max-width: 100%;
            }}

            .action-bar, .no-print {{
                display: none !important;
            }}

            .report-header {{
                background: #f6f8fa;
                border-bottom: 2px solid #0969da;
                color: #1f2328;
            }}

            .brand-title {{
                color: #1f2328;
            }}

            h1, h2, h3, h4 {{
                color: #0969da;
            }}

            pre {{
                background-color: #f6f8fa;
                border: 1px solid #d0d7de;
                border-left: 3px solid #1a7f37;
            }}

            code {{
                color: #1a7f37;
            }}

            p code, li code, blockquote code, td code {{
                background-color: #eff1f3;
                border-color: #d0d7de;
                color: #9a6700;
            }}

            .screenshot-container {{
                background-color: #f6f8fa;
                border-color: #d0d7de;
            }}

            .report-footer {{
                background-color: #ffffff;
                border-top: 1px solid #d0d7de;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-wrapper">
        <header class="report-header">
            <div>
                <div class="brand-title">
                    <span>SPECTRE // HUD</span>
                    <span class="brand-badge">PENTEST REPORT</span>
                </div>
            </div>
            <div class="header-meta">
                <div class="meta-item"><strong>Box:</strong> {html.escape(pname)}</div>
                <div class="meta-item"><strong>Target:</strong> {html.escape(target_str)}</div>
                <div class="meta-item"><strong>Datum:</strong> {now_str}</div>
            </div>
        </header>

        <div class="action-bar no-print">
            <button class="btn-action" onclick="window.print()">🖨 Drucken / PDF Exportieren</button>
        </div>

        <main class="report-body">
            {body_html}
        </main>

        <footer class="report-footer">
            <span>Generated with SpectreHUD Pentest &amp; CTF Companion</span>
            <span>{now_str}</span>
        </footer>
    </div>
</body>
</html>
"""

    @classmethod
    def export_to_file(
        cls, 
        markdown_content: str, 
        output_path: Path, 
        project_dir: Optional[Path] = None,
        project_name: Optional[str] = None,
        target_ip: Optional[str] = None
    ) -> bool:
        """Renders HTML from Markdown and writes it atomically to output_path."""
        out = Path(output_path)
        if out.suffix.lower() != ".html":
            out = out.with_suffix(".html")

        full_html = cls.build_full_html(
            markdown_content=markdown_content,
            project_dir=project_dir,
            project_name=project_name,
            target_ip=target_ip
        )
        try:
            return atomic_write_text(out, full_html, encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to write HTML report to {out}: {e}", exc_info=True)
            return False
