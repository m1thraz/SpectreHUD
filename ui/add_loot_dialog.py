from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QWidget,
)
from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QDoubleValidator
from typing import Dict, Any, Optional, Callable
from core.loot import (
    CATEGORIES,
    LOOT_TYPES,
    normalize_cvss_score,
    normalize_finding_references,
    normalize_finding_status,
    normalize_finding_targets,
)
from core.i18n import t
from ui.message_boxes import show_warning_dialog
from ui.base_dialog import BaseHudDialog
from ui.styles.icons import get_severity_color, get_theme_color, icon


class AddLootDialog(BaseHudDialog):
    """Dialog to capture new or edit existing session loot (credentials, hashes, flags, notes, PoCs)."""

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
        on_export_obsidian: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        self.entry_id = entry_id or kwargs.get("id")
        self.is_edit = is_edit or bool(self.entry_id)
        self.on_export_file = on_export_file
        self.on_export_obsidian = on_export_obsidian
        dialog_title = t(
            "loot_dialog.title_edit" if self.is_edit else "loot_dialog.title_new",
            "SPECTRE // EDIT SESSION LOOT" if self.is_edit else "SPECTRE // CAPTURE SESSION LOOT",
        )

        super().__init__(title=dialog_title, parent=parent)
        self.setMinimumWidth(540)
        self.resize(560, 600)

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

        # 1. Type, Severity, and Category Selection (Side by Side)
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

        # 1b. Severity / Schweregrad
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
        select_row.addLayout(sev_col, stretch=1)

        # 1c. Pentest Category
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
        select_row.addLayout(cat_col, stretch=2)

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
        self.txt_content.setFixedHeight(100)
        layout.addWidget(self.txt_content)

        lbl_recommendation = QLabel(
            t("loot_dialog.lbl_recommendation", "Recommendation (optional):")
        )
        lbl_recommendation.setProperty("class", "FormLabel")
        layout.addWidget(lbl_recommendation)

        self.txt_recommendation = QPlainTextEdit()
        self.txt_recommendation.setObjectName("CommandBox")
        self.txt_recommendation.setPlainText(self.initial_recommendation)
        self.txt_recommendation.setPlaceholderText(
            t(
                "loot_dialog.ph_recommendation",
                "Describe the concrete action required to remediate this finding.",
            )
        )
        self.txt_recommendation.setFixedHeight(100)
        layout.addWidget(self.txt_recommendation)

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
        layout.addWidget(self.chk_report_finding)

        self.finding_details_widget = QWidget()
        details_layout = QVBoxLayout(self.finding_details_widget)
        details_layout.setContentsMargins(0, 4, 0, 4)
        details_layout.setSpacing(8)

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
        details_layout.addLayout(details_row)

        details_layout.addWidget(
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
        self.txt_references.setFixedHeight(70)
        details_layout.addWidget(self.txt_references)
        self.finding_details_widget.setVisible(self.chk_report_finding.isChecked())
        self.chk_report_finding.toggled.connect(self._set_finding_details_visible)
        layout.addWidget(self.finding_details_widget)
        if self.chk_report_finding.isChecked():
            self.resize(max(self.width(), 660), max(self.height(), 740))

        # 4. Target IP
        lbl_target = QLabel(t("loot_dialog.lbl_targets", "Associated Targets (optional):"))
        lbl_target.setProperty("class", "FormLabel")
        layout.addWidget(lbl_target)

        self.txt_target = QLineEdit(", ".join(self.initial_targets))
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

            self.btn_export_obsidian = QPushButton(t("loot.export_obsidian", "Obsidian"))
            self.btn_export_obsidian.setProperty("class", "SecondaryBtn")
            if self.on_export_obsidian:
                self.btn_export_obsidian.clicked.connect(
                    lambda: self.on_export_obsidian(self.entry_id)
                )
            btn_layout.addWidget(self.btn_export_obsidian)
        else:
            self.btn_export_file = None
            self.btn_export_obsidian = None

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

    def _on_save(self) -> None:
        if not self.txt_title.text().strip():
            show_warning_dialog(
                self,
                t("dialog.error", "Error"),
                t("loot_dialog.err_title", "Please enter a title for the loot entry."),
            )
            return
        if not self.txt_content.toPlainText().strip():
            show_warning_dialog(
                self,
                t("dialog.error", "Error"),
                t("loot_dialog.err_content", "Please enter the content / value."),
            )
            return
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

    def _set_finding_details_visible(self, visible: bool) -> None:
        self.finding_details_widget.setVisible(visible)
        if visible and self.height() < 740:
            self.resize(max(self.width(), 660), 740)
        elif not visible and self.height() <= 740:
            self.resize(self.width(), 600)
