"""
HTML Document Template Assembly for SpectreHUD Reports.
"""

import html
from datetime import datetime
from typing import Optional

from core.reporting.assets import REPORT_CSS


def render_report_html(
    body_html: str,
    project_name: Optional[str] = None,
    target_ip: Optional[str] = None,
    timestamp: Optional[str] = None
) -> str:
    """Renders the complete, styled standalone HTML document."""
    pname = project_name or "Target"
    now_str = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_str = target_ip if target_ip and target_ip != "all" else "N/A"

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SpectreHUD // Pentest Report - {html.escape(pname)}</title>
    <style>
{REPORT_CSS}
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
