from typing import Dict, Any, List, Optional, Callable
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel

from core.snippet_manager import SnippetManager
from ui.snippet_card import SnippetCard
from ui.add_snippet_dialog import AddSnippetDialog


class CheatsheetController(QObject):
    """Controller managing cheatsheet snippets, categories, search filtering, and interpolation."""

    category_changed = pyqtSignal(str)
    snippets_updated = pyqtSignal()

    def __init__(self, snippet_manager: SnippetManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.snippet_manager = snippet_manager
        self.current_category_id: str = "all"
        self.filter_buttons: Dict[str, QPushButton] = {}

    def select_category(self, category_id: str) -> None:
        self.current_category_id = category_id
        for cid, btn in self.filter_buttons.items():
            btn.setProperty("class", "FilterPillActive" if cid == category_id else "FilterPill")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.category_changed.emit(category_id)

    def build_filter_pills(
        self, 
        pills_layout: QHBoxLayout, 
        on_select_category: Callable[[str], None]
    ) -> None:
        self.filter_buttons.clear()
        cats = self.snippet_manager.get_categories()
        for c in cats:
            cat_id = c.get("id")
            pill_text = f"{c.get('icon', '')} {c.get('name').split(' ')[-1] if ' ' in c.get('name') else c.get('name')}"
            if cat_id == "all":
                pill_text = "⚡ Alle Befehle"

            btn = QPushButton(pill_text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("class", "FilterPillActive" if cat_id == self.current_category_id else "FilterPill")
            btn.clicked.connect(lambda checked=False, cid=cat_id: on_select_category(cid))
            self.filter_buttons[cat_id] = btn
            pills_layout.addWidget(btn)

        pills_layout.addStretch()

    def render_content(
        self,
        content_layout: QVBoxLayout,
        search_query: str,
        variables: Dict[str, str],
        on_delete_snippet: Callable[[str], None],
        parent_widget: QWidget,
        show_empty_state_fn: Callable[[str], None]
    ) -> List[QWidget]:
        snippets = self.snippet_manager.get_snippets(
            category_id=self.current_category_id,
            search_query=search_query
        )

        if not snippets:
            show_empty_state_fn("Keine Befehle gefunden. Drücke Ctrl+N zum Hinzufügen.")
            return []

        rendered_cards: List[QWidget] = []
        for s in snippets:
            card = SnippetCard(s, variables=variables, parent=parent_widget)
            card.snippet_deleted.connect(on_delete_snippet)
            content_layout.addWidget(card)
            rendered_cards.append(card)

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
