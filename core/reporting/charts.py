"""
Visual Charts, Severity Badges, and Stats Widgets for SpectreHUD Reports.
"""

import html


def render_severity_badge(severity: str) -> str:
    """Renders a stylized HTML severity badge."""
    sev_clean = str(severity).strip().lower()
    mapping = {
        "critical": ("🔴 CRITICAL", "severity-critical"),
        "high": ("🟠 HIGH", "severity-high"),
        "medium": ("🟡 MEDIUM", "severity-medium"),
        "low": ("🟢 LOW", "severity-low"),
        "info": ("🔵 INFO", "severity-low"),
    }
    label, css_class = mapping.get(sev_clean, (severity.upper(), "severity-medium"))
    return f'<span class="severity-pill {css_class}">{html.escape(label)}</span>'


def render_metrics_summary(critical: int = 0, high: int = 0, medium: int = 0, low: int = 0) -> str:
    """Renders a formatted metrics summary row."""
    return (
        f'<div class="meta-item">'
        f"<strong>Findings:</strong> "
        f"🔴 {critical} Critical · 🟠 {high} High · 🟡 {medium} Medium · 🟢 {low} Low"
        f"</div>"
    )
