"""
Assets, CSS Stylesheets, and Media Encoding for SpectreHUD HTML Reports.
"""

import base64
import mimetypes
from pathlib import Path
from typing import Optional

from core.logger import get_logger
from ui.styles.fonts import get_report_font_stack

logger = get_logger(__name__)

MAX_EMBED_IMAGE_FILE_SIZE: int = 15 * 1024 * 1024  # 15 MB per image
MAX_EMBEDDED_IMAGES: int = 25
MAX_TOTAL_IMAGE_BYTES: int = 50 * 1024 * 1024  # 50 MB total session budget


class ImageEmbeddingBudget:
    """Tracks and enforces global image count and memory limits during HTML export."""

    def __init__(self, max_images: int = MAX_EMBEDDED_IMAGES, max_total_bytes: int = MAX_TOTAL_IMAGE_BYTES):
        self.max_images = max_images
        self.max_total_bytes = max_total_bytes
        self.embedded_count: int = 0
        self.embedded_bytes: int = 0

    def can_embed(self, file_size: int) -> bool:
        if self.embedded_count >= self.max_images:
            return False
        if self.embedded_bytes + file_size > self.max_total_bytes:
            return False
        return True

    def record(self, file_size: int) -> None:
        self.embedded_count += 1
        self.embedded_bytes += file_size

REPORT_CSS = """
:root {
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
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    background-color: var(--bg-color);
    color: var(--text-main);
    font-family: __REPORT_FONT_STACK__;
    font-size: 14px;
    line-height: 1.6;
    padding: 24px 16px;
}

.report-wrapper {
    max-width: 980px;
    margin: 0 auto;
    background-color: var(--container-bg);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
    overflow: hidden;
}

.report-header {
    background: linear-gradient(135deg, #161b22 0%, #0d1926 100%);
    border-bottom: 2px solid var(--accent-cyan);
    padding: 24px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
}

.brand-title {
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 1.5px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.brand-badge {
    background: linear-gradient(90deg, #00e5ff, #388bfd);
    color: #040d14;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 4px;
    text-transform: uppercase;
}

.header-meta {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 12px;
    color: var(--text-muted);
}

.meta-item {
    background-color: rgba(22, 27, 34, 0.8);
    border: 1px solid var(--border-color);
    border-radius: 5px;
    padding: 4px 10px;
}

.meta-item strong {
    color: var(--accent-blue);
}

.action-bar {
    background-color: #121820;
    border-bottom: 1px solid var(--border-color);
    padding: 10px 32px;
    display: flex;
    justify-content: flex-end;
    gap: 12px;
}

.btn-action {
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
}

.btn-action:hover {
    background-color: var(--accent-blue);
    color: #040d14;
    border-color: var(--accent-blue);
}

.report-body {
    padding: 32px;
}

h1, h2, h3, h4 {
    font-weight: 700;
    line-height: 1.3;
}

h1 {
    color: #ffffff;
    font-size: 24px;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 10px;
    margin-top: 10px;
    margin-bottom: 16px;
}

h2 {
    color: var(--accent-cyan);
    font-size: 18px;
    border-bottom: 1px solid rgba(48, 54, 61, 0.6);
    padding-bottom: 6px;
    margin-top: 28px;
    margin-bottom: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
}

h3 {
    color: var(--accent-blue);
    font-size: 15px;
    margin-top: 20px;
    margin-bottom: 8px;
}

h4 {
    color: #a5d6ff;
    font-size: 14px;
    margin-top: 16px;
    margin-bottom: 6px;
}

p {
    margin-bottom: 12px;
    color: var(--text-main);
}

hr {
    border: 0;
    border-top: 1px solid var(--border-color);
    margin: 24px 0;
}

pre {
    background-color: var(--code-bg);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--accent-green);
    border-radius: 6px;
    padding: 12px 16px;
    margin: 12px 0;
    overflow-x: auto;
}

code {
    font-family: 'Consolas', 'Cascadia Code', 'Fira Code', monospace;
    font-size: 12.5px;
    color: var(--accent-green);
}

p code, li code, blockquote code, td code {
    background-color: rgba(22, 27, 34, 0.9);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 2px 5px;
    font-size: 12px;
    color: var(--accent-gold);
}

blockquote {
    background-color: rgba(22, 27, 34, 0.6);
    border-left: 4px solid var(--accent-blue);
    border-radius: 0 6px 6px 0;
    padding: 10px 16px;
    margin: 14px 0;
    color: var(--text-muted);
    font-style: italic;
}

ul, ol {
    padding-left: 24px;
    margin-bottom: 14px;
}

li {
    margin-bottom: 4px;
}

a {
    color: var(--accent-blue);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
    color: var(--accent-cyan);
}

.screenshot-container {
    margin: 18px 0;
    background-color: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 8px;
    text-align: center;
}

.screenshot-img {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    display: block;
    margin: 0 auto;
}

/* Editable exports allow evidence images to be resized directly in-browser. */
main.report-body img {
    resize: both;
    overflow: hidden;
    max-width: 100%;
    display: inline-block;
}

.screenshot-caption {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 6px;
    font-style: italic;
}

.table-container {
    overflow-x: auto;
    margin: 14px 0;
}

table {
    width: 100%;
    border-collapse: collapse;
    border: 1px solid var(--border-color);
    font-size: 13px;
}

th, td {
    padding: 8px 12px;
    text-align: left;
    border: 1px solid var(--border-color);
}

th {
    background-color: #1c2128;
    color: var(--accent-cyan);
    font-weight: 600;
}

tr:nth-child(even) {
    background-color: rgba(22, 27, 34, 0.5);
}

.report-footer {
    border-top: 1px solid var(--border-color);
    padding: 16px 32px;
    background-color: #090d12;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    color: var(--text-muted);
}

.severity-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 11px;
    text-transform: uppercase;
}
.severity-critical { background-color: rgba(248, 81, 73, 0.2); color: #f85149; border: 1px solid #f85149; }
.severity-high { background-color: rgba(219, 109, 40, 0.2); color: #db6d28; border: 1px solid #db6d28; }
.severity-medium { background-color: rgba(210, 153, 34, 0.2); color: #d29922; border: 1px solid #d29922; }
.severity-low { background-color: rgba(63, 185, 80, 0.2); color: #3fb950; border: 1px solid #3fb950; }

@media print {
    body {
        background-color: #ffffff;
        color: #1f2328;
        padding: 0;
    }

    .report-wrapper {
        border: none;
        box-shadow: none;
        max-width: 100%;
    }

    .action-bar, .no-print {
        display: none !important;
    }

    main.report-body img {
        resize: none;
    }

    .report-header {
        background: #f6f8fa;
        border-bottom: 2px solid #0969da;
        color: #1f2328;
    }

    .brand-title {
        color: #1f2328;
    }

    h1, h2, h3, h4 {
        color: #0969da;
    }

    pre {
        background-color: #f6f8fa;
        border: 1px solid #d0d7de;
        border-left: 3px solid #1a7f37;
    }

    code {
        color: #1a7f37;
    }

    p code, li code, blockquote code, td code {
        background-color: #eff1f3;
        border-color: #d0d7de;
        color: #9a6700;
    }

    .screenshot-container {
        background-color: #f6f8fa;
        border-color: #d0d7de;
    }

    .report-footer {
        background-color: #ffffff;
        border-top: 1px solid #d0d7de;
    }
}
"""


REPORT_LIGHT_CSS = """
/* Light export theme: optimized for client review and printed hand-outs. */
:root {
    --bg-color: #f6f8fa;
    --container-bg: #ffffff;
    --card-bg: #f6f8fa;
    --border-color: #d0d7de;
    --text-main: #1f2328;
    --text-muted: #57606a;
    --code-bg: #f6f8fa;
}

.report-wrapper { box-shadow: 0 8px 24px rgba(31, 35, 40, 0.12); }
.report-header { background: linear-gradient(135deg, #f6f8fa 0%, #ddf4ff 100%); }
.brand-title, h1, h2, h3, h4 { color: #1f2328; }
.meta-item, .action-bar { background-color: #f6f8fa; }
.btn-action { background-color: #ffffff; color: #1f2328; }
pre { background-color: #f6f8fa; border-color: #d0d7de; }
code { color: #1a7f37; }
p code, li code, blockquote code, td code { background-color: #eff1f3; border-color: #d0d7de; color: #9a6700; }
blockquote { background-color: #f6f8fa; }
.screenshot-container { background-color: #f6f8fa; border-color: #d0d7de; }
.report-footer { background-color: #ffffff; border-color: #d0d7de; }
th { background-color: #f6f8fa; }
tr:nth-child(even) { background-color: #f6f8fa; }
"""


def get_report_css(theme: str = "dark", report_font_key: str = "segoe_ui") -> str:
    """Returns report CSS for the selected standalone export theme."""
    report_css = REPORT_CSS.replace("__REPORT_FONT_STACK__", get_report_font_stack(report_font_key))
    return report_css + (REPORT_LIGHT_CSS if theme.lower() == "light" else "")


def encode_image_base64(image_path: Path) -> Optional[str]:
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
