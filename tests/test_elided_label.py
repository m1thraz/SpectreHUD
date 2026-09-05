"""Tests for ElidedLabel and badge label configuration."""

from PyQt6.QtWidgets import QLabel, QSizePolicy

from ui.elided_label import ElidedLabel, configure_badge_label


def test_elided_label_renders_full_text_when_space_available(qapp):
    label = ElidedLabel("Short Title")
    label.resize(300, 30)
    label.show()
    qapp.processEvents()

    assert label.text() == "Short Title"
    assert label.full_text() == "Short Title"
    assert label.elided_text() == "Short Title"
    assert label.toolTip() == "Short Title"
    label.deleteLater()


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
    assert label.minimumWidth() == 0
    assert label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    label.deleteLater()


def test_elided_label_updates_text_and_tooltip(qapp):
    label = ElidedLabel("Initial")
    label.resize(60, 25)
    label.show()
    qapp.processEvents()

    label.setText("Updated Title That Is Rather Long")
    qapp.processEvents()

    assert label.text() == "Updated Title That Is Rather Long"
    assert label.toolTip() == "Updated Title That Is Rather Long"
    assert "…" in label.elided_text()
    label.deleteLater()


def test_configure_badge_label_reserves_minimum_width(qapp):
    raw_label = QLabel("TARGET")
    configure_badge_label(raw_label, "TARGET", padding=14)

    expected_min = raw_label.fontMetrics().horizontalAdvance("TARGET") + 14
    assert raw_label.minimumWidth() == expected_min
    assert raw_label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Preferred
    assert raw_label.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    raw_label.deleteLater()
