"""Theme-aware review dialog for explicit Loot/report reconciliation."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.i18n import t
from core.reporting import (
    LootDifferenceKind,
    LootReconciliationAction,
    LootReconciliationItem,
    LootReconciliationSelection,
)
from ui.base_dialog import BaseHudDialog


class LootReconciliationDialog(BaseHudDialog):
    """Collect per-finding decisions without making any mutation itself."""

    def __init__(
        self,
        items: tuple[LootReconciliationItem, ...],
        *,
        missing_count: int = 0,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(t("report.reconcile.title", "Review Loot Differences"), parent)
        self.setObjectName("LootReconciliationDialog")
        self.setMinimumSize(780, 420)
        self.resize(920, 520)
        self._items = items
        self._combos: dict[str, QComboBox] = {}
        self._build_ui(missing_count)

    @property
    def decisions(self) -> dict[str, LootReconciliationSelection]:
        decisions: dict[str, LootReconciliationSelection] = {}
        for entry_id, combo in self._combos.items():
            action = combo.currentData()
            if isinstance(action, LootReconciliationAction):
                item = next(item for item in self._items if item.entry_id == entry_id)
                decisions[entry_id] = LootReconciliationSelection(
                    action=action,
                    expected_report_hash=item.report_hash,
                    expected_loot_hash=item.loot_hash,
                )
        return decisions

    @property
    def append_missing(self) -> bool:
        return not self.chk_append_missing.isHidden() and self.chk_append_missing.isChecked()

    def _build_ui(self, missing_count: int) -> None:
        description = QLabel(
            t(
                "report.reconcile.description",
                "Loot and the report have diverged. Choose explicitly which version to keep for each finding. Unselected differences remain unchanged.",
            )
        )
        description.setWordWrap(True)
        self.body_layout.addWidget(description)

        safety = QLabel(
            t(
                "report.reconcile.safety",
                "The current report is backed up before selected changes are saved.",
            )
        )
        safety.setProperty("class", "DialogHint")
        safety.setWordWrap(True)
        self.body_layout.addWidget(safety)

        self.table = QTableWidget(len(self._items), 4)
        self.table.setObjectName("LootReconciliationTable")
        self.table.setHorizontalHeaderLabels(
            [
                t("report.reconcile.state", "State"),
                t("report.reconcile.report_version", "Report version"),
                t("report.reconcile.loot_version", "Loot version"),
                t("report.reconcile.action", "Action"),
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        for row, item in enumerate(self._items):
            state_text = (
                t("report.loot_sync_changed", "Changed")
                if item.kind is LootDifferenceKind.CHANGED
                else t("report.loot_sync_report_only", "Report only")
            )
            state = QTableWidgetItem(state_text)
            state.setData(Qt.ItemDataRole.UserRole, item.entry_id)
            self.table.setItem(row, 0, state)
            self.table.setItem(row, 1, QTableWidgetItem(item.report_title))
            loot_title = item.loot_title or t(
                "report.reconcile.no_loot_source", "Removed or no longer a Finding"
            )
            self.table.setItem(row, 2, QTableWidgetItem(loot_title))
            combo = self._build_action_combo(item)
            self.table.setCellWidget(row, 3, combo)
            if item.resolvable:
                self._combos[item.entry_id] = combo
                combo.currentIndexChanged.connect(self._update_apply_enabled)
        self.body_layout.addWidget(self.table, stretch=1)

        self.chk_append_missing = QCheckBox(
            t(
                "report.reconcile.append_missing",
                "Also add {count} new Loot finding(s)",
                count=missing_count,
            )
        )
        self.chk_append_missing.setObjectName("chk_reconcile_append_missing")
        self.chk_append_missing.setChecked(missing_count > 0)
        self.chk_append_missing.setVisible(missing_count > 0)
        self.chk_append_missing.toggled.connect(self._update_apply_enabled)
        self.body_layout.addWidget(self.chk_append_missing)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.btn_apply = QPushButton(t("report.reconcile.apply", "Apply selected changes"))
        self.btn_apply.setObjectName("btn_reconcile_apply")
        self.btn_apply.setProperty("class", "PrimaryBtn")
        self.btn_apply.clicked.connect(self.accept)
        cancel = QPushButton(t("dialog.cancel", "Cancel"))
        cancel.clicked.connect(self.reject)
        button_row.addWidget(cancel)
        button_row.addWidget(self.btn_apply)
        self.body_layout.addLayout(button_row)
        self._update_apply_enabled()

    def _build_action_combo(self, item: LootReconciliationItem) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName(f"reconcile_action_{item.entry_id}")
        if not item.resolvable:
            combo.addItem(t("report.reconcile.raw_required", "Raw Markdown required"), None)
            combo.setEnabled(False)
            combo.setToolTip(
                t(
                    "report.reconcile.raw_required_tip",
                    "This legacy marker has no safe finding boundary and was not changed.",
                )
            )
            return combo

        combo.addItem(
            t("report.reconcile.later", "Decide later"),
            LootReconciliationAction.LATER,
        )
        if item.kind is LootDifferenceKind.CHANGED:
            combo.addItem(
                t("report.reconcile.accept_report", "Keep report version"),
                LootReconciliationAction.ACCEPT_REPORT,
            )
            combo.addItem(
                t("report.reconcile.apply_loot", "Use Loot version"),
                LootReconciliationAction.APPLY_LOOT,
            )
            combo.addItem(
                t("report.reconcile.keep_both", "Keep both versions"),
                LootReconciliationAction.KEEP_BOTH,
            )
        else:
            combo.addItem(
                t("report.reconcile.detach", "Keep as report-only"),
                LootReconciliationAction.DETACH_REPORT,
            )
            combo.addItem(
                t("report.reconcile.delete", "Delete from report"),
                LootReconciliationAction.DELETE_REPORT,
            )
        return combo

    def _update_apply_enabled(self, *_args) -> None:
        selected = any(
            combo.currentData() is not LootReconciliationAction.LATER
            for combo in self._combos.values()
        )
        self.btn_apply.setEnabled(selected or self.append_missing)
