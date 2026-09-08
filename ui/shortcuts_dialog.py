"""
Shortcut Help Dialog for SpectreHUD.

Compact, dark cyber-themed dialog presenting a centralized overview of all
global and in-app keyboard shortcuts with live search filtering.
"""

from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QShortcut, QKeySequence

from core.shortcuts import ShortcutDefinition, get_shortcuts
from core.i18n import t
from ui.base_dialog import BaseHudDialog


CATEGORY_TITLES = {
    "phases": ("shortcuts.cat_phases", "PENTEST PHASEN"),
    "quick_capture": ("shortcuts.cat_quick_capture", "QUICK CAPTURE & STEUERUNG"),
    "navigation": ("shortcuts.cat_navigation", "NAVIGATION & MODI"),
    "general": ("shortcuts.cat_general", "ALLGEMEINE BEDIENUNG"),
    "report_editor": ("shortcuts.cat_report_editor", "REPORT EDITOR (NUR IM REPORT-MODUS)"),
}


class ShortcutRow(QFrame):
    """Visual row for a single shortcut definition."""

    def __init__(self, definition: ShortcutDefinition, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.definition = definition
        self.setObjectName("ShortcutRow")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(10)

        # 1. Key Badge
        self.lbl_key = QLabel(self.definition.sequence, self)
        self.lbl_key.setObjectName("ShortcutKeyBadge")
        self.lbl_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_key.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.lbl_key)

        # 2. Description Label
        self.desc_text = t(self.definition.label_key, self.definition.default_label)
        self.lbl_desc = QLabel(self.desc_text, self)
        self.lbl_desc.setObjectName("ShortcutDescription")
        self.lbl_desc.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.lbl_desc, stretch=1)

        # 3. Scope Badge
        is_global = self.definition.scope == "global"
        scope_text = (
            t("shortcuts.scope_global_badge", "GLOBAL")
            if is_global
            else t("shortcuts.scope_in_app_badge", "IN-APP")
        )
        self.lbl_scope = QLabel(scope_text, self)
        self.lbl_scope.setObjectName("ShortcutScopeBadge")
        self.lbl_scope.setProperty("scope", "global" if is_global else "in_app")
        self.lbl_scope.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_scope.setTextFormat(Qt.TextFormat.PlainText)
        if is_global:
            self.lbl_scope.setToolTip(
                t(
                    "shortcuts.scope_global_tip",
                    "Funktioniert systemweit (auch wenn SpectreHUD minimiert ist)",
                )
            )
        else:
            self.lbl_scope.setToolTip(
                t(
                    "shortcuts.scope_in_app_tip",
                    "Aktiv, wenn das SpectreHUD-Fenster fokussiert ist",
                )
            )
        layout.addWidget(self.lbl_scope)

    def matches(self, query: str) -> bool:
        """Check if this shortcut matches the filter search query."""
        if not query:
            return True
        q = query.lower()
        return (
            q in self.definition.sequence.lower()
            or q in self.desc_text.lower()
            or q in self.definition.category.lower()
            or q in self.definition.scope.lower()
        )


class ShortcutSection(QWidget):
    """Section container grouping shortcuts under a category header."""

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title
        self.rows: List[ShortcutRow] = []
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; background-color: transparent;")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 8)
        self._layout.setSpacing(4)

        # Header label
        self.header_label = QLabel(title, self)
        self.header_label.setObjectName("ShortcutSectionTitle")
        self._layout.addWidget(self.header_label)

    def add_row(self, row: ShortcutRow) -> None:
        self.rows.append(row)
        self._layout.addWidget(row)

    def filter_rows(self, query: str) -> int:
        """Filters rows and hides section if all rows are hidden. Returns visible count."""
        visible_count = 0
        for row in self.rows:
            matched = row.matches(query)
            row.setVisible(matched)
            if matched:
                visible_count += 1
        self.setVisible(visible_count > 0)
        return visible_count


class ShortcutHelpDialog(BaseHudDialog):
    """
    Compact, frameless dialog displaying SpectreHUD keyboard shortcuts
    with live search filtering and distinct Global vs In-App scoping.
    """

    def __init__(self, config_manager: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(title=t("shortcuts.title", "SPECTRE // SHORTCUTS"), parent=parent)
        self.config_manager = config_manager
        self.resize(620, 520)

        if hasattr(self, "content_container") and self.content_container:
            self.content_container.setAutoFillBackground(False)
            self.content_container.setStyleSheet(
                "background: transparent; background-color: transparent;"
            )

        self._sections: List[ShortcutSection] = []
        self._init_dialog_ui()

        # Keyboard shortcuts inside dialog
        QShortcut(QKeySequence("Ctrl+/"), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.txt_search.setFocus)

    def _init_dialog_ui(self) -> None:
        # Search filter bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.txt_search = QLineEdit(self)
        self.txt_search.setObjectName("ShortcutSearch")
        self.txt_search.setPlaceholderText(
            t(
                "shortcuts.search_placeholder",
                "Shortcuts oder Aktionen filtern (z. B. 'Phase', 'Loot', 'Ctrl+S')...",
            )
        )
        self.txt_search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.txt_search)

        self.body_layout.addLayout(search_row)

        # Scrollable container for shortcut sections
        scroll = QScrollArea(self)
        scroll.setObjectName("ShortcutsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setObjectName("ShortcutsScrollViewport")

        container = QWidget()
        container.setObjectName("ShortcutsContainer")
        container.setAutoFillBackground(False)
        container.setStyleSheet("background: transparent; background-color: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 6, 4)
        container_layout.setSpacing(6)

        # Load shortcuts and group by category
        shortcuts = get_shortcuts(self.config_manager)
        grouped: Dict[str, List[ShortcutDefinition]] = {}
        for sc in shortcuts:
            grouped.setdefault(sc.category, []).append(sc)

        # Build sections in standard order
        category_order = ["phases", "quick_capture", "navigation", "general", "report_editor"]
        for cat_key in category_order:
            if cat_key not in grouped:
                continue

            i18n_key, fallback_title = CATEGORY_TITLES.get(cat_key, (cat_key, cat_key.upper()))
            sec_title = t(i18n_key, fallback_title)
            section = ShortcutSection(sec_title, container)
            for sc_def in grouped[cat_key]:
                row = ShortcutRow(sc_def, section)
                section.add_row(row)

            self._sections.append(section)
            container_layout.addWidget(section)

        container_layout.addStretch()
        scroll.setWidget(container)
        self.body_layout.addWidget(scroll, stretch=1)

        # Footer hint
        lbl_hint = QLabel(
            t("shortcuts.footer_hint", "Tipp: Drücke Esc oder Ctrl+/ zum Schließen"),
            self,
        )
        lbl_hint.setObjectName("ShortcutFooterHint")
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_layout.addWidget(lbl_hint)

    def _on_search_changed(self, text: str) -> None:
        """Filters all shortcut sections based on search input."""
        query = text.strip()
        for section in self._sections:
            section.filter_rows(query)
