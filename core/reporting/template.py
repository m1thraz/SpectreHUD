"""
HTML Document Template Assembly for SpectreHUD Reports.
"""

import html
import json
from datetime import datetime
from typing import Optional

from core.reporting.styles import get_report_css


def render_report_html(
    body_html: str,
    project_name: Optional[str] = None,
    target_ip: Optional[str] = None,
    timestamp: Optional[str] = None,
    theme: str = "dark",
    report_font: str = "segoe_ui",
    language: str = "en",
    profile: str = "interactive",
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
    editable = "false" if is_professional else "true"
    print_guidance = (
        "Browser-Kopf- und Fußzeilen für ein sauberes PDF deaktivieren."
        if is_de
        else "Disable browser headers and footers for a clean PDF."
    )
    action_guidance = (
        f'<span class="print-guidance">{print_guidance}</span>' if is_professional else ""
    )
    save_button = (
        ""
        if is_professional
        else f'<button class="btn-action" onclick="downloadEditedHtml()">{btn_save}</button>'
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

        <footer class="report-footer">
            <span>Generated with SpectreHUD Pentest &amp; CTF Companion</span>
            <span>{now_str}</span>
        </footer>
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
