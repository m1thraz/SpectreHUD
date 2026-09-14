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


def test_render_applies_heading_margins_to_chapters_and_findings(qapp):
    controller, _editor, _preview = _controller()
    markdown = (
        "## 4. Technical Findings\n\n"
        "### Finding 1\n\n"
        "Description 1\n\n"
        "### Finding 2\n\n"
        "Description 2\n\n"
        "## 5. Remediation"
    )
    controller.render(markdown)

    blocks = []
    block = controller.document.firstBlock()
    while block.isValid():
        blocks.append(
            (
                block.text(),
                block.blockFormat().headingLevel(),
                block.blockFormat().topMargin(),
                block.blockFormat().bottomMargin(),
            )
        )
        block = block.next()

    h2_blocks = [b for b in blocks if b[1] == 2]
    h3_blocks = [b for b in blocks if b[1] == 3]

    assert len(h2_blocks) == 2
    assert len(h3_blocks) == 2
    # First block at top of document keeps a minimal top margin
    assert h2_blocks[0][2] == 4
    # Subsequent chapters get prominent top margin to separate chapters
    assert h2_blocks[1][2] >= 20
    assert h2_blocks[1][3] >= 6
    for b in h3_blocks:
        assert b[2] >= 16
        assert b[3] >= 4

