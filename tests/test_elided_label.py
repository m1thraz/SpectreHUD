"""Regression coverage for SpectreHUD's eliding label wrapper."""

from ui.elided_label import ElidedLabel


def test_elided_label_truncates_with_ellipsis_in_narrow_width(qapp):
    long_title = "Very Long Command Title That Absolutely Exceeds The Narrow Boundary"
    label = ElidedLabel(long_title)
    label.resize(80, 25)
    label.show()
    qapp.processEvents()

    assert label.text() == long_title
    assert label.full_text() == long_title
    assert "…" in label.elided_text()
    assert label.toolTip() == long_title
    label.deleteLater()
