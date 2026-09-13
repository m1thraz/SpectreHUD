"""Shared visual roles for Report Workspace inspectors."""

from typing import Optional

from PyQt6.QtWidgets import QLabel, QScrollArea, QWidget


def _add_widget_class(widget: QWidget, class_name: str) -> None:
    classes = str(widget.property("class") or "").split()
    if class_name not in classes:
        classes.append(class_name)
        widget.setProperty("class", " ".join(classes))


def style_inspector_header(
    panel: QWidget,
    title: QLabel,
    *,
    hint: Optional[QLabel] = None,
) -> None:
    _add_widget_class(panel, "ReportInspectorHeader")
    _add_widget_class(title, "ReportInspectorTitle")
    if hint is not None:
        _add_widget_class(hint, "ReportInspectorHint")


def style_inspector_section(panel: QWidget, title: QLabel) -> None:
    _add_widget_class(panel, "ReportInspectorSection")
    _add_widget_class(title, "ReportInspectorSectionTitle")


def style_inspector_scroll(scroll: QScrollArea, content: QWidget) -> None:
    _add_widget_class(scroll, "ReportInspectorScroll")
    _add_widget_class(content, "ReportInspectorBody")
