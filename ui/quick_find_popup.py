"""
Quick-Find Snippet HUD for SpectreHUD.

Spotlight-style lightweight popup for fast search over existing cheatsheet
snippets with instant variable interpolation and clipboard copying.
"""

import sys
from typing import Any, Callable, Dict, List, Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QEvent, QTimer
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QKeyEvent, QMouseEvent

from core.i18n import t
from core.snippets import TemplateEngine
from ui.styles.icons import get_theme_color
from ui.styles.theme import rgba_str


class SnippetResultRow(QFrame):
    """Clickable row representing a single search result snippet."""

    clicked = pyqtSignal(dict)

    def __init__(self, snippet: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.snippet = snippet
        self._is_selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()
        self.update_style()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # Top line: Title & Category / Subcategory
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        title_text = self.snippet.get("title", "")
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setStyleSheet(
            f"color: {get_theme_color('TEXT_PRIMARY')}; font-size: 12px; font-weight: 600;"
        )
        top_layout.addWidget(self.lbl_title, stretch=1)

        category_text = self.snippet.get("category", "") or self.snippet.get("subcategory", "")
        if category_text:
            self.lbl_category = QLabel(category_text)
            self.lbl_category.setStyleSheet(
                f"color: {get_theme_color('CYBER_BLUE_LIGHT')}; font-size: 10px; "
                f"background-color: {rgba_str(QColor(get_theme_color('BG_SURFACE')), 0.8)}; "
                f"border-radius: 3px; padding: 1px 5px;"
            )
            top_layout.addWidget(self.lbl_category)

        layout.addLayout(top_layout)

        # Bottom line: Template preview (elided command preview)
        template_text = self.snippet.get("template", "").replace("\n", " ").strip()
        self.lbl_template = QLabel(template_text)
        self.lbl_template.setStyleSheet(
            f"color: {get_theme_color('TEXT_MUTED')}; font-family: monospace; font-size: 11px;"
        )
        layout.addWidget(self.lbl_template)

    def set_selected(self, selected: bool) -> None:
        if self._is_selected != selected:
            self._is_selected = selected
            self.update_style()

    def update_style(self) -> None:
        if self._is_selected:
            bg = rgba_str(QColor(get_theme_color("CYAN_LIGHT")), 0.15)
            border = rgba_str(QColor(get_theme_color("CYAN_LIGHT")), 0.5)
        else:
            bg = "transparent"
            border = "transparent"

        self.setStyleSheet(
            f"""
            SnippetResultRow {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
            }}
            """
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.snippet)
        super().mousePressEvent(event)


class QuickFindPopup(QWidget):
    """
    Frameless, spotlight-style popup positioned near the mouse cursor
    for fast searching and copying of cheatsheet commands.
    """

    snippet_copied = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(
        self,
        cheatsheet_controller: Any,
        variable_provider: Optional[Callable[[], Dict[str, Any]]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.cheatsheet_ctrl = cheatsheet_controller
        self.variable_provider = variable_provider or dict
        self._has_been_active = False
        self._current_results: List[Dict[str, Any]] = []
        self._result_widgets: List[SnippetResultRow] = []
        self._selected_index: int = -1

        self._init_window()
        self._init_ui()

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(520, 320)

    def _init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)

        # Card container with glass HUD styling
        self.card = QFrame(self)
        self.card.setObjectName("QuickFindCard")
        bg_col = QColor(get_theme_color("BG_DARK"))
        accent_col = QColor(get_theme_color("ACCENT_BRAND"))
        self.card.setStyleSheet(
            f"""
            QFrame#QuickFindCard {{
                background-color: {rgba_str(bg_col, 0.96)};
                border: 1px solid {rgba_str(accent_col, 0.45)};
                border-radius: 8px;
            }}
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)

        # 1. Header Row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        lbl_title = QLabel(t("quick_find.title", "⚡ QUICK-FIND"))
        lbl_title.setToolTip(
            t(
                "quick_find.purpose_tip",
                "Cheatsheet-Snippets schnell durchsuchen und in die Zwischenablage kopieren",
            )
        )
        lbl_title.setStyleSheet(
            f"color: {get_theme_color('ACCENT_BRAND')}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;"
        )
        header_layout.addWidget(lbl_title)

        header_layout.addStretch()

        self.lbl_hint = QLabel("Esc: Close  |  \u21c5: Select  |  Enter: Copy")
        self.lbl_hint.setStyleSheet(
            f"color: {get_theme_color('TEXT_MUTED')}; font-size: 10px;"
        )
        header_layout.addWidget(self.lbl_hint)
        card_layout.addLayout(header_layout)

        # 2. Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            t("quick_find.placeholder", "Snippets durchsuchen...")
        )
        input_bg = QColor(get_theme_color("BG_INPUT"))
        border_col = QColor(get_theme_color("BORDER_DEFAULT"))
        focus_col = QColor(get_theme_color("ACCENT_BRAND"))
        self.search_input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {rgba_str(input_bg, 0.9)};
                color: {get_theme_color('TEXT_PRIMARY')};
                border: 1px solid {rgba_str(border_col, 0.5)};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {rgba_str(focus_col, 0.8)};
            }}
            """
        )
        self.search_input.textChanged.connect(self._on_search_changed)
        self.search_input.installEventFilter(self)
        card_layout.addWidget(self.search_input)

        # 3. Results Container
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 4, 0, 0)
        self.results_layout.setSpacing(4)

        # Status / Placeholder Label
        self.lbl_status = QLabel(
            t("quick_find.empty_prompt", "Tippen, um Snippets zu durchsuchen...")
        )
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(
            f"color: {get_theme_color('TEXT_MUTED')}; font-size: 12px; padding: 30px 0;"
        )
        self.results_layout.addWidget(self.lbl_status)
        self.results_layout.addStretch()

        card_layout.addWidget(self.results_container, stretch=1)
        outer_layout.addWidget(self.card)

    def eventFilter(self, watched, event: QEvent) -> bool:
        if watched == self.search_input and event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event  # type: ignore[assignment]
            key = key_event.key()

            if key == Qt.Key.Key_Down:
                self._select_next()
                return True
            elif key == Qt.Key.Key_Up:
                self._select_prev()
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._copy_selected()
                return True
            elif key == Qt.Key.Key_Escape:
                self.close()
                return True

        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._copy_selected()
            return
        if key == Qt.Key.Key_Down:
            self._select_next()
            return
        if key == Qt.Key.Key_Up:
            self._select_prev()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Dismisses popup if user clicks on the outer transparent margin."""
        if not self.card.geometry().contains(event.pos()):
            self.close()
            return
        super().mousePressEvent(event)

    def changeEvent(self, event: Optional[QEvent]) -> None:
        if event is not None and event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self._has_been_active = True
            elif self._has_been_active:
                self.close()
        super().changeEvent(event)

    def closeEvent(self, event) -> None:
        self.closed.emit()
        super().closeEvent(event)

    def _on_search_changed(self, text: str) -> None:
        query = text.strip()
        if not query:
            self._clear_results()
            self.lbl_status.setText(
                t("quick_find.empty_prompt", "Tippen, um Snippets zu durchsuchen...")
            )
            self.lbl_status.show()
            return

        try:
            snippets = self.cheatsheet_ctrl.get_snippets(category_id="all", search_query=query)
        except Exception:
            snippets = []

        # Enforce hard limit of max 5 results
        self._current_results = snippets[:5]
        self._populate_results()

    def _clear_widgets(self) -> None:
        for widget in self._result_widgets:
            self.results_layout.removeWidget(widget)
            widget.deleteLater()
        self._result_widgets.clear()
        self._selected_index = -1

    def _clear_results(self) -> None:
        self._current_results = []
        self._clear_widgets()

    def _populate_results(self) -> None:
        self._clear_widgets()

        if not self._current_results:
            self.lbl_status.setText(
                t("quick_find.no_results", "Keine passenden Snippets gefunden")
            )
            self.lbl_status.show()
            return

        self.lbl_status.hide()

        for idx, snip in enumerate(self._current_results):
            row = SnippetResultRow(snip, parent=self.results_container)
            row.clicked.connect(self._copy_item)
            self.results_layout.insertWidget(idx, row)
            self._result_widgets.append(row)

        self._selected_index = 0
        self._update_selection()

    def _select_next(self) -> None:
        if not self._result_widgets:
            return
        self._selected_index = (self._selected_index + 1) % len(self._result_widgets)
        self._update_selection()

    def _select_prev(self) -> None:
        if not self._result_widgets:
            return
        self._selected_index = (self._selected_index - 1 + len(self._result_widgets)) % len(
            self._result_widgets
        )
        self._update_selection()

    def _update_selection(self) -> None:
        for idx, row in enumerate(self._result_widgets):
            row.set_selected(idx == self._selected_index)

    def _copy_selected(self) -> None:
        if 0 <= self._selected_index < len(self._current_results):
            self._copy_item(self._current_results[self._selected_index])

    def _copy_item(self, snippet: Dict[str, Any]) -> None:
        template = snippet.get("template", "")
        variables = self.variable_provider() if callable(self.variable_provider) else {}
        rendered = TemplateEngine.render(template, variables)

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(rendered)
        try:
            import pyperclip

            pyperclip.copy(rendered)
        except Exception:
            pass

        self.snippet_copied.emit(rendered)

        # Brief visual feedback before closing
        self.lbl_hint.setText(t("quick_find.copied", "Kopiert!"))
        self.lbl_hint.setStyleSheet(
            f"color: {get_theme_color('STATUS_SUCCESS')}; font-weight: bold; font-size: 11px;"
        )
        QTimer.singleShot(120, self.close)

    def _force_focus_input(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                hwnd = int(self.winId())
                fg = user32.GetForegroundWindow()
                if fg != hwnd:
                    fore_thread = user32.GetWindowThreadProcessId(fg, None)
                    app_thread = kernel32.GetCurrentThreadId()
                    if fore_thread != app_thread and fore_thread != 0:
                        user32.AttachThreadInput(fore_thread, app_thread, True)
                        user32.BringWindowToTop(hwnd)
                        user32.SetForegroundWindow(hwnd)
                        user32.AttachThreadInput(fore_thread, app_thread, False)
                    else:
                        user32.BringWindowToTop(hwnd)
                        user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

        self.raise_()
        self.activateWindow()
        self.search_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.search_input.selectAll()

    def show_at_cursor(self) -> None:
        """Positions the popup near the active mouse cursor clamped to screen bounds."""
        self._has_been_active = False
        self.search_input.clear()
        self._clear_results()
        self.lbl_hint.setText("Esc: Close  |  \u21c5: Select  |  Enter: Copy")
        self.lbl_hint.setStyleSheet(
            f"color: {get_theme_color('TEXT_MUTED')}; font-size: 10px;"
        )
        self.lbl_status.setText(
            t("quick_find.empty_prompt", "Tippen, um Snippets zu durchsuchen...")
        )
        self.lbl_status.show()

        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()

        popup_width = self.width()
        popup_height = self.height()

        target_x = cursor_pos.x() - (popup_width // 2)
        target_y = cursor_pos.y() - (popup_height // 2)

        if screen:
            geom = screen.availableGeometry()
            target_x = max(geom.left() + 10, min(target_x, geom.right() - popup_width - 10))
            target_y = max(geom.top() + 10, min(target_y, geom.bottom() - popup_height - 10))

        self.move(QPoint(target_x, target_y))
        self.show()
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive
        )
        self.raise_()
        self.activateWindow()

        self._force_focus_input()
        QTimer.singleShot(0, self._force_focus_input)
        QTimer.singleShot(150, self._arm_autoclose)

    def _arm_autoclose(self) -> None:
        """Ensures the popup is marked active so focus-loss dismissal works reliably."""
        if self.isVisible():
            self._has_been_active = True
