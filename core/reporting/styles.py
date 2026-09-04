"""CSS stylesheets for standalone SpectreHUD reports."""

from core.fonts import get_report_font_stack


REPORT_BASE_CSS = """
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

/* Screen-mode styling for manual pagebreak marker */
@media screen {
    .spectre-page-break {
        position: relative;
        margin: 2.5rem 0;
        border-top: 1px dashed rgba(88, 166, 255, 0.4);
        text-align: center;
        height: 0;
    }
    .spectre-page-break::after {
        content: "PAGE BREAK";
        position: absolute;
        top: -10px;
        left: 50%;
        transform: translateX(-50%);
        background-color: var(--container-bg, #0d1117);
        padding: 2px 14px;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
        color: var(--text-muted, #8b949e);
        border-radius: 4px;
        border: 1px solid rgba(88, 166, 255, 0.25);
        text-transform: uppercase;
        user-select: none;
    }
    html[lang="de"] .spectre-page-break::after {
        content: "SEITENUMBRUCH";
    }
}
"""

REPORT_PRINT_CSS = """
/* Print & PDF Export Styling: Ensures clean pagination and prevents clipping of codeblocks, tables, and media */
@media print {
    @page {
        margin: 1.5cm;
    }

    body {
        background-color: #ffffff !important;
        color: #1f2328 !important;
        padding: 0 !important;
    }

    .report-wrapper {
        border: none !important;
        box-shadow: none !important;
        max-width: 100% !important;
        width: 100% !important;
        margin: 0 !important;
        background-color: transparent !important;
    }

    .action-bar, .no-print {
        display: none !important;
    }

    main.report-body img {
        resize: none !important;
    }

    .report-header {
        background: #f6f8fa !important;
        border-bottom: 2px solid #0969da !important;
        color: #1f2328 !important;
        page-break-after: avoid;
        break-after: avoid;
    }

    .brand-title {
        color: #1f2328 !important;
    }

    .brand-badge {
        border: 1px solid #0969da !important;
    }

    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
        page-break-after: avoid;
        break-after: avoid;
        page-break-inside: avoid;
        break-inside: avoid;
    }

    /* Print styling for codeblocks: no horizontal clipping, clean line wrapping, preserve indentation */
    pre {
        background-color: #f6f8fa !important;
        border: 1px solid #d0d7de !important;
        border-left: 3px solid #1a7f37 !important;
        color: #1f2328 !important;
        overflow: visible !important;
        overflow-x: visible !important;
        overflow-y: visible !important;
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
        max-height: none !important;
        page-break-inside: auto;
        break-inside: auto;
    }

    pre code, code {
        color: #1a7f37 !important;
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-wrap: anywhere !important;
        word-break: break-word !important;
    }

    p code, li code, blockquote code, td code {
        background-color: #eff1f3 !important;
        border-color: #d0d7de !important;
        color: #9a6700 !important;
        white-space: normal !important;
        word-wrap: break-word !important;
        overflow-wrap: anywhere !important;
    }

    blockquote {
        background-color: #f6f8fa !important;
        border-left: 4px solid #0969da !important;
        color: #57606a !important;
        page-break-inside: avoid;
        break-inside: avoid;
    }

    figure, .screenshot-container {
        background-color: #f6f8fa !important;
        border-color: #d0d7de !important;
        page-break-inside: avoid;
        break-inside: avoid;
    }

    .screenshot-img, img {
        max-width: 100% !important;
        height: auto !important;
        page-break-inside: avoid;
        break-inside: avoid;
    }

    .screenshot-caption, .screenshot-container p {
        page-break-before: avoid;
        break-before: avoid;
    }

    .finding-header, .finding-meta {
        page-break-inside: avoid;
        break-inside: avoid;
    }

    .table-container {
        overflow: visible !important;
        overflow-x: visible !important;
    }

    table {
        page-break-inside: auto;
        break-inside: auto;
    }

    thead {
        display: table-header-group;
    }

    tfoot {
        display: table-footer-group;
    }

    tr, tbody tr {
        page-break-inside: avoid;
        break-inside: avoid;
    }

    th, td {
        page-break-inside: avoid;
        break-inside: avoid;
    }

    th {
        background-color: #f6f8fa !important;
        color: #1f2328 !important;
    }

    td {
        border-color: #d0d7de !important;
    }

    /* Manual page break marker: forces a new page and hides screen styling */
    .spectre-page-break {
        display: block !important;
        break-before: page !important;
        page-break-before: always !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        visibility: hidden !important;
    }

    .report-footer {
        background-color: #ffffff !important;
        border-top: 1px solid #d0d7de !important;
        color: #57606a !important;
        page-break-before: avoid;
        break-before: avoid;
    }
}
"""

REPORT_CSS = REPORT_BASE_CSS + "\n" + REPORT_PRINT_CSS

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
.brand-title, h1, h2, h3, h4, h5, h6 { color: #000000 !important; }
h2 { border-bottom-color: #d0d7de; }
.meta-item, .action-bar { background-color: #f6f8fa; }
.btn-action { background-color: #ffffff; color: #1f2328; }
pre { background-color: #f6f8fa; border-color: #d0d7de; }
code { color: #1a7f37; }
p code, li code, blockquote code, td code { background-color: #eff1f3; border-color: #d0d7de; color: #9a6700; }
blockquote { background-color: #f6f8fa; }
.screenshot-container { background-color: #f6f8fa; border-color: #d0d7de; }
.report-footer { background-color: #ffffff; border-color: #d0d7de; }
th { background-color: #f6f8fa; color: #1f2328; }
tr:nth-child(even) { background-color: #f6f8fa; }
.spectre-page-break { border-top-color: #d0d7de; }
.spectre-page-break::after { background-color: #ffffff; color: #57606a; border-color: #d0d7de; }
"""


def get_report_css(theme: str = "dark", report_font_key: str = "segoe_ui") -> str:
    """Returns report CSS for the selected standalone export theme with print overrides."""
    base = REPORT_BASE_CSS.replace(
        "__REPORT_FONT_STACK__", get_report_font_stack(report_font_key)
    )
    theme_css = ("\n" + REPORT_LIGHT_CSS) if theme.lower() == "light" else ""
    return f"{base}{theme_css}\n{REPORT_PRINT_CSS}"
