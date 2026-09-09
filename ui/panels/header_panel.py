from typing import Optional
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget, QMenu
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QPoint
from PyQt6.QtGui import QResizeEvent
from core.i18n import t
from ui.styles.icons import icon


class HeaderPanel(QFrame):
    """
    Top HUD navigation and control bar.
    Contains Brand logo, Project/Box selector, Mode Switcher Tabs (Cheatsheet, Loot, History, Report),
    Snip trigger, Clipboard REC indicator, Settings/Options, Minimize, and Close button.
    """

    project_menu_requested = pyqtSignal(QPushButton)
    phase_menu_requested = pyqtSignal(QPushButton)
    mode_changed = pyqtSignal(str)
    screenshot_requested = pyqtSignal()
    quick_note_requested = pyqtSignal()
    toggle_rec_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    minimize_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.active_mode = "cheatsheet"
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 10, 6)
        layout.setSpacing(8)

        # Brand Title
        self.lbl_brand = QLabel("SPECTRE // HUD")
        self.lbl_brand.setTextFormat(Qt.TextFormat.PlainText)
        self.lbl_brand.setStyleSheet(
            "color: #00e5ff; font-size: 13px; font-weight: 800; letter-spacing: 0.5px; margin-right: 4px;"
        )
        layout.addWidget(self.lbl_brand)

        # Project / Box Selection Dropdown Trigger
        self.btn_project = QPushButton("Box: Default ▾")
        self.btn_project.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_project.setProperty("class", "ProjectSelectBtn")
        self.btn_project.setToolTip(
            t("header.project_tip", "Aktive CTF-Box auswählen oder neues Projekt anlegen")
        )
        self.btn_project.clicked.connect(lambda: self.project_menu_requested.emit(self.btn_project))
        layout.addWidget(self.btn_project)

        self.btn_phase: Optional[QPushButton] = None
        layout.addSpacing(4)

        # Mode Switcher Tabs
        self.btn_mode_cheatsheet = QPushButton(t("header.mode_cheatsheet", "Cheatsheet"))
        self.btn_mode_cheatsheet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_cheatsheet.setProperty("class", "ModeSwitchBtnActive")
        self.btn_mode_cheatsheet.setToolTip(
            t("header.cheatsheet_tip", "Browse reusable commands; current variables are filled when you copy")
        )
        self.btn_mode_cheatsheet.clicked.connect(lambda: self.mode_changed.emit("cheatsheet"))
        layout.addWidget(self.btn_mode_cheatsheet)

        self.btn_mode_history = QPushButton(t("header.mode_history", "History"))
        self.btn_mode_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_history.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_history.setToolTip(
            t("header.history_tip", "Review commands and output captured while clipboard REC is active")
        )
        self.btn_mode_history.clicked.connect(lambda: self.mode_changed.emit("history"))
        layout.addWidget(self.btn_mode_history)

        self.btn_mode_notes = QPushButton(t("header.mode_notes", "Notes"))
        self.btn_mode_notes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_notes.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_notes.setToolTip(
            t("header.notes_tip", "Open the Quick Notes capture and triage inbox")
        )
        self.btn_mode_notes.clicked.connect(lambda: self.mode_changed.emit("notes"))
        layout.addWidget(self.btn_mode_notes)

        self.btn_mode_loot = QPushButton(t("header.mode_loot", "Loot"))
        self.btn_mode_loot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_loot.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_loot.setToolTip(
            t("header.loot_tip", "Manage structured evidence and findings used by reports")
        )
        self.btn_mode_loot.clicked.connect(lambda: self.mode_changed.emit("loot"))
        layout.addWidget(self.btn_mode_loot)

        self.btn_mode_report = QPushButton(t("header.mode_report", "Report"))
        self.btn_mode_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mode_report.setProperty("class", "ModeSwitchBtn")
        self.btn_mode_report.setToolTip(
            t(
                "header.report_tip",
                "Open the editable report for the active project (Ctrl+5)",
            )
        )
        self.btn_mode_report.clicked.connect(lambda: self.mode_changed.emit("report"))
        layout.addWidget(self.btn_mode_report)

        # Navigation / Actions Separator
        self.nav_separator = QFrame()
        self.nav_separator.setFrameShape(QFrame.Shape.VLine)
        self.nav_separator.setProperty("class", "HeaderDivider")
        layout.addWidget(self.nav_separator)

        layout.addStretch()

        # Quick Note Button
        self.btn_quick_note = QPushButton(t("header.note", "Note"))
        self.btn_quick_note.setProperty("class", "ProjectSelectBtn")
        self.btn_quick_note.setIcon(icon("fa5s.pen"))
        self.btn_quick_note.setIconSize(QSize(13, 13))
        self.btn_quick_note.setToolTip(
            t("header.note_tip", "Capture a thought in the Quick Notes inbox (Ctrl+Alt+N)")
        )
        self.btn_quick_note.clicked.connect(self.quick_note_requested.emit)
        layout.addWidget(self.btn_quick_note)

        # Screenshot Snip Button
        self.btn_screenshot = QPushButton(t("header.snip", "Snip"))
        self.btn_screenshot.setProperty("class", "ProjectSelectBtn")
        self.btn_screenshot.setIcon(icon("fa5s.crop-alt"))
        self.btn_screenshot.setIconSize(QSize(13, 13))
        self.btn_screenshot.setToolTip(
            t("header.snip_tip", "Capture a region screenshot directly as Loot (Ctrl+Alt+X)")
        )
        self.btn_screenshot.clicked.connect(self.screenshot_requested.emit)
        layout.addWidget(self.btn_screenshot)

        # Clipboard Recording Indicator Button
        self.btn_rec_indicator = QPushButton("REC: Off")
        self.btn_rec_indicator.setObjectName("RecIndicatorBtn")
        self.btn_rec_indicator.setProperty("paused", "true")
        self.btn_rec_indicator.setIcon(icon("fa5s.circle", color="#8b949e", color_active="#8b949e"))
        self.btn_rec_indicator.setIconSize(QSize(10, 10))
        self.btn_rec_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rec_indicator.setToolTip(
            t(
                "header.rec_tooltip_paused",
                "Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+Alt+R zum Starten der Aufzeichnung.",
            )
        )
        self.btn_rec_indicator.clicked.connect(self.toggle_rec_requested.emit)
        layout.addWidget(self.btn_rec_indicator)

        # Action Overflow Button (shown when space is constrained)
        self.btn_overflow = QPushButton()
        self.btn_overflow.setObjectName("HeaderOverflowBtn")
        self.btn_overflow.setProperty("class", "ProjectSelectBtn")
        self.btn_overflow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_overflow.setIcon(icon("fa5s.ellipsis-h"))
        self.btn_overflow.setIconSize(QSize(13, 13))
        self.btn_overflow.setToolTip(
            t("header.overflow_tip", "Weitere Aktionen (Quick Note, Snip, REC)")
        )
        self.btn_overflow.clicked.connect(self._show_overflow_menu)
        self.btn_overflow.setVisible(False)
        layout.addWidget(self.btn_overflow)

        # Settings & Hotkeys Button
        self.btn_settings = QPushButton(t("header.opt", ""))
        self.btn_settings.setProperty("class", "ProjectSelectBtn")
        self.btn_settings.setIcon(icon("fa5s.cog"))
        self.btn_settings.setIconSize(QSize(14, 14))
        self.btn_settings.setToolTip(
            t("header.opt_tip", "Einstellungen & Optionen öffnen (Ctrl+,)")
        )
        self.btn_settings.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.btn_settings)

        # Minimize button in HUD header
        self.btn_minimize = QPushButton("🗕")
        self.btn_minimize.setProperty("class", "MinimizeBtn")
        self.btn_minimize.setToolTip(
            t("header.minimize_tip", "Overlay minimieren / verstecken (Esc)")
        )
        self.btn_minimize.clicked.connect(self.minimize_requested.emit)
        layout.addWidget(self.btn_minimize)

        # Close button: quits via the transactional shutdown path (save first)
        self.btn_close = QPushButton("✕")
        self.btn_close.setProperty("class", "CloseBtn")
        self.btn_close.setToolTip(
            t(
                "header.quit_tip",
                "SpectreHUD beenden – speichert zuerst das aktive Projekt (Ctrl+Q)",
            )
        )
        self.btn_close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.btn_close)

        self.update_overflow_state()

    def _calculate_visible_action_count(self, width: int) -> int:
        """
        Determines how many action buttons (0..3) fit into the header without clipping,
        analogous to category pills overflow calculation.
        Order of priority / layout from left to right:
        1. Quick Note
        2. Screenshot Snip
        3. REC Indicator
        """
        fixed_items = [
            self.lbl_brand,
            self.btn_project,
            self.btn_mode_cheatsheet,
            self.btn_mode_history,
            self.btn_mode_notes,
            self.btn_mode_loot,
            self.btn_mode_report,
            self.nav_separator,
            self.btn_settings,
            self.btn_minimize,
            self.btn_close,
        ]
        if self.btn_phase is not None:
            fixed_items.append(self.btn_phase)

        fixed_w = sum(w.sizeHint().width() for w in fixed_items)
        action_items = [self.btn_quick_note, self.btn_screenshot, self.btn_rec_indicator]
        action_widths = [w.sizeHint().width() for w in action_items]
        overflow_w = self.btn_overflow.sizeHint().width() if hasattr(self, "btn_overflow") else 32

        layout = self.layout()
        if layout is not None:
            margins = layout.contentsMargins()
            margin_w = margins.left() + margins.right()
            spacing = layout.spacing()
        else:
            margin_w = 22
            spacing = 8

        buffer = 12
        num_fixed = len(fixed_items)

        # 1. Check if all 3 action items fit directly without overflow button
        total_items_3 = num_fixed + 3
        gaps_3 = max(0, total_items_3 - 1)
        w3 = fixed_w + sum(action_widths) + margin_w + (gaps_3 * spacing) + buffer
        if width >= w3:
            return 3

        # 2. Check largest k in [2, 1] that fits with overflow button
        for k in (2, 1):
            total_items_k = num_fixed + k + 1
            gaps_k = max(0, total_items_k - 1)
            wk = fixed_w + sum(action_widths[:k]) + overflow_w + margin_w + (gaps_k * spacing) + buffer
            if width >= wk:
                return k

        return 0

    def update_overflow_state(self, width: Optional[int] = None) -> None:
        """Shows or hides action buttons progressively based on available horizontal space."""
        if width is None:
            width = self.width()

        if width <= 0:
            return

        visible_count = self._calculate_visible_action_count(width)

        action_items = [self.btn_quick_note, self.btn_screenshot, self.btn_rec_indicator]
        for idx, btn in enumerate(action_items):
            btn.setVisible(idx < visible_count)

        self.btn_overflow.setVisible(visible_count < 3)
        self._update_overflow_indicator()

    def _update_overflow_indicator(self) -> None:
        """Updates overflow button appearance according to active state of hidden actions."""
        if not hasattr(self, "btn_overflow"):
            return
        is_active = getattr(self, "_rec_active", False)
        rec_in_overflow = self.btn_rec_indicator.isHidden()
        if is_active and rec_in_overflow:
            self.btn_overflow.setIcon(icon("fa5s.ellipsis-h", color="#ef4444", color_active="#ef4444"))
            self.btn_overflow.setToolTip(
                t(
                    "header.overflow_tip_rec_active",
                    "Weitere Aktionen [REC AKTIV] (Quick Note, Snip, REC)",
                )
            )
        else:
            self.btn_overflow.setIcon(icon("fa5s.ellipsis-h"))
            self.btn_overflow.setToolTip(
                t("header.overflow_tip", "Weitere Aktionen (Quick Note, Snip, REC)")
            )

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_overflow_state(event.size().width())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.update_overflow_state(self.width())

    def _build_overflow_menu(self) -> QMenu:
        """Builds the popup menu containing only the action buttons that are currently hidden."""
        menu = QMenu(self)
        menu.setProperty("class", "SecondaryMenu")

        hide_note = self.btn_quick_note.isHidden()
        hide_snip = self.btn_screenshot.isHidden()
        hide_rec = self.btn_rec_indicator.isHidden()

        # If none are hidden (e.g. called programmatically in tests), show all
        if not (hide_note or hide_snip or hide_rec):
            hide_note = hide_snip = hide_rec = True

        if hide_note:
            act_note = menu.addAction(
                icon("fa5s.pen"),
                t("header.quick_note_action", "Quick Note (Ctrl+Alt+N)"),
            )
            act_note.triggered.connect(self.quick_note_requested.emit)

        if hide_snip:
            act_snip = menu.addAction(
                icon("fa5s.crop-alt"),
                t("header.snip_action", "Snip (Ctrl+S)"),
            )
            act_snip.triggered.connect(self.screenshot_requested.emit)

        if hide_rec:
            if hide_note or hide_snip:
                menu.addSeparator()
            is_rec_active = getattr(self, "_rec_active", False)
            if is_rec_active:
                rec_text = t("header.rec_pause_action", "REC: ON (Pause)")
                rec_icon = icon("fa5s.circle", color="#ef4444", color_active="#ef4444")
            else:
                rec_text = t("header.rec_resume_action", "REC: Off (Start)")
                rec_icon = icon("fa5s.circle", color="#8b949e", color_active="#8b949e")
            act_rec = menu.addAction(rec_icon, rec_text)
            act_rec.triggered.connect(self.toggle_rec_requested.emit)

        return menu

    def _show_overflow_menu(self) -> None:
        """Displays the action overflow menu anchored to the overflow button."""
        menu = self._build_overflow_menu()
        pos = self.btn_overflow.mapToGlobal(QPoint(0, self.btn_overflow.height() + 2))
        menu.exec(pos)

    def set_active_mode(self, mode: str) -> None:
        """Updates visual active tab styling for the selected mode."""
        self.active_mode = mode
        self.btn_mode_cheatsheet.setProperty(
            "class", "ModeSwitchBtnActive" if mode == "cheatsheet" else "ModeSwitchBtn"
        )
        self.btn_mode_history.setProperty(
            "class", "ModeSwitchBtnActive" if mode == "history" else "ModeSwitchBtn"
        )
        self.btn_mode_notes.setProperty(
            "class", "ModeSwitchBtnActive" if mode == "notes" else "ModeSwitchBtn"
        )
        self.btn_mode_loot.setProperty(
            "class", "ModeSwitchBtnActive" if mode == "loot" else "ModeSwitchBtn"
        )
        self.btn_mode_report.setProperty(
            "class", "ModeSwitchBtnActive" if mode == "report" else "ModeSwitchBtn"
        )

        for btn in [
            self.btn_mode_cheatsheet,
            self.btn_mode_history,
            self.btn_mode_notes,
            self.btn_mode_loot,
            self.btn_mode_report,
        ]:
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_project_title(self, project_name: str) -> None:
        """Updates the project dropdown button text."""
        self.btn_project.setText(f"Box: {project_name} ▾")

    def set_phase(self, phase_key: Optional[str]) -> None:
        """Updates the phase dropdown button text."""
        self._current_phase_key = phase_key
        if self.btn_phase:
            if not phase_key:
                self.btn_phase.setText(t("header.phase_unassigned", "Phase: Unassigned ▾"))
            else:
                from core.phases import get_phase
                phase = get_phase(phase_key)
                self.btn_phase.setText(f"{phase.short} ▾")

    def update_rec_indicator(self, is_active: bool) -> None:
        """Updates the visual indicator for clipboard history recording state."""
        self._rec_active = is_active
        if is_active:
            self.btn_rec_indicator.setText("REC: ON")
            self.btn_rec_indicator.setIcon(icon("fa5s.circle", color="#ef4444", color_active="#ef4444"))
            self.btn_rec_indicator.setProperty("paused", "false")
            self.btn_rec_indicator.setToolTip(
                t(
                    "header.rec_tooltip_active",
                    "Clipboard-Logger ist AKTIV (Aufzeichnung läuft).\nKlicken oder Ctrl+Alt+R zum Pausieren.",
                )
            )
        else:
            self.btn_rec_indicator.setText("REC: Off")
            self.btn_rec_indicator.setIcon(icon("fa5s.circle", color="#8b949e", color_active="#8b949e"))
            self.btn_rec_indicator.setProperty("paused", "true")
            self.btn_rec_indicator.setToolTip(
                t(
                    "header.rec_tooltip_paused",
                    "Clipboard-Logger ist PAUSIERT (keine Aufzeichnung).\nKlicken oder Ctrl+Alt+R zum Starten der Aufzeichnung.",
                )
            )
        self.btn_rec_indicator.style().unpolish(self.btn_rec_indicator)
        self.btn_rec_indicator.style().polish(self.btn_rec_indicator)
        self._update_overflow_indicator()

    def update_notes_badge(self, count: int = 0) -> None:
        """Notes tab label without count badge, keeping clean title."""
        self.btn_mode_notes.setText(t("header.mode_notes", "Notes"))

    def update_history_badge(self, notes_count: int = 0) -> None:
        """Kept for backward compatibility."""
        base_text = t("header.mode_history", "History")
        if notes_count > 0:
            self.btn_mode_history.setText(f"{base_text} [{notes_count}]")
        else:
            self.btn_mode_history.setText(base_text)

    def retranslate(self) -> None:
        """Dynamically re-translates all texts on language changes."""
        self.btn_mode_cheatsheet.setText(t("header.mode_cheatsheet", "Cheatsheet"))
        self.btn_mode_history.setText(t("header.mode_history", "History"))
        self.btn_mode_notes.setText(t("header.mode_notes", "Notes"))
        self.btn_mode_loot.setText(t("header.mode_loot", "Loot"))
        self.btn_mode_report.setText(t("header.mode_report", "Report"))
        self.btn_mode_cheatsheet.setToolTip(
            t("header.cheatsheet_tip", "Browse reusable commands; current variables are filled when you copy")
        )
        self.btn_mode_history.setToolTip(
            t("header.history_tip", "Review commands and output captured while clipboard REC is active")
        )
        self.btn_mode_notes.setToolTip(
            t("header.notes_tip", "Open the Quick Notes capture and triage inbox")
        )
        self.btn_mode_loot.setToolTip(
            t("header.loot_tip", "Manage structured evidence and findings used by reports")
        )
        self.btn_mode_report.setToolTip(
            t(
                "header.report_tip",
                "Open the editable report for the active project (Ctrl+5)",
            )
        )
        self.btn_quick_note.setText(t("header.note", "Note"))
        self.btn_quick_note.setToolTip(
            t("header.note_tip", "Capture a thought in the Quick Notes inbox (Ctrl+Alt+N)")
        )
        self.btn_screenshot.setText(t("header.snip", "Snip"))
        self.btn_screenshot.setToolTip(
            t("header.snip_tip", "Capture a region screenshot directly as Loot (Ctrl+Alt+X)")
        )
        self.btn_settings.setText(t("header.opt", ""))
        self.btn_settings.setToolTip(
            t("header.opt_tip", "Einstellungen & Optionen öffnen (Ctrl+,)")
        )
        self.btn_minimize.setToolTip(
            t("header.minimize_tip", "Overlay minimieren / verstecken (Esc)")
        )
        self.btn_close.setToolTip(
            t(
                "header.quit_tip",
                "SpectreHUD beenden – speichert zuerst das aktive Projekt (Ctrl+Q)",
            )
        )
        self.btn_project.setToolTip(t("header.project_tip", "Switch active project or engagement"))
        if self.btn_phase:
            self.btn_phase.setToolTip(
                t("header.phase_tip", "Set the phase assigned to new captures (Ctrl+Alt+1..6)")
            )
            self.set_phase(getattr(self, "_current_phase_key", None))
        is_active = getattr(self, "_rec_active", False)
        self.update_rec_indicator(is_active)
