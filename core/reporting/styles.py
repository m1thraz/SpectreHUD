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
.severity-info { background-color: rgba(88, 166, 255, 0.15); color: #58a6ff; border: 1px solid #58a6ff; }

.report-finding {
    margin: 18px 0 24px;
    padding: 16px 18px;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--accent-blue);
    border-radius: 6px;
}

.finding-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 10px;
}

.report-finding .finding-header h3 {
    margin: 0;
}

.finding-severity {
    flex: 0 0 auto;
}

.finding-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 20px;
    margin: 0 0 14px;
    color: var(--text-muted);
    font-size: 11px;
}

.finding-meta-item {
    display: flex;
    gap: 6px;
}

.finding-meta-label {
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.finding-description h4,
.finding-recommendation h4 {
    margin-top: 12px;
}

.spectre-spacer { display: block; break-inside: avoid; }
.spectre-spacer.spacer-small { height: 0.5rem; }
.spectre-spacer.spacer-medium { height: 1rem; }
.spectre-spacer.spacer-large { height: 2rem; }

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

REPORT_PROFESSIONAL_CSS = """
/* Professional Print is deliberately isolated from the editable interactive report. */
body[data-report-profile="professional_print"] {
    --report-text: #20272d;
    --report-muted: #66717a;
    --report-border: #d7dde1;
    --report-surface: #f5f7f8;
    --report-accent: #315f66;
    --report-accent-soft: #e7eff0;
    --severity-critical: #9e2f35;
    --severity-high: #a9552d;
    --severity-medium: #8a6b18;
    --severity-low: #3f704d;
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 28px;
    --space-section: 52px;
    background: #e9edef;
    color: var(--report-text);
    font-size: 10.5pt;
    line-height: 1.62;
    padding: 24px;
}

body[data-report-profile="professional_print"] .report-wrapper {
    width: 210mm;
    max-width: 100%;
    margin: 0 auto;
    background: #ffffff;
    border: 0;
    border-radius: 0;
    box-shadow: 0 10px 30px rgba(32, 39, 45, 0.12);
    overflow: visible;
}

body[data-report-profile="professional_print"] .report-header {
    display: none;
}

body[data-report-profile="professional_print"] .action-bar {
    background: #ffffff;
    border-bottom: 1px solid var(--report-border);
    color: var(--report-muted);
    padding: 10px 18mm;
    align-items: center;
}

body[data-report-profile="professional_print"] .print-guidance {
    margin-right: auto;
    font-size: 10px;
    letter-spacing: 0.02em;
}

body[data-report-profile="professional_print"] .btn-action {
    background: #ffffff;
    border-color: var(--report-border);
    border-radius: 2px;
    color: var(--report-accent);
}

body[data-report-profile="professional_print"] .report-body {
    padding: 0 18mm 18mm;
    color: var(--report-text);
}

body[data-report-profile="professional_print"] .report-cover {
    min-height: 255mm;
    display: flex;
    flex-direction: column;
    padding: 22mm 0 14mm;
    break-after: page;
    page-break-after: always;
}

body[data-report-profile="professional_print"] .report-cover-topline {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 28px;
}

body[data-report-profile="professional_print"] .report-cover-kicker {
    color: var(--report-accent);
    font-size: 10px;
    font-weight: 750;
    letter-spacing: 0.18em;
}

body[data-report-profile="professional_print"] .report-cover-severity {
    padding: 1px 0 2px;
    font-size: 7.5px;
    font-weight: 700;
    letter-spacing: 0.14em;
}

body[data-report-profile="professional_print"] .report-cover-title-block {
    margin-top: 62mm;
    max-width: 145mm;
}

body[data-report-profile="professional_print"] .report-cover-title {
    margin: 0;
    padding: 0;
    border: 0;
    color: var(--report-text) !important;
    font-size: 34pt;
    font-weight: 650;
    letter-spacing: -0.035em;
    line-height: 1.08;
}

body[data-report-profile="professional_print"] .report-cover-rule {
    width: 36mm;
    margin-top: 12mm;
    border-top: 3px solid var(--report-accent);
}

body[data-report-profile="professional_print"] .report-cover-meta {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10mm 16mm;
    margin-top: auto;
    padding-top: 18mm;
    border-top: 1px solid var(--report-border);
}

body[data-report-profile="professional_print"] .report-cover-meta-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    min-width: 0;
}

body[data-report-profile="professional_print"] .report-cover-meta-label {
    color: #899198;
    font-size: 7px;
    font-weight: 650;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

body[data-report-profile="professional_print"] .report-cover-meta-value {
    color: var(--report-text);
    font-size: 11.5px;
    font-weight: 650;
    overflow-wrap: anywhere;
}

body[data-report-profile="professional_print"] .report-cover-brand {
    margin-top: 14mm;
    color: #a0a7ac;
    font-size: 6.5px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

body[data-report-profile="professional_print"] .report-section {
    margin-top: var(--space-section);
}

body[data-report-profile="professional_print"] .report-header-metadata {
    margin-top: 16mm;
}

body[data-report-profile="professional_print"] h1,
body[data-report-profile="professional_print"] h2,
body[data-report-profile="professional_print"] h3,
body[data-report-profile="professional_print"] h4 {
    color: var(--report-text) !important;
    display: block;
}

body[data-report-profile="professional_print"] .report-section > h2:first-child {
    margin: 0 0 var(--space-lg);
    padding: 0 0 var(--space-sm);
    border-bottom: 2px solid var(--report-accent);
    font-size: 21pt;
    font-weight: 620;
    letter-spacing: -0.02em;
}

body[data-report-profile="professional_print"] .report-section h3 {
    margin: 26px 0 10px;
    font-size: 13pt;
    font-weight: 650;
}

body[data-report-profile="professional_print"] .report-attack-path ol {
    margin: 0;
    padding: 1mm 0 1mm 24px;
    border-left: 1px solid var(--report-border);
}

body[data-report-profile="professional_print"] .report-attack-path li {
    margin: 0 0 12px;
    padding-left: 8px;
}

body[data-report-profile="professional_print"] .report-attack-path li::marker {
    color: var(--report-muted);
    font-size: 9pt;
    font-weight: 650;
}

body[data-report-profile="professional_print"] p {
    margin-bottom: 11px;
    color: var(--report-text);
}

body[data-report-profile="professional_print"] hr {
    margin: 28px 0;
    border-color: var(--report-border);
}

body[data-report-profile="professional_print"] .table-container {
    margin: 18px 0 24px;
    overflow: visible;
}

body[data-report-profile="professional_print"] table {
    border: 0;
    border-top: 2px solid var(--report-accent);
    border-bottom: 1px solid var(--report-border);
    color: var(--report-text);
    font-size: 9.5pt;
    table-layout: fixed;
}

body[data-report-profile="professional_print"] .findings-matrix th:nth-child(1),
body[data-report-profile="professional_print"] .findings-matrix td:nth-child(1) { width: 6%; }
body[data-report-profile="professional_print"] .findings-matrix th:nth-child(2),
body[data-report-profile="professional_print"] .findings-matrix td:nth-child(2) { width: 46%; }
body[data-report-profile="professional_print"] .findings-matrix th:nth-child(3),
body[data-report-profile="professional_print"] .findings-matrix td:nth-child(3) { width: 15%; }
body[data-report-profile="professional_print"] .findings-matrix th:nth-child(4),
body[data-report-profile="professional_print"] .findings-matrix td:nth-child(4) { width: 19%; }
body[data-report-profile="professional_print"] .findings-matrix th:nth-child(5),
body[data-report-profile="professional_print"] .findings-matrix td:nth-child(5) { width: 14%; }

body[data-report-profile="professional_print"] .action-plan th:nth-child(1),
body[data-report-profile="professional_print"] .action-plan td:nth-child(1) { width: 9%; }
body[data-report-profile="professional_print"] .action-plan th:nth-child(2),
body[data-report-profile="professional_print"] .action-plan td:nth-child(2) { width: 72%; }
body[data-report-profile="professional_print"] .action-plan th:nth-child(3),
body[data-report-profile="professional_print"] .action-plan td:nth-child(3) { width: 19%; }

body[data-report-profile="professional_print"] .action-plan th:first-child,
body[data-report-profile="professional_print"] .action-plan td:first-child {
    white-space: nowrap;
}

body[data-report-profile="professional_print"] th,
body[data-report-profile="professional_print"] td {
    padding: 8px 10px;
    border: 0;
    border-bottom: 1px solid var(--report-border);
    vertical-align: top;
    overflow-wrap: anywhere;
}

body[data-report-profile="professional_print"] th {
    background: var(--report-accent-soft);
    color: var(--report-muted);
    font-size: 8pt;
    font-weight: 650;
    letter-spacing: 0.04em;
}

body[data-report-profile="professional_print"] tr:nth-child(even) {
    background: var(--report-surface);
}

body[data-report-profile="professional_print"] pre {
    margin: 16px 0 22px;
    padding: 13px 15px;
    background: var(--report-surface);
    border: 1px solid var(--report-border);
    border-left: 3px solid var(--report-accent);
    border-radius: 0;
    color: var(--report-text);
    overflow: visible;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
}

body[data-report-profile="professional_print"] pre code,
body[data-report-profile="professional_print"] code {
    color: #304b50;
}

body[data-report-profile="professional_print"] blockquote {
    margin: 18px 0;
    padding: 10px 16px;
    background: var(--report-surface);
    border-left-color: var(--report-accent);
    border-radius: 0;
    color: var(--report-muted);
}

body[data-report-profile="professional_print"] .severity-pill,
body[data-report-profile="professional_print"] .report-cover-severity {
    background: transparent;
    border-width: 0 0 1px;
    border-radius: 0;
    padding: 1px 2px;
    font-size: 8.5px;
    letter-spacing: 0.08em;
}

body[data-report-profile="professional_print"] .severity-critical { color: var(--severity-critical); }
body[data-report-profile="professional_print"] .severity-high { color: var(--severity-high); }
body[data-report-profile="professional_print"] .severity-medium { color: var(--severity-medium); }
body[data-report-profile="professional_print"] .severity-low { color: var(--severity-low); }
body[data-report-profile="professional_print"] .severity-info { color: var(--report-muted); }

body[data-report-profile="professional_print"] .report-finding {
    margin: 12mm 0 15mm;
    padding: 0 0 0 5mm;
    background: transparent;
    border: 0;
    border-left: 1.5px solid var(--report-accent);
    border-radius: 0;
}

body[data-report-profile="professional_print"] .finding-header {
    margin-bottom: 4mm;
    padding-bottom: 3mm;
    border-bottom: 1px solid var(--report-border);
}

body[data-report-profile="professional_print"] .finding-header h3 {
    margin: 0;
    color: var(--report-text) !important;
    font-size: 14pt;
    line-height: 1.3;
}

body[data-report-profile="professional_print"] .finding-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 1.5mm 0;
    margin-bottom: 5mm;
    color: var(--report-muted);
}

body[data-report-profile="professional_print"] .finding-meta-item {
    min-width: 0;
    flex-direction: row;
    gap: 1.5mm;
    align-items: baseline;
}

body[data-report-profile="professional_print"] .finding-meta-item:not(:last-child)::after {
    content: "·";
    margin: 0 3mm;
    color: var(--report-border);
}

body[data-report-profile="professional_print"] .finding-meta-label {
    flex: 0 0 auto;
    color: #899198;
    font-size: 7pt;
    font-weight: 650;
    letter-spacing: 0.06em;
}

body[data-report-profile="professional_print"] .finding-meta-value {
    color: var(--report-text);
    min-width: 0;
    font-size: 9pt;
    overflow-wrap: anywhere;
}

body[data-report-profile="professional_print"] .finding-description h4,
body[data-report-profile="professional_print"] .finding-recommendation h4 {
    margin: 0 0 3mm;
    color: #7d878e !important;
    font-size: 7.25pt;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

body[data-report-profile="professional_print"] .finding-recommendation {
    margin-top: 6mm;
}

body[data-report-profile="professional_print"] .report-footer {
    display: none;
}

body[data-report-profile="professional_print"] .report-appendix::before {
    content: "APPENDIX";
    display: block;
    margin-bottom: 4mm;
    color: #899198;
    font-size: 7pt;
    font-weight: 700;
    letter-spacing: 0.18em;
}

html[lang="de"] body[data-report-profile="professional_print"] .report-appendix::before {
    content: "ANHANG";
}

@media print {
    body[data-report-profile="professional_print"] {
        background: #ffffff !important;
        padding: 0 !important;
    }

    body[data-report-profile="professional_print"] .report-wrapper {
        width: 100% !important;
        box-shadow: none !important;
    }

    body[data-report-profile="professional_print"] .report-body {
        padding: 0 !important;
    }

    body[data-report-profile="professional_print"] .report-cover {
        width: 210mm;
        min-height: 297mm;
        padding: 22mm 18mm 14mm;
    }

    body[data-report-profile="professional_print"] .report-section {
        margin-top: 12mm;
    }

    body[data-report-profile="professional_print"] h1,
    body[data-report-profile="professional_print"] h2,
    body[data-report-profile="professional_print"] h3,
    body[data-report-profile="professional_print"] h4,
    body[data-report-profile="professional_print"] .report-section > h2:first-child,
    body[data-report-profile="professional_print"] .report-section > h3:first-child {
        break-after: avoid;
        page-break-after: avoid;
    }

    body[data-report-profile="professional_print"] p,
    body[data-report-profile="professional_print"] li {
        orphans: 3;
        widows: 3;
    }

    body[data-report-profile="professional_print"] .report-finding {
        break-inside: avoid;
        page-break-inside: avoid;
    }

    body[data-report-profile="professional_print"] .finding-header,
    body[data-report-profile="professional_print"] .finding-meta {
        break-after: avoid;
        page-break-after: avoid;
        break-inside: avoid;
        page-break-inside: avoid;
    }

    body[data-report-profile="professional_print"] .finding-description h4,
    body[data-report-profile="professional_print"] .finding-recommendation h4 {
        break-after: avoid;
        page-break-after: avoid;
    }

    body[data-report-profile="professional_print"] pre {
        overflow: visible;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
        word-break: break-word;
        break-inside: avoid;
        page-break-inside: avoid;
    }

    body[data-report-profile="professional_print"] table {
        break-inside: auto;
        page-break-inside: auto;
    }

    body[data-report-profile="professional_print"] thead {
        display: table-header-group;
    }

    body[data-report-profile="professional_print"] tr,
    body[data-report-profile="professional_print"] tbody tr {
        break-inside: avoid;
        page-break-inside: avoid;
    }

    body[data-report-profile="professional_print"] .report-appendix {
        break-before: page;
        page-break-before: always;
        padding-top: 8mm;
    }

    body[data-report-profile="professional_print"] blockquote,
    body[data-report-profile="professional_print"] figure {
        break-inside: avoid;
        page-break-inside: avoid;
    }
}

@media screen and (max-width: 760px) {
    body[data-report-profile="professional_print"] {
        padding: 0;
    }

    body[data-report-profile="professional_print"] .report-body,
    body[data-report-profile="professional_print"] .action-bar {
        padding-left: 7vw;
        padding-right: 7vw;
    }

    body[data-report-profile="professional_print"] .report-cover-meta {
        grid-template-columns: 1fr;
    }
}
"""


def get_report_css(
    theme: str = "dark",
    report_font_key: str = "segoe_ui",
    profile: str = "interactive",
) -> str:
    """Returns report CSS for the selected standalone export theme with print overrides."""
    base = REPORT_BASE_CSS.replace(
        "__REPORT_FONT_STACK__", get_report_font_stack(report_font_key)
    )
    theme_css = ("\n" + REPORT_LIGHT_CSS) if theme.lower() == "light" else ""
    professional_css = (
        "\n" + REPORT_PROFESSIONAL_CSS if profile == "professional_print" else ""
    )
    return f"{base}{theme_css}\n{REPORT_PRINT_CSS}{professional_css}"
