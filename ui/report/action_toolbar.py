"""Construction of the Report Editor's document action toolbar."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QWidget

from core.i18n import t
from ui.report.toolbar import REPORT_TOOLBAR_ICON_SIZE

IconFactory = Callable[[str, Optional[str]], QIcon]


@dataclass(frozen=True)
class ReportViewOption:
    mode: Any
    translation_key: str
    fallback: str
    icon_name: str


@dataclass(frozen=True)
class ReportActionCallbacks:
    change_view: Callable[[Any], None]
    toggle_navigator: Callable[[], None]
    populate_navigator: Callable[[], None]
    toggle_raw: Callable[[], None]
    append_loot: Callable[[], None]
    regenerate: Callable[[], None]
    export: Callable[[], None]
    toggle_metadata: Callable[[bool], None]
    toggle_theme: Callable[[], None]
    save: Callable[[], Any]


class ReportActionToolbar(QWidget):
    """Own the widgets and signal wiring for document-level report actions."""

    def __init__(
        self,
        *,
        parent: QWidget,
        callbacks: ReportActionCallbacks,
        view_options: tuple[ReportViewOption, ...],
        icon_factory: IconFactory,
        error_color: str,
    ):
        super().__init__(parent)
        self.setObjectName("ReportActionToolbar")
        self._callbacks = callbacks
        self._icon_factory = icon_factory
        self.view_actions: dict[Any, QAction] = {}
        self._build(view_options, error_color)

    def _icon(self, icon_name: str, color: Optional[str] = None) -> QIcon:
        return self._icon_factory(icon_name, color)

    def _build(
        self,
        view_options: tuple[ReportViewOption, ...],
        error_color: str,
    ) -> None:
        toolbar = QHBoxLayout(self)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        self.btn_change_view = QPushButton(t("report.change_view", "Change View"))
        self.btn_change_view.setProperty("class", "SecondaryBtn")
        self.btn_change_view.setToolTip(
            t("report.change_view_tip", "Choose report editor layout")
        )
        self.btn_change_view.setIcon(self._icon("fa5s.columns"))
        self.btn_change_view.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self._build_view_menu(view_options)
        toolbar.addWidget(self.btn_change_view)

        self.btn_navigator = QPushButton(t("report.navigator", "Navigator"))
        self.btn_navigator.setObjectName("btn_report_navigator")
        self.btn_navigator.setProperty("class", "SecondaryBtn OutlineDropdownBtn")
        self.btn_navigator.setCheckable(True)
        navigator_tooltip = t(
            "report.navigator_tip",
            "Show / hide Report Navigator sidebar (Ctrl+Shift+N)",
        )
        self.btn_navigator.setToolTip(navigator_tooltip)
        self.btn_navigator.setAccessibleName(navigator_tooltip)
        self.btn_navigator.setIcon(self._icon("fa5s.sitemap"))
        self.btn_navigator.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_navigator.clicked.connect(self._callbacks.toggle_navigator)
        self.navigator_menu = QMenu(self.btn_navigator)
        self.navigator_menu.aboutToShow.connect(self._callbacks.populate_navigator)
        toolbar.addWidget(self.btn_navigator)

        self.btn_toggle_raw = QPushButton()
        self.btn_toggle_raw.setObjectName("btn_toggle_raw")
        self.btn_toggle_raw.setProperty(
            "class", "SecondaryBtn FormatToolBtn ReportIconBtn"
        )
        self.btn_toggle_raw.setToolTip(
            t(
                "report.toggle_raw_tip",
                "Toggle between structured form and Markdown source",
            )
        )
        self.btn_toggle_raw.setIcon(self._icon("fa5s.code"))
        self.btn_toggle_raw.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_toggle_raw.clicked.connect(self._callbacks.toggle_raw)
        toolbar.addWidget(self.btn_toggle_raw)

        self.btn_report_actions = QPushButton(t("report.actions", "Report Actions"))
        self.btn_report_actions.setObjectName("btn_report_actions")
        self.btn_report_actions.setProperty(
            "class", "SecondaryBtn OutlineDropdownBtn"
        )
        self.btn_report_actions.setToolTip(
            t(
                "report.actions_tip",
                "Synchronize project Loot or rebuild the report",
            )
        )
        self.btn_report_actions.setIcon(self._icon("fa5s.tools"))
        self.btn_report_actions.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.report_actions_menu = QMenu(self.btn_report_actions)

        self.action_sync_loot = QAction(
            self._icon("fa5s.sync-alt"),
            t("report.sync_loot", "Sync Loot & Findings"),
            self.report_actions_menu,
        )
        self.action_sync_loot.triggered.connect(self._callbacks.append_loot)
        self.report_actions_menu.addAction(self.action_sync_loot)
        self.report_actions_menu.addSeparator()

        self.action_regenerate = QAction(
            self._icon("fa5s.sync-alt"),
            t("report.regenerate", "Regenerate from Loot"),
            self.report_actions_menu,
        )
        self.action_regenerate.setToolTip(
            t(
                "report.regenerate_destructive_tip",
                "Rebuilds the report after confirmation",
            )
        )
        self.action_regenerate.triggered.connect(self._callbacks.regenerate)
        self.report_actions_menu.addAction(self.action_regenerate)
        self.btn_report_actions.setMenu(self.report_actions_menu)
        toolbar.addWidget(self.btn_report_actions)

        self.btn_append_loot = QPushButton(
            t("report.sync_loot", "Sync Loot & Findings")
        )
        self.btn_append_loot.setProperty("class", "SecondaryBtn AppendLootBtn")
        self.btn_append_loot.setToolTip(
            t(
                "report.sync_loot_tip",
                "Add new findings or review changed and report-only findings",
            )
        )
        self.btn_append_loot.setIcon(self._icon("fa5s.plus-circle"))
        self.btn_append_loot.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_append_loot.clicked.connect(self._callbacks.append_loot)
        toolbar.addWidget(self.btn_append_loot)

        self.btn_regenerate = QPushButton(
            t("report.regenerate", "Regenerate from Loot")
        )
        self.btn_regenerate.setProperty("class", "SecondaryBtn RegenerateBtn")
        self.btn_regenerate.setToolTip(
            t(
                "report.regenerate_tip",
                "Updates report structure and appends new loot entries",
            )
        )
        self.btn_regenerate.setIcon(self._icon("fa5s.sync-alt", error_color))
        self.btn_regenerate.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_regenerate.clicked.connect(self._callbacks.regenerate)
        toolbar.addWidget(self.btn_regenerate)

        self.btn_export = QPushButton(t("report.export", "Export..."))
        self.btn_export.setProperty("class", "SecondaryBtn")
        self.btn_export.setToolTip(
            t("report.export_tip", "Choose how to export the current report")
        )
        self.btn_export.setIcon(self._icon("fa5s.file-export"))
        self.btn_export.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_export.clicked.connect(self._callbacks.export)
        toolbar.addWidget(self.btn_export)

        self.btn_report_metadata = QPushButton()
        self.btn_report_metadata.setObjectName("btn_report_metadata")
        self.btn_report_metadata.setProperty(
            "class", "SecondaryBtn FormatToolBtn ReportIconBtn"
        )
        self.btn_report_metadata.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_report_metadata.setCheckable(True)
        self.btn_report_metadata.toggled.connect(self._callbacks.toggle_metadata)
        toolbar.addWidget(self.btn_report_metadata)

        self.btn_report_theme = QPushButton()
        self.btn_report_theme.setObjectName("btn_report_theme")
        self.btn_report_theme.setProperty(
            "class", "SecondaryBtn FormatToolBtn ReportIconBtn"
        )
        self.btn_report_theme.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_report_theme.clicked.connect(self._callbacks.toggle_theme)
        toolbar.addWidget(self.btn_report_theme)

        toolbar.addStretch()
        self.lbl_status = QLabel("")
        self.lbl_status.setProperty("class", "ReportStatusLabel")
        self.lbl_status.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        toolbar.addWidget(self.lbl_status)

        self.btn_save = QPushButton()
        self.btn_save.setObjectName("btn_save_report")
        self.btn_save.setProperty(
            "class", "SecondaryBtn FormatToolBtn ReportIconBtn SaveIconBtn"
        )
        save_tooltip = t(
            "report.save_tip", "Save changes to active box report.md (Ctrl+S)"
        )
        self.btn_save.setToolTip(save_tooltip)
        self.btn_save.setAccessibleName(save_tooltip)
        self.btn_save.setIcon(self._icon("fa5s.save"))
        self.btn_save.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_save.clicked.connect(self._callbacks.save)
        toolbar.addWidget(self.btn_save)

    def _build_view_menu(
        self, view_options: tuple[ReportViewOption, ...]
    ) -> None:
        self.view_menu = QMenu(self.btn_change_view)
        for option in view_options:
            action = QAction(t(option.translation_key, option.fallback), self.view_menu)
            action.setIcon(self._icon(option.icon_name))
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, mode=option.mode: self._callbacks.change_view(
                    mode
                )
            )
            self.view_menu.addAction(action)
            self.view_actions[option.mode] = action
        self.btn_change_view.setMenu(self.view_menu)
