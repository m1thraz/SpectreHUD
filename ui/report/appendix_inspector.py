"""
SpectreHUD Report Workspace Appendix & Evidence Inspector.
Provides a structured cockpit for managing executed command history,
screenshot evidence gallery, and supplementary raw notes/dumps.
"""

from pathlib import Path
import re
from typing import Any, Optional
import uuid

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.reporting import (
    ReportAppendix,
    ReportEvidenceItem,
    ReportWorkspaceDocument,
)
from ui.glass_panel import GlassPanel
from ui.message_boxes import show_warning_dialog
from ui.report.dialogs import (
    ClipboardHistoryPickerDialog,
    LootImagePickerDialog,
)
from ui.styles.icons import icon

_SUPPORTED_LANGUAGES = [
    ("bash", "Bash / Shell"),
    ("sh", "POSIX sh"),
    ("powershell", "PowerShell"),
    ("cmd", "Windows CMD / Batch"),
    ("python", "Python"),
    ("json", "JSON"),
    ("sql", "SQL"),
    ("text", "Klartext / Output"),
]


class CommandSnippetCard(GlassPanel):
    """Card representing a single command or PoC snippet in Appendix A."""

    changed = pyqtSignal()
    delete_requested = pyqtSignal(object)
    move_up_requested = pyqtSignal(object)
    move_down_requested = pyqtSignal(object)

    def __init__(self, item: ReportEvidenceItem, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        # Top controls row
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.btn_up = QPushButton()
        self.btn_up.setIcon(icon("fa5s.chevron-up", color="#8b949e"))
        self.btn_up.setFixedSize(26, 24)
        self.btn_up.setToolTip(t("report.move_up", "Nach oben verschieben"))
        self.btn_up.setStyleSheet("QPushButton { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 3px; } QPushButton:hover { background: rgba(255,255,255,0.15); }")
        self.btn_up.clicked.connect(lambda: self.move_up_requested.emit(self))
        top_row.addWidget(self.btn_up)

        self.btn_down = QPushButton()
        self.btn_down.setIcon(icon("fa5s.chevron-down", color="#8b949e"))
        self.btn_down.setFixedSize(26, 24)
        self.btn_down.setToolTip(t("report.move_down", "Nach unten verschieben"))
        self.btn_down.setStyleSheet("QPushButton { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 3px; } QPushButton:hover { background: rgba(255,255,255,0.15); }")
        self.btn_down.clicked.connect(lambda: self.move_down_requested.emit(self))
        top_row.addWidget(self.btn_down)

        self.edit_caption = QLineEdit()
        self.edit_caption.setPlaceholderText(t("report.appendix_cmd_caption_placeholder", "Beschreibung / Titel (z.B. Portscan Enumeration)"))
        self.edit_caption.setText(self.item.caption)
        self.edit_caption.setStyleSheet(
            "QLineEdit { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.12); "
            "border-radius: 4px; padding: 4px 8px; color: #f0f6fc; font-weight: bold; font-size: 12px; } "
            "QLineEdit:focus { border: 1px solid #7ee787; }"
        )
        self.edit_caption.textChanged.connect(self._on_data_changed)
        top_row.addWidget(self.edit_caption, stretch=1)

        self.combo_lang = QComboBox()
        for key, label in _SUPPORTED_LANGUAGES:
            self.combo_lang.addItem(label, key)
        curr_lang = getattr(self.item, "language", "") or "bash"
        idx = self.combo_lang.findData(curr_lang)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)
        else:
            self.combo_lang.addItem(curr_lang, curr_lang)
            self.combo_lang.setCurrentIndex(self.combo_lang.count() - 1)
        self.combo_lang.setStyleSheet(
            "QComboBox { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.12); "
            "border-radius: 4px; padding: 3px 8px; color: #c9d1d9; font-size: 11px; } "
            "QComboBox:focus { border: 1px solid #7ee787; }"
        )
        self.combo_lang.currentIndexChanged.connect(self._on_data_changed)
        top_row.addWidget(self.combo_lang)

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(icon("fa5s.trash-alt", color="#f85149"))
        self.btn_delete.setFixedSize(26, 24)
        self.btn_delete.setToolTip(t("report.delete", "Snippet löschen"))
        self.btn_delete.setStyleSheet(
            "QPushButton { background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.3); border-radius: 3px; } "
            "QPushButton:hover { background: rgba(248, 81, 73, 0.25); }"
        )
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self))
        top_row.addWidget(self.btn_delete)

        layout.addLayout(top_row)

        # Code editor
        self.edit_code = QPlainTextEdit()
        self.edit_code.setPlaceholderText(t("report.appendix_cmd_code_placeholder", "# Befehl oder PoC-Code eingeben..."))
        self.edit_code.setPlainText(self.item.content)
        self.edit_code.setStyleSheet(
            "QPlainTextEdit { background: rgba(13, 17, 23, 0.85); border: 1px solid rgba(255, 255, 255, 0.1); "
            "border-radius: 4px; padding: 6px; color: #7ee787; font-family: 'Consolas', 'Cascadia Code', monospace; "
            "font-size: 11px; } "
            "QPlainTextEdit:focus { border: 1px solid #7ee787; }"
        )
        # Adapt height based on line count
        lines_count = max(3, min(15, len(self.item.content.splitlines()) + 1))
        self.edit_code.setMinimumHeight(lines_count * 18 + 20)
        self.edit_code.textChanged.connect(self._on_data_changed)
        layout.addWidget(self.edit_code)

    def _on_data_changed(self) -> None:
        self.item.caption = self.edit_caption.text().strip()
        self.item.language = self.combo_lang.currentData() or "bash"
        self.item.content = self.edit_code.toPlainText()
        self.changed.emit()


class ScreenshotCard(GlassPanel):
    """Card representing a single screenshot evidence item in Appendix B."""

    changed = pyqtSignal()
    delete_requested = pyqtSignal(object)
    move_up_requested = pyqtSignal(object)
    move_down_requested = pyqtSignal(object)

    def __init__(
        self,
        item: ReportEvidenceItem,
        project_dir: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.item = item
        self.project_dir = project_dir
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        # 1. Thumbnail preview
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(110, 75)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setStyleSheet(
            "QLabel { background: rgba(13, 17, 23, 0.8); border: 1px solid rgba(255, 255, 255, 0.15); "
            "border-radius: 4px; }"
        )
        self._load_thumbnail()
        layout.addWidget(self.lbl_thumb)

        # 2. Text fields
        field_layout = QVBoxLayout()
        field_layout.setSpacing(5)

        self.edit_caption = QLineEdit()
        self.edit_caption.setPlaceholderText(t("report.appendix_img_caption_placeholder", "Bildunterschrift / Titel (z.B. Root Proof)"))
        self.edit_caption.setText(self.item.caption)
        self.edit_caption.setStyleSheet(
            "QLineEdit { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.12); "
            "border-radius: 4px; padding: 4px 8px; color: #f0f6fc; font-weight: bold; font-size: 12px; } "
            "QLineEdit:focus { border: 1px solid #00e5ff; }"
        )
        self.edit_caption.textChanged.connect(self._on_data_changed)
        field_layout.addWidget(self.edit_caption)

        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        lbl_path_icon = QLabel()
        lbl_path_icon.setPixmap(icon("fa5s.folder", color="#8b949e").pixmap(14, 14))
        path_row.addWidget(lbl_path_icon)

        self.edit_path = QLineEdit()
        self.edit_path.setPlaceholderText(t("report.appendix_img_path_placeholder", "Dateipfad oder URL..."))
        self.edit_path.setText(self.item.content)
        self.edit_path.setStyleSheet(
            "QLineEdit { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); "
            "border-radius: 4px; padding: 3px 6px; color: #8b949e; font-size: 11px; font-family: monospace; } "
            "QLineEdit:focus { border: 1px solid #00e5ff; color: #c9d1d9; }"
        )
        self.edit_path.textChanged.connect(self._on_path_changed)
        path_row.addWidget(self.edit_path, stretch=1)

        field_layout.addLayout(path_row)
        layout.addLayout(field_layout, stretch=1)

        # 3. Actions column
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_up = QPushButton()
        self.btn_up.setIcon(icon("fa5s.chevron-up", color="#8b949e"))
        self.btn_up.setFixedSize(26, 22)
        self.btn_up.setToolTip(t("report.move_up", "Nach oben verschieben"))
        self.btn_up.setStyleSheet("QPushButton { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 3px; } QPushButton:hover { background: rgba(255,255,255,0.15); }")
        self.btn_up.clicked.connect(lambda: self.move_up_requested.emit(self))
        btn_layout.addWidget(self.btn_up)

        self.btn_down = QPushButton()
        self.btn_down.setIcon(icon("fa5s.chevron-down", color="#8b949e"))
        self.btn_down.setFixedSize(26, 22)
        self.btn_down.setToolTip(t("report.move_down", "Nach unten verschieben"))
        self.btn_down.setStyleSheet("QPushButton { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 3px; } QPushButton:hover { background: rgba(255,255,255,0.15); }")
        self.btn_down.clicked.connect(lambda: self.move_down_requested.emit(self))
        btn_layout.addWidget(self.btn_down)

        self.btn_delete = QPushButton()
        self.btn_delete.setIcon(icon("fa5s.trash-alt", color="#f85149"))
        self.btn_delete.setFixedSize(26, 22)
        self.btn_delete.setToolTip(t("report.delete", "Screenshot entfernen"))
        self.btn_delete.setStyleSheet(
            "QPushButton { background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.3); border-radius: 3px; } "
            "QPushButton:hover { background: rgba(248, 81, 73, 0.25); }"
        )
        self.btn_delete.clicked.connect(lambda: self.delete_requested.emit(self))
        btn_layout.addWidget(self.btn_delete)

        layout.addLayout(btn_layout)

    def _load_thumbnail(self) -> None:
        path_str = (self.item.content or "").strip()
        full_path: Optional[Path] = None
        if path_str:
            p = Path(path_str)
            if p.is_file():
                full_path = p
            elif self.project_dir:
                p_rel = self.project_dir / path_str
                if p_rel.is_file():
                    full_path = p_rel

        if full_path and full_path.is_file():
            pix = QPixmap(str(full_path))
            if not pix.isNull():
                self.lbl_thumb.setPixmap(
                    pix.scaled(106, 71, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                )
                return

        # Fallback icon
        self.lbl_thumb.setPixmap(icon("fa5s.image", color="#484f58").pixmap(32, 32))

    def _on_path_changed(self) -> None:
        self.item.content = self.edit_path.text().strip()
        self._load_thumbnail()
        self.changed.emit()

    def _on_data_changed(self) -> None:
        self.item.caption = self.edit_caption.text().strip()
        self.changed.emit()


class ReportAppendixInspector(QWidget):
    """Contextual Inspector Cockpit for Report Appendix & Evidence."""

    appendix_changed = pyqtSignal(ReportAppendix)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportAppendixInspector")
        self._appendix = ReportAppendix()
        self._loot_manager: Any = None
        self._clipboard_history: Any = None
        self._project_dir: Optional[Path] = None
        self._language = "de"
        self._loading = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_changed)

        self._build_ui()

    def set_context(
        self,
        loot_manager: Any = None,
        clipboard_history: Any = None,
        project_dir: Optional[Path] = None,
    ) -> None:
        """Configures external sources for loot screenshots and clipboard command history."""
        self._loot_manager = loot_manager
        self._clipboard_history = clipboard_history
        self._project_dir = project_dir

    def minimumSizeHint(self) -> QSize:
        return QSize(260, 200)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Header Card
        self.header_card = GlassPanel(self)
        v_header = QVBoxLayout(self.header_card)
        v_header.setContentsMargins(12, 8, 12, 8)
        v_header.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(icon("fa5s.paperclip", color="#00e5ff").pixmap(20, 20))
        top_row.addWidget(lbl_icon)

        self.lbl_title = QLabel(t("report.inspector_appendix_title", "Anhang & Nachweise"))
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()

        self.lbl_badge = QLabel()
        self.lbl_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 3px 10px; border-radius: 4px; "
            "background: rgba(0, 229, 255, 0.15); color: #00e5ff; border: 1px solid rgba(0, 229, 255, 0.35);"
        )
        top_row.addWidget(self.lbl_badge)
        v_header.addLayout(top_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.btn_quick_history = QPushButton(t("report.appendix_quick_history", "Snippet aus History..."))
        self.btn_quick_history.setIcon(icon("fa5s.history", color="#79c0ff"))
        self.btn_quick_history.setStyleSheet(
            "QPushButton { background: rgba(121, 192, 255, 0.12); border: 1px solid rgba(121, 192, 255, 0.35); "
            "border-radius: 4px; color: #79c0ff; font-weight: bold; padding: 4px 10px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(121, 192, 255, 0.25); }"
        )
        self.btn_quick_history.clicked.connect(self._on_pick_history_clicked)
        actions_row.addWidget(self.btn_quick_history)
        actions_row.addStretch()

        v_header.addLayout(actions_row)

        main_layout.addWidget(self.header_card)

        # 2. Scroll Area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 12)
        scroll_layout.setSpacing(12)

        # --- Card A: Command Protocols & PoCs ---
        self.card_a = GlassPanel(scroll_content)
        card_a_layout = QVBoxLayout(self.card_a)
        card_a_layout.setContentsMargins(14, 12, 14, 14)
        card_a_layout.setSpacing(10)

        header_a = QHBoxLayout()
        header_a.setSpacing(8)
        lbl_icon_a = QLabel()
        lbl_icon_a.setPixmap(icon("fa5s.terminal", color="#7ee787").pixmap(16, 16))
        header_a.addWidget(lbl_icon_a)

        self.lbl_title_a = QLabel(t("report.appendix_section_a_title", "Anhang A: Ausgeführte Befehle & PoCs"))
        self.lbl_title_a.setStyleSheet("font-size: 13px; font-weight: bold; color: #f0f6fc;")
        header_a.addWidget(self.lbl_title_a)
        header_a.addStretch()

        self.btn_pick_history = QPushButton(t("report.appendix_btn_history", "Aus History wählen..."))
        self.btn_pick_history.setIcon(icon("fa5s.history", color="#79c0ff"))
        self.btn_pick_history.setStyleSheet(
            "QPushButton { background: rgba(121, 192, 255, 0.1); border: 1px solid rgba(121, 192, 255, 0.25); "
            "border-radius: 4px; color: #79c0ff; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(121, 192, 255, 0.2); }"
        )
        self.btn_pick_history.clicked.connect(self._on_pick_history_clicked)
        header_a.addWidget(self.btn_pick_history)

        self.btn_import_all_history = QPushButton(t("report.appendix_btn_import_all", "Alle Befehle übernehmen"))
        self.btn_import_all_history.setIcon(icon("fa5s.layer-group", color="#d2a8ff"))
        self.btn_import_all_history.setStyleSheet(
            "QPushButton { background: rgba(210, 168, 255, 0.1); border: 1px solid rgba(210, 168, 255, 0.25); "
            "border-radius: 4px; color: #d2a8ff; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(210, 168, 255, 0.2); }"
        )
        self.btn_import_all_history.clicked.connect(self._on_import_all_history_clicked)
        header_a.addWidget(self.btn_import_all_history)

        self.btn_add_cmd = QPushButton(t("report.appendix_btn_add_cmd", "+ Manuelles Snippet"))
        self.btn_add_cmd.setIcon(icon("fa5s.plus", color="#7ee787"))
        self.btn_add_cmd.setStyleSheet(
            "QPushButton { background: rgba(126, 231, 135, 0.1); border: 1px solid rgba(126, 231, 135, 0.25); "
            "border-radius: 4px; color: #7ee787; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(126, 231, 135, 0.2); }"
        )
        self.btn_add_cmd.clicked.connect(self._on_add_cmd_clicked)
        header_a.addWidget(self.btn_add_cmd)

        card_a_layout.addLayout(header_a)

        # Snippets container
        self.snippets_container = QWidget()
        self.snippets_layout = QVBoxLayout(self.snippets_container)
        self.snippets_layout.setContentsMargins(0, 0, 0, 0)
        self.snippets_layout.setSpacing(8)
        card_a_layout.addWidget(self.snippets_container)

        self.lbl_empty_cmd = QLabel(t("report.appendix_empty_cmd", "Noch keine Befehle hinterlegt. Klicken Sie auf '+ Manuelles Snippet' oder wählen Sie Befehle aus der History."))
        self.lbl_empty_cmd.setStyleSheet("color: #8b949e; font-style: italic; font-size: 11px; padding: 8px;")
        card_a_layout.addWidget(self.lbl_empty_cmd)

        scroll_layout.addWidget(self.card_a)

        # --- Card B: Screenshots & Image Evidence ---
        self.card_b = GlassPanel(scroll_content)
        card_b_layout = QVBoxLayout(self.card_b)
        card_b_layout.setContentsMargins(14, 12, 14, 14)
        card_b_layout.setSpacing(10)

        header_b = QHBoxLayout()
        header_b.setSpacing(8)
        lbl_icon_b = QLabel()
        lbl_icon_b.setPixmap(icon("fa5s.camera", color="#00e5ff").pixmap(16, 16))
        header_b.addWidget(lbl_icon_b)

        self.lbl_title_b = QLabel(t("report.appendix_section_b_title", "Anhang B: Screenshots & Bildnachweise"))
        self.lbl_title_b.setStyleSheet("font-size: 13px; font-weight: bold; color: #f0f6fc;")
        header_b.addWidget(self.lbl_title_b)
        header_b.addStretch()

        self.btn_pick_loot = QPushButton(t("report.appendix_btn_loot", "Aus Projekt-Loot wählen..."))
        self.btn_pick_loot.setIcon(icon("fa5s.gem", color="#00e5ff"))
        self.btn_pick_loot.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.1); border: 1px solid rgba(0, 229, 255, 0.25); "
            "border-radius: 4px; color: #00e5ff; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(0, 229, 255, 0.2); }"
        )
        self.btn_pick_loot.clicked.connect(self._on_pick_loot_clicked)
        header_b.addWidget(self.btn_pick_loot)

        self.btn_pick_file = QPushButton(t("report.appendix_btn_disk", "Datei von Festplatte..."))
        self.btn_pick_file.setIcon(icon("fa5s.folder-open", color="#f2cc60"))
        self.btn_pick_file.setStyleSheet(
            "QPushButton { background: rgba(242, 204, 96, 0.1); border: 1px solid rgba(242, 204, 96, 0.25); "
            "border-radius: 4px; color: #f2cc60; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(242, 204, 96, 0.2); }"
        )
        self.btn_pick_file.clicked.connect(self._on_pick_file_clicked)
        header_b.addWidget(self.btn_pick_file)

        self.btn_add_img = QPushButton(t("report.appendix_btn_add_img", "+ Bildpfad"))
        self.btn_add_img.setIcon(icon("fa5s.plus", color="#7ee787"))
        self.btn_add_img.setStyleSheet(
            "QPushButton { background: rgba(126, 231, 135, 0.1); border: 1px solid rgba(126, 231, 135, 0.25); "
            "border-radius: 4px; color: #7ee787; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(126, 231, 135, 0.2); }"
        )
        self.btn_add_img.clicked.connect(self._on_add_img_clicked)
        header_b.addWidget(self.btn_add_img)

        card_b_layout.addLayout(header_b)

        # Screenshots container
        self.screenshots_container = QWidget()
        self.screenshots_layout = QVBoxLayout(self.screenshots_container)
        self.screenshots_layout.setContentsMargins(0, 0, 0, 0)
        self.screenshots_layout.setSpacing(8)
        card_b_layout.addWidget(self.screenshots_container)

        self.lbl_empty_sc = QLabel(t("report.appendix_empty_sc", "Noch keine Screenshots hinterlegt. Fügen Sie Nachweise aus dem Loot oder von der Festplatte hinzu."))
        self.lbl_empty_sc.setStyleSheet("color: #8b949e; font-style: italic; font-size: 11px; padding: 8px;")
        card_b_layout.addWidget(self.lbl_empty_sc)

        scroll_layout.addWidget(self.card_b)

        # --- Card C: Supplementary Raw Data & Notes ---
        self.card_c = GlassPanel(scroll_content)
        card_c_layout = QVBoxLayout(self.card_c)
        card_c_layout.setContentsMargins(14, 12, 14, 14)
        card_c_layout.setSpacing(8)

        header_c = QHBoxLayout()
        header_c.setSpacing(8)
        lbl_icon_c = QLabel()
        lbl_icon_c.setPixmap(icon("fa5s.sticky-note", color="#f2cc60").pixmap(16, 16))
        header_c.addWidget(lbl_icon_c)

        self.lbl_title_c = QLabel(t("report.appendix_section_c_title", "Anhang C: Ergänzende Rohdaten & Notizen"))
        self.lbl_title_c.setStyleSheet("font-size: 13px; font-weight: bold; color: #f0f6fc;")
        header_c.addWidget(self.lbl_title_c)
        header_c.addStretch()
        card_c_layout.addLayout(header_c)

        lbl_desc_c = QLabel(t("report.appendix_notes_desc", "Freitext für vollständige Portscan-Dumps, Banner-Ausgaben, Hash-Listen oder ergänzende Rohdaten."))
        lbl_desc_c.setStyleSheet("font-size: 11px; color: #8b949e;")
        card_c_layout.addWidget(lbl_desc_c)

        self.edit_notes = QPlainTextEdit()
        self.edit_notes.setPlaceholderText(t("report.appendix_notes_placeholder", "Zusätzliche Rohdaten, Auszüge oder Referenzen einfügen..."))
        self.edit_notes.setStyleSheet(
            "QPlainTextEdit { background: rgba(13, 17, 23, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); "
            "border-radius: 4px; padding: 8px; color: #c9d1d9; font-family: monospace; font-size: 11px; } "
            "QPlainTextEdit:focus { border: 1px solid #f2cc60; }"
        )
        self.edit_notes.setMinimumHeight(150)
        self.edit_notes.textChanged.connect(self._on_notes_changed)
        card_c_layout.addWidget(self.edit_notes)

        scroll_layout.addWidget(self.card_c)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

    # ------------------------------------------------------------------ #
    # Data Loading & Synchronization
    # ------------------------------------------------------------------ #

    def load_appendix(self, doc: ReportWorkspaceDocument) -> None:
        """Loads appendix content from the workspace document into the inspector."""
        self._loading = True
        self._language = doc.language
        self._appendix = doc.get_appendix()

        self._render_command_snippets()
        self._render_screenshots()

        self.edit_notes.setPlainText(self._appendix.custom_notes)
        self._update_badges()
        self._loading = False

    def _render_command_snippets(self) -> None:
        # Clear existing cards
        while self.snippets_layout.count() > 0:
            item = self.snippets_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_items = bool(self._appendix.command_snippets)
        self.lbl_empty_cmd.setVisible(not has_items)

        for snip in self._appendix.command_snippets:
            card = CommandSnippetCard(snip, parent=self.snippets_container)
            card.changed.connect(self._on_card_data_changed)
            card.delete_requested.connect(self._on_delete_cmd)
            card.move_up_requested.connect(self._on_move_up_cmd)
            card.move_down_requested.connect(self._on_move_down_cmd)
            self.snippets_layout.addWidget(card)

    def _render_screenshots(self) -> None:
        # Clear existing cards
        while self.screenshots_layout.count() > 0:
            item = self.screenshots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_items = bool(self._appendix.screenshots)
        self.lbl_empty_sc.setVisible(not has_items)

        for sc in self._appendix.screenshots:
            card = ScreenshotCard(sc, project_dir=self._project_dir, parent=self.screenshots_container)
            card.changed.connect(self._on_card_data_changed)
            card.delete_requested.connect(self._on_delete_sc)
            card.move_up_requested.connect(self._on_move_up_sc)
            card.move_down_requested.connect(self._on_move_down_sc)
            self.screenshots_layout.addWidget(card)

    def _update_badges(self) -> None:
        cmd_count = len(self._appendix.command_snippets)
        sc_count = len(self._appendix.screenshots)
        if self._language == "de":
            self.lbl_badge.setText(f"{cmd_count} Befehle · {sc_count} Nachweise")
        else:
            self.lbl_badge.setText(f"{cmd_count} Commands · {sc_count} Evidence")

    def _on_notes_changed(self) -> None:
        if self._loading:
            return
        self._appendix.custom_notes = self.edit_notes.toPlainText()
        self._debounce_timer.start()

    def _on_card_data_changed(self) -> None:
        if self._loading:
            return
        self._update_badges()
        self._debounce_timer.start()

    def _emit_changed(self) -> None:
        self.appendix_changed.emit(self._appendix)

    # ------------------------------------------------------------------ #
    # Command Snippet Actions
    # ------------------------------------------------------------------ #

    def _on_add_cmd_clicked(self) -> None:
        new_item = ReportEvidenceItem(
            id=f"cmd_{uuid.uuid4().hex[:6]}",
            type="terminal",
            caption="",
            content="",
            language="bash",
        )
        self._appendix.command_snippets.append(new_item)
        self._render_command_snippets()
        self._update_badges()
        self._debounce_timer.start()

    def _on_delete_cmd(self, card: CommandSnippetCard) -> None:
        if card.item in self._appendix.command_snippets:
            self._appendix.command_snippets.remove(card.item)
            self._render_command_snippets()
            self._update_badges()
            self._debounce_timer.start()

    def _on_move_up_cmd(self, card: CommandSnippetCard) -> None:
        lst = self._appendix.command_snippets
        if card.item in lst:
            idx = lst.index(card.item)
            if idx > 0:
                lst[idx], lst[idx - 1] = lst[idx - 1], lst[idx]
                self._render_command_snippets()
                self._debounce_timer.start()

    def _on_move_down_cmd(self, card: CommandSnippetCard) -> None:
        lst = self._appendix.command_snippets
        if card.item in lst:
            idx = lst.index(card.item)
            if idx < len(lst) - 1:
                lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]
                self._render_command_snippets()
                self._debounce_timer.start()

    def _on_pick_history_clicked(self) -> None:
        if not self._clipboard_history:
            show_warning_dialog(
                self,
                t("report.no_clipboard_title", "Keine Clipboard-Einträge"),
                t("report.no_clipboard_msg", "In der Clipboard-Historie wurden noch keine Einträge erfasst."),
            )
            return

        history = self._clipboard_history.get_all_history()
        if not history:
            show_warning_dialog(
                self,
                t("report.no_clipboard_title", "Keine Clipboard-Einträge"),
                t("report.no_clipboard_msg", "In der Clipboard-Historie wurden noch keine Einträge erfasst."),
            )
            return

        dialog = ClipboardHistoryPickerDialog(history, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_entry:
            text = (dialog.selected_entry.get("text") or "").strip()
            first_line = text.splitlines()[0] if text else "Command Output"
            if len(first_line) > 50:
                first_line = first_line[:47] + "..."

            # Infer language
            lang = "bash"
            low_text = text.lower()
            if "powershell" in low_text or "get-process" in low_text or "whoami /priv" in low_text:
                lang = "powershell"
            elif low_text.startswith("{") or low_text.startswith("["):
                lang = "json"

            new_item = ReportEvidenceItem(
                id=f"cmd_{uuid.uuid4().hex[:6]}",
                type="terminal",
                caption=first_line,
                content=text,
                language=lang,
                source_loot_id=dialog.selected_entry.get("id"),
            )
            self._appendix.command_snippets.append(new_item)
            self._render_command_snippets()
            self._update_badges()
            self._debounce_timer.start()

    def _on_import_all_history_clicked(self) -> None:
        if not self._clipboard_history:
            return

        history = self._clipboard_history.get_all_history()
        if not history:
            return

        existing_contents = {s.content.strip() for s in self._appendix.command_snippets if s.content.strip()}
        added = 0
        for entry in history:
            text = (entry.get("text") or "").strip()
            if not text or text in existing_contents:
                continue

            first_line = text.splitlines()[0]
            if len(first_line) > 50:
                first_line = first_line[:47] + "..."

            lang = "bash"
            low = text.lower()
            if "powershell" in low or "get-" in low:
                lang = "powershell"
            elif low.startswith("{") or low.startswith("["):
                lang = "json"

            self._appendix.command_snippets.append(
                ReportEvidenceItem(
                    id=f"cmd_{uuid.uuid4().hex[:6]}",
                    type="terminal",
                    caption=first_line,
                    content=text,
                    language=lang,
                    source_loot_id=entry.get("id"),
                )
            )
            existing_contents.add(text)
            added += 1

        if added > 0:
            self._render_command_snippets()
            self._update_badges()
            self._debounce_timer.start()

    # ------------------------------------------------------------------ #
    # Screenshot Actions
    # ------------------------------------------------------------------ #

    def _on_add_img_clicked(self) -> None:
        new_item = ReportEvidenceItem(
            id=f"sc_{uuid.uuid4().hex[:6]}",
            type="screenshot",
            caption="",
            content="",
        )
        self._appendix.screenshots.append(new_item)
        self._render_screenshots()
        self._update_badges()
        self._debounce_timer.start()

    def _on_delete_sc(self, card: ScreenshotCard) -> None:
        if card.item in self._appendix.screenshots:
            self._appendix.screenshots.remove(card.item)
            self._render_screenshots()
            self._update_badges()
            self._debounce_timer.start()

    def _on_move_up_sc(self, card: ScreenshotCard) -> None:
        lst = self._appendix.screenshots
        if card.item in lst:
            idx = lst.index(card.item)
            if idx > 0:
                lst[idx], lst[idx - 1] = lst[idx - 1], lst[idx]
                self._render_screenshots()
                self._debounce_timer.start()

    def _on_move_down_sc(self, card: ScreenshotCard) -> None:
        lst = self._appendix.screenshots
        if card.item in lst:
            idx = lst.index(card.item)
            if idx < len(lst) - 1:
                lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]
                self._render_screenshots()
                self._debounce_timer.start()

    def _on_pick_loot_clicked(self) -> None:
        if not self._loot_manager:
            return

        screenshot_entries = [
            e
            for e in self._loot_manager.get_all_entries()
            if (e.get("type") in ("screenshot", "image") or "![image]" in (e.get("content") or ""))
        ]
        if not screenshot_entries:
            show_warning_dialog(
                self,
                t("report.no_screenshots_title", "Keine Screenshots gefunden"),
                t("report.no_screenshots_msg", "Im aktiven Projekt wurden noch keine Screenshots in Loot erfasst."),
            )
            return

        dialog = LootImagePickerDialog(screenshot_entries, project_dir=self._project_dir, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_entry:
            entry = dialog.selected_entry
            title = entry.get("title", "Screenshot")
            content = (entry.get("content") or "").strip()
            rel_path = content
            m = re.search(r"\((.*?)\)", content)
            if m:
                rel_path = m.group(1)

            ev_item = ReportEvidenceItem(
                id=f"sc_{uuid.uuid4().hex[:6]}",
                type="screenshot",
                caption=title,
                content=rel_path,
                source_loot_id=entry.get("id"),
            )
            self._appendix.screenshots.append(ev_item)
            self._render_screenshots()
            self._update_badges()
            self._debounce_timer.start()

    def _on_pick_file_clicked(self) -> None:
        start_dir = ""
        if self._project_dir and self._project_dir.is_dir():
            sc_dir = self._project_dir / "screenshots"
            start_dir = str(sc_dir) if sc_dir.is_dir() else str(self._project_dir)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("report.select_image_title", "Select Image"),
            start_dir,
            t(
                "report.select_image_filter",
                "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.svg);;All Files (*.*)",
            ),
        )
        if file_path:
            p = Path(file_path)
            # Check if inside project_dir
            if self._project_dir and self._project_dir in p.parents:
                rel_content = str(p.relative_to(self._project_dir)).replace("\\", "/")
            else:
                rel_content = str(p).replace("\\", "/")

            caption = p.stem.replace("_", " ").replace("-", " ").title()
            ev_item = ReportEvidenceItem(
                id=f"sc_{uuid.uuid4().hex[:6]}",
                type="screenshot",
                caption=caption,
                content=rel_content,
            )
            self._appendix.screenshots.append(ev_item)
            self._render_screenshots()
            self._update_badges()
            self._debounce_timer.start()
