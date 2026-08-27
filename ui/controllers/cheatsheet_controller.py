from typing import Dict, Any, List, Optional, Callable
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu

from core.snippet_manager import SnippetManager
from ui.snippet_card import SnippetCard
from ui.add_snippet_dialog import AddSnippetDialog


CATEGORY_SHORT_NAMES: Dict[str, str] = {
    "all": "Alle",
    "favorites": "★ Favoriten",
    "web_http": "Web",
    "linux_shell": "Linux",
    "windows_powershell": "Windows",
    "windows_ad": "Windows",
    "network_scanning": "Netzwerk",
    "network_recon": "Netzwerk",
    "sql_databases": "SQL",
    "crypto_encoding": "Krypto",
    "crypto_hashes": "Krypto",
    "shells_payloads": "Shells",
    "password_cracking": "Passwörter",
    "post_exploitation": "Post-Ex",
    "custom_snippets": "Eigene",
}


class CheatsheetController(QObject):
    """Controller managing cheatsheet snippets, categories, search filtering, and interpolation."""

    category_changed = pyqtSignal(str)
    snippets_updated = pyqtSignal()

    def __init__(self, snippet_manager: SnippetManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.snippet_manager = snippet_manager
        self.current_category_id: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}
        self.btn_more: Optional[QPushButton] = None
        self._more_menu: Optional[QMenu] = None
        self._overflow_cat_ids: List[str] = []
        self._search_expanded: bool = False
        self._last_query: str = ""

    def select_category(self, category_id: str) -> None:
        self.current_category_id = category_id
        self._search_expanded = False
        
        # Update primary pill styles
        for cid, btn in self.filter_buttons.items():
            is_active = (cid == category_id)
            btn.setProperty("class", "FilterPillActive" if is_active else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Update "Mehr ▾" button state
        if self.btn_more:
            if category_id in self._overflow_cat_ids:
                short = CATEGORY_SHORT_NAMES.get(category_id, "Mehr")
                self.btn_more.setText(f"{short} ▾")
                self.btn_more.setProperty("class", "FilterPillActive")
            else:
                self.btn_more.setText("Mehr ▾")
                self.btn_more.setProperty("class", "FilterPill")
            self.btn_more.style().unpolish(self.btn_more)
            self.btn_more.style().polish(self.btn_more)

        self.category_changed.emit(category_id)

    def build_filter_pills(
        self, 
        pills_layout: QHBoxLayout, 
        on_select_category: Callable[[str], None]
    ) -> None:
        self.filter_buttons.clear()
        self._overflow_cat_ids.clear()
        self.btn_more = None
        self._more_menu = None

        cats = self.snippet_manager.get_categories()

        # Group categories: Keep top categories as primary pills, place rest in "Mehr ▾"
        primary_ids = {
            "all", "favorites", "web_http", "linux_shell", 
            "windows_powershell", "windows_ad", 
            "network_scanning", "network_recon", 
            "sql_databases", "custom_snippets"
        }

        all_cat = None
        fav_cat = None
        custom_cat = None
        primary_cats = []
        overflow_cats = []

        for c in cats:
            cid = c.get("id")
            if cid == "all":
                all_cat = c
            elif cid == "favorites":
                fav_cat = c
            elif cid == "custom_snippets":
                custom_cat = c
            elif cid in primary_ids:
                primary_cats.append(c)
            else:
                overflow_cats.append(c)

        ordered_primary = []
        if all_cat:
            ordered_primary.append(all_cat)
        if fav_cat:
            ordered_primary.append(fav_cat)
        ordered_primary.extend(primary_cats)
        if custom_cat:
            ordered_primary.append(custom_cat)

        # Render primary pills on the bar
        for c in ordered_primary:
            cat_id = c.get("id")
            full_name = c.get("name", "").strip().lstrip("\ufe0f \t")
            pill_text = CATEGORY_SHORT_NAMES.get(cat_id, full_name[:12])

            btn = QPushButton(pill_text)
            btn.setToolTip(f"{full_name} ({c.get('count', 0)})" if full_name else pill_text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "FilterPillActive" if cat_id == self.current_category_id else "FilterPill")
            btn.clicked.connect(lambda checked=False, cid=cat_id: on_select_category(cid))
            self.filter_buttons[cat_id] = btn
            pills_layout.addWidget(btn)

        # Render "Mehr ▾" dropdown menu button for remaining categories
        if overflow_cats:
            self._overflow_cat_ids = [c.get("id") for c in overflow_cats]

            is_overflow_active = self.current_category_id in self._overflow_cat_ids
            more_label = "Mehr ▾"
            if is_overflow_active:
                short = CATEGORY_SHORT_NAMES.get(self.current_category_id, "Mehr")
                more_label = f"{short} ▾"

            self.btn_more = QPushButton(more_label)
            self.btn_more.setProperty("class", "FilterPillActive" if is_overflow_active else "FilterPill")
            self.btn_more.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_more.setToolTip("Weitere Kategorien anzeigen")

            self._more_menu = QMenu(self.btn_more)
            for c in overflow_cats:
                cid = c.get("id")
                cname = c.get("name", cid).strip().lstrip("\ufe0f \t")
                count = c.get("count", 0)
                action_text = f"{cname} ({count})" if count else cname
                
                act = self._more_menu.addAction(action_text)
                act.triggered.connect(lambda checked=False, target_cid=cid: on_select_category(target_cid))

            self.btn_more.setMenu(self._more_menu)
            pills_layout.addWidget(self.btn_more)

        pills_layout.addStretch()

    def _on_favorite_toggled(self, snippet_id: str, is_fav: bool) -> None:
        """Handles toggling favorite on a card."""
        self.snippet_manager.toggle_favorite(snippet_id)
        self.snippets_updated.emit()

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        variables: Dict[str, str],
        on_delete_snippet: Callable[[str], None],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None]
    ) -> List[QWidget]:
        # Reset expand state if search query changed
        if search_query != self._last_query:
            self._search_expanded = False
            self._last_query = search_query

        all_matching = self.snippet_manager.get_snippets(
            category_id=self.current_category_id,
            search_query=search_query
        )

        if not all_matching:
            show_empty_state_fn("Keine Befehle gefunden. Drücke Ctrl+N zum Hinzufügen.")
            return []

        # When searching, cap at top 25 unless expanded
        is_capped = bool(search_query.strip()) and not self._search_expanded and len(all_matching) > 25
        snippets = all_matching[:25] if is_capped else all_matching

        rendered_cards: List[QWidget] = []
        for s in snippets:
            card = SnippetCard(s, variables=variables, parent=parent_widget)
            card.snippet_deleted.connect(on_delete_snippet)
            card.favorite_toggled.connect(self._on_favorite_toggled)
            content_layout.addWidget(card)
            rendered_cards.append(card)

        # If capped, render expander button
        if is_capped:
            remaining = len(all_matching) - len(snippets)
            btn_expand = QPushButton(f"▾ Weitere {remaining} Treffer anzeigen (Insgesamt {len(all_matching)})")
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
            self.snippet_manager.add_custom_snippet(
                title=data["title"],
                category=data["category"],
                subcategory=data["subcategory"],
                template=data["template"],
                description=data["description"],
                tags=data.get("tags", [])
            )
            self.snippets_updated.emit()
            return True
        return False

    def delete_snippet(self, snippet_id: str) -> None:
        self.snippet_manager.delete_snippet(snippet_id)
        self.snippets_updated.emit()
