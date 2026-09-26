from datetime import datetime
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QFrame,
    QWidget,
)
from PyQt6.QtCore import QLocale, Qt
from PyQt6.QtGui import QColor, QDoubleValidator
from typing import Dict, Any, Optional, Callable, Sequence
from core.loot import (
    CATEGORIES,
    LOOT_TYPES,
    normalize_cvss_score,
    normalize_finding_references,
    normalize_finding_status,
    normalize_finding_targets,
)
from core.i18n import t
from core.export_plugins import ExportPluginMetadata
from ui.message_boxes import show_warning_dialog
from ui.plugin_text import plugin_text
from ui.base_dialog import BaseHudDialog
from ui.styles.icons import get_severity_color, get_theme_color, icon
from ui.styles.theme import rgba_str


class AddLootDialog(BaseHudDialog):
    """Dialog to capture new or edit existing session loot (credentials, hashes, flags, notes, PoCs)."""

    _details_expanded: bool = False
    _cached_draft: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        target_ip: str = "",
        current_target_ip: str = "",
        default_type: str = "note",
        initial_type: str = "note",
        entry_type: str = "note",
        default_category: str = "misc",
        initial_category: str = "misc",
        category: str = "misc",
        default_title: str = "",
        initial_title: str = "",
        title: str = "",
        default_content: str = "",
        initial_content: str = "",
        content: str = "",
        default_recommendation: str = "",
        initial_recommendation: str = "",
        recommendation: str = "",
        default_report_role: str = "evidence",
        default_targets: Optional[list[str]] = None,
        default_cvss_score: Any = None,
        default_cvss_vector: str = "",
        default_finding_status: str = "open",
        default_references: Optional[list[str]] = None,
        entry_id: Optional[str] = None,
        is_edit: bool = False,
        on_export_file: Optional[Callable[[str], None]] = None,
        loot_append_plugins: Sequence[ExportPluginMetadata] = (),
        on_export_plugin: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ):
        self.entry_id = entry_id or kwargs.get("id")
        self.is_edit = is_edit or bool(self.entry_id)
        self.on_export_file = on_export_file
        self.loot_append_plugins = tuple(loot_append_plugins)
        self.on_export_plugin = on_export_plugin
        dialog_title = t(
            "loot_dialog.title_edit" if self.is_edit else "loot_dialog.title_new",
            "SPECTRE // EDIT SESSION LOOT" if self.is_edit else "SPECTRE // CAPTURE SESSION LOOT",
        )

        self.current_target_ip = target_ip or current_target_ip or kwargs.get("target", "")
        self.initial_type = default_type or initial_type or entry_type or kwargs.get("type", "note")
        self.initial_category = (
            default_category or initial_category or category or kwargs.get("cat", "misc")
        )
        self.initial_severity = (
            kwargs.get("default_severity")
            or kwargs.get("initial_severity")
            or kwargs.get("severity")
            or "info"
        )
        self.initial_title = default_title or initial_title or title or kwargs.get("name", "")
        self.initial_content = (
            default_content or initial_content or content or kwargs.get("text", "")
        )
        self.initial_recommendation = (
            default_recommendation
            or initial_recommendation
            or recommendation
            or kwargs.get("remediation", "")
        )
        self.initial_report_role = str(kwargs.get("report_role", default_report_role) or "evidence")
        self.initial_targets = normalize_finding_targets(
            kwargs.get("targets", default_targets),
            fallback_target=self.current_target_ip,
        )
        self.initial_cvss_score = normalize_cvss_score(kwargs.get("cvss_score", default_cvss_score))
        self.initial_cvss_vector = str(kwargs.get("cvss_vector", default_cvss_vector) or "").strip()
        self.initial_finding_status = normalize_finding_status(
            kwargs.get("finding_status", default_finding_status)
        )
        self.initial_references = normalize_finding_references(
            kwargs.get("references", default_references)
        )

        has_existing_details = bool(
            (self.initial_severity and self.initial_severity.lower() != "info")
            or bool(self.initial_recommendation)
            or bool(
                self.initial_targets
                and self.initial_targets
                != ([self.current_target_ip] if self.current_target_ip else [])
            )
            or self.initial_cvss_score is not None
            or bool(self.initial_cvss_vector)
            or bool(self.initial_references)
            or self.initial_report_role in {"finding", "legacy"}
        )
        self._is_details_expanded = has_existing_details or AddLootDialog._details_expanded

        self._draft_loaded = False
        self._draft_time = ""
        if (
            not self.is_edit
            and not self.initial_title
            and not self.initial_content
            and AddLootDialog._cached_draft
        ):
            draft = AddLootDialog._cached_draft
            self.initial_title = draft.get("title", "")
            self.initial_content = draft.get("content", "")
            if draft.get("type"):
                self.initial_type = draft["type"]
            if draft.get("category"):
                self.initial_category = draft["category"]
            if draft.get("target"):
                self.current_target_ip = draft["target"]
            self._draft_loaded = True
            self._draft_time = draft.get("time", "")

        super().__init__(title=dialog_title, parent=parent)
        self.setMinimumWidth(540)
        self.resize(560, 640 if self._is_details_expanded else 440)

        # When opened non-modally (Quick Loot), set to True after first activation
        # so clicking outside dismisses the window. Stays False in modal (exec()) mode.
        self._dismiss_on_deactivate = False
        self._has_been_active = False

        self._init_form()


    @property
    def dismiss_on_deactivate(self) -> bool:
        return self._dismiss_on_deactivate

    @dismiss_on_deactivate.setter
    def dismiss_on_deactivate(self, val: bool) -> None:
        self._dismiss_on_deactivate = val

    def changeEvent(self, event) -> None:
        """In non-modal mode: close when the window loses focus after having been active."""
        if (
            event is not None
            and event.type() == event.Type.ActivationChange
            and self._dismiss_on_deactivate
        ):
            if self.isActiveWindow():
                self._has_been_active = True
            elif self._has_been_active:
                self.close()
        super().changeEvent(event)

    def _init_form(self) -> None:
        layout = self.body_layout

        # Recovery Banner
        self.recovery_banner = QFrame(self)
        self.recovery_banner.setObjectName("QuickLootRecoveryBanner")
        self.recovery_banner.setStyleSheet(
            f"""
            QFrame#QuickLootRecoveryBanner {{
                background-color: {rgba_str(QColor(get_theme_color("BG_DARK")), 0.95)};
                border: 1px solid {rgba_str(QColor(get_theme_color("ACCENT_BRAND")), 0.5)};
                border-radius: 4px;
            }}
            """
        )
        rec_layout = QHBoxLayout(self.recovery_banner)
        rec_layout.setContentsMargins(8, 4, 8, 4)
        self.lbl_recovery = QLabel(self.recovery_banner)
        self.lbl_recovery.setStyleSheet(
            f"color: {get_theme_color('ACCENT_BRAND')}; font-size: 11px; font-weight: 600;"
        )
        rec_layout.addWidget(self.lbl_recovery)
        rec_layout.addStretch()
        self.btn_discard_draft = QPushButton(
            t("draft.discard", "Discard Draft"), self.recovery_banner
        )
        self.btn_discard_draft.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_discard_draft.setFixedHeight(22)
        self.btn_discard_draft.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                color: {get_theme_color('TEXT_MUTED')};
                border: 1px solid {get_theme_color('BORDER_MUTED')};
                border-radius: 3px;
                font-size: 10px;
                padding: 1px 8px;
            }}
            QPushButton:hover {{
                color: {get_theme_color('TEXT_PRIMARY')};
                border-color: {get_theme_color('BORDER_GLOW')};
            }}
            """
        )
        self.btn_discard_draft.clicked.connect(self._discard_draft)
        rec_layout.addWidget(self.btn_discard_draft)
        layout.addWidget(self.recovery_banner)

        if self._draft_loaded:
            self.lbl_recovery.setText(
                f"{t('draft.restored', 'Unsaved draft restored')} ({self._draft_time})"
            )
            self.recovery_banner.show()
        else:
            self.recovery_banner.hide()

        # 1. Type and Category Selection (Side by Side in primary section)
        select_row = QHBoxLayout()
        select_row.setSpacing(10)

        # 1a. Type
        type_col = QVBoxLayout()
        type_col.setSpacing(4)
        lbl_type = QLabel(t("loot_dialog.lbl_type", "Entry Type:"))
        lbl_type.setProperty("class", "FormLabel")
        type_col.addWidget(lbl_type)

        self.combo_type = QComboBox()
        for i, loot_type in enumerate(LOOT_TYPES):
            self.combo_type.addItem(loot_type["name"], loot_type["id"])
            if loot_type["id"] == self.initial_type:
                self.combo_type.setCurrentIndex(i)
        type_col.addWidget(self.combo_type)
        select_row.addLayout(type_col, stretch=1)

        # 1b. Pentest Category
        cat_col = QVBoxLayout()
        cat_col.setSpacing(4)
        lbl_cat = QLabel(t("loot_dialog.lbl_category", "Pentest Phase / Category:"))
        lbl_cat.setProperty("class", "FormLabel")
        cat_col.addWidget(lbl_cat)

        self.combo_category = QComboBox()
        for i, c in enumerate(sorted(CATEGORIES, key=lambda x: int(x.get("order", 0)))):
            self.combo_category.addItem(c["name"], c["id"])
            if c["id"] == self.initial_category:
                self.combo_category.setCurrentIndex(i)
        cat_col.addWidget(self.combo_category)
        select_row.addLayout(cat_col, stretch=1)

        layout.addLayout(select_row)

        # 2. Title
        lbl_title = QLabel(t("loot_dialog.lbl_name", "Title / Identifier:"))
        lbl_title.setProperty("class", "FormLabel")
        layout.addWidget(lbl_title)

        self.txt_title = QLineEdit(self.initial_title)
        self.txt_title.setPlaceholderText(
            t("loot_dialog.ph_name", "e.g. SSH Key user 'alice', MySQL Root Password, user.txt")
        )
        layout.addWidget(self.txt_title)

        # 3. Content / Value
        lbl_content = QLabel(
            t("loot_dialog.lbl_content", "Content / Password / Hash / Flag / Note:")
        )
        lbl_content.setProperty("class", "FormLabel")
        layout.addWidget(lbl_content)

        self.txt_content = QPlainTextEdit()
        self.txt_content.setObjectName("CommandBox")
        self.txt_content.setPlainText(self.initial_content)
        self.txt_content.setPlaceholderText(
            t("loot_dialog.ph_content", "e.g. admin:SuperSecretPass! or THM{fl4g_h3r3}")
        )
        self.txt_content.setFixedHeight(90)
        layout.addWidget(self.txt_content)

        # 4. Progressive Disclosure Toggle
        self.btn_toggle_details = QPushButton(self)
        self.btn_toggle_details.setObjectName("LootDetailsToggleBtn")
        self.btn_toggle_details.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_details.setStyleSheet(
            f"""
            QPushButton#LootDetailsToggleBtn {{
                background: transparent;
                color: {get_theme_color("ACCENT_BRAND")};
                border: none;
                text-align: left;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 0px;
            }}
            QPushButton#LootDetailsToggleBtn:hover {{
                color: {get_theme_color("CYAN_LIGHT", get_theme_color("ACCENT_BRAND"))};
            }}
            """
        )
        self.btn_toggle_details.clicked.connect(self._toggle_details)
        layout.addWidget(self.btn_toggle_details)

        # 5. Collapsible Details Container
        self.details_widget = QWidget(self)
        det_layout = QVBoxLayout(self.details_widget)
        det_layout.setContentsMargins(0, 2, 0, 2)
        det_layout.setSpacing(6)

        # Row: Severity & Associated Targets
        det_top_row = QHBoxLayout()
        det_top_row.setSpacing(10)

        # Severity
        sev_col = QVBoxLayout()
        sev_col.setSpacing(4)
        lbl_sev = QLabel(t("loot_dialog.lbl_severity", "Severity:"))
        lbl_sev.setProperty("class", "FormLabel")
        sev_col.addWidget(lbl_sev)

        self.combo_severity = QComboBox()
        severities = [
            (t("severity.info", "Info"), "info"),
            (t("severity.low", "Low"), "low"),
            (t("severity.medium", "Medium"), "medium"),
            (t("severity.high", "High"), "high"),
            (t("severity.critical", "Critical"), "critical"),
        ]
        for i, (s_label, s_id) in enumerate(severities):
            sev_icon = icon("fa5s.circle", color=get_severity_color(s_id))
            self.combo_severity.addItem(sev_icon, s_label, s_id)
            if s_id == self.initial_severity.lower():
                self.combo_severity.setCurrentIndex(i)
        sev_col.addWidget(self.combo_severity)
        det_top_row.addLayout(sev_col, stretch=1)

        # Targets
        target_col = QVBoxLayout()
        target_col.setSpacing(4)
        lbl_target = QLabel(t("loot_dialog.lbl_targets", "Associated Targets (optional):"))
        lbl_target.setProperty("class", "FormLabel")
        target_col.addWidget(lbl_target)

        self.txt_target = QLineEdit(", ".join(self.initial_targets))
        self.txt_target.setPlaceholderText(t("loot_dialog.ph_targets", "10.10.10.x, /api/v1/auth"))
        target_col.addWidget(self.txt_target)
        det_top_row.addLayout(target_col, stretch=2)

        det_layout.addLayout(det_top_row)

        # Recommendation
        lbl_recommendation = QLabel(
            t("loot_dialog.lbl_recommendation", "Recommendation (optional):")
        )
        lbl_recommendation.setProperty("class", "FormLabel")
        det_layout.addWidget(lbl_recommendation)

        self.txt_recommendation = QPlainTextEdit()
        self.txt_recommendation.setObjectName("CommandBox")
        self.txt_recommendation.setPlainText(self.initial_recommendation)
        self.txt_recommendation.setPlaceholderText(
            t(
                "loot_dialog.ph_recommendation",
                "Describe the concrete action required to remediate this finding.",
            )
        )
        self.txt_recommendation.setFixedHeight(70)
        det_layout.addWidget(self.txt_recommendation)

        # Standalone Report Finding Checkbox
        self.chk_report_finding = QCheckBox(
            t("loot_dialog.report_finding", "Use as a standalone report finding")
        )
        self.chk_report_finding.setToolTip(
            t(
                "loot_dialog.report_finding_tip",
                "Finding Loot appears in generated reports; other Loot remains available as supporting evidence.",
            )
        )
        self.chk_report_finding.setChecked(self.initial_report_role in {"finding", "legacy"})
        det_layout.addWidget(self.chk_report_finding)

        # Finding Details (status, cvss, vector, references)
        self.finding_details_widget = QWidget()
        finding_layout = QVBoxLayout(self.finding_details_widget)
        finding_layout.setContentsMargins(0, 4, 0, 4)
        finding_layout.setSpacing(8)

        details_row = QHBoxLayout()
        details_row.setSpacing(10)
        status_col = QVBoxLayout()
        status_col.addWidget(
            self._form_label(t("loot_dialog.lbl_finding_status", "Finding Status:"))
        )
        self.combo_finding_status = QComboBox()
        for status in ("open", "in_progress", "resolved", "accepted_risk"):
            self.combo_finding_status.addItem(
                t(f"report.status_{status}", status.replace("_", " ").title()),
                status,
            )
        self.combo_finding_status.setCurrentIndex(
            max(0, self.combo_finding_status.findData(self.initial_finding_status))
        )
        status_col.addWidget(self.combo_finding_status)
        details_row.addLayout(status_col, stretch=1)

        score_col = QVBoxLayout()
        score_col.addWidget(self._form_label(t("loot_dialog.lbl_cvss_score", "CVSS Score:")))
        self.txt_cvss_score = QLineEdit()
        score_validator = QDoubleValidator(0.0, 10.0, 1, self)
        score_validator.setLocale(QLocale.c())
        self.txt_cvss_score.setValidator(score_validator)
        self.txt_cvss_score.setPlaceholderText("0.0–10.0")
        if self.initial_cvss_score is not None:
            self.txt_cvss_score.setText(f"{self.initial_cvss_score:.1f}")
        score_col.addWidget(self.txt_cvss_score)
        details_row.addLayout(score_col, stretch=1)

        vector_col = QVBoxLayout()
        vector_col.addWidget(self._form_label(t("loot_dialog.lbl_cvss_vector", "CVSS Vector:")))
        self.txt_cvss_vector = QLineEdit(self.initial_cvss_vector)
        self.txt_cvss_vector.setPlaceholderText("CVSS:3.1/AV:N/AC:L/PR:N/...")
        vector_col.addWidget(self.txt_cvss_vector)
        details_row.addLayout(vector_col, stretch=2)
        finding_layout.addLayout(details_row)

        finding_layout.addWidget(
            self._form_label(t("loot_dialog.lbl_references", "References (one per line):"))
        )
        self.txt_references = QPlainTextEdit()
        self.txt_references.setObjectName("CommandBox")
        self.txt_references.setPlainText("\n".join(self.initial_references))
        self.txt_references.setPlaceholderText(
            t(
                "loot_dialog.ph_references",
                "CVE, advisory, ticket, or documentation URL",
            )
        )
        self.txt_references.setFixedHeight(65)
        finding_layout.addWidget(self.txt_references)

        self.finding_details_widget.setVisible(self.chk_report_finding.isChecked())
        self.chk_report_finding.toggled.connect(self._set_finding_details_visible)
        det_layout.addWidget(self.finding_details_widget)

        layout.addWidget(self.details_widget)
        self._set_details_expanded(self._is_details_expanded)
        self.txt_target.setPlaceholderText(t("loot_dialog.ph_targets", "10.10.10.x, /api/v1/auth"))
        layout.addWidget(self.txt_target)

        # 5. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel(t("loot_dialog.btn_hint", "↵ Enter: Save | Esc: Cancel"))
        lbl_hint.setStyleSheet(f"color: {get_theme_color('TEXT_MUTED')}; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)

        if self.is_edit and self.entry_id:
            self.btn_export_file = QPushButton(t("loot.export_file", "Export (.md)"))
            self.btn_export_file.setProperty("class", "SecondaryBtn")
            if self.on_export_file:
                self.btn_export_file.clicked.connect(lambda: self.on_export_file(self.entry_id))
            btn_layout.addWidget(self.btn_export_file)

            self.plugin_export_buttons: dict[str, QPushButton] = {}
            if self.on_export_plugin:
                for metadata in self.loot_append_plugins:
                    plugin_name = plugin_text(metadata.display_name)
                    button = QPushButton(plugin_name)
                    button.setProperty("class", "SecondaryBtn")
                    button.clicked.connect(
                        lambda _checked=False, plugin_id=metadata.plugin_id: self.on_export_plugin(
                            plugin_id, self.entry_id
                        )
                    )
                    btn_layout.addWidget(button)
                    self.plugin_export_buttons[metadata.plugin_id] = button
        else:
            self.btn_export_file = None
            self.plugin_export_buttons = {}

        btn_layout.addStretch()

        self.btn_cancel = QPushButton(t("dialog.cancel", "Cancel"))
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        save_label = t("dialog.update", "Update") if self.is_edit else t("dialog.save", "Save")
        self.btn_save = QPushButton(save_label)
        self.btn_save.setProperty("class", "PrimaryBtn")
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

    def _discard_draft(self) -> None:
        AddLootDialog._cached_draft = None
        self.txt_title.clear()
        self.txt_content.clear()
        self.recovery_banner.hide()

    def _save_draft_if_dirty(self) -> None:
        if self.is_edit:
            return
        title = self.txt_title.text().strip() if hasattr(self, "txt_title") else ""
        content = self.txt_content.toPlainText().strip() if hasattr(self, "txt_content") else ""
        initial_title = (self.initial_title or "").strip()
        initial_content = (self.initial_content or "").strip()
        if (title or content) and (title != initial_title or content != initial_content):
            AddLootDialog._cached_draft = {
                "title": title,
                "content": content,
                "type": self.combo_type.currentData() if hasattr(self, "combo_type") else "note",
                "category": self.combo_category.currentData() if hasattr(self, "combo_category") else "misc",
                "target": self.txt_target.text().strip() if hasattr(self, "txt_target") else "",
                "time": datetime.now().strftime("%H:%M:%S"),
            }

    def closeEvent(self, event) -> None:
        self._save_draft_if_dirty()
        super().closeEvent(event)

    def reject(self) -> None:
        self._save_draft_if_dirty()
        super().reject()

    def _on_save(self) -> None:
        title = self.txt_title.text().strip()
        content = self.txt_content.toPlainText().strip()

        # Minimal capture without friction: auto-generate title if content exists
        if not title and content:
            first_line = content.split("\n")[0].strip()
            title = first_line[:30] if len(first_line) > 30 else first_line
            if not title:
                title = f"Loot {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            self.txt_title.setText(title)
        elif title and not content:
            content = title
            self.txt_content.setPlainText(content)
        elif not title and not content:
            show_warning_dialog(
                self,
                t("dialog.error", "Error"),
                t("loot_dialog.err_title", "Please enter a title or content for the loot entry."),
            )
            return

        AddLootDialog._cached_draft = None
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        targets = normalize_finding_targets(self.txt_target.text())
        data = {
            "type": self.combo_type.currentData(),
            "severity": self.combo_severity.currentData(),
            "category": self.combo_category.currentData(),
            "title": self.txt_title.text().strip(),
            "content": self.txt_content.toPlainText().strip(),
            "recommendation": self.txt_recommendation.toPlainText().strip(),
            "report_role": ("finding" if self.chk_report_finding.isChecked() else "evidence"),
            "target_ip": targets[0] if targets else "",
            "targets": targets,
            "cvss_score": normalize_cvss_score(self.txt_cvss_score.text()),
            "cvss_vector": self.txt_cvss_vector.text().strip(),
            "finding_status": self.combo_finding_status.currentData(),
            "references": normalize_finding_references(self.txt_references.toPlainText()),
        }
        if self.entry_id:
            data["id"] = self.entry_id
        return data

    @staticmethod
    def _form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("class", "FormLabel")
        return label

    def _toggle_details(self) -> None:
        self._set_details_expanded(not self.details_widget.isVisible())

    def _set_details_expanded(self, expanded: bool) -> None:
        AddLootDialog._details_expanded = expanded
        self.details_widget.setVisible(expanded)
        if expanded:
            self.btn_toggle_details.setText(
                t("loot_dialog.toggle_details_hide", "▼ Weniger Details")
            )
            if self.height() < 640:
                self.resize(max(self.width(), 580), 640)
        else:
            self.btn_toggle_details.setText(
                t(
                    "loot_dialog.toggle_details_show",
                    "▶ Weitere Details (Severity, Targets, Empfehlung, CVSS)",
                )
            )
            if self.height() > 440:
                self.resize(self.width(), 440)

    def _set_finding_details_visible(self, visible: bool) -> None:
        self.finding_details_widget.setVisible(visible)
        if visible and self.height() < 720:
            self.resize(max(self.width(), 620), 720)
        elif not visible and self.height() > 640:
            self.resize(self.width(), 640)
