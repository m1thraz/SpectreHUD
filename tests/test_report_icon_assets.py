import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication

from ui.report.dialogs import ReportIconPickerDialog
from ui.report.icon_assets import REPORT_ICONS, ReportIconError, render_report_icon


app = QApplication.instance() or QApplication(sys.argv)


def test_render_report_icon_creates_reusable_project_png(tmp_path):
    relative_path = render_report_icon(tmp_path, "fa5s.key", size=32)
    asset_path = tmp_path / Path(relative_path)

    assert relative_path == "assets/icons/fa5s_key_32.png"
    assert asset_path.is_file()
    image = QImage(str(asset_path))
    assert not image.isNull()
    assert image.width() == image.height() == 32

    with patch("ui.report.icon_assets.atomic_write_bytes") as write:
        assert render_report_icon(tmp_path, "fa5s.key", size=32) == relative_path
    write.assert_not_called()
    assert list((tmp_path / "assets" / "icons").glob("*.png")) == [asset_path]


@pytest.mark.parametrize(
    ("icon_name", "variant"),
    (("missing-dot", None), ("fa5s.definitely-not-an-icon", None), ("fa5s.key", "theme")),
)
def test_render_report_icon_rejects_invalid_input(tmp_path, icon_name, variant):
    with pytest.raises(ReportIconError):
        render_report_icon(tmp_path, icon_name, variant=variant)


def test_report_icon_picker_is_curated_searchable_and_filterable(qapp):
    dialog = ReportIconPickerDialog()
    try:
        assert dialog.list_widget.count() == len(REPORT_ICONS)
        assert dialog.selected_icon is not None

        dialog.search_edit.setText("Credential")
        assert dialog.list_widget.count() == 1
        assert dialog.selected_icon.key == "credential"

        dialog.search_edit.clear()
        security_index = dialog.category_combo.findData("security")
        dialog.category_combo.setCurrentIndex(security_index)
        assert dialog.list_widget.count() > 1
        assert all(icon.category == "security" for icon in dialog._filtered_icons)
    finally:
        dialog.deleteLater()
