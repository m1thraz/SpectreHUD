"""Focused tests for Report Workspace preview interaction ownership."""

from core.reporting import wrap_section_markdown
from PyQt6.QtWidgets import QScrollBar

from ui.report.preview import ReportDocument, ReportPreviewEdit
from ui.report.preview_controller import ReportPreviewController
from ui.report.source_editor import ReportSourceEditor


def _controller(*, split_mode=True, light_mode=False):
    editor = ReportSourceEditor()
    document = ReportDocument()
    preview = ReportPreviewEdit()
    preview.setDocument(document)
    controller = ReportPreviewController(
        editor=editor,
        preview=preview,
        document=document,
        light_mode_provider=lambda: light_mode,
        split_mode_provider=lambda: split_mode,
    )
    return controller, editor, preview


def test_render_indexes_and_focuses_semantic_landmark(qapp):
    controller, _editor, preview = _controller()
    markdown = wrap_section_markdown(
        "## Executive Summary\n\nAssessment body",
        "executive_summary",
    )

    controller.render(markdown)
    controller.focus("section", "executive_summary")

    target = ("section", "executive_summary")
    assert target in controller.landmarks
    assert controller.active_target == target
    assert preview.textCursor().position() == controller.landmarks[target]
    assert len(preview.extraSelections()) == 1
    assert "SPECTRE_NAV_PREVIEW_" not in preview.toPlainText()


def test_scroll_sync_uses_proportional_ranges_in_split_mode(qapp):
    controller, _editor, _preview = _controller(split_mode=True)
    target = QScrollBar()
    target.setRange(0, 200)

    controller._sync_scrollbars(50, 100, target)

    assert target.value() == 100
    assert controller.syncing_scroll is False


def test_scroll_sync_is_inactive_outside_split_mode(qapp):
    controller, editor, preview = _controller(split_mode=False)
    editor.verticalScrollBar().setRange(0, 100)
    preview.verticalScrollBar().setRange(0, 200)

    controller.on_editor_scroll(50)

    assert preview.verticalScrollBar().value() == 0
