from typing import Dict, Any, List, Optional, Callable
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QMenu,
    QMessageBox,
)

from core.snippet_manager import SnippetManager
from core.storage import PersistenceError, StorageError
from core.logger import get_logger
from core.menu_actions import MenuAction
from core.event_bus import EventBus, EventType
from core.i18n import t
from ui.snippet_card import SnippetCard
from ui.add_snippet_dialog import AddSnippetDialog
from ui.menu_builder import build_qmenu

logger = get_logger("cheatsheet_controller")


CATEGORY_SHORT_NAMES: Dict[str, tuple[str, str]] = {
    "all": ("cheatsheet.category_all", "All"),
    "favorites": ("cheatsheet.category_favorites", "★ Favorites"),
    "web_http": ("cheatsheet.category_web", "Web"),
    "linux_shell": ("cheatsheet.category_linux", "Linux"),
    "windows_powershell": ("cheatsheet.category_windows", "Windows"),
    "windows_ad": ("cheatsheet.category_windows", "Windows"),
    "network_scanning": ("cheatsheet.category_network", "Network"),
    "network_recon": ("cheatsheet.category_network", "Network"),
    "sql_databases": ("cheatsheet.category_sql", "SQL"),
    "crypto_encoding": ("cheatsheet.category_crypto", "Crypto"),
    "crypto_hashes": ("cheatsheet.category_crypto", "Crypto"),
    "shells_payloads": ("cheatsheet.category_shells", "Shells"),
    "password_cracking": ("cheatsheet.category_passwords", "Passwords"),
    "post_exploitation": ("cheatsheet.category_post_ex", "Post-Ex"),
    "custom_snippets": ("cheatsheet.category_custom", "Custom"),
}


def _category_short_name(category_id: str, fallback: str = "More") -> str:
    translation = CATEGORY_SHORT_NAMES.get(category_id)
    if translation is None:
        return fallback
    key, english_fallback = translation
    return t(key, english_fallback)


PRIORITY_CATEGORY_IDS: List[str] = [
    "all",
    "favorites",
    "custom_snippets",
    "web_http",
    "linux_shell",
    "windows_powershell",
    "windows_ad",
    "network_scanning",
    "network_recon",
    "sql_databases",
    "privesc",
    "file_transfer",
    "shells",
    "password_cracking",
    "pivoting",
    "av_evasion",
    "wireless",
    "cloud",
    "mobile",
    "iot_hardware",
    "social_engineering",
    "binary_exploitation",
    "cryptography",
    "forensics",
    "osint",
]


def _order_categories(cats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Orders categories by prioritized relevance while preserving defensive copies."""
    cat_by_id = {c.get("id"): c for c in cats}
    ordered = []
    seen = set()
    for pid in PRIORITY_CATEGORY_IDS:
        if pid in cat_by_id:
            ordered.append(cat_by_id[pid])
            seen.add(pid)
    for c in cats:
        cid = c.get("id")
        if cid not in seen:
            ordered.append(c)
            seen.add(cid)
    return ordered


def _estimate_pill_width(pill_text: str, font_metrics: QFontMetrics) -> int:
    """Calculates horizontal pixel requirement for a FilterPill button."""
    text_width = font_metrics.horizontalAdvance(pill_text)
    # FilterPill CSS padding: 3px 10px, border: 1px -> 22px + margin/safety
    return max(36, text_width + 24)


class CheatsheetController(QObject):
    """UI-independent controller managing cheatsheet snippets, categories, search filtering, and MenuAction DTOs."""

    category_changed = pyqtSignal(str)
    snippets_updated = pyqtSignal()

    def __init__(
        self,
        snippet_manager: SnippetManager,
        event_bus: Optional[EventBus] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.snippet_manager = snippet_manager
        self.event_bus = event_bus if event_bus is not None else EventBus()
        self.current_category_id: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}
        self.btn_more: Optional[QPushButton] = None
        self._more_menu: Optional[QMenu] = None
        self._overflow_cat_ids: List[str] = []
        self._search_expanded: bool = False
        self._last_query: str = ""
        self._last_visible_count: int = -1
        self._last_available_width: int = -1

    def _notify_persistence_error(
        self, operation: str, error: Exception, parent_widget: Optional[QWidget] = None
    ) -> None:
        logger.error(f"Persistence error during {operation}: {error}")
        target_widget = parent_widget
        if target_widget is None:
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                target_widget = app.activeWindow()
        QMessageBox.critical(
            target_widget,
            t("dialog.storage_error", "Speicherfehler"),
            t(
                "cheatsheet.storage_error_msg",
                "Snippet-Änderung konnte nicht auf die Festplatte geschrieben werden:\n{error}\n\nDie laufenden Sitzungsdaten im Speicher bleiben geschützt.",
                error=str(error),
            ),
        )

    # ------------------------------------------------------------------ #
    # Pure Domain Methods (UI-Independent)
    # ------------------------------------------------------------------ #

    def get_categories(self) -> List[Dict[str, Any]]:
        return self.snippet_manager.get_categories()

    def get_snippets(
        self, category_id: Optional[str] = None, search_query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        target_cat = category_id if category_id is not None else self.current_category_id
        return self.snippet_manager.get_snippets(category_id=target_cat, search_query=search_query)

    def add_custom_snippet(
        self,
        title: str,
        category: str,
        subcategory: str,
        template: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> str:
        try:
            new_snip = self.snippet_manager.add_custom_snippet(
                title=title,
                category=category,
                subcategory=subcategory,
                template=template,
                description=description,
                tags=tags or [],
            )
            self.snippets_updated.emit()
            self.event_bus.publish(
                EventType.SNIPPETS_UPDATED, {"action": "add", "snippet": new_snip}
            )
            return new_snip["id"] if isinstance(new_snip, dict) else str(new_snip)
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("add_custom_snippet", e)
            return ""

    def delete_snippet(self, snippet_id: str) -> None:
        try:
            self.snippet_manager.delete_snippet(snippet_id)
            self.snippets_updated.emit()
            self.event_bus.publish(
                EventType.SNIPPETS_UPDATED, {"action": "delete", "id": snippet_id}
            )
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("delete_snippet", e)

    def toggle_favorite(self, snippet_id: str) -> bool:
        try:
            is_fav = self.snippet_manager.toggle_favorite(snippet_id)
            self.snippets_updated.emit()
            self.event_bus.publish(
                EventType.SNIPPETS_UPDATED,
                {"action": "favorite", "id": snippet_id, "is_favorite": is_fav},
            )
            return is_fav
        except (PersistenceError, StorageError, OSError) as e:
            self._notify_persistence_error("toggle_favorite", e)
            return False

    def get_overflow_category_actions(
        self,
        on_select_category: Optional[Callable[[str], None]] = None,
        overflow_cats: Optional[List[Dict[str, Any]]] = None,
    ) -> List[MenuAction]:
        """Returns MenuAction DTOs for categories that overflow the primary horizontal bar."""
        if overflow_cats is None:
            cats = self.get_categories()
            if self._overflow_cat_ids:
                overflow_cats = [c for c in cats if c.get("id") in self._overflow_cat_ids]
            else:
                primary_ids = set(PRIORITY_CATEGORY_IDS[:10])
                overflow_cats = [c for c in cats if c.get("id") not in primary_ids]

        actions: List[MenuAction] = []
        for c in overflow_cats:
            cid = c.get("id")
            cname = c.get("name", cid).strip().lstrip("\ufe0f \t")
            count = c.get("count", 0)
            text = f"{cname} ({count})" if count else cname
            is_active = cid == self.current_category_id
            actions.append(
                MenuAction(
                    id=f"select_cat:{cid}",
                    text=text,
                    checked=is_active,
                    callback=lambda target_cid=cid: (
                        on_select_category(target_cid)
                        if on_select_category
                        else self.select_category(target_cid)
                    ),
                    data={"category_id": cid},
                )
            )
        return actions

    # ------------------------------------------------------------------ #
    # UI Selection & Pill Adapters
    # ------------------------------------------------------------------ #

    def select_category(self, category_id: str) -> None:
        self.current_category_id = category_id
        self._search_expanded = False

        # Update primary pill styles
        for cid, btn in self.filter_buttons.items():
            is_active = cid == category_id
            btn.setProperty("class", "FilterPillActive" if is_active else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Update "Mehr ▾" button state
        if self.btn_more:
            if category_id in self._overflow_cat_ids:
                short = _category_short_name(category_id, t("cheatsheet.more", "More"))
                self.btn_more.setText(f"{short} ▾")
                self.btn_more.setProperty("class", "FilterPillActive")
            else:
                self.btn_more.setText(t("cheatsheet.more_categories", "More ▾"))
                self.btn_more.setProperty("class", "FilterPill")
            self.btn_more.style().unpolish(self.btn_more)
            self.btn_more.style().polish(self.btn_more)

        self.category_changed.emit(category_id)

    def _calculate_visible_count(
        self,
        available_width: int,
        ordered_cats: List[Dict[str, Any]],
        font_metrics: QFontMetrics,
        spacing: int = 6,
    ) -> int:
        """Determines how many category pills fit horizontally before overflowing into 'Mehr ▾'."""
        n = len(ordered_cats)
        if n == 0 or available_width <= 0:
            return 0

        pill_widths = []
        for c in ordered_cats:
            cid = c.get("id")
            full_name = c.get("name", "").strip().lstrip("\ufe0f \t")
            pill_text = _category_short_name(cid, full_name[:12])
            pill_widths.append(_estimate_pill_width(pill_text, font_metrics))

        # Check if all n items fit directly without "Mehr ▾"
        total_all = sum(pill_widths) + max(0, n - 1) * spacing
        if total_all <= available_width:
            return n

        # Otherwise we need the "Mehr ▾" button at the end
        more_text = t("cheatsheet.more_categories", "More ▾")
        more_width = _estimate_pill_width(more_text, font_metrics) + 12

        # Find largest k >= 1 such that first k items + more_width + k * spacing <= available_width
        current_width = 0
        best_k = 1
        for k in range(1, n):
            current_width += pill_widths[k - 1]
            total_with_more = current_width + (k * spacing) + more_width
            if total_with_more <= available_width:
                best_k = k
            else:
                break
        return best_k

    def build_filter_pills(
        self,
        pills_layout: QHBoxLayout,
        on_select_category: Callable[[str], None],
        available_width: Optional[int] = None,
    ) -> None:
        """Populates horizontal category pills dynamically based on available width."""
        self.filter_buttons.clear()
        self._overflow_cat_ids.clear()
        self.btn_more = None
        self._more_menu = None

        # Clear existing widgets from layout if any
        while pills_layout.count():
            item = pills_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cats = self.snippet_manager.get_categories()
        ordered_cats = _order_categories(cats)

        parent = pills_layout.parentWidget()
        font = parent.font() if parent else QFont()
        font_metrics = QFontMetrics(font)

        if available_width is None or available_width < 300:
            if parent and parent.width() >= 300:
                margins = pills_layout.contentsMargins()
                available_width = max(0, parent.width() - margins.left() - margins.right())
            else:
                available_width = 720 - 40  # Sensible default width

        visible_count = self._calculate_visible_count(
            available_width, ordered_cats, font_metrics, spacing=pills_layout.spacing()
        )
        self._last_visible_count = visible_count
        self._last_available_width = available_width

        primary_cats = ordered_cats[:visible_count]
        overflow_cats = ordered_cats[visible_count:]

        # Render primary pills on the bar
        for c in primary_cats:
            cat_id = c.get("id")
            full_name = c.get("name", "").strip().lstrip("\ufe0f \t")
            pill_text = _category_short_name(cat_id, full_name[:12])

            btn = QPushButton(pill_text)
            btn.setToolTip(f"{full_name} ({c.get('count', 0)})" if full_name else pill_text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty(
                "class", "FilterPillActive" if cat_id == self.current_category_id else "FilterPill"
            )
            btn.clicked.connect(lambda checked=False, cid=cat_id: on_select_category(cid))
            self.filter_buttons[cat_id] = btn
            pills_layout.addWidget(btn)

        # Render "Mehr ▾" dropdown menu button for remaining categories
        if overflow_cats:
            self._overflow_cat_ids = [c.get("id") for c in overflow_cats]

            is_overflow_active = self.current_category_id in self._overflow_cat_ids
            more_label = t("cheatsheet.more_categories", "More ▾")
            if is_overflow_active:
                short = _category_short_name(
                    self.current_category_id,
                    t("cheatsheet.more", "More"),
                )
                more_label = f"{short} ▾"

            self.btn_more = QPushButton(more_label)
            self.btn_more.setProperty(
                "class", "FilterPillActive" if is_overflow_active else "FilterPill"
            )
            self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_more.setToolTip(t("cheatsheet.more_categories_tip", "Show more categories"))

            actions = self.get_overflow_category_actions(
                on_select_category, overflow_cats=overflow_cats
            )
            self._more_menu = build_qmenu(actions, parent_widget=self.btn_more)
            self.btn_more.setMenu(self._more_menu)
            pills_layout.addWidget(self.btn_more)

        pills_layout.addStretch()

    def update_pills_width(
        self,
        available_width: int,
        on_select_category: Callable[[str], None],
        pills_layout: QHBoxLayout,
    ) -> bool:
        """Dynamically adjusts visible pills to match available width with zero layout thrashing."""
        if available_width <= 0:
            return False

        cats = self.snippet_manager.get_categories()
        ordered_cats = _order_categories(cats)
        parent = pills_layout.parentWidget()
        font = parent.font() if parent else QFont()
        font_metrics = QFontMetrics(font)

        target_count = self._calculate_visible_count(
            available_width, ordered_cats, font_metrics, spacing=pills_layout.spacing()
        )
        if target_count != self._last_visible_count:
            self.build_filter_pills(
                pills_layout,
                on_select_category,
                available_width=available_width,
            )
            return True
        return False

    def _on_favorite_toggled(self, snippet_id: str, is_fav: bool) -> None:
        """Handles toggling favorite on a card."""
        self.toggle_favorite(snippet_id)

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        variables: Dict[str, str],
        on_delete_snippet: Callable[[str], None],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None],
        on_copied: Optional[Callable[[str], None]] = None,
    ) -> List[QWidget]:
        # Reset expand state if search query changed
        if search_query != self._last_query:
            self._search_expanded = False
            self._last_query = search_query

        all_matching = self.snippet_manager.get_snippets(
            category_id=self.current_category_id, search_query=search_query
        )

        if not all_matching:
            show_empty_state_fn(
                t("cheatsheet.empty_state", "No commands found. Press Ctrl+N to add a new command.")
            )
            return []

        # When searching, cap at top 25 unless expanded
        is_capped = (
            bool(search_query.strip()) and not self._search_expanded and len(all_matching) > 25
        )
        snippets = all_matching[:25] if is_capped else all_matching

        rendered_cards: List[QWidget] = []
        for s in snippets:
            card = SnippetCard(s, variables=variables, parent=parent_widget)
            card.snippet_deleted.connect(on_delete_snippet)
            card.favorite_toggled.connect(self._on_favorite_toggled)
            if on_copied is not None:
                card.copied.connect(on_copied)
            content_layout.addWidget(card)
            rendered_cards.append(card)

        # If capped, render expander button
        if is_capped:
            remaining = len(all_matching) - len(snippets)
            btn_expand = QPushButton(
                t(
                    "cheatsheet.expand_results",
                    "▾ Show {remaining} more results (Total {total})",
                    remaining=remaining,
                    total=len(all_matching),
                )
            )
            btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_expand.setStyleSheet("""
                QPushButton {
                    background: rgba(0, 229, 255, 0.08);
                    border: 1px dashed rgba(0, 229, 255, 0.35);
                    border-radius: 6px;
                    color: #00e5ff;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 8px;
                    margin: 8px 4px 12px 4px;
                }
                QPushButton:hover {
                    background: rgba(0, 229, 255, 0.18);
                    border: 1px solid #00e5ff;
                }
            """)

            def _expand():
                self._search_expanded = True
                self.snippets_updated.emit()

            btn_expand.clicked.connect(_expand)
            content_layout.addWidget(btn_expand)
            rendered_cards.append(btn_expand)

        return rendered_cards

    def update_variables(self, cards: List[QWidget], variables: Dict[str, str]) -> None:
        for card in cards:
            if isinstance(card, SnippetCard):
                card.update_variables(variables)

    def open_add_dialog(self, parent_widget: QWidget) -> bool:
        cats = self.snippet_manager.get_categories()
        dlg = AddSnippetDialog(cats, parent=parent_widget)
        if dlg.exec():
            data = dlg.get_data()
            self.add_custom_snippet(
                title=data["title"],
                category=data["category"],
                subcategory=data["subcategory"],
                template=data["template"],
                description=data["description"],
                tags=data.get("tags", []),
            )
            return True
        return False
