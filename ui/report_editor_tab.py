"""
Report-Editor-Tab: bearbeitet die projekt-lokale report.md direkt im
Fenster, kein externer Editor nötig.

Layout: QSplitter mit Markdown-Quelltext links (QPlainTextEdit) und
gerenderter Live-Vorschau rechts (QTextEdit.setMarkdown - Qt-Bordmittel,
keine zusätzliche Markdown-Dependency nötig). Vorschau wird debounced
(300ms nach letzter Änderung) aktualisiert, damit schnelles Tippen nicht
bei jedem Tastendruck neu rendert.

Bewusste Trennung von core.reporting.file_manager.ReportFileManager: dieses
Widget kennt nur "lade Text rein / hol Text raus", die eigentliche
Backup-vor-Regenerierung-Logik lebt im FileManager, nicht hier - damit
sie ohne Qt testbar bleibt.
"""

from enum import Enum
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QMessageBox,
    QDialog,
)
from PyQt6.QtGui import (
    QKeySequence,
    QShortcut,
)
from core.reporting import (
    ReportAppendix,
    ReportAttackPath,
    ReportExecutiveSummary,
    ReportFileManager,
    ReportFindingItem,
    ReportMetadata,
    ReportMutationService,
    ReportRemediationPlan,
    ReportScopeMethodology,
    ReportSessionService,
    ReportTemplate,
    ReportWorkspaceDocument,
    TemplateRepository,
    assess_report_readiness,
    build_report_navigation,
)
from core.config import ConfigManager
from ui.coordinators.export_coordinator import ExportCoordinator
from core.i18n import t
from core.logger import get_logger
from core.phases import normalize_phase_key
from core.fonts import get_report_font_stack
from core.platform import open_path  # noqa: F401
from core.theme_loader import ThemeLoader
from ui.report.dialogs import (
    LootEntryPickerDialog,
    MarkdownTableDialog,  # noqa: F401
    ReportIconPickerDialog,  # noqa: F401
)
from ui.report.export_actions import ReportExportActions
from ui.report.evidence_actions import ReportEvidenceActions
from ui.report.format_actions import ReportFormatActions
from ui.report.navigation import ReportLocation
from ui.report.action_toolbar import (
    ReportActionCallbacks,
    ReportActionToolbar,
    ReportViewOption,
)
from ui.report.workspace_router import ReportRouteContext
from ui.report.icon_assets import render_report_icon  # noqa: F401
from ui.report.preview_transforms import (
    strip_preview_surrogates,
)
from ui.report.preview_controller import ReportPreviewController
from ui.report.mutation_actions import (
    ReportMutationActions,
    ReportMutationCallbacks,
)
from ui.report.session_controller import ReportSessionController
from ui.report.toolbar import build_format_toolbar
from ui.report.workspace_shell import (
    ReportWorkspaceCallbacks,
    ReportWorkspaceShell,
    build_report_workspace_shell,
    wrap_glass_surface,
)
from ui.styles.icons import icon
from ui.message_boxes import (
    ask_confirmation,  # noqa: F401
    show_error_dialog,  # noqa: F401
    show_information_dialog,  # noqa: F401
    show_warning_dialog,
)

logger = get_logger("report_editor")

PREVIEW_DEBOUNCE_MS = 300
DRAFT_DEBOUNCE_MS = 5_000
AUTOSAVE_INTERVAL_MS = 45_000


class ViewMode(Enum):
    WORKSPACE = "workspace"
    EDITOR = "editor"
    SPLIT = "split"
    PREVIEW = "preview"


class ReportEditorTab(QWidget):
    """Editierbarer Markdown-Report mit Live-Vorschau für das aktive Projekt."""

    # Für main_window: signalisiert, ob ungespeicherte Änderungen vorliegen
    dirty_changed = pyqtSignal(bool)

    def __init__(
        self,
        report_file_manager: ReportFileManager,
        loot_manager,
        clipboard_history,
        parent: Optional[QWidget] = None,
        config_manager: Optional[ConfigManager] = None,
        export_coordinator: Optional[ExportCoordinator] = None,
    ):
        super().__init__(parent)
        self.report_file_manager = report_file_manager
        self.report_session = ReportSessionService(report_file_manager)
        self.report_mutations = ReportMutationService(report_file_manager)
        self.loot_manager = loot_manager
        self.clipboard_history = clipboard_history
        self.config = config_manager
        self.export_coordinator = export_coordinator
        theme_id = (
            self.config.get("theme", ThemeLoader.FALLBACK_THEME_ID)
            if self.config
            else ThemeLoader.FALLBACK_THEME_ID
        )
        self._toolbar_palette = ThemeLoader().load_theme(theme_id)
        self.template_repo = TemplateRepository()
        self.active_template: Optional[ReportTemplate] = None
        self.current_project: Optional[str] = None
        self._dirty = False
        self._view_mode = ViewMode.WORKSPACE
        self._light_report_view = False
        self._preview_markdown_snapshot: Optional[str] = None
        self._preview_landmarks: dict[tuple[str, str], int] = {}
        self._active_preview_target: Optional[tuple[str, str]] = None
        self.session_controller = ReportSessionController(
            service=self.report_session,
            parent=self,
            set_status=lambda message: self.lbl_status.setText(message),
        )
        self.mutation_actions = ReportMutationActions(
            parent=self,
            service=self.report_mutations,
            template_repository=self.template_repo,
            loot_manager=lambda: self.loot_manager,
            clipboard_history=lambda: self.clipboard_history,
            callbacks=ReportMutationCallbacks(
                current_project=lambda: self.current_project,
                current_markdown=self.current_markdown,
                is_dirty=self.is_dirty,
                commit_preview=self._commit_preview_if_active,
                save_pending=self.save,
                active_template=lambda: self.active_template,
                set_active_template=self._set_active_template,
                apply_content=self._apply_persisted_mutation,
                set_loot_sync_state=self._set_loot_sync_state,
                set_status=lambda message: self.lbl_status.setText(message),
            ),
        )

        self.format_actions = ReportFormatActions(
            editor=lambda: self.editor,
            parent_widget=self,
            loot_manager_provider=lambda: self.loot_manager,
            report_file_manager_provider=lambda: self.report_file_manager,
            current_project_provider=lambda: self.current_project,
            format_toolbar_provider=lambda: getattr(self, "format_toolbar_widget", None),
        )
        self.export_actions = ReportExportActions(
            parent_widget=self,
            editor=lambda: self.editor,
            report_file_manager_provider=lambda: self.report_file_manager,
            export_coordinator_provider=lambda: self.export_coordinator,
            current_project_provider=lambda: self.current_project,
            active_template_provider=lambda: self.active_template,
            report_font_key_provider=lambda: self._report_font_key(),
        )
        self.evidence_actions = ReportEvidenceActions(
            parent_widget=self,
            loot_manager_provider=lambda: self.loot_manager,
            clipboard_history_provider=lambda: self.clipboard_history,
            report_file_manager_provider=lambda: self.report_file_manager,
            current_project_provider=lambda: self.current_project,
            attach_evidence=lambda item: self.finding_inspector.attach_evidence_item(
                item, insert_into_description=True
            ),
        )

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._update_preview)

        self._draft_timer = QTimer(self)
        self._draft_timer.setSingleShot(True)
        self._draft_timer.setInterval(DRAFT_DEBOUNCE_MS)
        self._draft_timer.timeout.connect(self._save_draft_snapshot)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

        self._workspace_doc: Optional[ReportWorkspaceDocument] = None
        self._syncing_from_inspector = False
        self._workspace_parse_timer = QTimer(self)
        self._workspace_parse_timer.setSingleShot(True)
        self._workspace_parse_timer.setInterval(500)
        self._workspace_parse_timer.timeout.connect(self._sync_markdown_to_workspace)

        self._build_ui()
        self._ensure_active_template()

    # ------------------------------------------------------------------ #
    # UI-Aufbau
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        layout = self._main_layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Ebene 1: Dokumentaktionen (links) und Projekt-Status (rechts)
        self.action_toolbar_widget = ReportActionToolbar(
            parent=self,
            callbacks=ReportActionCallbacks(
                change_view=lambda mode: self._set_view_mode(mode),
                toggle_navigator=lambda: self._toggle_navigator(),
                populate_navigator=lambda: self._populate_navigator_menu(),
                toggle_raw=lambda: self._toggle_inspector_raw(),
                append_loot=lambda: self._on_append_loot_clicked(),
                regenerate=lambda: self._on_regenerate_clicked(),
                export=lambda: self.export_actions.on_export_clicked(),
                toggle_metadata=lambda visible: self._toggle_report_metadata(visible),
                toggle_theme=lambda: self._toggle_report_color_mode(),
                save=lambda: self.save(),
            ),
            view_options=(
                ReportViewOption(
                    ViewMode.WORKSPACE,
                    "report.mode_workspace",
                    "Workspace",
                    "fa5s.project-diagram",
                ),
                ReportViewOption(
                    ViewMode.EDITOR,
                    "report.mode_editor",
                    "Editor",
                    "fa5s.edit",
                ),
                ReportViewOption(
                    ViewMode.SPLIT,
                    "report.mode_split",
                    "Split",
                    "fa5s.columns",
                ),
                ReportViewOption(
                    ViewMode.PREVIEW,
                    "report.mode_preview",
                    "Live Preview",
                    "fa5s.eye",
                ),
            ),
            icon_factory=lambda name, color=None: self._toolbar_icon(name, color),
            error_color=self._toolbar_palette["STATUS_ERROR"],
        )
        self._expose_action_toolbar_handles(self.action_toolbar_widget)
        layout.addWidget(self.action_toolbar_widget)

        # Ebene 2: Formatierungsleiste (Struktur, Inline-Stil, Einfügen)
        self.format_toolbar_widget = build_format_toolbar(
            self,
            {
                "heading_1": lambda: self.format_actions.format_heading(1),
                "heading_2": lambda: self.format_actions.format_heading(2),
                "heading_3": lambda: self.format_actions.format_heading(3),
                "heading_4": lambda: self.format_actions.format_heading(4),
                "heading_5": lambda: self.format_actions.format_heading(5),
                "heading_6": lambda: self.format_actions.format_heading(6),
                "bold": lambda: self.format_actions.format_wrap("**", "**"),
                "italic": lambda: self.format_actions.format_wrap("*", "*"),
                "strikethrough": lambda: self.format_actions.format_wrap("~~", "~~"),
                "code": lambda: self.format_actions.format_wrap("`", "`"),
                "code_block": self.format_actions.format_code_block,
                "align_left": lambda: self.format_actions.format_align("left"),
                "align_center": lambda: self.format_actions.format_align("center"),
                "align_right": lambda: self.format_actions.format_align("right"),
                "list": lambda: self.format_actions.format_list(False),
                "numbered_list": lambda: self.format_actions.format_list(True),
                "quote": self.format_actions.format_quote,
                "horizontal_rule": self.format_actions.format_horizontal_rule,
                "image": self.format_actions.format_image,
                "icon": self.format_actions.format_icon,
                "link": self.format_actions.format_link,
                "table": self.format_actions.format_table,
                "page_break": self.format_actions.format_page_break,
                "spacer_small": lambda: self.format_actions.format_spacer("small"),
                "spacer_medium": lambda: self.format_actions.format_spacer("medium"),
                "spacer_large": lambda: self.format_actions.format_spacer("large"),
            },
            on_toggle_collapse=self._on_toolbar_collapse_toggled,
            icon_color=self._toolbar_palette["CYBER_BLUE_LIGHT"],
            icon_active_color=self._toolbar_palette["TEXT_PRIMARY"],
        )
        layout.addWidget(self.format_toolbar_widget)

        self._build_editor_splitter(layout)
        self._setup_shortcuts()
        self._apply_view_mode(self._view_mode)

    def _on_toolbar_collapse_toggled(self, collapsed: bool) -> None:
        """Collapse or expand Ebene 1 alongside Ebene 2."""
        self.action_toolbar_widget.setVisible(not collapsed)
        self._main_layout.setSpacing(0 if collapsed else 6)
        if not collapsed and self._view_mode == ViewMode.PREVIEW:
            self.format_toolbar_widget.tools_container.setVisible(False)

    def _expose_action_toolbar_handles(
        self, toolbar: ReportActionToolbar
    ) -> None:
        """Keep stable tab attributes while the toolbar owns construction."""
        self.btn_change_view = toolbar.btn_change_view
        self.btn_navigator = toolbar.btn_navigator
        self.navigator_menu = toolbar.navigator_menu
        self.btn_toggle_raw = toolbar.btn_toggle_raw
        self.btn_report_actions = toolbar.btn_report_actions
        self.report_actions_menu = toolbar.report_actions_menu
        self.action_sync_loot = toolbar.action_sync_loot
        self.action_regenerate = toolbar.action_regenerate
        self.btn_append_loot = toolbar.btn_append_loot
        self.btn_regenerate = toolbar.btn_regenerate
        self.btn_export = toolbar.btn_export
        self.btn_report_metadata = toolbar.btn_report_metadata
        self.btn_report_theme = toolbar.btn_report_theme
        self.lbl_status = toolbar.lbl_status
        self.btn_save = toolbar.btn_save
        self.view_menu = toolbar.view_menu
        self._view_actions = toolbar.view_actions
        self._update_report_metadata_button()
        self._update_report_theme_button()

    def _toolbar_icon(self, icon_name: str, color: Optional[str] = None):
        """Create a toolbar icon using the active app theme through the central wrapper."""
        return icon(
            icon_name,
            color=color or self._toolbar_palette["CYBER_BLUE_LIGHT"],
            color_active=self._toolbar_palette["TEXT_PRIMARY"],
        )

    def _build_editor_splitter(self, layout: QVBoxLayout) -> None:
        """Build and expose the Report Workspace shell."""
        shell = build_report_workspace_shell(
            parent=self,
            callbacks=ReportWorkspaceCallbacks(
                navigate=lambda location: self.navigate_to(location),
                add_finding=lambda: self._on_add_finding_requested(),
                sync_loot=lambda: self._on_append_loot_clicked(),
                text_changed=lambda: self._on_text_changed(),
                metadata_changed=lambda value: self._on_metadata_changed(value),
                finding_changed=lambda value: self._on_finding_changed(value),
                finding_deleted=lambda value: self._on_finding_deleted(value),
                finding_duplicated=lambda value: self._on_finding_duplicated(value),
                section_changed=lambda identity, content: self._on_section_changed(
                    identity, content
                ),
                summary_changed=lambda value: self._on_summary_changed(value),
                finding_action_changed=(
                    lambda finding_id, recommendation, status:
                    self._on_finding_action_changed(
                        finding_id, recommendation, status
                    )
                ),
                remediation_plan_changed=(
                    lambda value: self._on_remediation_plan_changed(value)
                ),
                attack_path_changed=lambda value: self._on_attack_path_changed(value),
                scope_changed=lambda value: self._on_scope_changed(value),
                appendix_changed=lambda value: self._on_appendix_changed(value),
                editor_scroll=lambda value: self._on_editor_scroll(value),
                preview_scroll=lambda value: self._on_preview_scroll(value),
            ),
            evidence_actions=self.evidence_actions,
        )
        self._expose_workspace_shell(shell)
        self.preview_controller = ReportPreviewController(
            editor=self.editor,
            preview=self.preview,
            document=self.preview_document,
            light_mode_provider=lambda: self._light_report_view,
            split_mode_provider=lambda: self._view_mode == ViewMode.SPLIT,
        )
        self._preview_landmarks = self.preview_controller.landmarks
        self._active_preview_target = self.preview_controller.active_target
        layout.addWidget(self.find_replace)
        self._apply_preview_font()
        self._apply_report_color_mode()
        layout.addWidget(self.splitter, stretch=1)

    def _expose_workspace_shell(self, shell: ReportWorkspaceShell) -> None:
        """Keep stable tab handles while the shell owns widget construction."""
        self.splitter = shell.splitter
        self.navigator = shell.navigator
        self.navigator_glass = shell.navigator_glass
        self.center_stack = shell.center_stack
        self.editor = shell.editor
        self._highlighter = shell.highlighter
        self.find_replace = shell.find_replace
        self.editor_glass = shell.editor_glass
        self.metadata_inspector = shell.metadata_inspector
        self.metadata_inspector_glass = shell.metadata_inspector_glass
        self.readiness_inspector = shell.readiness_inspector
        self.readiness_inspector_glass = shell.readiness_inspector_glass
        self.finding_inspector = shell.finding_inspector
        self.finding_inspector_glass = shell.finding_inspector_glass
        self.section_inspector = shell.section_inspector
        self.section_inspector_glass = shell.section_inspector_glass
        self.summary_inspector = shell.summary_inspector
        self.summary_inspector_glass = shell.summary_inspector_glass
        self.remediation_inspector = shell.remediation_inspector
        self.remediation_inspector_glass = shell.remediation_inspector_glass
        self.attack_path_inspector = shell.attack_path_inspector
        self.attack_path_inspector_glass = shell.attack_path_inspector_glass
        self.scope_inspector = shell.scope_inspector
        self.scope_inspector_glass = shell.scope_inspector_glass
        self.appendix_inspector = shell.appendix_inspector
        self.appendix_inspector_glass = shell.appendix_inspector_glass
        self.preview_document = shell.preview_document
        self.preview = shell.preview
        self.preview_glass = shell.preview_glass
        self.workspace_router = shell.router

    @staticmethod
    def _wrap_glass_surface(widget):
        """Compatibility entry point for callers outside the workspace shell."""
        return wrap_glass_surface(widget)

    def _setup_shortcuts(self) -> None:
        """Register report editing and view-mode shortcuts."""
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        sc_save.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_save_shift = QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.save)
        sc_save_shift.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_cycle = QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self._cycle_view_mode)
        sc_cycle.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode1 = QShortcut(
            QKeySequence("Ctrl+1"), self, activated=lambda: self._set_view_mode(ViewMode.EDITOR)
        )
        sc_mode1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode2 = QShortcut(
            QKeySequence("Ctrl+2"), self, activated=lambda: self._set_view_mode(ViewMode.SPLIT)
        )
        sc_mode2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode3 = QShortcut(
            QKeySequence("Ctrl+3"), self, activated=lambda: self._set_view_mode(ViewMode.PREVIEW)
        )
        sc_mode3.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode4 = QShortcut(
            QKeySequence("Ctrl+4"), self, activated=lambda: self._set_view_mode(ViewMode.WORKSPACE)
        )
        sc_mode4.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_nav = QShortcut(
            QKeySequence("Ctrl+Shift+N"), self, activated=self._toggle_navigator
        )
        sc_nav.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self._shortcut_find = QShortcut(
            QKeySequence("Ctrl+F"), self.editor, activated=self.find_replace.open
        )
        self._shortcut_find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_find_close = QShortcut(
            QKeySequence("Esc"), self.find_replace, activated=self.find_replace.close_bar
        )
        self._shortcut_find_close.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        for sequence, callback in (
            ("Ctrl+B", lambda: self.format_actions.format_wrap("**", "**")),
            ("Ctrl+I", lambda: self.format_actions.format_wrap("*", "*")),
            ("Ctrl+K", lambda: self.format_actions.format_wrap("`", "`")),
            ("Ctrl+Shift+X", lambda: self.format_actions.format_wrap("~~", "~~")),
            ("Ctrl+Shift+L", lambda: self.format_actions.format_align("left")),
            ("Ctrl+Shift+E", lambda: self.format_actions.format_align("center")),
            ("Ctrl+Shift+R", lambda: self.format_actions.format_align("right")),
            ("Ctrl+Shift+Q", self.format_actions.format_quote),
            ("Ctrl+Shift+I", self.format_actions.format_image),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self.editor, activated=callback)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)


    def _report_font_key(self) -> str:
        return self.config.get("report_font", "segoe_ui") if self.config else "segoe_ui"

    def _apply_preview_font(self) -> None:
        """Apply configured typography and color mode to the preview document."""
        report_font = get_report_font_stack(self._report_font_key())
        self.preview_controller.configure_typography(report_font)
    def _toggle_report_color_mode(self) -> None:
        self._light_report_view = not self._light_report_view
        self._apply_report_color_mode()

    def _toggle_report_metadata(self, visible: bool) -> None:
        self.editor.set_metadata_visible(visible)
        self._update_report_metadata_button()

    def _update_report_metadata_button(self) -> None:
        if not hasattr(self, "btn_report_metadata"):
            return
        visible = self.editor.metadata_visible() if hasattr(self, "editor") else False
        tooltip = (
            t("report.hide_metadata", "Hide Spectre metadata")
            if visible
            else t("report.show_metadata", "Show Spectre metadata")
        )
        self.btn_report_metadata.setToolTip(tooltip)
        self.btn_report_metadata.setAccessibleName(tooltip)
        self.btn_report_metadata.setIcon(
            self._toolbar_icon("fa5s.eye" if visible else "fa5s.eye-slash")
        )

    def _apply_report_color_mode(self) -> None:
        widgets = [self.editor, self.preview, self.editor_glass, self.preview_glass]
        if hasattr(self, "navigator_glass"):
            widgets.extend([self.navigator_glass, self.center_stack])
        for widget in widgets:
            widget.setProperty("reportLight", self._light_report_view)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self._highlighter.set_light_mode(self._light_report_view)
        self._apply_preview_font()
        self._update_report_theme_button()
        self._update_preview()

    def _update_report_theme_button(self) -> None:
        if not hasattr(self, "btn_report_theme"):
            return
        tooltip = (
            t("report.view_dark", "Switch report panes to dark mode")
            if self._light_report_view
            else t("report.view_light", "Switch report panes to light mode")
        )
        self.btn_report_theme.setToolTip(tooltip)
        self.btn_report_theme.setAccessibleName(tooltip)
        self.btn_report_theme.setIcon(
            self._toolbar_icon("fa5s.moon" if self._light_report_view else "fa5s.sun")
        )

    def refresh_font_configuration(self) -> None:
        """Refresh preview typography after settings are saved."""
        self._apply_preview_font()
        self._update_preview()

    # ------------------------------------------------------------------ #
    # Projekt-Wechsel / Laden
    # ------------------------------------------------------------------ #

    def load_project(self, project_name: str) -> None:
        """
        Lädt den Report des angegebenen Projekts in den Editor.
        Muss von main_window bei jedem Projektwechsel aufgerufen werden -
        prüft NICHT selbst auf ungespeicherte Änderungen im vorherigen
        Projekt, das ist Aufgabe des Aufrufers (siehe confirm_discard_if_dirty).
        """
        self.current_project = project_name
        loaded = self.session_controller.load_project(project_name)
        self.preview_document.set_project_dir(loaded.project_dir)
        content = loaded.markdown

        # setPlainText löst textChanged aus -> _dirty würde faelschlich True
        # werden, deshalb Signal kurz blocken.
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)
        self._set_dirty(loaded.restored_draft)
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(content)
        if hasattr(self, "navigator"):
            self._refresh_workspace_navigator(preserve_selection=False)
        if self._view_mode == ViewMode.WORKSPACE:
            self._on_navigate_requested("metadata", None)
        self._update_preview()
        self._update_status_label()

    # ------------------------------------------------------------------ #
    # Dirty-State
    # ------------------------------------------------------------------ #

    def is_dirty(self) -> bool:
        return self._dirty

    def current_markdown(self) -> str:
        """Return the canonical Markdown owned by the editor."""
        return self.editor.toPlainText()

    def replace_markdown(self, markdown: str) -> None:
        """Replace the canonical Markdown through the tab's public boundary."""
        self.editor.setPlainText(markdown)

    def set_export_coordinator(self, coordinator: ExportCoordinator) -> None:
        """Update the shared export dependency without exposing tab internals."""
        self.export_coordinator = coordinator

    def confirm_discard_if_dirty(self) -> bool:
        """
        Fragt bei ungespeicherten Änderungen nach, ob gespeichert, verworfen
        oder abgebrochen werden soll. Gibt True zurück, wenn der Aufrufer
        fortfahren darf (gespeichert oder bewusst verworfen), False bei
        Abbruch (z.B. Projekt-/Moduswechsel soll NICHT stattfinden).
        """
        if not self._dirty:
            return True

        msg = QMessageBox(self.window() if self else None)
        msg.setWindowTitle(t("report.unsaved_prompt_title", "Unsaved Changes"))
        msg.setText(
            t("report.unsaved_prompt_message", "The report has unsaved changes.\n\nSave them now?")
        )
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Save)

        reply = msg.exec()
        if reply == QMessageBox.StandardButton.Save:
            return self.save()
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        return False  # Cancel

    def _set_dirty(self, value: bool) -> None:
        if value != self._dirty:
            self._dirty = value
            self.dirty_changed.emit(value)
        self._update_status_label()

    def _on_text_changed(self) -> None:
        if getattr(self, "_syncing_from_inspector", False):
            return
        if (
            hasattr(self, "preview_controller")
            and self.preview_controller.syncing_scroll
        ):
            return
        self._set_dirty(True)
        self._preview_timer.start()  # debounced preview
        self._draft_timer.start()  # debounced crash recovery snapshot
        if hasattr(self, "_workspace_parse_timer"):
            self._workspace_parse_timer.start()

    def _enter_preview_mode(self) -> None:
        """Enters editable live preview mode and takes a markdown baseline snapshot."""
        if self._preview_timer.isActive():
            self._preview_timer.stop()
        self._update_preview()
        self._preview_markdown_snapshot = self.editor.toPlainText()
        self.preview.setReadOnly(False)
        self.preview.setFocus()

    def _commit_preview_to_markdown(self) -> None:
        """Commits rich-text edits from the preview document back to the markdown editor."""
        from core.reporting import preserve_markers_in_preview_roundtrip

        raw_markdown = strip_preview_surrogates(self.preview_document.toMarkdown())
        new_markdown = preserve_markers_in_preview_roundtrip(
            self._preview_markdown_snapshot or "", raw_markdown
        )
        old_len = len(self._preview_markdown_snapshot or "")
        new_len = len(new_markdown)

        # Sanity check against severe conversion loss
        if old_len > 200 and new_len < old_len * 0.6:
            reply = show_warning_dialog(
                self.window() if self else None,
                t("report.warn_large_diff_title", "Ungewöhnlich große Änderung"),
                t(
                    "report.warn_large_diff_msg",
                    "Die Bearbeitung in der Live-Ansicht hat den Inhalt stark verkürzt "
                    "(möglicher Konvertierungsverlust).\n\nTrotzdem übernehmen?",
                ),
                buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                default_button=QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                # Discard: reset preview to previous markdown
                self._update_preview()
                self._preview_markdown_snapshot = None
                return

        if new_markdown != self._preview_markdown_snapshot:
            self.editor.blockSignals(True)
            self.editor.setPlainText(new_markdown)
            self.editor.blockSignals(False)
            self._set_dirty(True)

        self._preview_markdown_snapshot = None

    def _set_view_mode(self, mode: ViewMode) -> None:
        """Switches the view mode and handles preview commit / readonly transitions."""
        if mode == self._view_mode:
            return

        # Leaving PREVIEW mode -> commit edits and make preview read-only
        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()
            self.preview.setReadOnly(True)

        # Entering PREVIEW mode -> make editable and take snapshot
        if mode == ViewMode.PREVIEW:
            self._enter_preview_mode()

        self._view_mode = mode
        self._apply_view_mode(mode)
        self._update_status_label()

    def _toggle_navigator(self) -> None:
        """Toggles visibility of the Navigator sidebar without disrupting 2-column Split view."""
        if not hasattr(self, "navigator_glass"):
            return
        is_vis = not self.navigator_glass.isVisible()
        self.navigator_glass.setVisible(is_vis)
        if hasattr(self, "btn_navigator"):
            self.btn_navigator.setChecked(is_vis)
        total_w = self.splitter.width() or 1000
        cur_sizes = self.splitter.sizes()
        ratio = (
            (cur_sizes[1] / max(1, cur_sizes[1] + cur_sizes[2]))
            if (len(cur_sizes) >= 3 and (cur_sizes[1] + cur_sizes[2]) > 0)
            else 0.5
        )
        ratio = max(0.25, min(0.75, ratio))
        nav_w = min(max(180, cur_sizes[0] if cur_sizes[0] > 0 else 260), 400)

        if is_vis:
            if self._view_mode == ViewMode.EDITOR:
                self.splitter.setSizes([nav_w, max(200, total_w - nav_w), 0])
            else:
                rem = max(350, total_w - nav_w)
                c_w = max(200, int(rem * ratio))
                p_w = max(150, rem - c_w)
                self.splitter.setSizes([nav_w, c_w, p_w])
        else:
            if self._view_mode == ViewMode.EDITOR:
                self.splitter.setSizes([0, total_w, 0])
            else:
                c_w = max(200, int(total_w * ratio))
                p_w = max(150, total_w - c_w)
                self.splitter.setSizes([0, c_w, p_w])

    def _toggle_inspector_raw(self) -> None:
        """Toggles center editing widget between the active Form Inspector and Raw Markdown Editor."""
        if self.center_stack.currentWidget() == self.editor_glass:
            target = getattr(self, "_last_active_inspector", self.finding_inspector_glass)
            self.center_stack.setCurrentWidget(target)
            self.btn_toggle_raw.setIcon(self._toolbar_icon("fa5s.code"))
            self.btn_toggle_raw.setToolTip(t("report.toggle_raw_code", "Switch to Markdown source"))
        else:
            self._last_active_inspector = self.center_stack.currentWidget()
            self.center_stack.setCurrentWidget(self.editor_glass)
            self.btn_toggle_raw.setIcon(self._toolbar_icon("fa5s.sliders-h"))
            self.btn_toggle_raw.setToolTip(t("report.toggle_raw_form", "Switch to structured form"))
        self._update_contextual_toolbar_visibility()

    def _update_contextual_toolbar_visibility(self) -> None:
        """Show Markdown tools only while the Markdown surface is actually active."""
        if not hasattr(self, "format_toolbar_widget"):
            return
        raw_active = (
            hasattr(self, "center_stack")
            and hasattr(self, "editor_glass")
            and self.center_stack.currentWidget() == self.editor_glass
        )
        show_formatting = self._view_mode in (ViewMode.EDITOR, ViewMode.SPLIT) or (
            self._view_mode == ViewMode.WORKSPACE and raw_active
        )
        self.format_toolbar_widget.setVisible(show_formatting)
        if show_formatting:
            self.format_toolbar_widget.tools_container.setVisible(
                not self.format_toolbar_widget.is_collapsed()
            )
        self.action_toolbar_widget.setVisible(True)
        workspace_active = self._view_mode == ViewMode.WORKSPACE
        self.btn_toggle_raw.setVisible(not workspace_active)
        self.btn_report_actions.setVisible(workspace_active)
        self.btn_append_loot.setVisible(not workspace_active)
        self.btn_regenerate.setVisible(not workspace_active)

    def _update_view_button(self) -> None:
        labels = {
            ViewMode.WORKSPACE: t("report.mode_workspace", "Workspace"),
            ViewMode.EDITOR: t("report.mode_editor", "Editor"),
            ViewMode.SPLIT: t("report.mode_split", "Split"),
            ViewMode.PREVIEW: t("report.mode_preview", "Live Preview"),
        }
        icons = {
            ViewMode.WORKSPACE: "fa5s.project-diagram",
            ViewMode.EDITOR: "fa5s.edit",
            ViewMode.SPLIT: "fa5s.columns",
            ViewMode.PREVIEW: "fa5s.eye",
        }
        self.btn_change_view.setText(labels.get(self._view_mode, t("report.change_view", "Change View")))
        self.btn_change_view.setIcon(self._toolbar_icon(icons.get(self._view_mode, "fa5s.columns")))

    def _apply_view_mode(self, mode: ViewMode) -> None:
        """Applies visibility and splitter layout for the selected view mode."""
        for action_mode, action in self._view_actions.items():
            action.setChecked(action_mode == mode)
        nav_visible = self.navigator_glass.isVisible() if hasattr(self, "navigator_glass") else False
        if mode in (ViewMode.EDITOR, ViewMode.SPLIT):
            # The legacy views are deliberately clean Markdown surfaces; the
            # navigator remains available through its explicit toolbar toggle.
            nav_visible = False
            self.navigator_glass.setVisible(False)
            self.center_stack.setCurrentWidget(self.editor_glass)
        if hasattr(self, "btn_navigator"):
            self.btn_navigator.setChecked(nav_visible)

        total_w = self.splitter.width() or 1000
        cur_sizes = self.splitter.sizes()
        ratio = (
            (cur_sizes[1] / max(1, cur_sizes[1] + cur_sizes[2]))
            if (len(cur_sizes) >= 3 and (cur_sizes[1] + cur_sizes[2]) > 0)
            else 0.5
        )
        ratio = max(0.25, min(0.75, ratio))
        nav_w = min(max(180, cur_sizes[0] if cur_sizes[0] > 0 else 260), 400) if nav_visible else 0

        if mode == ViewMode.WORKSPACE:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(True)
            if hasattr(self, "btn_navigator"):
                self.btn_navigator.setChecked(True)
            self.center_stack.setVisible(True)
            self.preview_glass.setVisible(True)
            if self.center_stack.currentWidget() == self.editor_glass:
                target = getattr(self, "_last_active_inspector", self.finding_inspector_glass)
                self.center_stack.setCurrentWidget(target)
                if hasattr(self, "btn_toggle_raw"):
                    self.btn_toggle_raw.setIcon(self._toolbar_icon("fa5s.code"))
            actual_nav_w = nav_w if nav_w > 0 else 260
            rem = max(350, total_w - actual_nav_w)
            c_w = max(200, int(rem * ratio))
            p_w = max(150, rem - c_w)
            self.splitter.setSizes([actual_nav_w, c_w, p_w])
            self._sync_scroll_editor_to_preview()
        elif mode == ViewMode.SPLIT:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(nav_visible)
            self.center_stack.setVisible(True)
            self.preview_glass.setVisible(True)
            rem = max(350, total_w - nav_w)
            c_w = max(200, int(rem * ratio))
            p_w = max(150, rem - c_w)
            self.splitter.setSizes([nav_w, c_w, p_w])
            self._sync_scroll_editor_to_preview()
        elif mode == ViewMode.EDITOR:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(nav_visible)
            self.center_stack.setVisible(True)
            self.preview_glass.setVisible(False)
            self.splitter.setSizes([nav_w, max(200, total_w - nav_w), 0])
        elif mode == ViewMode.PREVIEW:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(False)
            self.center_stack.setVisible(False)
            self.preview_glass.setVisible(True)
            self.splitter.setSizes([0, 0, total_w])
        self._update_contextual_toolbar_visibility()
        self._update_view_button()

    def _cycle_view_mode(self) -> None:
        """Cycles through all report views, starting with the primary workspace."""
        modes = [ViewMode.WORKSPACE, ViewMode.EDITOR, ViewMode.SPLIT, ViewMode.PREVIEW]
        idx = modes.index(self._view_mode) if self._view_mode in modes else 0
        self._set_view_mode(modes[(idx + 1) % len(modes)])

    def save(self) -> bool:
        if not self.current_project:
            return False

        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()

        saved = self.session_controller.save(
            self.current_project, self.editor.toPlainText()
        )
        if saved:
            self._set_dirty(False)
            if self._draft_timer.isActive():
                self._draft_timer.stop()
        return saved

    def _autosave(self) -> None:
        """Persist a dirty report without interrupting the user on failures."""
        if not self.is_dirty() or not self.current_project:
            return
        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()
        if self.session_controller.autosave(
            self.current_project, self.editor.toPlainText()
        ):
            self._set_dirty(False)

    def closeEvent(self, event) -> None:
        self._autosave_timer.stop()
        super().closeEvent(event)

    def _on_regenerate_clicked(self) -> None:
        self.mutation_actions.regenerate()

    def _on_append_loot_clicked(self) -> None:
        self.mutation_actions.append_missing_loot()

    def _commit_preview_if_active(self) -> None:
        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()

    def _set_active_template(self, template: ReportTemplate) -> None:
        self.active_template = template

    def _apply_persisted_mutation(
        self, markdown: str, preserve_cursor: bool
    ) -> None:
        cursor_position = self.editor.textCursor().position() if preserve_cursor else 0
        self.editor.blockSignals(True)
        self.editor.setPlainText(markdown)
        self.editor.blockSignals(False)
        self._set_dirty(False)
        self._update_preview()
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(markdown)
        if hasattr(self, "navigator"):
            self._refresh_workspace_navigator()
        if preserve_cursor:
            cursor = self.editor.textCursor()
            cursor.setPosition(min(cursor_position, len(markdown)))
            self.editor.setTextCursor(cursor)

    def _ensure_active_template(self) -> None:
        """Keeps the most recently selected template available for the next dialog."""
        templates = self.template_repo.get_all_templates()
        if self.active_template is None and templates:
            self.active_template = templates[0]




    # ------------------------------------------------------------------ #
    # Vorschau & Status
    # ------------------------------------------------------------------ #

    def _update_preview(self) -> None:
        project_dir = None
        if self.current_project:
            project_dir = self.report_file_manager.project_manager.get_project_dir(
                self.current_project
            )
        self.preview_controller.render(self.editor.toPlainText(), project_dir)
        self._active_preview_target = self.preview_controller.active_target
    def _update_status_label(self) -> None:
        if not self.current_project:
            self.lbl_status.setText("")
            return
        status_text = (
            f"● {t('report.unsaved', 'Unsaved changes')}"
            if self._dirty
            else f"✓ {t('report.saved', 'Saved')}"
        )
        mode_label = {
            ViewMode.WORKSPACE: t("report.view_workspace_short", "Workspace"),
            ViewMode.EDITOR: t("report.view_editor_short", "Editor"),
            ViewMode.SPLIT: t("report.view_split_short", "Split"),
            ViewMode.PREVIEW: t("report.view_preview_short", "Live Preview"),
        }.get(self._view_mode, "Split")
        self.lbl_status.setText(f"{self.current_project} — {status_text} · [{mode_label}]")

    # ------------------------------------------------------------------ #
    # Scroll-Sync (Split-View)
    # ------------------------------------------------------------------ #

    def _on_editor_scroll(self, value: int) -> None:
        self.preview_controller.on_editor_scroll(value)

    def _on_preview_scroll(self, value: int) -> None:
        self.preview_controller.on_preview_scroll(value)

    def _sync_scroll_editor_to_preview(self) -> None:
        self.preview_controller.sync_editor_to_preview()
    def _jump_to_heading_line(self, line_number: int) -> None:
        """Positions cursor at the given 1-based line number and ensures it is visible."""
        block = self.editor.document().findBlockByNumber(line_number - 1)
        if block.isValid():
            cursor = self.editor.textCursor()
            cursor.setPosition(block.position())
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
            self.editor.setFocus()
            self._sync_scroll_editor_to_preview()

    def _populate_navigator_menu(self) -> None:
        self.navigator_menu.clear()
        navigation = build_report_navigation(self.editor.toPlainText())
        groups = (
            (t("report.navigator_sections", "Sections"), navigation.sections),
            (t("report.navigator_findings", "Findings"), navigation.findings),
        )
        has_entries = False
        for label, entries in groups:
            if not entries:
                continue
            has_entries = True
            submenu = self.navigator_menu.addMenu(label)
            for entry in entries:
                action = submenu.addAction(entry.title)
                action.triggered.connect(
                    lambda _checked=False, kind=entry.kind, identity=entry.identity: (
                        self._navigate_to_report_item(kind, identity)
                    )
                )
        if not has_entries:
            action = self.navigator_menu.addAction(
                t(
                    "report.navigator_empty",
                    "No navigable report sections yet. Generate or structure the report to populate this menu.",
                )
            )
            action.setEnabled(False)

    def _navigate_to_report_item(self, kind: str, identity: str) -> None:
        if self._view_mode == ViewMode.PREVIEW:
            self._set_view_mode(ViewMode.EDITOR)
        navigation = build_report_navigation(self.editor.toPlainText())
        entries = navigation.sections if kind == "section" else navigation.findings
        target = next((entry for entry in entries if entry.identity == identity), None)
        if target is not None:
            self._jump_to_heading_line(target.line_number)

    # ------------------------------------------------------------------ #
    # Crash Recovery & Draft Snapshots
    # ------------------------------------------------------------------ #

    def _save_draft_snapshot(self) -> None:
        """Saves an in-flight draft snapshot for crash recovery if content is dirty."""
        if not self._dirty or not self.current_project:
            return
        self.session_controller.save_draft(
            self.current_project, self.editor.toPlainText()
        )

    # ------------------------------------------------------------------ #
    # Workspace Navigation & Modulare Inspektoren
    # ------------------------------------------------------------------ #

    def _get_target_ip(self) -> str:
        if not self.current_project:
            return ""
        try:
            pm = getattr(self.report_file_manager, "project_manager", None)
            if pm and hasattr(pm, "get_project_data"):
                data = pm.get_project_data(self.current_project)
                if isinstance(data, dict):
                    return str(data.get("target_ip") or "")
        except Exception:
            pass
        return ""

    def _get_project_dir(self) -> Optional[Path]:
        if not self.current_project:
            return None
        rfm = self.report_file_manager
        if rfm and getattr(rfm, "project_manager", None):
            try:
                pname = rfm.resolve_project_name(self.current_project)
                return rfm.project_manager.get_project_dir(pname)
            except Exception:
                pass
        return None

    def refresh_loot_sync_state(self) -> None:
        """Refresh the navigator's non-destructive Loot/report comparison."""
        if not hasattr(self, "navigator"):
            return
        self.mutation_actions.refresh_loot_sync_state()

    def _set_loot_sync_state(self, missing: int, stale: int, orphaned: int) -> None:
        self.navigator.set_loot_sync_state(
            missing, stale, orphaned
        )
        if hasattr(self, "action_sync_loot"):
            self.action_sync_loot.setEnabled(bool(missing))

    def _refresh_workspace_navigator(self, *, preserve_selection: bool = True) -> None:
        """Reload navigator content while retaining the active report context."""
        if self._workspace_doc is None or not hasattr(self, "navigator"):
            return
        selected_data = None
        if preserve_selection:
            selected = self.navigator.tree.currentItem()
            selected_data = (
                selected.data(0, Qt.ItemDataRole.UserRole) if selected is not None else None
            )
        self.navigator.load_document(
            self._workspace_doc,
            project_name=self.current_project or "",
            target_ip=self._get_target_ip(),
        )
        if selected_data:
            self.navigator.select_item(*selected_data)
        if (
            hasattr(self, "readiness_inspector")
            and self.center_stack.currentWidget() == self.readiness_inspector_glass
        ):
            self.readiness_inspector.load_assessment(
                assess_report_readiness(self._workspace_doc)
            )
        self.refresh_loot_sync_state()

    def _sync_markdown_to_workspace(self) -> None:
        """Parses current editor markdown into workspace document and refreshes navigator."""
        if getattr(self, "_syncing_from_inspector", False):
            return
        content = self.editor.toPlainText()
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(content)
        if hasattr(self, "navigator"):
            self._refresh_workspace_navigator()

    def _sync_workspace_doc_to_editor(self) -> None:
        """Serializes workspace document to markdown and updates editor without re-triggering parse."""
        if self._workspace_doc is None:
            return
        new_md = self._workspace_doc.to_markdown()
        self._syncing_from_inspector = True
        try:
            cur = self.editor.textCursor()
            pos = cur.position()
            self.editor.setPlainText(new_md)
            cur.setPosition(min(pos, len(new_md)))
            self.editor.setTextCursor(cur)
        finally:
            self._syncing_from_inspector = False
        self._set_dirty(True)
        self._draft_timer.start()
        self._update_preview()
        if hasattr(self, "navigator"):
            self._refresh_workspace_navigator()

    def _on_navigate_requested(self, view_type: str, item_id: Optional[str]) -> None:
        """Compatibility adapter for legacy internal and test callers."""
        self.navigate_to(ReportLocation.from_legacy(view_type, item_id))

    def navigate_to(self, location: ReportLocation) -> None:
        """Show the inspector and preview focus for a semantic report location."""
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        if self._view_mode != ViewMode.WORKSPACE:
            self._set_view_mode(ViewMode.WORKSPACE)

        route = self.workspace_router.route(
            location,
            self._workspace_doc,
            ReportRouteContext(
                target_ip=self._get_target_ip(),
                project_dir=self._get_project_dir(),
                loot_manager=self.loot_manager,
                clipboard_history=self.clipboard_history,
            ),
        )
        if route.surface is not None:
            self.center_stack.setCurrentWidget(route.surface)
            if route.structured:
                self._last_active_inspector = route.surface
        if route.structured is not None and hasattr(self, "btn_toggle_raw"):
            icon_name = "fa5s.code" if route.structured else "fa5s.sliders-h"
            self.btn_toggle_raw.setIcon(self._toolbar_icon(icon_name))
        self.navigator.select_location(location)
        self._update_contextual_toolbar_visibility()
        if route.preview_target is None:
            self._clear_preview_focus()
        else:
            self._focus_preview_on_item(*route.preview_target)

    def _focus_preview_on_item(
        self,
        kind: str,
        identity: str,
        *,
        remember: bool = True,
    ) -> None:
        self.preview_controller.focus(kind, identity, remember=remember)
        self._active_preview_target = self.preview_controller.active_target

    def _clear_preview_focus(self) -> None:
        self.preview_controller.clear_focus()
        self._active_preview_target = None
    def _on_add_finding_requested(self) -> None:
        """Creates a finding — offering unreferenced Loot entries if available to preserve Loot workflow."""
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())

        # Check for unreferenced loot entries to preserve Loot workflow
        unreferenced_loot = []
        if self.loot_manager:
            from core.reporting import extract_report_markers

            markers = extract_report_markers(self.editor.toPlainText())
            for entry in self.loot_manager.get_all_entries():
                if entry.get("id") and entry["id"] not in markers:
                    unreferenced_loot.append(entry)

        chosen_entry = None
        if unreferenced_loot:
            dialog = LootEntryPickerDialog(unreferenced_loot, parent=self)
            dialog.setWindowTitle(
                t("report.add_finding_from_loot_title", "Create Finding from Unassigned Loot")
            )
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_entry:
                chosen_entry = dialog.selected_entry

        import uuid
        from core.reporting import format_loot_marker, loot_content_hash

        if chosen_entry:
            new_id = chosen_entry["id"]
            new_finding = ReportFindingItem(
                id=new_id,
                title=chosen_entry.get("title") or t("report.new_finding_default_title", "New Finding"),
                severity=chosen_entry.get("severity", "medium"),
                status="open",
                phase=normalize_phase_key(chosen_entry.get("phase") or chosen_entry.get("category") or "recon"),
                targets=[str(chosen_entry["target_ip"])] if chosen_entry.get("target_ip") else [],
                description=chosen_entry.get("content", ""),
                recommendation=chosen_entry.get("recommendation", ""),
                loot_marker=format_loot_marker(new_id, loot_content_hash(chosen_entry)),
            )
        else:
            new_id = f"finding-{uuid.uuid4().hex[:6]}"
            new_finding = ReportFindingItem(
                id=new_id,
                title=t("report.new_finding_default_title", "New Finding"),
                severity="medium",
                status="open",
                phase="recon",
                targets=[self._get_target_ip()] if self._get_target_ip() else [],
                description="",
                recommendation="",
            )

        self._workspace_doc.add_finding(new_finding)
        self._sync_workspace_doc_to_editor()
        self._on_navigate_requested("finding", new_id)

    def _on_metadata_changed(self, updated: ReportMetadata) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        self._workspace_doc.metadata = updated
        self._sync_workspace_doc_to_editor()

    def _on_finding_changed(self, updated: ReportFindingItem) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        self._workspace_doc.update_finding(updated)
        self._sync_workspace_doc_to_editor()
        if hasattr(self, "summary_inspector_glass") and self.center_stack.currentWidget() == self.summary_inspector_glass:
            self.summary_inspector.load_summary(self._workspace_doc)
        if hasattr(self, "remediation_inspector_glass") and self.center_stack.currentWidget() == self.remediation_inspector_glass:
            self.remediation_inspector.load_remediation(self._workspace_doc)
        if hasattr(self, "attack_path_inspector_glass") and self.center_stack.currentWidget() == self.attack_path_inspector_glass:
            self.attack_path_inspector.load_attack_path(self._workspace_doc)

    def _on_finding_deleted(self, finding_id: str) -> None:
        if self._workspace_doc is None:
            return
        self._workspace_doc.remove_finding(finding_id)
        self._sync_workspace_doc_to_editor()
        remaining = self._workspace_doc.findings[0] if self._workspace_doc.findings else None
        self._on_navigate_requested(
            "finding" if remaining else "findings_overview",
            remaining.id if remaining else None,
        )

    def _on_finding_duplicated(self, finding_id: str) -> None:
        import uuid

        if self._workspace_doc is None:
            return
        orig = self._workspace_doc.get_finding(finding_id)
        if not orig:
            return
        new_id = f"finding-{uuid.uuid4().hex[:6]}"
        dup = ReportFindingItem(
            id=new_id,
            title=f"{orig.title} (Kopie)",
            severity=orig.severity,
            status=orig.status,
            phase=orig.phase,
            targets=list(orig.targets),
            description=orig.description,
            recommendation=orig.recommendation,
            references=list(orig.references),
        )
        self._workspace_doc.add_finding(dup)
        self._sync_workspace_doc_to_editor()
        self._on_navigate_requested("finding", new_id)

    def _on_section_changed(self, identity: str, content: str) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        narr = next(
            (n for n in self._workspace_doc.narratives if n.identity == identity or n.section_type == identity),
            None,
        )
        if narr:
            narr.content = content
        self._sync_workspace_doc_to_editor()

    def _on_summary_changed(self, updated: ReportExecutiveSummary) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        self._workspace_doc.set_executive_summary(updated)
        self._sync_workspace_doc_to_editor()

    def _on_finding_action_changed(self, finding_id: str, new_rec: str, new_status: str) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        target = self._workspace_doc.get_finding(finding_id)
        if target:
            target.recommendation = new_rec
            target.status = new_status
            self._sync_workspace_doc_to_editor()
            if hasattr(self, "summary_inspector_glass") and self.center_stack.currentWidget() == self.summary_inspector_glass:
                self.summary_inspector.load_summary(self._workspace_doc)

    def _on_remediation_plan_changed(self, updated: ReportRemediationPlan) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        self._workspace_doc.set_remediation_plan(updated)
        self._sync_workspace_doc_to_editor()

    def _on_attack_path_changed(self, updated: ReportAttackPath) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        self._workspace_doc.set_attack_path(updated)
        self._sync_workspace_doc_to_editor()

    def _on_scope_changed(self, updated: ReportScopeMethodology) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        self._workspace_doc.set_scope_methodology(updated)
        self._sync_workspace_doc_to_editor()

    def _on_appendix_changed(self, updated: ReportAppendix) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())
        self._workspace_doc.set_appendix(updated)
        self._sync_workspace_doc_to_editor()
