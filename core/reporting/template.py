"""
HTML Document Template Assembly for SpectreHUD Reports.
"""

import html
import json
from datetime import datetime
from typing import Optional

from core.reporting.styles import get_report_css


def _css_string(value: str) -> str:
    """Quote untrusted report metadata for use in a generated CSS string."""
    escaped = []
    for char in value.replace("\r", " ").replace("\n", " "):
        if char in {'\\', '"', "<", ">", "&"} or ord(char) < 0x20:
            escaped.append(f"\\{ord(char):x} ")
        else:
            escaped.append(char)
    return f'"{"".join(escaped)}"'


def _professional_page_css(
    project_name: str,
    classification: Optional[str],
    language: str,
    report_label: Optional[str] = None,
) -> str:
    is_de = language.lower().startswith("de")
    default_label = "Penetrationstest-Bericht" if is_de else "Penetration Test Report"
    resolved_label = report_label or default_label
    page_label = "Seite " if is_de else "Page "
    return f"""
@media print {{
    @page {{
        size: A4;
        margin: 22mm 18mm 20mm;
        @top-left {{
            content: {_css_string(project_name)};
            color: #899198;
            font: 7.25pt "Segoe UI", sans-serif;
        }}
        @top-right {{
            content: {_css_string(resolved_label)};
            color: #899198;
            font: 7.25pt "Segoe UI", sans-serif;
        }}
        @bottom-left {{
            content: {_css_string(classification or "")};
            color: #899198;
            font: 7.25pt "Segoe UI", sans-serif;
        }}
        @bottom-right {{
            content: {_css_string(page_label)} counter(page);
            color: #899198;
            font: 7.25pt "Segoe UI", sans-serif;
        }}
    }}
    @page :first {{
        margin: 0;
        @top-left {{ content: none; }}
        @top-right {{ content: none; }}
        @bottom-left {{ content: none; }}
        @bottom-right {{ content: none; }}
    }}
}}
"""


def render_report_html(
    body_html: str,
    project_name: Optional[str] = None,
    target_ip: Optional[str] = None,
    timestamp: Optional[str] = None,
    theme: str = "dark",
    report_font: str = "segoe_ui",
    language: str = "en",
    profile: str = "interactive",
    classification: Optional[str] = None,
    report_label: Optional[str] = None,
) -> str:
    """Renders the complete, styled standalone HTML document."""
    pname = project_name or "Target"
    now_str = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_str = target_ip if target_ip and target_ip != "all" else "N/A"
    report_css = get_report_css(theme, report_font, profile)
    safe_project_name = "".join(char for char in pname if char.isalnum() or char in "-_").strip(
        "-_"
    )
    download_filename = json.dumps(f"report_edited_{safe_project_name or 'report'}.html")
    # JSON alone permits literal '<', which an HTML parser could interpret as
    # a closing script tag inside the inline script below.
    download_filename = (
        download_filename.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )

    is_de = (language or "").lower().startswith("de")
    html_lang = "de" if is_de else "en"
    date_label = "Datum:" if is_de else "Date:"
    btn_print = "🖨 Drucken / PDF Exportieren" if is_de else "🖨 Print / Export PDF"
    btn_save = "💾 Bearbeitete Version speichern" if is_de else "💾 Save Edited HTML"
    is_professional = profile == "professional_print"
    if is_professional:
        btn_print = "Drucken / PDF exportieren" if is_de else "Print / Export PDF"
        report_css += _professional_page_css(
            pname, classification, language, report_label=report_label
        )
    editable = "true"
    print_guidance = (
        "Browser-Kopf- und Fußzeilen für ein sauberes PDF deaktivieren."
        if is_de
        else "Disable browser headers and footers for a clean PDF."
    )
    action_guidance = (
        f'<span class="print-guidance">{print_guidance}</span>' if is_professional else ""
    )
    save_button = f'<button class="btn-action" onclick="downloadEditedHtml()">{btn_save}</button>'
    footer = (
        ""
        if is_professional
        else """
        <footer class="report-footer">
            <span>Generated with SpectreHUD Pentest &amp; CTF Companion</span>
            <span>{timestamp}</span>
        </footer>""".format(timestamp=now_str)
    )

    return f"""<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SpectreHUD // Pentest Report - {html.escape(pname)}</title>
    <style>
{report_css}
    </style>
</head>
<body data-report-profile="{html.escape(profile)}">
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
                <div class="meta-item"><strong>{date_label}</strong> {now_str}</div>
            </div>
        </header>

        <div class="action-bar no-print">
            {action_guidance}
            <button class="btn-action" onclick="window.print()">{btn_print}</button>
            {save_button}
        </div>

        <main class="report-body" contenteditable="{editable}" spellcheck="false">
            {body_html}
        </main>

        {footer}
    </div>
    <script data-report-editor>
        function downloadEditedHtml() {{
            const clone = document.documentElement.cloneNode(true);
            const body = clone.querySelector('main.report-body');
            if (body) body.removeAttribute('contenteditable');
            clone.querySelectorAll('.no-print, script[data-report-editor]').forEach((element) => element.remove());

            const html = '<!DOCTYPE html>\\n' + clone.outerHTML;
            const blob = new Blob([html], {{ type: 'text/html' }});
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = {download_filename};
            anchor.click();
            setTimeout(() => URL.revokeObjectURL(url), 0);
        }}
    </script>
</body>
</html>
"""
