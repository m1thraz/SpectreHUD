"""
Loot Table Model for SpectreHUD.

Standard-compliant QAbstractTableModel providing decoupled, virtualized,
and high-performance data binding for loot items (credentials, hashes, flags, notes, etc.).
"""

from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant


class LootTableModel(QAbstractTableModel):
    """
    Qt Table Model for Loot Entries.
    Columns:
      0: Type / Badge
      1: Category
      2: Title
      3: Content Preview
      4: Target IP
      5: Timestamp
    """

    COLUMNS = [
        "Type",
        "Category",
        "Title",
        "Content",
        "Target IP",
        "Timestamp"
    ]

    def __init__(self, entries: Optional[List[Dict[str, Any]]] = None, parent=None):
        super().__init__(parent)
        self._entries: List[Dict[str, Any]] = list(entries) if entries else []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._entries) or index.row() < 0:
            return QVariant()

        entry = self._entries[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return entry.get("type", "note").capitalize()
            elif col == 1:
                return entry.get("category", "misc").upper()
            elif col == 2:
                return entry.get("title", "")
            elif col == 3:
                content = entry.get("content", "")
                # Truncate content for single-line table display
                first_line = content.split("\n")[0].strip()
                if len(first_line) > 80 or "\n" in content:
                    return first_line[:77] + "..." if len(first_line) > 80 else first_line + "..."
                return first_line
            elif col == 4:
                return entry.get("target_ip", "")
            elif col == 5:
                return entry.get("timestamp", "")

        elif role == Qt.ItemDataRole.ToolTipRole:
            full_content = entry.get("content", "")
            title = entry.get("title", "")
            entry_type = entry.get("type", "")
            return f"[{entry_type.upper()}] {title}\n{full_content}"

        elif role == Qt.ItemDataRole.UserRole:
            # Returns the raw dictionary item
            return entry

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 1, 4, 5):
                return Qt.AlignmentFlag.AlignCenter.value
            return Qt.AlignmentFlag.AlignLeft.value

        return QVariant()

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
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

    def set_entries(self, entries: List[Dict[str, Any]]) -> None:
        """Resets the model with a new list of entries."""
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def get_entries(self) -> List[Dict[str, Any]]:
        """Returns shallow copy of current entries."""
        return list(self._entries)

    def get_entry(self, row: int) -> Optional[Dict[str, Any]]:
        """Returns entry at specific row index."""
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Finds entry by its unique ID."""
        for entry in self._entries:
            if entry.get("id") == entry_id:
                return entry
        return None

    def add_entry(self, entry: Dict[str, Any], index: int = 0) -> None:
        """Inserts a new entry at specified index (default top)."""
        idx = max(0, min(index, len(self._entries)))
        self.beginInsertRows(QModelIndex(), idx, idx)
        self._entries.insert(idx, entry)
        self.endInsertRows()

    def update_entry(self, updated_entry: Dict[str, Any]) -> bool:
        """Updates an existing entry by ID and emits dataChanged."""
        target_id = updated_entry.get("id")
        if not target_id:
            return False
        for row, entry in enumerate(self._entries):
            if entry.get("id") == target_id:
                self._entries[row] = updated_entry
                top_left = self.index(row, 0)
                bottom_right = self.index(row, len(self.COLUMNS) - 1)
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole])
                return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        """Removes an entry by ID and emits row removal signals."""
        for row, entry in enumerate(self._entries):
            if entry.get("id") == entry_id:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._entries.pop(row)
                self.endRemoveRows()
                return True
        return False

    def clear(self) -> None:
        """Wipes all entries."""
        self.beginResetModel()
        self._entries.clear()
        self.endResetModel()
