from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QApplication,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, QTimer, Qt, QSize
from typing import Dict, Any, Optional
from core.template_engine import TemplateEngine
from ui.param_prompt_dialog import ParamPromptDialog
from ui.command_edit_dialog import CommandEditDialog
from core.i18n import t
from ui.styles.icons import icon
from ui.styles.palette import STATUS_ERROR, STATUS_SUCCESS, STATUS_WARNING, TEXT_DIMMED
import pyperclip


CARD_ICON_SIZE = QSize(13, 13)


class SnippetCard(QFrame):
    """Visual card displaying a single command snippet with natural word wrapping, inline parameter prompts and 1-click copying."""

    copied = pyqtSignal(str)
    deleted = pyqtSignal(str)
    snippet_deleted = deleted
    favorite_toggled = pyqtSignal(str, bool)

    def __init__(self, snippet: Dict[str, Any], variables: Dict[str, Any], parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SnippetCard")
        self.snippet = snippet
        self.variables = variables
        self._rendered_command = ""
        self._init_ui()
        self.update_variables(variables)

    def _init_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header Row: Star, Title & Category Badge
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        # Star / Favorite Button
        is_fav = bool(self.snippet.get("is_favorite", False))
        self.btn_fav = QPushButton()
        self.btn_fav.setIcon(
            icon("fa5s.star", color=STATUS_WARNING if is_fav else TEXT_DIMMED)
        )
        self.btn_fav.setIconSize(CARD_ICON_SIZE)
        self.btn_fav.setProperty("class", "StarBtnActive" if is_fav else "StarBtn")
        self.btn_fav.setToolTip(
            t("snippet.fav_remove", "Favorit entfernen")
            if is_fav
            else t("snippet.fav_add", "Als Favorit anheften")
        )
        self.btn_fav.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fav.clicked.connect(self._toggle_favorite)
        header_layout.addWidget(self.btn_fav, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.lbl_title = QLabel(self.snippet.get("title") or t("snippet.unnamed", "Unbenannter Befehl"))
        self.lbl_title.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_title.setObjectName("SnippetTitle")
        self.lbl_title.setWordWrap(True)
        header_layout.addWidget(self.lbl_title, stretch=1)

        cat_part = self.snippet.get("category", "").strip().lstrip("\ufe0f \t")
        subcat_part = self.snippet.get("subcategory", "").strip()
        cat_text = f"{cat_part} › {subcat_part}" if subcat_part else cat_part
        self.lbl_category = QLabel(cat_text)
        self.lbl_category.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_category.setObjectName("SnippetCategory")
        header_layout.addWidget(
            self.lbl_category, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        # Delete button if custom snippet
        if self.snippet.get("is_custom", False):
            self.btn_delete = QPushButton()
            self.btn_delete.setIcon(icon("fa5s.trash", color=STATUS_ERROR))
            self.btn_delete.setIconSize(CARD_ICON_SIZE)
            self.btn_delete.setProperty("class", "CardDangerIconBtn")
            self.btn_delete.setToolTip(
                t("snippet.delete_tip", "Delete this custom command")
            )
            self.btn_delete.clicked.connect(lambda: self.deleted.emit(self.snippet.get("id", "")))
            header_layout.addWidget(self.btn_delete)

        layout.addLayout(header_layout)

        # Description (if present)
        desc_text = self.snippet.get("description", "")
        if desc_text:
            self.lbl_desc = QLabel(desc_text)
            self.lbl_desc.setTextFormat(Qt.TextFormat.PlainText)
            self.lbl_desc.setObjectName("SnippetDesc")
            self.lbl_desc.setWordWrap(True)
            layout.addWidget(self.lbl_desc)

        # Command Box & Copy Button Row
        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(10)

        # Naturally wrapping selectable code label without expanding the card
        self.lbl_command = QLabel()
        self.lbl_command.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_command.setObjectName("CommandLabel")
        self.lbl_command.setWordWrap(True)
        self.lbl_command.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.lbl_command.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.lbl_command.setMinimumWidth(0)

        cmd_row.addWidget(self.lbl_command, stretch=1)

        # Inline Tweak Button
        self.btn_tweak = QPushButton()
        self.btn_tweak.setIcon(icon("fa5s.pen"))
        self.btn_tweak.setIconSize(CARD_ICON_SIZE)
        self.btn_tweak.setProperty("class", "CardIconBtn")
        self.btn_tweak.setToolTip(
            t("snippet.tweak_tip", "Befehl anpassen vor dem Kopieren")
        )
        self.btn_tweak.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tweak.clicked.connect(self._open_command_editor)
        cmd_row.addWidget(self.btn_tweak, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.btn_copy = QPushButton()
        self.btn_copy.setIcon(icon("fa5s.copy"))
        self.btn_copy.setIconSize(CARD_ICON_SIZE)
        self.btn_copy.setProperty("class", "CardIconBtn")
        self.btn_copy.setToolTip(t("snippet.copy", "Copy"))
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_command)
        cmd_row.addWidget(self.btn_copy, alignment=Qt.AlignmentFlag.AlignVCenter)
        cmd_row.setStretch(0, 1)

        layout.addLayout(cmd_row)

    def _open_command_editor(self) -> None:
        """Opens a roomy modal editor before copying an ad-hoc command variant."""
        dialog = CommandEditDialog(self._rendered_command, parent=self.window())
        if dialog.exec():
            text_to_copy = dialog.get_command()
            if text_to_copy:
                self._perform_clipboard_copy(text_to_copy, target_btn=self.btn_tweak)

    def update_variables(self, variables: Dict[str, Any]) -> None:
        """Rerenders the command template with current variables."""
        self.variables = variables
        template = self.snippet.get("template", "")
        self._rendered_command = TemplateEngine.render(template, variables)
        self.lbl_command.setText(self._rendered_command)

    def _perform_clipboard_copy(
        self, text_to_copy: str, target_btn: Optional[QPushButton] = None
    ) -> None:
        """Helper to copy text to clipboard and trigger visual feedback."""
        if not text_to_copy:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(text_to_copy)
        try:
            pyperclip.copy(text_to_copy)
        except (pyperclip.PyperclipException, OSError):
            pass

        btn = target_btn or self.btn_copy
        btn.setText("")
        btn.setIcon(icon("fa5s.check", color=STATUS_SUCCESS))
        btn.setProperty("class", "CardIconBtnSuccess")
        btn.setToolTip(t("snippet.copied", "Copied!"))
        btn.style().unpolish(btn)
        btn.style().polish(btn)

        QTimer.singleShot(1200, lambda: self._reset_copy_btn(btn))
        self.copied.emit(text_to_copy)

    def _reset_copy_btn(self, btn: Optional[QPushButton] = None) -> None:
        target = btn or self.btn_copy
        target.setText("")
        target.setProperty("class", "CardIconBtn")
        if target is self.btn_tweak:
            target.setIcon(icon("fa5s.pen"))
            target.setToolTip(t("snippet.tweak_tip", "Adjust command before copying"))
        else:
            target.setIcon(icon("fa5s.copy"))
            target.setToolTip(t("snippet.copy", "Copy"))
        target.style().unpolish(target)
        target.style().polish(target)

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
                parent=self.window(),
            )

            if dlg.exec():
                custom_values = dlg.get_values()
                if hasattr(main_win, "config") and hasattr(main_win.config, "set_cached_param"):
                    for k, v in custom_values.items():
                        main_win.config.set_cached_param(k, v)

                text_to_copy = TemplateEngine.render_with_custom(
                    template, self.variables, custom_values
                ).strip()
            else:
                return

        if text_to_copy:
            self._perform_clipboard_copy(text_to_copy)

    def _toggle_favorite(self) -> None:
        """Toggles favorite state for this snippet and emits signal."""
        current_state = bool(self.snippet.get("is_favorite", False))
        new_state = not current_state
        self.snippet["is_favorite"] = new_state

        self.btn_fav.setIcon(
            icon("fa5s.star", color=STATUS_WARNING if new_state else TEXT_DIMMED)
        )
        self.btn_fav.setProperty("class", "StarBtnActive" if new_state else "StarBtn")
        self.btn_fav.setToolTip(
            t("snippet.fav_remove", "Favorit entfernen")
            if new_state
            else t("snippet.fav_add", "Als Favorit anheften")
        )
        self.btn_fav.style().polish(self.btn_fav)

        self.favorite_toggled.emit(self.snippet.get("id", ""), new_state)
