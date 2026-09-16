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
    FindingPromotionService,
    ReportMutationService,
    ReportRemediationPlan,
    ReportScopeMethodology,
    ReportSessionService,
    ReportTemplate,
    ReportWorkspaceDocument,
    TemplateRepository,
    assess_report_readiness,
    build_report_navigation,
    duplicate_report_finding,
    strip_generator_footer,
)
from core.config import ConfigManager
from ui.coordinators.export_coordinator import ExportCoordinator
from core.i18n import t
from core.logger import get_logger
from core.fonts import get_report_font_stack
from core.theme_loader import ThemeLoader
from ui.report.export_actions import ReportExportActions
from ui.report.evidence_actions import ReportEvidenceActions
from ui.report.finding_promotion_actions import (
    FindingPromotionCallbacks,
    ReportFindingPromotionActions,
)
from ui.report.format_actions import ReportFormatActions
from ui.report.navigation import ReportLocation, ReportLocationKind
from ui.report.action_toolbar import (
    ReportActionCallbacks,
    ReportActionToolbar,
    ReportViewOption,
)
from ui.report.workspace_router import ReportRouteContext
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
)
from ui.styles.icons import icon
from ui.message_boxes import show_warning_dialog

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

    action_toolbar: ReportActionToolbar
    workspace_shell: ReportWorkspaceShell
    preview_controller: ReportPreviewController

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
        self.session_controller = ReportSessionController(
            service=ReportSessionService(report_file_manager),
            parent=self,
            set_status=lambda message: self.action_toolbar.lbl_status.setText(message),
        )
        self.mutation_actions = ReportMutationActions(
            parent=self,
            service=ReportMutationService(report_file_manager),
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
                set_status=lambda message: self.action_toolbar.lbl_status.setText(message),
            ),
        )

        self.format_actions = ReportFormatActions(
            editor=lambda: self.workspace_shell.editor,
            parent_widget=self,
            loot_manager_provider=lambda: self.loot_manager,
            report_file_manager_provider=lambda: self.report_file_manager,
            current_project_provider=lambda: self.current_project,
            format_toolbar_provider=lambda: getattr(self, "format_toolbar_widget", None),
        )
        self.export_actions = ReportExportActions(
            parent_widget=self,
            editor=lambda: self.workspace_shell.editor,
            report_file_manager_provider=lambda: self.report_file_manager,
            export_coordinator_provider=lambda: self.export_coordinator,
            current_project_provider=lambda: self.current_project,
            active_template_provider=lambda: self.active_template,
            report_font_key_provider=lambda: self._report_font_key(),
            prepare_export=self._commit_preview_if_active,
        )
        self.evidence_actions = ReportEvidenceActions(
            parent_widget=self,
            loot_manager_provider=lambda: self.loot_manager,
            clipboard_history_provider=lambda: self.clipboard_history,
            report_file_manager_provider=lambda: self.report_file_manager,
            current_project_provider=lambda: self.current_project,
            attach_evidence=lambda item: (
                self.workspace_shell.finding_inspector.attach_evidence_item(
                    item, insert_into_description=True
                )
            ),
        )
        self.finding_promotion_actions = ReportFindingPromotionActions(
            parent=self,
            service=FindingPromotionService(),
            loot_manager=lambda: self.loot_manager,
            callbacks=FindingPromotionCallbacks(
                current_markdown=self.current_markdown,
                add_finding=self._add_promoted_finding,
            ),
        )

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self.refresh_preview)

        self._draft_timer = QTimer(self)
        self._draft_timer.setSingleShot(True)
        self._draft_timer.setInterval(DRAFT_DEBOUNCE_MS)
        self._draft_timer.timeout.connect(self._save_draft_snapshot)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self.autosave)
        self._autosave_timer.start()

        self._workspace_doc: Optional[ReportWorkspaceDocument] = None
        self._syncing_from_inspector = False
        self._workspace_parse_timer = QTimer(self)
        self._workspace_parse_timer.setSingleShot(True)
        self._workspace_parse_timer.setInterval(500)
        self._workspace_parse_timer.timeout.connect(self.sync_workspace_from_markdown)

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
        self.action_toolbar = ReportActionToolbar(
            parent=self,
            callbacks=ReportActionCallbacks(
                change_view=lambda mode: self.set_view_mode(mode),
                toggle_navigator=lambda: self._toggle_navigator(),
                populate_navigator=lambda: self._populate_navigator_menu(),
                toggle_raw=lambda: self._toggle_inspector_raw(),
                append_loot=lambda: self.mutation_actions.synchronize_loot(),
                regenerate=lambda: self.mutation_actions.regenerate(),
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
        self._update_report_metadata_button()
        self._update_report_theme_button()
        layout.addWidget(self.action_toolbar)

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
        self.action_toolbar.setVisible(not collapsed)
        self._main_layout.setSpacing(0 if collapsed else 6)
        if not collapsed and self._view_mode == ViewMode.PREVIEW:
            self.format_toolbar_widget.tools_container.setVisible(False)

    def _toolbar_icon(self, icon_name: str, color: Optional[str] = None):
        """Create a toolbar icon using the active app theme through the central wrapper."""
        return icon(
            icon_name,
            color=color or self._toolbar_palette["CYBER_BLUE_LIGHT"],
            color_active=self._toolbar_palette["TEXT_PRIMARY"],
        )

    def _build_editor_splitter(self, layout: QVBoxLayout) -> None:
        """Build the Report Workspace shell."""
        self.workspace_shell = build_report_workspace_shell(
            parent=self,
            callbacks=ReportWorkspaceCallbacks(
                navigate=lambda location: self.navigate_to(location),
                add_finding=lambda: self.add_finding(),
                promote_finding=self.finding_promotion_actions.promote,
                sync_loot=lambda: self.mutation_actions.synchronize_loot(),
                text_changed=lambda: self._on_text_changed(),
                metadata_changed=lambda value: self._on_metadata_changed(value),
                finding_changed=lambda value: self._on_finding_changed(value),
                finding_deleted=lambda value: self.delete_finding(value),
                finding_duplicated=lambda value: self.duplicate_finding(value),
                section_changed=lambda identity, content: self._on_section_changed(
                    identity, content
                ),
                summary_changed=lambda value: self._on_summary_changed(value),
                finding_action_changed=(
                    lambda finding_id, recommendation, status: self._on_finding_action_changed(
                        finding_id, recommendation, status
                    )
                ),
                remediation_plan_changed=(lambda value: self._on_remediation_plan_changed(value)),
                attack_path_changed=lambda value: self._on_attack_path_changed(value),
                scope_changed=lambda value: self._on_scope_changed(value),
                appendix_changed=lambda value: self._on_appendix_changed(value),
                editor_scroll=lambda value: self.preview_controller.on_editor_scroll(value),
                preview_scroll=lambda value: self.preview_controller.on_preview_scroll(value),
            ),
            evidence_actions=self.evidence_actions,
        )
        self.preview_controller = ReportPreviewController(
            editor=self.workspace_shell.editor,
            preview=self.workspace_shell.preview,
            document=self.workspace_shell.preview_document,
            light_mode_provider=lambda: self._light_report_view,
            split_mode_provider=lambda: self._view_mode == ViewMode.SPLIT,
        )
        layout.addWidget(self.workspace_shell.find_replace)
        self._apply_preview_font()
        self._apply_report_color_mode()
        layout.addWidget(self.workspace_shell.splitter, stretch=1)

    def _setup_shortcuts(self) -> None:
        """Register report editing and view-mode shortcuts."""
        sc_save = QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save)
        sc_save.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc_save_shift = QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self.save)
        sc_save_shift.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_cycle = QShortcut(QKeySequence("Ctrl+Shift+V"), self, activated=self.cycle_view_mode)
        sc_cycle.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode1 = QShortcut(
            QKeySequence("Ctrl+1"), self, activated=lambda: self.set_view_mode(ViewMode.EDITOR)
        )
        sc_mode1.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode2 = QShortcut(
            QKeySequence("Ctrl+2"), self, activated=lambda: self.set_view_mode(ViewMode.SPLIT)
        )
        sc_mode2.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode3 = QShortcut(
            QKeySequence("Ctrl+3"), self, activated=lambda: self.set_view_mode(ViewMode.PREVIEW)
        )
        sc_mode3.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_mode4 = QShortcut(
            QKeySequence("Ctrl+4"), self, activated=lambda: self.set_view_mode(ViewMode.WORKSPACE)
        )
        sc_mode4.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        sc_nav = QShortcut(QKeySequence("Ctrl+Shift+N"), self, activated=self._toggle_navigator)
        sc_nav.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

        self._shortcut_find = QShortcut(
            QKeySequence("Ctrl+F"),
            self.workspace_shell.editor,
            activated=self.workspace_shell.find_replace.open,
        )
        self._shortcut_find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._shortcut_find_close = QShortcut(
            QKeySequence("Esc"),
            self.workspace_shell.find_replace,
            activated=self.workspace_shell.find_replace.close_bar,
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
            shortcut = QShortcut(
                QKeySequence(sequence), self.workspace_shell.editor, activated=callback
            )
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
        self.workspace_shell.editor.set_metadata_visible(visible)
        self._update_report_metadata_button()

    def _update_report_metadata_button(self) -> None:
        if not hasattr(self, "action_toolbar"):
            return
        visible = (
            self.workspace_shell.editor.metadata_visible()
            if hasattr(self, "workspace_shell")
            else False
        )
        tooltip = (
            t("report.hide_metadata", "Hide Spectre metadata")
            if visible
            else t("report.show_metadata", "Show Spectre metadata")
        )
        self.action_toolbar.btn_report_metadata.setToolTip(tooltip)
        self.action_toolbar.btn_report_metadata.setAccessibleName(tooltip)
        self.action_toolbar.btn_report_metadata.setIcon(
            self._toolbar_icon("fa5s.eye" if visible else "fa5s.eye-slash")
        )

    def _apply_report_color_mode(self) -> None:
        widgets = [
            self.workspace_shell.editor,
            self.workspace_shell.preview,
            self.workspace_shell.editor_glass,
            self.workspace_shell.preview_glass,
        ]

        for widget in widgets:
            widget.setProperty("reportLight", self._light_report_view)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.workspace_shell.highlighter.set_light_mode(self._light_report_view)
        self._apply_preview_font()
        self._update_report_theme_button()
        self.refresh_preview()

    def _update_report_theme_button(self) -> None:
        if not hasattr(self, "action_toolbar"):
            return
        tooltip = (
            t("report.view_dark", "Switch report panes to dark mode")
            if self._light_report_view
            else t("report.view_light", "Switch report panes to light mode")
        )
        self.action_toolbar.btn_report_theme.setToolTip(tooltip)
        self.action_toolbar.btn_report_theme.setAccessibleName(tooltip)
        self.action_toolbar.btn_report_theme.setIcon(
            self._toolbar_icon("fa5s.moon" if self._light_report_view else "fa5s.sun")
        )

    def refresh_font_configuration(self) -> None:
        """Refresh preview typography after settings are saved."""
        self._apply_preview_font()
        self.refresh_preview()

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
        self.workspace_shell.preview_document.set_project_dir(loaded.project_dir)
        content = strip_generator_footer(loaded.markdown)

        # setPlainText löst textChanged aus -> _dirty würde faelschlich True
        # werden, deshalb Signal kurz blocken.
        self.workspace_shell.editor.blockSignals(True)
        self.workspace_shell.editor.setPlainText(content)
        self.workspace_shell.editor.blockSignals(False)
        self._set_dirty(loaded.restored_draft or content != loaded.markdown)
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(content)
        self._refresh_workspace_navigator(preserve_selection=False)
        if self._view_mode == ViewMode.WORKSPACE:
            self.navigate_to(ReportLocation(ReportLocationKind.METADATA))
        self.refresh_preview()
        self._update_status_label()

    # ------------------------------------------------------------------ #
    # Dirty-State
    # ------------------------------------------------------------------ #

    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def view_mode(self) -> ViewMode:
        return self._view_mode

    @property
    def light_report_view(self) -> bool:
        return self._light_report_view

    @property
    def workspace_document(self) -> Optional[ReportWorkspaceDocument]:
        return self._workspace_doc

    def current_markdown(self) -> str:
        """Return the canonical Markdown owned by the editor."""
        return self.workspace_shell.editor.toPlainText()

    def replace_markdown(self, markdown: str) -> None:
        """Replace the canonical Markdown through the tab's public boundary."""
        self.workspace_shell.editor.setPlainText(markdown)

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
        if hasattr(self, "preview_controller") and self.preview_controller.syncing_scroll:
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
        self.refresh_preview()
        self._preview_markdown_snapshot = self.workspace_shell.editor.toPlainText()
        self.workspace_shell.preview.setReadOnly(False)
        self.workspace_shell.preview.setFocus()

    def _commit_preview_to_markdown(self) -> bool:
        """Commits rich-text edits from the preview document back to the markdown editor."""
        from core.reporting import preserve_markers_in_preview_roundtrip

        raw_markdown = strip_preview_surrogates(self.workspace_shell.preview_document.toMarkdown())
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
                self.refresh_preview()
                self._preview_markdown_snapshot = self.workspace_shell.editor.toPlainText()
                return False

        if new_markdown != self._preview_markdown_snapshot:
            self.workspace_shell.editor.blockSignals(True)
            self.workspace_shell.editor.setPlainText(new_markdown)
            self.workspace_shell.editor.blockSignals(False)
            self._set_dirty(True)

        self._preview_markdown_snapshot = (
            new_markdown if self._view_mode == ViewMode.PREVIEW else None
        )
        return True

    def set_view_mode(self, mode: ViewMode) -> None:
        """Switches the view mode and handles preview commit / readonly transitions."""
        if mode == self._view_mode:
            return

        # Leaving PREVIEW mode -> commit edits and make preview read-only
        if self._view_mode == ViewMode.PREVIEW:
            if not self._commit_preview_to_markdown():
                return
            self.workspace_shell.preview.setReadOnly(True)

        # Entering PREVIEW mode -> make editable and take snapshot
        if mode == ViewMode.PREVIEW:
            self._enter_preview_mode()

        self._view_mode = mode
        self._apply_view_mode(mode)
        self._update_status_label()

    def _toggle_navigator(self) -> None:
        """Toggles visibility of the Navigator sidebar without disrupting 2-column Split view."""
        is_vis = not self.workspace_shell.navigator_glass.isVisible()
        self.workspace_shell.navigator_glass.setVisible(is_vis)
        self.action_toolbar.btn_navigator.setChecked(is_vis)
        total_w = self.workspace_shell.splitter.width() or 1000
        cur_sizes = self.workspace_shell.splitter.sizes()
        ratio = (
            (cur_sizes[1] / max(1, cur_sizes[1] + cur_sizes[2]))
            if (len(cur_sizes) >= 3 and (cur_sizes[1] + cur_sizes[2]) > 0)
            else 0.5
        )
        ratio = max(0.25, min(0.75, ratio))
        nav_w = min(max(180, cur_sizes[0] if cur_sizes[0] > 0 else 260), 400)

        if is_vis:
            if self._view_mode == ViewMode.EDITOR:
                self.workspace_shell.splitter.setSizes([nav_w, max(200, total_w - nav_w), 0])
            else:
                rem = max(350, total_w - nav_w)
                c_w = max(200, int(rem * ratio))
                p_w = max(150, rem - c_w)
                self.workspace_shell.splitter.setSizes([nav_w, c_w, p_w])
        else:
            if self._view_mode == ViewMode.EDITOR:
                self.workspace_shell.splitter.setSizes([0, total_w, 0])
            else:
                c_w = max(200, int(total_w * ratio))
                p_w = max(150, total_w - c_w)
                self.workspace_shell.splitter.setSizes([0, c_w, p_w])

    def _toggle_inspector_raw(self) -> None:
        """Toggles center editing widget between the active Form Inspector and Raw Markdown Editor."""
        if self.workspace_shell.center_stack.currentWidget() == self.workspace_shell.editor_glass:
            target = getattr(
                self, "_last_active_inspector", self.workspace_shell.finding_inspector_glass
            )
            self.workspace_shell.center_stack.setCurrentWidget(target)
            self.action_toolbar.btn_toggle_raw.setIcon(self._toolbar_icon("fa5s.code"))
            self.action_toolbar.btn_toggle_raw.setToolTip(
                t("report.toggle_raw_code", "Switch to Markdown source")
            )
        else:
            self._last_active_inspector = self.workspace_shell.center_stack.currentWidget()
            self.workspace_shell.center_stack.setCurrentWidget(self.workspace_shell.editor_glass)
            self.action_toolbar.btn_toggle_raw.setIcon(self._toolbar_icon("fa5s.sliders-h"))
            self.action_toolbar.btn_toggle_raw.setToolTip(
                t("report.toggle_raw_form", "Switch to structured form")
            )
        self._update_contextual_toolbar_visibility()

    def _update_contextual_toolbar_visibility(self) -> None:
        """Show Markdown tools only while the Markdown surface is actually active."""
        if not hasattr(self, "format_toolbar_widget"):
            return
        raw_active = (
            self.workspace_shell.center_stack.currentWidget() == self.workspace_shell.editor_glass
        )
        show_formatting = self._view_mode in (ViewMode.EDITOR, ViewMode.SPLIT) or (
            self._view_mode == ViewMode.WORKSPACE and raw_active
        )
        self.format_toolbar_widget.setVisible(show_formatting)
        if show_formatting:
            self.format_toolbar_widget.tools_container.setVisible(
                not self.format_toolbar_widget.is_collapsed()
            )
        self.action_toolbar.setVisible(True)
        workspace_active = self._view_mode == ViewMode.WORKSPACE
        self.action_toolbar.btn_toggle_raw.setVisible(not workspace_active)
        self.action_toolbar.btn_report_actions.setVisible(workspace_active)
        self.action_toolbar.btn_append_loot.setVisible(not workspace_active)
        self.action_toolbar.btn_regenerate.setVisible(not workspace_active)

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
        self.action_toolbar.btn_change_view.setText(
            labels.get(self._view_mode, t("report.change_view", "Change View"))
        )
        self.action_toolbar.btn_change_view.setIcon(
            self._toolbar_icon(icons.get(self._view_mode, "fa5s.columns"))
        )

    def _apply_view_mode(self, mode: ViewMode) -> None:
        """Applies visibility and splitter layout for the selected view mode."""
        for action_mode, action in self.action_toolbar.view_actions.items():
            action.setChecked(action_mode == mode)
        nav_visible = self.workspace_shell.navigator_glass.isVisible()
        if mode in (ViewMode.EDITOR, ViewMode.SPLIT):
            # The legacy views are deliberately clean Markdown surfaces; the
            # navigator remains available through its explicit toolbar toggle.
            nav_visible = False
            self.workspace_shell.navigator_glass.setVisible(False)
            self.workspace_shell.center_stack.setCurrentWidget(self.workspace_shell.editor_glass)
        self.action_toolbar.btn_navigator.setChecked(nav_visible)

        total_w = self.workspace_shell.splitter.width() or 1000
        cur_sizes = self.workspace_shell.splitter.sizes()
        ratio = (
            (cur_sizes[1] / max(1, cur_sizes[1] + cur_sizes[2]))
            if (len(cur_sizes) >= 3 and (cur_sizes[1] + cur_sizes[2]) > 0)
            else 0.5
        )
        ratio = max(0.25, min(0.75, ratio))
        nav_w = min(max(180, cur_sizes[0] if cur_sizes[0] > 0 else 260), 400) if nav_visible else 0

        if mode == ViewMode.WORKSPACE:
            self.workspace_shell.navigator_glass.setVisible(True)
            self.action_toolbar.btn_navigator.setChecked(True)
            self.workspace_shell.center_stack.setVisible(True)
            self.workspace_shell.preview_glass.setVisible(True)
            if (
                self.workspace_shell.center_stack.currentWidget()
                == self.workspace_shell.editor_glass
            ):
                target = getattr(
                    self, "_last_active_inspector", self.workspace_shell.finding_inspector_glass
                )
                self.workspace_shell.center_stack.setCurrentWidget(target)
                self.action_toolbar.btn_toggle_raw.setIcon(self._toolbar_icon("fa5s.code"))
            actual_nav_w = nav_w if nav_w > 0 else 260
            rem = max(350, total_w - actual_nav_w)
            c_w = max(200, int(rem * ratio))
            p_w = max(150, rem - c_w)
            self.workspace_shell.splitter.setSizes([actual_nav_w, c_w, p_w])
            self.preview_controller.sync_editor_to_preview()
        elif mode == ViewMode.SPLIT:
            self.workspace_shell.navigator_glass.setVisible(nav_visible)
            self.workspace_shell.center_stack.setVisible(True)
            self.workspace_shell.preview_glass.setVisible(True)
            rem = max(350, total_w - nav_w)
            c_w = max(200, int(rem * ratio))
            p_w = max(150, rem - c_w)
            self.workspace_shell.splitter.setSizes([nav_w, c_w, p_w])
            self.preview_controller.sync_editor_to_preview()
        elif mode == ViewMode.EDITOR:
            self.workspace_shell.navigator_glass.setVisible(nav_visible)
            self.workspace_shell.center_stack.setVisible(True)
            self.workspace_shell.preview_glass.setVisible(False)
            self.workspace_shell.splitter.setSizes([nav_w, max(200, total_w - nav_w), 0])
        elif mode == ViewMode.PREVIEW:
            self.workspace_shell.navigator_glass.setVisible(False)
            self.workspace_shell.center_stack.setVisible(False)
            self.workspace_shell.preview_glass.setVisible(True)
            self.workspace_shell.splitter.setSizes([0, 0, total_w])
        self._update_contextual_toolbar_visibility()
        self._update_view_button()

    def cycle_view_mode(self) -> None:
        """Cycles through all report views, starting with the primary workspace."""
        modes = [ViewMode.WORKSPACE, ViewMode.EDITOR, ViewMode.SPLIT, ViewMode.PREVIEW]
        idx = modes.index(self._view_mode) if self._view_mode in modes else 0
        self.set_view_mode(modes[(idx + 1) % len(modes)])

    def save(self) -> bool:
        if not self.current_project:
            return False

        if self._view_mode == ViewMode.PREVIEW:
            if not self._commit_preview_to_markdown():
                return False

        saved = self.session_controller.save(
            self.current_project, self.workspace_shell.editor.toPlainText()
        )
        if saved:
            self._set_dirty(False)
            if self._draft_timer.isActive():
                self._draft_timer.stop()
        return saved

    def autosave(self) -> None:
        """Persist a dirty report without interrupting the user on failures."""
        if not self.is_dirty() or not self.current_project:
            return
        if self._view_mode == ViewMode.PREVIEW:
            if not self._commit_preview_to_markdown():
                return
        if self.session_controller.autosave(
            self.current_project, self.workspace_shell.editor.toPlainText()
        ):
            self._set_dirty(False)

    def closeEvent(self, event) -> None:
        self._autosave_timer.stop()
        super().closeEvent(event)

    def _commit_preview_if_active(self) -> bool:
        return self._view_mode != ViewMode.PREVIEW or self._commit_preview_to_markdown()

    def _set_active_template(self, template: ReportTemplate) -> None:
        self.active_template = template

    def _apply_persisted_mutation(self, markdown: str, preserve_cursor: bool) -> None:
        cursor_position = (
            self.workspace_shell.editor.textCursor().position() if preserve_cursor else 0
        )
        self.workspace_shell.editor.blockSignals(True)
        self.workspace_shell.editor.setPlainText(markdown)
        self.workspace_shell.editor.blockSignals(False)
        self._set_dirty(False)
        self.refresh_preview()
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(markdown)
        self._refresh_workspace_navigator()
        if preserve_cursor:
            cursor = self.workspace_shell.editor.textCursor()
            cursor.setPosition(min(cursor_position, len(markdown)))
            self.workspace_shell.editor.setTextCursor(cursor)

    def _ensure_active_template(self) -> None:
        """Keeps the most recently selected template available for the next dialog."""
        templates = self.template_repo.get_all_templates()
        if self.active_template is None and templates:
            self.active_template = templates[0]

    # ------------------------------------------------------------------ #
    # Vorschau & Status
    # ------------------------------------------------------------------ #

    def refresh_preview(self) -> None:
        project_dir = None
        if self.current_project:
            project_dir = self.report_file_manager.project_manager.get_project_dir(
                self.current_project
            )
        self.preview_controller.render(self.workspace_shell.editor.toPlainText(), project_dir)

    def _update_status_label(self) -> None:
        if not self.current_project:
            self.action_toolbar.lbl_status.setText("")
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
        self.action_toolbar.lbl_status.setText(
            f"{self.current_project} — {status_text} · [{mode_label}]"
        )

    # ------------------------------------------------------------------ #
    # Scroll-Sync (Split-View)
    # ------------------------------------------------------------------ #

    def _jump_to_heading_line(self, line_number: int) -> None:
        """Positions cursor at the given 1-based line number and ensures it is visible."""
        block = self.workspace_shell.editor.document().findBlockByNumber(line_number - 1)
        if block.isValid():
            cursor = self.workspace_shell.editor.textCursor()
            cursor.setPosition(block.position())
            self.workspace_shell.editor.setTextCursor(cursor)
            self.workspace_shell.editor.ensureCursorVisible()
            self.workspace_shell.editor.setFocus()
            self.preview_controller.sync_editor_to_preview()

    def _populate_navigator_menu(self) -> None:
        self.action_toolbar.navigator_menu.clear()
        navigation = build_report_navigation(self.workspace_shell.editor.toPlainText())
        groups = (
            (t("report.navigator_sections", "Sections"), navigation.sections),
            (t("report.navigator_findings", "Findings"), navigation.findings),
        )
        has_entries = False
        for label, entries in groups:
            if not entries:
                continue
            has_entries = True
            submenu = self.action_toolbar.navigator_menu.addMenu(label)
            for entry in entries:
                action = submenu.addAction(entry.title)
                action.triggered.connect(
                    lambda _checked=False, kind=entry.kind, identity=entry.identity: (
                        self.navigate_source_to(ReportLocation(ReportLocationKind(kind), identity))
                    )
                )
        if not has_entries:
            action = self.action_toolbar.navigator_menu.addAction(
                t(
                    "report.navigator_empty",
                    "No navigable report sections yet. Generate or structure the report to populate this menu.",
                )
            )
            action.setEnabled(False)

    def navigate_source_to(self, location: ReportLocation) -> None:
        """Focus a semantic heading in the Markdown source editor."""
        if location.identity is None:
            return
        if self._view_mode == ViewMode.PREVIEW:
            self.set_view_mode(ViewMode.EDITOR)
        navigation = build_report_navigation(self.workspace_shell.editor.toPlainText())
        entries = (
            navigation.sections
            if location.kind is ReportLocationKind.SECTION
            else navigation.findings
        )
        target = next((entry for entry in entries if entry.identity == location.identity), None)
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
            self.current_project, self.workspace_shell.editor.toPlainText()
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
        self.mutation_actions.refresh_loot_sync_state()

    def _set_loot_sync_state(self, missing: int, stale: int, orphaned: int) -> None:
        self.workspace_shell.navigator.set_loot_sync_state(missing, stale, orphaned)
        self.action_toolbar.action_sync_loot.setEnabled(bool(missing or stale or orphaned))

    def _refresh_workspace_navigator(self, *, preserve_selection: bool = True) -> None:
        """Reload navigator content while retaining the active report context."""
        if self._workspace_doc is None:
            return
        selected_data = None
        if preserve_selection:
            selected = self.workspace_shell.navigator.tree.currentItem()
            selected_data = (
                selected.data(0, Qt.ItemDataRole.UserRole) if selected is not None else None
            )
        self.workspace_shell.navigator.load_document(
            self._workspace_doc,
            project_name=self.current_project or "",
            target_ip=self._get_target_ip(),
        )
        if selected_data:
            self.workspace_shell.navigator.select_item(*selected_data)
        if (
            self.workspace_shell.center_stack.currentWidget()
            == self.workspace_shell.readiness_inspector_glass
        ):
            self.workspace_shell.readiness_inspector.load_assessment(
                assess_report_readiness(self._workspace_doc)
            )
        self.refresh_loot_sync_state()

    def sync_workspace_from_markdown(self) -> None:
        """Parses current editor markdown into workspace document and refreshes navigator."""
        if getattr(self, "_syncing_from_inspector", False):
            return
        content = self.workspace_shell.editor.toPlainText()
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(content)
        self._refresh_workspace_navigator()

    def apply_workspace_document(self) -> None:
        """Serializes workspace document to markdown and updates editor without re-triggering parse."""
        if self._workspace_doc is None:
            return
        new_md = self._workspace_doc.to_markdown()
        self._syncing_from_inspector = True
        try:
            cur = self.workspace_shell.editor.textCursor()
            pos = cur.position()
            self.workspace_shell.editor.setPlainText(new_md)
            cur.setPosition(min(pos, len(new_md)))
            self.workspace_shell.editor.setTextCursor(cur)
        finally:
            self._syncing_from_inspector = False
        self._set_dirty(True)
        self._draft_timer.start()
        self.refresh_preview()
        self._refresh_workspace_navigator()

    def navigate_to(self, location: ReportLocation) -> None:
        """Show the inspector and preview focus for a semantic report location."""
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        if self._view_mode != ViewMode.WORKSPACE:
            self.set_view_mode(ViewMode.WORKSPACE)

        route = self.workspace_shell.router.route(
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
            self.workspace_shell.center_stack.setCurrentWidget(route.surface)
            if route.structured:
                self._last_active_inspector = route.surface
        if route.structured is not None:
            icon_name = "fa5s.code" if route.structured else "fa5s.sliders-h"
            self.action_toolbar.btn_toggle_raw.setIcon(self._toolbar_icon(icon_name))
        self.workspace_shell.navigator.select_location(location)
        self._update_contextual_toolbar_visibility()
        if route.preview_target is None:
            self.preview_controller.clear_focus()
        else:
            self.preview_controller.focus(*route.preview_target)

    def add_finding(self) -> None:
        """Create a blank finding without implicitly consuming Loot."""
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )

        import uuid

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
        self.apply_workspace_document()
        self.navigate_to(ReportLocation.finding(new_id))

    def _add_promoted_finding(self, finding: ReportFindingItem) -> None:
        """Commit a prepared promotion result to the active workspace document."""
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.add_finding(finding)
        self.apply_workspace_document()
        self.navigate_to(ReportLocation.finding(finding.id))

    def _on_metadata_changed(self, updated: ReportMetadata) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.metadata = updated
        self.apply_workspace_document()

    def _on_finding_changed(self, updated: ReportFindingItem) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.update_finding(updated)
        self.apply_workspace_document()
        if (
            self.workspace_shell.center_stack.currentWidget()
            == self.workspace_shell.summary_inspector_glass
        ):
            self.workspace_shell.summary_inspector.load_summary(self._workspace_doc)
        if (
            self.workspace_shell.center_stack.currentWidget()
            == self.workspace_shell.remediation_inspector_glass
        ):
            self.workspace_shell.remediation_inspector.load_remediation(self._workspace_doc)
        if (
            self.workspace_shell.center_stack.currentWidget()
            == self.workspace_shell.attack_path_inspector_glass
        ):
            self.workspace_shell.attack_path_inspector.load_attack_path(self._workspace_doc)

    def delete_finding(self, finding_id: str) -> None:
        if self._workspace_doc is None:
            return
        self._workspace_doc.remove_finding(finding_id)
        self.apply_workspace_document()
        remaining = self._workspace_doc.findings[0] if self._workspace_doc.findings else None
        self.navigate_to(
            ReportLocation.finding(remaining.id)
            if remaining
            else ReportLocation(ReportLocationKind.FINDINGS_OVERVIEW)
        )

    def duplicate_finding(self, finding_id: str) -> None:
        import uuid

        if self._workspace_doc is None:
            return
        orig = self._workspace_doc.get_finding(finding_id)
        if not orig:
            return
        new_id = f"finding-{uuid.uuid4().hex[:6]}"
        dup = duplicate_report_finding(
            orig,
            new_id=new_id,
            title=f"{orig.title} (Kopie)",
        )
        self._workspace_doc.add_finding(dup)
        self.apply_workspace_document()
        self.navigate_to(ReportLocation.finding(new_id))

    def _on_section_changed(self, identity: str, content: str) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        narr = next(
            (
                n
                for n in self._workspace_doc.narratives
                if n.identity == identity or n.section_type == identity
            ),
            None,
        )
        if narr:
            narr.content = content
        self.apply_workspace_document()

    def _on_summary_changed(self, updated: ReportExecutiveSummary) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.set_executive_summary(updated)
        self.apply_workspace_document()

    def _on_finding_action_changed(self, finding_id: str, new_rec: str, new_status: str) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        target = self._workspace_doc.get_finding(finding_id)
        if target:
            target.recommendation = new_rec
            target.status = new_status
            self.apply_workspace_document()
            if (
                self.workspace_shell.center_stack.currentWidget()
                == self.workspace_shell.summary_inspector_glass
            ):
                self.workspace_shell.summary_inspector.load_summary(self._workspace_doc)

    def _on_remediation_plan_changed(self, updated: ReportRemediationPlan) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.set_remediation_plan(updated)
        self.apply_workspace_document()

    def _on_attack_path_changed(self, updated: ReportAttackPath) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.set_attack_path(updated)
        self.apply_workspace_document()

    def _on_scope_changed(self, updated: ReportScopeMethodology) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.set_scope_methodology(updated)
        self.apply_workspace_document()

    def _on_appendix_changed(self, updated: ReportAppendix) -> None:
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(
                self.workspace_shell.editor.toPlainText()
            )
        self._workspace_doc.set_appendix(updated)
        self.apply_workspace_document()
