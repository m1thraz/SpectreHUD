"""
Visual Charts, Severity Badges, and Stats Widgets for SpectreHUD Reports.
"""

import html


def render_severity_badge(severity: str, *, include_emoji: bool = False) -> str:
    """Renders a stylized HTML severity badge."""
    sev_clean = str(severity).strip().lower()
    mapping = {
        "critical": ("🔴", "CRITICAL", "severity-critical"),
        "high": ("🟠", "HIGH", "severity-high"),
        "medium": ("🟡", "MEDIUM", "severity-medium"),
        "low": ("🟢", "LOW", "severity-low"),
        "info": ("🔵", "INFO", "severity-info"),
    }
    emoji, label, css_class = mapping.get(
        sev_clean, ("", severity.upper(), "severity-medium")
    )
    if include_emoji and emoji:
        label = f"{emoji} {label}"
    return f'<span class="severity-pill {css_class}">{html.escape(label)}</span>'


def render_metrics_summary(critical: int = 0, high: int = 0, medium: int = 0, low: int = 0) -> str:
    """Renders a formatted metrics summary row."""
    counts = render_severity_counts(critical, high, medium, low)
    return (
        f'<div class="meta-item">'
        f"<strong>Findings:</strong> "
        f"{counts}"
        f"</div>"
    )


def render_severity_counts(critical: int, high: int, medium: int, low: int) -> str:
    """Keep severity readable in Markdown while HTML exports enhance the same labels."""
    counts = (
        ("critical", critical),
        ("high", high),
        ("medium", medium),
        ("low", low),
    )
    return " · ".join(
        f"{render_severity_badge(severity, include_emoji=False)} {count}"
        for severity, count in counts
    )
