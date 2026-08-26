from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QApplication, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt
from typing import Dict, Any, Optional
from core.template_engine import TemplateEngine
from ui.param_prompt_dialog import ParamPromptDialog
import pyperclip

class SnippetCard(QFrame):
    """Visual card displaying a single command snippet with natural word wrapping, inline parameter prompts and 1-click copying."""

    copied = pyqtSignal(str)
    deleted = pyqtSignal(str)
    snippet_deleted = deleted

    def __init__(self, snippet: Dict[str, Any], variables: Dict[str, Any], parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.snippet = snippet
        self.variables = variables
        self._rendered_command = ""
        self._init_ui()
        self.update_variables(variables)

    def _init_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header Row: Title & Category Badge
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.lbl_title = QLabel(self.snippet.get("title", "Unbenannter Befehl"))
        self.lbl_title.setObjectName("SnippetTitle")
        self.lbl_title.setWordWrap(True)
        header_layout.addWidget(self.lbl_title, stretch=1)

        cat_part = self.snippet.get('category', '').strip().lstrip("\ufe0f \t")
        subcat_part = self.snippet.get('subcategory', '').strip()
        cat_text = f"{cat_part} › {subcat_part}" if subcat_part else cat_part
        self.lbl_category = QLabel(cat_text)
        self.lbl_category.setObjectName("SnippetCategory")
        header_layout.addWidget(self.lbl_category, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Delete button if custom snippet
        if self.snippet.get("is_custom", False):
            self.btn_delete = QPushButton("✕")
            self.btn_delete.setProperty("class", "DangerBtn")
            self.btn_delete.setToolTip("Diesen eigenen Befehl löschen")
            self.btn_delete.clicked.connect(lambda: self.deleted.emit(self.snippet.get("id", "")))
            header_layout.addWidget(self.btn_delete)

        layout.addLayout(header_layout)

        # Description (if present)
        desc_text = self.snippet.get("description", "")
        if desc_text:
            self.lbl_desc = QLabel(desc_text)
            self.lbl_desc.setObjectName("SnippetDesc")
            self.lbl_desc.setWordWrap(True)
            layout.addWidget(self.lbl_desc)

        # Command Box & Copy Button Row
        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(10)

        # Naturally wrapping selectable code label without expanding the card
        self.lbl_command = QLabel()
        self.lbl_command.setObjectName("CommandLabel")
        self.lbl_command.setWordWrap(True)
        self.lbl_command.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | 
            Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_command.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        
        cmd_row.addWidget(self.lbl_command, stretch=1)

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.setFixedWidth(85)
        self.btn_copy.clicked.connect(self._copy_command)
        cmd_row.addWidget(self.btn_copy, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(cmd_row)

    def update_variables(self, variables: Dict[str, Any]) -> None:
        """Rerenders the command template with current variables."""
        self.variables = variables
        template = self.snippet.get("template", "")
        self._rendered_command = TemplateEngine.render(template, variables)
        self.lbl_command.setText(self._rendered_command)

    def _copy_command(self) -> None:
        """
        Copies rendered command to clipboard.
        If unresolved inline parameters exist, prompts the user via ParamPromptDialog first.
        """
        template = self.snippet.get("template", "")
        unresolved = TemplateEngine.extract_unresolved_placeholders(template, self.variables)

        text_to_copy = self._rendered_command.strip()

        if unresolved:
            cached_params = {}
            main_win = self.window()
            if hasattr(main_win, "config") and hasattr(main_win.config, "session_param_cache"):
                cached_params = main_win.config.session_param_cache

            dlg = ParamPromptDialog(
                template=template,
                variables=self.variables,
                unresolved_params=unresolved,
                cached_params=cached_params,
                parent=self.window()
            )

            if dlg.exec():
                custom_values = dlg.get_values()
                if hasattr(main_win, "config") and hasattr(main_win.config, "set_cached_param"):
                    for k, v in custom_values.items():
                        main_win.config.set_cached_param(k, v)

                text_to_copy = TemplateEngine.render_with_custom(template, self.variables, custom_values).strip()
            else:
                return

        if text_to_copy:
            clipboard = QApplication.clipboard()
            clipboard.setText(text_to_copy)
            try:
                pyperclip.copy(text_to_copy)
            except (pyperclip.PyperclipException, OSError) as exc:
                logger.debug(f"pyperclip copy fallback failed: {exc}")

            self.btn_copy.setText("✓ Copied!")
            self.btn_copy.setProperty("class", "CopyBtnSuccess")
            self.btn_copy.style().unpolish(self.btn_copy)
            self.btn_copy.style().polish(self.btn_copy)

            QTimer.singleShot(1200, self._reset_copy_btn)
            self.copied.emit(text_to_copy)

    def _reset_copy_btn(self) -> None:
        self.btn_copy.setText("Copy")
        self.btn_copy.setProperty("class", "CopyBtn")
        self.btn_copy.style().unpolish(self.btn_copy)
        self.btn_copy.style().polish(self.btn_copy)
