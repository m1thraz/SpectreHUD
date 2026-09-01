"""
Snippet List Model for SpectreHUD.

Standard-compliant QAbstractListModel providing decoupled data binding
and fast virtualization for Cheatsheet snippets and search filtering.
"""

import html
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt, QVariant


class SnippetListModel(QAbstractListModel):
    """
    Qt List Model for Snippet Items.
    Roles:
      - DisplayRole: Snippet title
      - UserRole: Full snippet dictionary
      - ToolTipRole: Formatted description & command template preview
    """

    def __init__(self, snippets: Optional[List[Dict[str, Any]]] = None, parent=None):
        super().__init__(parent)
        self._snippets: List[Dict[str, Any]] = list(snippets) if snippets else []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._snippets)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._snippets) or index.row() < 0:
            return QVariant()

        snippet = self._snippets[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return snippet.get("title", "")

        elif role == Qt.ItemDataRole.UserRole:
            return snippet

        elif role == Qt.ItemDataRole.ToolTipRole:
            title = snippet.get("title", "")
            desc = snippet.get("description", "")
            template = snippet.get("template", "")
            tooltip_parts = [f"<b>{html.escape(title)}</b>"]
            if desc:
                tooltip_parts.append(html.escape(desc))
            if template:
                tooltip_parts.append(f"<code>{html.escape(template)}</code>")
            return "\n\n".join(tooltip_parts)

        return QVariant()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # ------------------------------------------------------------------ #
    # Data Mutation & Access
    # ------------------------------------------------------------------ #

    def set_snippets(self, snippets: List[Dict[str, Any]]) -> None:
        """Resets the model with a new list of snippets."""
        self.beginResetModel()
        self._snippets = list(snippets)
        self.endResetModel()

    def get_snippets(self) -> List[Dict[str, Any]]:
        """Returns shallow copy of current snippets."""
        return list(self._snippets)

    def get_snippet(self, row: int) -> Optional[Dict[str, Any]]:
        """Returns snippet dictionary at specific row."""
        if 0 <= row < len(self._snippets):
            return self._snippets[row]
        return None

    def get_snippet_by_id(self, snippet_id: str) -> Optional[Dict[str, Any]]:
        """Finds snippet by its ID."""
        for s in self._snippets:
            if s.get("id") == snippet_id:
                return s
        return None

    def add_snippet(self, snippet: Dict[str, Any], index: int = 0) -> None:
        """Inserts a new snippet."""
        idx = max(0, min(index, len(self._snippets)))
        self.beginInsertRows(QModelIndex(), idx, idx)
        self._snippets.insert(idx, snippet)
        self.endInsertRows()

    def update_snippet(self, updated_snippet: Dict[str, Any]) -> bool:
        """Updates an existing snippet by ID."""
        target_id = updated_snippet.get("id")
        if not target_id:
            return False
        for row, s in enumerate(self._snippets):
            if s.get("id") == target_id:
                self._snippets[row] = updated_snippet
                idx = self.index(row, 0)
                self.dataChanged.emit(
                    idx, idx, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole]
                )
                return True
        return False

    def delete_snippet(self, snippet_id: str) -> bool:
        """Removes a snippet by ID."""
        for row, s in enumerate(self._snippets):
            if s.get("id") == snippet_id:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._snippets.pop(row)
                self.endRemoveRows()
                return True
        return False

    def clear(self) -> None:
        """Wipes all snippets."""
        self.beginResetModel()
        self._snippets.clear()
        self.endResetModel()
