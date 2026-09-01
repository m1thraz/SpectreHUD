"""
History Table Model for SpectreHUD.

Standard-compliant QAbstractTableModel providing decoupled data binding
for Clipboard Watcher history entries.
"""

from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant


class HistoryTableModel(QAbstractTableModel):
    """
    Qt Table Model for Clipboard History.
    Columns:
      0: Timestamp
      1: Target IP
      2: Type (Command / Output)
      3: Content Preview
    """

    COLUMNS = ["Timestamp", "Target IP", "Type", "Content"]

    def __init__(self, history: Optional[List[Dict[str, Any]]] = None, parent=None):
        super().__init__(parent)
        self._history: List[Dict[str, Any]] = list(history) if history else []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._history)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._history) or index.row() < 0:
            return QVariant()

        entry = self._history[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return entry.get("timestamp", "")
            elif col == 1:
                return entry.get("target_ip", "")
            elif col == 2:
                return "Output" if entry.get("is_multiline") else "Command"
            elif col == 3:
                text = entry.get("text", "")
                first_line = text.split("\n")[0].strip()
                if len(first_line) > 90 or "\n" in text:
                    return first_line[:87] + "..." if len(first_line) > 90 else first_line + "..."
                return first_line

        elif role == Qt.ItemDataRole.ToolTipRole:
            return entry.get("text", "")

        elif role == Qt.ItemDataRole.UserRole:
            return entry

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 1, 2):
                return Qt.AlignmentFlag.AlignCenter.value
            return Qt.AlignmentFlag.AlignLeft.value

        return QVariant()

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        elif orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return QVariant()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # ------------------------------------------------------------------ #
    # Data Mutation & Access
    # ------------------------------------------------------------------ #

    def set_history(self, history: List[Dict[str, Any]]) -> None:
        """Resets the model with a new list of history entries."""
        self.beginResetModel()
        self._history = list(history)
        self.endResetModel()

    def get_history(self) -> List[Dict[str, Any]]:
        """Returns shallow copy of current history items."""
        return list(self._history)

    def get_entry(self, row: int) -> Optional[Dict[str, Any]]:
        """Returns entry at specific row."""
        if 0 <= row < len(self._history):
            return self._history[row]
        return None

    def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Finds entry by ID."""
        for e in self._history:
            if e.get("id") == entry_id:
                return e
        return None

    def add_entry(self, entry: Dict[str, Any], index: int = 0) -> None:
        """Inserts a new history item."""
        idx = max(0, min(index, len(self._history)))
        self.beginInsertRows(QModelIndex(), idx, idx)
        self._history.insert(idx, entry)
        self.endInsertRows()

    def delete_entry(self, entry_id: str) -> bool:
        """Removes an entry by ID."""
        for row, e in enumerate(self._history):
            if e.get("id") == entry_id:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._history.pop(row)
                self.endRemoveRows()
                return True
        return False

    def clear(self) -> None:
        """Clears all history."""
        self.beginResetModel()
        self._history.clear()
        self.endResetModel()
