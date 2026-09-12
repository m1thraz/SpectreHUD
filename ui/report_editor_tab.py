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
import re
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QPushButton,
    QLabel,
    QMessageBox,
    QFileDialog,  # noqa: F401
    QDialog,
    QMenu,
    QStackedWidget,
)
from PyQt6.QtGui import QAction, QColor, QFont, QShortcut, QKeySequence, QTextCharFormat

from core.reporting import (
    ReportFileManager,
    ReportFindingItem,
    ReportMetadata,
    ReportTemplate,
    ReportWorkspaceDocument,
    TemplateRepository,
)
from core.config import ConfigManager
from ui.coordinators.export_coordinator import ExportCoordinator
from core.logger import get_logger
from core.i18n import t
from core.fonts import get_report_font_stack
from core.platform import open_path  # noqa: F401
from core.theme_loader import ThemeLoader
from ui.report.dialogs import (
    LootImagePickerDialog,  # noqa: F401
    MarkdownTableDialog,  # noqa: F401
    ReportGenerationDialog,
    ReportIconPickerDialog,  # noqa: F401
    ReportRegenerationConfirmDialog,
)
from ui.report.export_actions import ReportExportActions
from ui.report.format_actions import ReportFormatActions
from ui.report.finding_inspector import ReportFindingInspector
from ui.report.metadata_inspector import ReportMetadataInspector
from ui.report.section_inspector import ReportSectionInspector
from ui.report.workspace_navigator import ReportWorkspaceNavigator
from ui.report.icon_assets import render_report_icon  # noqa: F401
from ui.report.find_replace import FindReplaceBar
from ui.glass_panel import GlassPanel
from ui.report.preview import ReportDocument, ReportPreviewEdit
from ui.report.source_editor import ReportSourceEditor
from ui.report.toolbar import REPORT_TOOLBAR_ICON_SIZE, build_format_toolbar
from ui.styles.icons import icon
from ui.message_boxes import (
    ask_confirmation,  # noqa: F401
    show_error_dialog,  # noqa: F401
    show_information_dialog,  # noqa: F401
    show_warning_dialog,
)
from core.reporting import build_report_navigation
from core.reporting import (
    discard_draft,
    get_draft,
    has_recoverable_draft,
    save_draft,
)

logger = get_logger("report_editor")

PREVIEW_DEBOUNCE_MS = 300
DRAFT_DEBOUNCE_MS = 5_000
AUTOSAVE_INTERVAL_MS = 45_000
PREVIEW_PAGEBREAK_TOKEN = "SPECTRE_PAGEBREAK_PREVIEW_TOKEN"
PREVIEW_PAGEBREAK_LABEL = "──────── PAGE BREAK ────────"
PREVIEW_SPACER_TOKENS = {
    size: f"SPECTRE_SPACER_PREVIEW_{size.upper()}" for size in ("small", "medium", "large")
}
PREVIEW_SPACER_LABELS = {
    "small": "──── SPACER · SMALL ────",
    "medium": "──── SPACER · MEDIUM ────",
    "large": "──── SPACER · LARGE ────",
}
PREVIEW_PAGEBREAK_LINE_RE = re.compile(
    rf"(?m)^.*(?:{re.escape(PREVIEW_PAGEBREAK_LABEL)}|"
    + "|".join(re.escape(label) for label in PREVIEW_SPACER_LABELS.values())
    + r").*(?:\r?\n)?"
)


def _markdown_with_preview_pagebreaks(markdown: str) -> str:
    """Expose page-break comments to Qt while preserving fenced code examples."""
    from core.reporting import PAGEBREAK_REGEX, SPACER_REGEX

    lines = markdown.splitlines()
    in_fence = False
    fence_marker = ""
    rendered = []
    for line in lines:
        stripped = line.lstrip()
        opening = re.match(r"(`{3,}|~{3,})", stripped)
        if opening:
            marker = opening.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
            elif marker[0] == fence_marker:
                in_fence = False
                fence_marker = ""
            rendered.append(line)
        elif not in_fence and PAGEBREAK_REGEX.fullmatch(line.strip()):
            rendered.append(PREVIEW_PAGEBREAK_TOKEN)
        elif not in_fence and (spacer_match := SPACER_REGEX.fullmatch(line.strip())):
            rendered.append(PREVIEW_SPACER_TOKENS[spacer_match.group(1).lower()])
        else:
            rendered.append(line)
    return "\n".join(rendered)


def _strip_preview_pagebreaks(markdown: str) -> str:
    """Remove the visual surrogate before canonical markers are reconciled."""
    return PREVIEW_PAGEBREAK_LINE_RE.sub("", markdown)


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
        parent: QWidget = None,
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
        self._view_mode = ViewMode.SPLIT
        self._light_report_view = False
        self._preview_markdown_snapshot: Optional[str] = None

        self._syncing_scroll = False

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
        self.action_toolbar_widget = self._build_action_toolbar()
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

    def _build_action_toolbar(self) -> QWidget:
        """Build Ebene 1: Document actions on the left, status text on the right."""
        container = QWidget(self)
        container.setObjectName("ReportActionToolbar")
        toolbar = QHBoxLayout(container)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(6)

        # Compact view selector; shortcuts remain available for power users.
        self.btn_change_view = QPushButton(t("report.change_view", "Change View"))
        self.btn_change_view.setProperty("class", "SecondaryBtn")
        self.btn_change_view.setToolTip(t("report.change_view_tip", "Choose report editor layout"))
        self.btn_change_view.setIcon(self._toolbar_icon("fa5s.columns"))
        self.btn_change_view.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self._build_view_menu()
        toolbar.addWidget(self.btn_change_view)

        self.btn_navigator = QPushButton(t("report.navigator", "Report Navigator ▾"))
        self.btn_navigator.setProperty("class", "SecondaryBtn OutlineDropdownBtn")
        navigator_tooltip = t(
            "report.navigator_tip", "Navigate to report sections and findings"
        )
        self.btn_navigator.setToolTip(navigator_tooltip)
        self.btn_navigator.setAccessibleName(navigator_tooltip)
        self.btn_navigator.setIcon(self._toolbar_icon("fa5s.sitemap"))
        self.btn_navigator.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.navigator_menu = QMenu(self.btn_navigator)
        self.navigator_menu.aboutToShow.connect(self._populate_navigator_menu)
        self.btn_navigator.setMenu(self.navigator_menu)
        toolbar.addWidget(self.btn_navigator)

        self.btn_append_loot = QPushButton(t("report.append_loot", "Add Missing Loot"))
        self.btn_append_loot.setProperty("class", "SecondaryBtn AppendLootBtn")
        self.btn_append_loot.setToolTip(
            t(
                "report.append_loot_tip",
                "Appends missing loot entries to the report without overwriting manual notes",
            )
        )
        self.btn_append_loot.setIcon(self._toolbar_icon("fa5s.plus-circle"))
        self.btn_append_loot.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_append_loot.clicked.connect(self._on_append_loot_clicked)
        toolbar.addWidget(self.btn_append_loot)

        self.btn_regenerate = QPushButton(t("report.regenerate", "Regenerate from Loot"))
        self.btn_regenerate.setProperty("class", "SecondaryBtn RegenerateBtn")
        self.btn_regenerate.setToolTip(
            t("report.regenerate_tip", "Updates report structure and appends new loot entries")
        )
        self.btn_regenerate.setIcon(
            self._toolbar_icon("fa5s.sync-alt", color=self._toolbar_palette["STATUS_ERROR"])
        )
        self.btn_regenerate.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_regenerate.clicked.connect(self._on_regenerate_clicked)
        toolbar.addWidget(self.btn_regenerate)

        self.btn_export = QPushButton(t("report.export", "Export..."))
        self.btn_export.setProperty("class", "SecondaryBtn")
        self.btn_export.setToolTip(
            t("report.export_tip", "Choose how to export the current report")
        )
        self.btn_export.setIcon(self._toolbar_icon("fa5s.file-export"))
        self.btn_export.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_export.clicked.connect(self.export_actions.on_export_clicked)
        toolbar.addWidget(self.btn_export)

        self.btn_report_metadata = QPushButton()
        self.btn_report_metadata.setObjectName("btn_report_metadata")
        self.btn_report_metadata.setProperty(
            "class", "SecondaryBtn FormatToolBtn ReportIconBtn"
        )
        self.btn_report_metadata.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_report_metadata.setCheckable(True)
        self.btn_report_metadata.toggled.connect(self._toggle_report_metadata)
        toolbar.addWidget(self.btn_report_metadata)
        self._update_report_metadata_button()

        self.btn_report_theme = QPushButton()
        self.btn_report_theme.setObjectName("btn_report_theme")
        self.btn_report_theme.setProperty(
            "class", "SecondaryBtn FormatToolBtn ReportIconBtn"
        )
        self.btn_report_theme.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_report_theme.clicked.connect(self._toggle_report_color_mode)
        toolbar.addWidget(self.btn_report_theme)
        self._update_report_theme_button()

        # Verschiebe Status-Text nach rechts auf Ebene 1
        toolbar.addStretch()

        self.lbl_status = QLabel("")
        self.lbl_status.setProperty("class", "ReportStatusLabel")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self.lbl_status)

        # Kompakter QtAwesome-Save-Button rechts neben dem Status-Label
        self.btn_save = QPushButton()
        self.btn_save.setObjectName("btn_save_report")
        self.btn_save.setProperty(
            "class", "SecondaryBtn FormatToolBtn ReportIconBtn SaveIconBtn"
        )
        save_tooltip = t("report.save_tip", "Save changes to active box report.md (Ctrl+S)")
        self.btn_save.setToolTip(save_tooltip)
        self.btn_save.setAccessibleName(save_tooltip)
        self.btn_save.setIcon(self._toolbar_icon("fa5s.save"))
        self.btn_save.setIconSize(REPORT_TOOLBAR_ICON_SIZE)
        self.btn_save.clicked.connect(self.save)
        toolbar.addWidget(self.btn_save)

        return container

    def _toolbar_icon(self, icon_name: str, color: Optional[str] = None):
        """Create a toolbar icon using the active app theme through the central wrapper."""
        return icon(
            icon_name,
            color=color or self._toolbar_palette["CYBER_BLUE_LIGHT"],
            color_active=self._toolbar_palette["TEXT_PRIMARY"],
        )

    def _build_view_menu(self) -> None:
        """Populate the compact view selector."""
        self.view_menu = QMenu(self.btn_change_view)
        self._view_actions = {}
        for mode, key, fallback, icon_name in (
            (ViewMode.WORKSPACE, "report.mode_workspace", "Workspace", "fa5s.columns"),
            (ViewMode.SPLIT, "report.mode_split", "Split", "fa5s.window-restore"),
            (ViewMode.EDITOR, "report.mode_editor", "Editor", "fa5s.edit"),
            (ViewMode.PREVIEW, "report.mode_preview", "Live Preview", "fa5s.eye"),
        ):
            action = QAction(t(key, fallback), self.view_menu)
            action.setIcon(self._toolbar_icon(icon_name))
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, selected=mode: self._set_view_mode(selected)
            )
            self.view_menu.addAction(action)
            self._view_actions[mode] = action
        self.btn_change_view.setMenu(self.view_menu)

    def _build_editor_splitter(self, layout: QVBoxLayout) -> None:
        """Build the 3-column workspace splitter: Navigator, Focus Center, Live Preview."""
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Spalte 1: Navigator (links)
        self.navigator = ReportWorkspaceNavigator(self)
        self.navigator.navigate_requested.connect(self._on_navigate_requested)
        self.navigator.add_finding_requested.connect(self._on_add_finding_requested)
        self.navigator_glass = self._wrap_glass_surface(self.navigator)
        self.splitter.addWidget(self.navigator_glass)

        # Spalte 2: Fokus-Zentrum (Mitte)
        self.center_stack = QStackedWidget(self)

        # Page 0: Raw Markdown Editor
        self.editor = ReportSourceEditor()
        self.editor.setPlaceholderText(
            t(
                "report.editor_placeholder",
                "No report available for this project yet.\n\n"
                "Click 'Regenerate from Loot' above to start with an "
                "auto-generated report, or write your markdown directly here.",
            )
        )
        self.editor.setProperty("class", "ReportSourceEditor")
        self.editor.textChanged.connect(self._on_text_changed)
        from ui.markdown_highlighter import MarkdownHighlighter

        self._highlighter = MarkdownHighlighter(self.editor.document())
        self.find_replace = FindReplaceBar(self.editor, self)
        layout.addWidget(self.find_replace)
        self.editor_glass = self._wrap_glass_surface(self.editor)
        self.center_stack.addWidget(self.editor_glass)

        # Page 1: Metadata Inspector
        self.metadata_inspector = ReportMetadataInspector(self)
        self.metadata_inspector.metadata_changed.connect(self._on_metadata_changed)
        self.metadata_inspector_glass = self._wrap_glass_surface(self.metadata_inspector)
        self.center_stack.addWidget(self.metadata_inspector_glass)

        # Page 2: Finding Inspector
        self.finding_inspector = ReportFindingInspector(self)
        self.finding_inspector.finding_changed.connect(self._on_finding_changed)
        self.finding_inspector.finding_deleted.connect(self._on_finding_deleted)
        self.finding_inspector.finding_duplicated.connect(self._on_finding_duplicated)
        self.finding_inspector_glass = self._wrap_glass_surface(self.finding_inspector)
        self.center_stack.addWidget(self.finding_inspector_glass)

        # Page 3: Section Inspector
        self.section_inspector = ReportSectionInspector(self)
        self.section_inspector.section_changed.connect(self._on_section_changed)
        self.section_inspector_glass = self._wrap_glass_surface(self.section_inspector)
        self.center_stack.addWidget(self.section_inspector_glass)

        self.splitter.addWidget(self.center_stack)

        # Spalte 3: Live Preview (rechts)
        self.preview_document = ReportDocument(parent=self)
        self._apply_preview_font()

        self.preview = ReportPreviewEdit()
        self.preview.setDocument(self.preview_document)
        self.preview.setReadOnly(True)
        self.preview.setProperty("class", "ReportPreview")
        self.preview_glass = self._wrap_glass_surface(self.preview)
        self.splitter.addWidget(self.preview_glass)
        self._apply_report_color_mode()

        # Bi-directional scroll-sync between editor and live preview in Split mode
        self.editor.verticalScrollBar().valueChanged.connect(self._on_editor_scroll)
        self.preview.verticalScrollBar().valueChanged.connect(self._on_preview_scroll)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 1)
        layout.addWidget(self.splitter, stretch=1)

    @staticmethod
    def _wrap_glass_surface(widget):
        panel = GlassPanel()
        panel.setProperty("class", "ReportGlassPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        if hasattr(widget, "viewport") and callable(widget.viewport) and widget.viewport():
            widget.viewport().setAutoFillBackground(False)
        return panel

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
        """Apply the report font to the rich-text live preview."""
        report_font = get_report_font_stack(self._report_font_key())
        primary_font = report_font.split(",", 1)[0].strip().strip("'\"")
        preview_font = QFont(primary_font, 10)
        preview_font.setStyleHint(QFont.StyleHint.SansSerif)
        self.preview_document.setDefaultFont(preview_font)
        palette = (
            {
                "text": "#1f2328",
                "heading": "#0550ae",
                "heading_2": "#0969da",
                "heading_3": "#0550ae",
                "border": "#d0d7de",
                "code_bg": "#f6f8fa",
                "code": "#1a7f37",
                "quote": "#57606a",
                "link": "#0969da",
            }
            if self._light_report_view
            else {
                "text": "#f0f6fc",
                "heading": "#58a6ff",
                "heading_2": "#79c0ff",
                "heading_3": "#a5d6ff",
                "border": "#30363d",
                "code_bg": "#161b22",
                "code": "#7ee787",
                "quote": "#8b949e",
                "link": "#58a6ff",
            }
        )
        css = """
            body { font-family: __REPORT_FONT_STACK__; font-size: 13px; color: __TEXT__; line-height: 1.6; }
            h1, h2, h3, h4, h5, h6 { color: __HEADING__; font-family: __REPORT_FONT_STACK__; font-weight: 600; margin-top: 14px; margin-bottom: 6px; }
            h1 { font-size: 18px; border-bottom: 1px solid __BORDER__; padding-bottom: 4px; }
            h2 { font-size: 15px; border-bottom: 1px solid __BORDER__; padding-bottom: 3px; color: __HEADING_2__; }
            h3 { font-size: 14px; color: __HEADING_3__; }
            code { font-family: 'Cascadia Code', 'Consolas', 'Fira Code', monospace; background-color: __CODE_BG__; color: __CODE__; padding: 2px 4px; border-radius: 4px; font-size: 12px; }
            pre { background-color: __CODE_BG__; border: 1px solid __BORDER__; border-radius: 6px; padding: 8px; }
            blockquote { border-left: 3px solid __LINK__; margin: 8px 0; padding-left: 10px; color: __QUOTE__; }
            hr { border: 0; border-top: 1px solid __BORDER__; margin: 14px 0; }
            a { color: __LINK__; text-decoration: none; }
            img { max-width: 100%; border-radius: 6px; border: 1px solid __BORDER__; margin: 8px 0; }
            ul, ol { padding-left: 20px; margin: 6px 0; }
            li { margin: 3px 0; }
            p { margin: 6px 0; }
        """
        replacements = {
            "__REPORT_FONT_STACK__": report_font,
            "__TEXT__": palette["text"],
            "__HEADING__": palette["heading"],
            "__HEADING_2__": palette["heading_2"],
            "__HEADING_3__": palette["heading_3"],
            "__BORDER__": palette["border"],
            "__CODE_BG__": palette["code_bg"],
            "__CODE__": palette["code"],
            "__QUOTE__": palette["quote"],
            "__LINK__": palette["link"],
        }
        for marker, value in replacements.items():
            css = css.replace(marker, value)
        self.preview_document.setDefaultStyleSheet(css)

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
        proj_dir = self.report_file_manager.project_manager.get_project_dir(project_name)
        self.preview_document.set_project_dir(proj_dir)

        content = self.report_file_manager.load(project_name)

        # Crash Recovery: Check for uncommitted draft from unexpected termination
        if has_recoverable_draft(proj_dir, content):
            res = get_draft(proj_dir)
            if res:
                draft_text, draft_time = res
                time_str = draft_time.strftime("%H:%M:%S")
                msg = QMessageBox(self.window() if self else None)
                msg.setWindowTitle(t("report.draft_recovery_title", "Recover Unsaved Draft"))
                msg.setText(
                    t(
                        "report.draft_recovery_msg",
                        "An unsaved draft for '{project}' from {time} was found.\n\nDo you want to restore it?",
                        project=project_name,
                        time=time_str,
                    )
                )
                msg.setIcon(QMessageBox.Icon.Question)
                btn_restore = msg.addButton(
                    t("report.draft_restore_btn", "Restore Draft"),
                    QMessageBox.ButtonRole.AcceptRole,
                )
                msg.addButton(
                    t("report.draft_discard_btn", "Discard Draft"),
                    QMessageBox.ButtonRole.RejectRole,
                )
                msg.setDefaultButton(btn_restore)
                msg.exec()

                if msg.clickedButton() is btn_restore:
                    content = draft_text
                    self.editor.blockSignals(True)
                    self.editor.setPlainText(content)
                    self.editor.blockSignals(False)
                    self._set_dirty(True)
                    self._update_preview()
                    self._update_status_label()
                    return
                else:
                    discard_draft(proj_dir)

        # setPlainText löst textChanged aus -> _dirty würde faelschlich True
        # werden, deshalb Signal kurz blocken.
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)
        self._set_dirty(False)
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(content)
        if hasattr(self, "navigator"):
            self.navigator.load_document(
                self._workspace_doc,
                project_name=project_name,
                target_ip=self._get_target_ip(),
            )
        self._update_preview()
        self._update_status_label()

    # ------------------------------------------------------------------ #
    # Dirty-State
    # ------------------------------------------------------------------ #

    def is_dirty(self) -> bool:
        return self._dirty

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
        if self._syncing_scroll:
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

        raw_markdown = _strip_preview_pagebreaks(self.preview_document.toMarkdown())
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

    def _apply_view_mode(self, mode: ViewMode) -> None:
        """Applies visibility and splitter layout for the selected view mode."""
        for action_mode, action in self._view_actions.items():
            action.setChecked(action_mode == mode)
        if hasattr(self, "format_toolbar_widget"):
            if self.format_toolbar_widget.is_collapsed():
                self.format_toolbar_widget.setVisible(True)
                self.format_toolbar_widget.tools_container.setVisible(False)
            else:
                self.format_toolbar_widget.setVisible(mode != ViewMode.PREVIEW)
                self.format_toolbar_widget.tools_container.setVisible(mode != ViewMode.PREVIEW)
        if mode == ViewMode.WORKSPACE:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(True)
            self.center_stack.setVisible(True)
            self.preview_glass.setVisible(True)
            total_w = self.splitter.width() or 1000
            self.splitter.setSizes([260, (total_w - 260) // 2, (total_w - 260) // 2])
        elif mode == ViewMode.EDITOR:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(False)
            self.center_stack.setVisible(True)
            self.center_stack.setCurrentWidget(self.editor_glass)
            self.preview_glass.setVisible(False)
        elif mode == ViewMode.PREVIEW:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(False)
            self.center_stack.setVisible(False)
            self.preview_glass.setVisible(True)
        elif mode == ViewMode.SPLIT:
            if hasattr(self, "navigator_glass"):
                self.navigator_glass.setVisible(False)
            self.center_stack.setVisible(True)
            self.center_stack.setCurrentWidget(self.editor_glass)
            self.preview_glass.setVisible(True)
            total_w = self.splitter.width() or 800
            self.splitter.setSizes([0, total_w // 2, total_w // 2])
            self._sync_scroll_editor_to_preview()

    def _cycle_view_mode(self) -> None:
        """Cycles through EDITOR -> SPLIT -> WORKSPACE -> PREVIEW -> EDITOR."""
        modes = [ViewMode.EDITOR, ViewMode.SPLIT, ViewMode.WORKSPACE, ViewMode.PREVIEW]
        idx = modes.index(self._view_mode)
        self._set_view_mode(modes[(idx + 1) % len(modes)])

    def save(self) -> bool:
        if not self.current_project:
            return False

        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()

        ok = self.report_file_manager.save(
            self.editor.toPlainText(), project_name=self.current_project
        )
        if ok:
            self._set_dirty(False)
            proj_dir = self.report_file_manager.project_manager.get_project_dir(
                self.current_project
            )
            discard_draft(proj_dir)
            if self._draft_timer.isActive():
                self._draft_timer.stop()
        else:
            show_error_dialog(
                self.window() if self else None,
                t("dialog.error", "Error"),
                t("report.save_error", "The report could not be saved. Details are in the log.")
            )
        return ok

    def _autosave(self) -> None:
        """Persist a dirty report without interrupting the user on failures."""
        if not self.is_dirty() or not self.current_project:
            return
        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()
        try:
            ok = self.report_file_manager.save(
                self.editor.toPlainText(), project_name=self.current_project
            )
        except Exception:
            logger.exception("Autosave failed for report '%s'", self.current_project)
            self.lbl_status.setText(
                t("report.autosave_failed", "Autosave failed — please save manually")
            )
            return
        if ok:
            self._set_dirty(False)
        else:
            logger.error("Autosave failed for report '%s'", self.current_project)
            self.lbl_status.setText(
                t("report.autosave_failed", "Autosave failed — please save manually")
            )

    def closeEvent(self, event) -> None:
        self._autosave_timer.stop()
        super().closeEvent(event)

    def _on_regenerate_clicked(self) -> None:
        """Commit and save user Markdown before destructive regeneration.

        Confirmation follows that save so the backup captures the latest work; unlike
        additive sync, successful regeneration replaces the complete report structure.
        """
        if not self.current_project:
            return

        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()

        if self._dirty:
            if not self.save():
                logger.error(
                    "Could not save pending report edits before regenerate for project '%s'",
                    self.current_project,
                )
                return

        has_existing = self.report_file_manager.exists(self.current_project)
        current_content = self.editor.toPlainText().strip()
        if has_existing and current_content:
            confirmation = ReportRegenerationConfirmDialog(parent=self)
            if confirmation.exec() != QDialog.DialogCode.Accepted:
                return

        dialog = ReportGenerationDialog(
            template_repo=self.template_repo,
            selected_template=self.active_template,
            has_existing_report=has_existing,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected_template is None:
            return
        self.active_template = dialog.selected_template

        from core.reporting import ReportBackupError, ReportSaveError

        try:
            new_content = self.report_file_manager.regenerate(
                self.loot_manager,
                self.clipboard_history,
                project_name=self.current_project,
                template=self.active_template,
            )
            self.editor.blockSignals(True)
            self.editor.setPlainText(new_content)
            self.editor.blockSignals(False)
            self._set_dirty(False)
            self._update_preview()
        except ReportBackupError as e:
            logger.error(f"Regenerierung abgebrochen wegen Backup-Fehler: {e}")
            show_error_dialog(
                self.window() if self else None,
                t("report.backup_failed_title", "Backup fehlgeschlagen"),
                t(
                    "report.backup_failed_msg",
                    "Das automatische Backup des bisherigen Reports ist fehlgeschlagen.\n\n"
                    "Zum Schutz deiner bestehenden Notizen wurde die Regenerierung abgebrochen.",
                ),
                details=str(e),
            )
        except ReportSaveError as e:
            logger.error(f"Regenerierung: Speichern fehlgeschlagen: {e}")
            show_error_dialog(
                self.window() if self else None,
                t("report.save_failed_title", "Speichern fehlgeschlagen"),
                t(
                    "report.save_failed_msg",
                    "Der neu generierte Report konnte nicht auf die Festplatte geschrieben werden.\n\n"
                    "Der bisherige Report bleibt erhalten.",
                ),
                details=str(e),
            )

    def _on_append_loot_clicked(self) -> None:
        """Appends unreferenced loot entries to existing report sections without rewriting user text."""
        if not self.current_project:
            return

        if self._view_mode == ViewMode.PREVIEW:
            self._commit_preview_to_markdown()

        # Ensure dirty changes are saved before performing additive sync
        if self._dirty:
            if not self.save():
                logger.error(
                    "Could not save pending report edits before appending loot for project '%s'",
                    self.current_project,
                )
                return

        from core.reporting import ReportBackupError, ReportSaveError

        cursor = self.editor.textCursor()
        saved_pos = cursor.position()

        try:
            result = self.report_file_manager.append_missing_loot(
                self.loot_manager,
                project_name=self.current_project,
                template=self.active_template,
            )
        except ReportBackupError as exc:
            logger.error("Append missing loot aborted due to backup error: %s", exc)
            show_error_dialog(
                self.window() if self else None,
                t("dialog.error", "Error"),
                t(
                    "report.append_backup_failed_msg",
                    "Das automatische Backup des bisherigen Reports ist fehlgeschlagen.\n\n"
                    "Zum Schutz deiner bestehenden Notizen wurde das Ergänzen abgebrochen.",
                ),
                details=str(exc),
            )
            return
        except ReportSaveError as exc:
            logger.error("Append missing loot: save failed: %s", exc)
            show_error_dialog(
                self.window() if self else None,
                t("dialog.error", "Error"),
                t(
                    "report.append_save_failed_msg",
                    "Der ergänzte Report konnte nicht auf die Festplatte geschrieben werden.\n\n"
                    "Der bisherige Report bleibt erhalten.",
                ),
                details=str(exc),
            )
            return

        if result.added_count == 0:
            self.lbl_status.setText(
                t("report.append_loot_no_changes", "No missing loot entries found")
            )
            return

        self.editor.blockSignals(True)
        self.editor.setPlainText(result.content)
        self.editor.blockSignals(False)
        self._set_dirty(False)
        self._update_preview()

        # Restore cursor position within bounds
        new_cursor = self.editor.textCursor()
        new_cursor.setPosition(min(saved_pos, len(result.content)))
        self.editor.setTextCursor(new_cursor)

        if result.used_fallback:
            self.lbl_status.setText(
                t(
                    "report.append_loot_success_fallback",
                    "{count} entries appended · {fallback_count} category(ies) under 'New Loot Entries'",
                    count=result.added_count,
                    fallback_count=len(result.fallback_categories),
                )
            )
        else:
            self.lbl_status.setText(
                t(
                    "report.append_loot_success",
                    "{count} new loot entries appended",
                    count=result.added_count,
                )
            )

    def _ensure_active_template(self) -> None:
        """Keeps the most recently selected template available for the next dialog."""
        templates = self.template_repo.get_all_templates()
        if self.active_template is None and templates:
            self.active_template = templates[0]




    # ------------------------------------------------------------------ #
    # Vorschau & Status
    # ------------------------------------------------------------------ #

    def _update_preview(self) -> None:
        if self.current_project:
            proj_dir = self.report_file_manager.project_manager.get_project_dir(
                self.current_project
            )
            self.preview_document.set_project_dir(proj_dir)
        self.preview.setMarkdown(_markdown_with_preview_pagebreaks(self.editor.toPlainText()))
        self._decorate_preview_pagebreaks()
        self._sync_scroll_editor_to_preview()

    def _decorate_preview_pagebreaks(self) -> None:
        cursor = self.preview_document.find(PREVIEW_PAGEBREAK_TOKEN)
        while not cursor.isNull():
            char_format = QTextCharFormat()
            char_format.setForeground(QColor("#57606a" if self._light_report_view else "#8b949e"))
            char_format.setFontWeight(QFont.Weight.DemiBold)
            cursor.insertText(PREVIEW_PAGEBREAK_LABEL, char_format)
            block_format = cursor.blockFormat()
            block_format.setAlignment(Qt.AlignmentFlag.AlignCenter)
            block_format.setTopMargin(3)
            block_format.setBottomMargin(3)
            cursor.setBlockFormat(block_format)
            cursor = self.preview_document.find(PREVIEW_PAGEBREAK_TOKEN, cursor)
        for size, token in PREVIEW_SPACER_TOKENS.items():
            cursor = self.preview_document.find(token)
            while not cursor.isNull():
                char_format = QTextCharFormat()
                char_format.setForeground(
                    QColor("#6e7781" if self._light_report_view else "#6e7681")
                )
                cursor.insertText(PREVIEW_SPACER_LABELS[size], char_format)
                block_format = cursor.blockFormat()
                block_format.setAlignment(Qt.AlignmentFlag.AlignCenter)
                margin = {"small": 3, "medium": 7, "large": 14}[size]
                block_format.setTopMargin(margin)
                block_format.setBottomMargin(margin)
                cursor.setBlockFormat(block_format)
                cursor = self.preview_document.find(token, cursor)

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
        """Synchronizes preview scrollbar proportionally when editor scrolls in Split mode."""
        if self._syncing_scroll or self._view_mode != ViewMode.SPLIT:
            return
        ed_bar = self.editor.verticalScrollBar()
        pr_bar = self.preview.verticalScrollBar()
        ed_max = ed_bar.maximum()
        pr_max = pr_bar.maximum()
        if ed_max <= 0 or pr_max <= 0:
            return
        ratio = value / ed_max
        self._syncing_scroll = True
        try:
            pr_bar.setValue(int(ratio * pr_max))
        finally:
            self._syncing_scroll = False

    def _on_preview_scroll(self, value: int) -> None:
        """Synchronizes editor scrollbar proportionally when preview scrolls in Split mode."""
        if self._syncing_scroll or self._view_mode != ViewMode.SPLIT:
            return
        ed_bar = self.editor.verticalScrollBar()
        pr_bar = self.preview.verticalScrollBar()
        ed_max = ed_bar.maximum()
        pr_max = pr_bar.maximum()
        if ed_max <= 0 or pr_max <= 0:
            return
        ratio = value / pr_max
        self._syncing_scroll = True
        try:
            ed_bar.setValue(int(ratio * ed_max))
        finally:
            self._syncing_scroll = False

    def _sync_scroll_editor_to_preview(self) -> None:
        """Aligns preview scroll position to editor position (e.g. after mode switch or reload)."""
        if self._view_mode != ViewMode.SPLIT:
            return
        ed_bar = self.editor.verticalScrollBar()
        pr_bar = self.preview.verticalScrollBar()
        ed_max = ed_bar.maximum()
        pr_max = pr_bar.maximum()
        if ed_max <= 0 or pr_max <= 0:
            return
        ratio = ed_bar.value() / ed_max
        self._syncing_scroll = True
        try:
            pr_bar.setValue(int(ratio * pr_max))
        finally:
            self._syncing_scroll = False

    # ------------------------------------------------------------------ #
    # Semantische Sprung-Navigation
    # ------------------------------------------------------------------ #

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
        proj_dir = self.report_file_manager.project_manager.get_project_dir(
            self.current_project
        )
        save_draft(proj_dir, self.editor.toPlainText())

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

    def _sync_markdown_to_workspace(self) -> None:
        """Parses current editor markdown into workspace document and refreshes navigator."""
        if getattr(self, "_syncing_from_inspector", False):
            return
        content = self.editor.toPlainText()
        self._workspace_doc = ReportWorkspaceDocument.from_markdown(content)
        if hasattr(self, "navigator"):
            self.navigator.load_document(
                self._workspace_doc,
                project_name=self.current_project or "",
                target_ip=self._get_target_ip(),
            )

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
        self._update_preview()

    def _on_navigate_requested(self, view_type: str, item_id: Optional[str]) -> None:
        """Switches the center inspector stack to the requested document section or finding."""
        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())

        if view_type == "metadata":
            self.metadata_inspector.load_metadata(self._workspace_doc.metadata)
            self.center_stack.setCurrentWidget(self.metadata_inspector_glass)
        elif view_type == "finding" and item_id:
            finding = self._workspace_doc.get_finding(item_id)
            if finding:
                self.finding_inspector.load_finding(finding)
                self.center_stack.setCurrentWidget(self.finding_inspector_glass)
        elif view_type == "findings_overview":
            if self._workspace_doc.findings:
                first = self._workspace_doc.findings[0]
                self.finding_inspector.load_finding(first)
                self.center_stack.setCurrentWidget(self.finding_inspector_glass)
            else:
                self.center_stack.setCurrentWidget(self.editor_glass)
        elif view_type == "section" and item_id:
            narr = next(
                (n for n in self._workspace_doc.narratives if n.identity == item_id or n.section_type == item_id),
                None,
            )
            title = narr.title if narr else item_id
            content = narr.content if narr else ""
            icon_map = {
                "executive_summary": "fa5s.align-left",
                "scope_limitations": "fa5s.bullseye",
                "attack_path": "fa5s.route",
                "remediation_table": "fa5s.tasks",
                "appendix": "fa5s.paperclip",
            }
            sec_icon = icon_map.get(item_id, "fa5s.edit")
            self.section_inspector.load_section(item_id, title, content, icon_name=sec_icon)
            self.center_stack.setCurrentWidget(self.section_inspector_glass)
        elif view_type == "raw_markdown":
            self.center_stack.setCurrentWidget(self.editor_glass)

    def _on_add_finding_requested(self) -> None:
        """Creates a new finding in the workspace model and opens the finding inspector."""
        import uuid

        if self._workspace_doc is None:
            self._workspace_doc = ReportWorkspaceDocument.from_markdown(self.editor.toPlainText())

        new_id = f"finding-{uuid.uuid4().hex[:6]}"
        new_finding = ReportFindingItem(
            id=new_id,
            title=t("report.new_finding_default_title", "Neue Schwachstelle"),
            severity="medium",
            status="open",
            phase="recon",
            description="",
            recommendation="",
        )
        self._workspace_doc.add_finding(new_finding)
        self._sync_workspace_doc_to_editor()
        self.navigator.load_document(
            self._workspace_doc,
            project_name=self.current_project or "",
            target_ip=self._get_target_ip(),
        )
        self.navigator.select_item("finding", new_id)
        self.finding_inspector.load_finding(new_finding)
        self.center_stack.setCurrentWidget(self.finding_inspector_glass)

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

    def _on_finding_deleted(self, finding_id: str) -> None:
        if self._workspace_doc is None:
            return
        self._workspace_doc.remove_finding(finding_id)
        self._sync_workspace_doc_to_editor()
        self.navigator.load_document(
            self._workspace_doc,
            project_name=self.current_project or "",
            target_ip=self._get_target_ip(),
        )
        self.center_stack.setCurrentWidget(self.editor_glass)

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
        self.navigator.load_document(
            self._workspace_doc,
            project_name=self.current_project or "",
            target_ip=self._get_target_ip(),
        )
        self.navigator.select_item("finding", new_id)
        self.finding_inspector.load_finding(dup)
        self.center_stack.setCurrentWidget(self.finding_inspector_glass)

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
