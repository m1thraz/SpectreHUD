"""
SpectreHUD Report Workspace Scope & Methodology Inspector.
Provides a structured cockpit for managing In-Scope targets, IP subnets,
Out-of-Scope exclusions, assessment approach (Black/Grey/Whitebox), and Rules of Engagement.
"""

from typing import List, Optional

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.i18n import t
from core.reporting import (
    ReportScopeMethodology,
    ReportWorkspaceDocument,
    ScopeExclusionItem,
    ScopeTargetItem,
)
from ui.glass_panel import GlassPanel
from ui.styles.icons import icon


class ReportScopeInspector(QWidget):
    """Contextual Inspector for Scope & Methodology."""

    scope_changed = pyqtSignal(ReportScopeMethodology)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ReportScopeInspector")
        self._scope = ReportScopeMethodology()
        self._project_target_ip = ""
        self._language = "de"
        self._loading = False

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self._emit_changed)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Header Card
        self.header_card = GlassPanel(self)
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(8)

        lbl_icon = QLabel()
        lbl_icon.setPixmap(icon("fa5s.bullseye", color="#00e5ff").pixmap(20, 20))
        h_layout.addWidget(lbl_icon)

        self.lbl_title = QLabel(t("report.inspector_scope_title", "Scope & Methodik"))
        self.lbl_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #f0f6fc;")
        h_layout.addWidget(self.lbl_title)
        h_layout.addStretch()

        self.lbl_badge = QLabel()
        self.lbl_badge.setStyleSheet(
            "font-size: 11px; font-weight: bold; padding: 3px 10px; border-radius: 4px; "
            "background: rgba(0, 229, 255, 0.15); color: #00e5ff; border: 1px solid rgba(0, 229, 255, 0.35);"
        )
        h_layout.addWidget(self.lbl_badge)

        self.btn_import_target = QPushButton(t("report.scope_import_project_ip", "Projekt-IP übernehmen"))
        self.btn_import_target.setIcon(icon("fa5s.download", color="#7ee787"))
        self.btn_import_target.setStyleSheet(
            "QPushButton { background: rgba(126, 231, 135, 0.12); border: 1px solid rgba(126, 231, 135, 0.35); "
            "border-radius: 4px; color: #7ee787; font-weight: bold; padding: 4px 10px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(126, 231, 135, 0.25); }"
        )
        self.btn_import_target.clicked.connect(self._on_import_target_clicked)
        h_layout.addWidget(self.btn_import_target)

        main_layout.addWidget(self.header_card)

        # 2. Scroll Area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(12, 8, 12, 12)
        self.content_layout.setSpacing(10)

        # --- Approach Card ---
        approach_card = GlassPanel(content_widget)
        appr_layout = QVBoxLayout(approach_card)
        appr_layout.setContentsMargins(12, 10, 12, 10)
        appr_layout.setSpacing(8)

        lbl_appr_header = QLabel(t("report.scope_approach_header", "Pentest-Ansatz & Methodik"))
        lbl_appr_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        appr_layout.addWidget(lbl_appr_header)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.appr_group = QButtonGroup(self)

        self.btn_blackbox = QPushButton(t("report.approach_blackbox", "Blackbox"))
        self.btn_blackbox.setIcon(icon("fa5s.user-secret", color="#f85149"))
        self.btn_blackbox.setCheckable(True)
        self._style_approach_btn(self.btn_blackbox, "#f85149")
        self.appr_group.addButton(self.btn_blackbox)
        btn_row.addWidget(self.btn_blackbox)

        self.btn_greybox = QPushButton(t("report.approach_greybox", "Greybox"))
        self.btn_greybox.setIcon(icon("fa5s.user-shield", color="#d29922"))
        self.btn_greybox.setCheckable(True)
        self._style_approach_btn(self.btn_greybox, "#d29922")
        self.appr_group.addButton(self.btn_greybox)
        btn_row.addWidget(self.btn_greybox)

        self.btn_whitebox = QPushButton(t("report.approach_whitebox", "Whitebox"))
        self.btn_whitebox.setIcon(icon("fa5s.file-code", color="#58a6ff"))
        self.btn_whitebox.setCheckable(True)
        self._style_approach_btn(self.btn_whitebox, "#58a6ff")
        self.appr_group.addButton(self.btn_whitebox)
        btn_row.addWidget(self.btn_whitebox)

        btn_row.addStretch()
        appr_layout.addLayout(btn_row)

        self.btn_blackbox.clicked.connect(lambda: self._set_approach("blackbox"))
        self.btn_greybox.clicked.connect(lambda: self._set_approach("greybox"))
        self.btn_whitebox.clicked.connect(lambda: self._set_approach("whitebox"))

        self.lbl_appr_desc = QLabel()
        self.lbl_appr_desc.setStyleSheet("font-size: 11px; color: #8b949e; font-style: italic;")
        appr_layout.addWidget(self.lbl_appr_desc)

        self.txt_appr_details = QLineEdit()
        self.txt_appr_details.setPlaceholderText(
            t("report.approach_details_placeholder", "Zusätzliche Methodik-Details / Berechtigungsstufen (optional)...")
        )
        self.txt_appr_details.setStyleSheet(
            "QLineEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; padding: 4px 8px; } "
            "QLineEdit:focus { border-color: #00e5ff; }"
        )
        self.txt_appr_details.textChanged.connect(self._on_field_changed)
        appr_layout.addWidget(self.txt_appr_details)

        self.content_layout.addWidget(approach_card)

        # --- In-Scope Targets Card ---
        in_card = GlassPanel(content_widget)
        in_layout = QVBoxLayout(in_card)
        in_layout.setContentsMargins(12, 10, 12, 10)
        in_layout.setSpacing(8)

        in_header_row = QHBoxLayout()
        lbl_in_header = QLabel(t("report.scope_in_targets_header", "In-Scope Ziele & Netzwerke"))
        lbl_in_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        in_header_row.addWidget(lbl_in_header)
        in_header_row.addStretch()

        self.btn_add_in = QPushButton(t("report.scope_add_target", "Ziel hinzufügen"))
        self.btn_add_in.setIcon(icon("fa5s.plus", color="#00e5ff"))
        self.btn_add_in.setStyleSheet(
            "QPushButton { background: rgba(0, 229, 255, 0.12); border: 1px solid rgba(0, 229, 255, 0.35); "
            "border-radius: 4px; color: #00e5ff; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(0, 229, 255, 0.25); }"
        )
        self.btn_add_in.clicked.connect(self._on_add_in_target_clicked)
        in_header_row.addWidget(self.btn_add_in)
        in_layout.addLayout(in_header_row)

        self.tbl_in_targets = QTableWidget()
        self.tbl_in_targets.setColumnCount(5)
        self.tbl_in_targets.setHorizontalHeaderLabels([
            t("report.col_target", "Ziel / Host / Subnetz"),
            t("report.col_target_type", "Typ"),
            t("report.col_target_env", "Umgebung"),
            t("report.col_description", "Beschreibung"),
            t("report.col_action", "Aktion"),
        ])
        self._style_table(self.tbl_in_targets)
        self.tbl_in_targets.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_in_targets.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_in_targets.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_in_targets.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tbl_in_targets.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_in_targets.setMinimumHeight(150)
        in_layout.addWidget(self.tbl_in_targets)

        self.content_layout.addWidget(in_card)

        # --- Out-of-Scope Targets Card ---
        out_card = GlassPanel(content_widget)
        out_layout = QVBoxLayout(out_card)
        out_layout.setContentsMargins(12, 10, 12, 10)
        out_layout.setSpacing(8)

        out_header_row = QHBoxLayout()
        lbl_out_header = QLabel(t("report.scope_out_targets_header", "Out-of-Scope & Ausschlusskriterien"))
        lbl_out_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        out_header_row.addWidget(lbl_out_header)
        out_header_row.addStretch()

        self.btn_add_out = QPushButton(t("report.scope_add_exclusion", "Ausschluss hinzufügen"))
        self.btn_add_out.setIcon(icon("fa5s.plus", color="#f85149"))
        self.btn_add_out.setStyleSheet(
            "QPushButton { background: rgba(248, 81, 73, 0.12); border: 1px solid rgba(248, 81, 73, 0.35); "
            "border-radius: 4px; color: #f85149; font-weight: bold; padding: 3px 8px; font-size: 11px; } "
            "QPushButton:hover { background: rgba(248, 81, 73, 0.25); }"
        )
        self.btn_add_out.clicked.connect(self._on_add_out_target_clicked)
        out_header_row.addWidget(self.btn_add_out)
        out_layout.addLayout(out_header_row)

        self.tbl_out_targets = QTableWidget()
        self.tbl_out_targets.setColumnCount(3)
        self.tbl_out_targets.setHorizontalHeaderLabels([
            t("report.col_excluded_target", "Ausgeschlossenes Ziel / Komponente"),
            t("report.col_exclusion_reason", "Grund / Kriterium"),
            t("report.col_action", "Aktion"),
        ])
        self._style_table(self.tbl_out_targets)
        self.tbl_out_targets.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_out_targets.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_out_targets.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_out_targets.setMinimumHeight(120)
        out_layout.addWidget(self.tbl_out_targets)

        self.content_layout.addWidget(out_card)

        # --- Rules of Engagement & Limitations Card ---
        roe_card = GlassPanel(content_widget)
        roe_layout = QVBoxLayout(roe_card)
        roe_layout.setContentsMargins(12, 10, 12, 10)
        roe_layout.setSpacing(8)

        lbl_roe_header = QLabel(t("report.scope_roe_header", "Testeinschränkungen & Rules of Engagement"))
        lbl_roe_header.setStyleSheet("font-size: 12px; font-weight: bold; color: #f0f6fc;")
        roe_layout.addWidget(lbl_roe_header)

        # Standard checkboxes
        self.chk_no_dos = QCheckBox(
            t("report.roe_no_dos", "Keine Denial-of-Service-Angriffe (DoS/DDoS) oder Beeinträchtigung der Verfügbarkeit")
        )
        self._style_checkbox(self.chk_no_dos)
        self.chk_no_dos.toggled.connect(self._on_field_changed)
        roe_layout.addWidget(self.chk_no_dos)

        self.chk_no_social = QCheckBox(
            t("report.roe_no_social", "Kein Social Engineering / Phishing gegen Mitarbeiter oder Dritte")
        )
        self._style_checkbox(self.chk_no_social)
        self.chk_no_social.toggled.connect(self._on_field_changed)
        roe_layout.addWidget(self.chk_no_social)

        self.chk_no_data = QCheckBox(
            t("report.roe_no_data", "Keine dauerhafte Veränderung oder Zerstörung von Geschäfts- und Produktivdaten")
        )
        self._style_checkbox(self.chk_no_data)
        self.chk_no_data.toggled.connect(self._on_field_changed)
        roe_layout.addWidget(self.chk_no_data)

        self.chk_service_window = QCheckBox(
            t("report.roe_service_window", "Prüfaktivitäten ausschließlich innerhalb vereinbarter Testfenster")
        )
        self._style_checkbox(self.chk_service_window)
        self.chk_service_window.toggled.connect(self._on_field_changed)
        roe_layout.addWidget(self.chk_service_window)

        lbl_custom = QLabel(t("report.scope_custom_rules_label", "Individuelle Absprachen / Notfallkontakte:"))
        lbl_custom.setStyleSheet("font-size: 11px; color: #8b949e; font-weight: 500; margin-top: 4px;")
        roe_layout.addWidget(lbl_custom)

        self.txt_custom_rules = QPlainTextEdit()
        self.txt_custom_rules.setPlaceholderText(
            t("report.scope_custom_rules_placeholder", "Z. B. Notfall-Hotline des SOC, Eskalations-Ansprechpartner, besondere Whitelists...")
        )
        self.txt_custom_rules.setMaximumHeight(75)
        self.txt_custom_rules.setStyleSheet(
            "QPlainTextEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; padding: 4px; } "
            "QPlainTextEdit:focus { border-color: #00e5ff; }"
        )
        self.txt_custom_rules.textChanged.connect(self._on_field_changed)
        roe_layout.addWidget(self.txt_custom_rules)

        self.content_layout.addWidget(roe_card)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, stretch=1)

    def _style_approach_btn(self, btn: QPushButton, active_color: str) -> None:
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #8b949e;
                font-weight: 600;
                font-size: 11px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                border-color: {active_color};
                color: #f0f6fc;
            }}
            QPushButton:checked {{
                background: rgba(48, 54, 61, 0.4);
                border-color: {active_color};
                color: {active_color};
            }}
            """
        )

    def _style_table(self, table: QTableWidget) -> None:
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setStyleSheet(
            """
            QTableWidget {
                background: #161b22;
                border: 1px solid #30363d;
                border-radius: 4px;
                gridline-color: #21262d;
                color: #f0f6fc;
                font-size: 11px;
            }
            QHeaderView::section {
                background: #0d1117;
                color: #8b949e;
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid #30363d;
                padding: 5px 8px;
            }
            """
        )

    def _style_checkbox(self, chk: QCheckBox) -> None:
        chk.setStyleSheet(
            """
            QCheckBox {
                color: #c9d1d9;
                font-size: 11px;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #30363d;
                background: #0d1117;
            }
            QCheckBox::indicator:checked {
                background: #00e5ff;
                border-color: #00e5ff;
            }
            """
        )

    def set_project_target_ip(self, ip: str) -> None:
        self._project_target_ip = (ip or "").strip()

    def load_scope(self, doc: ReportWorkspaceDocument) -> None:
        """Loads structured scope methodology from document."""
        self._loading = True
        try:
            self._language = doc.language
            self._scope = doc.get_scope_methodology()
            meta_scope = doc.metadata.target_scope.strip()
            if meta_scope and not self._project_target_ip:
                self._project_target_ip = meta_scope

            self.lbl_title.setText(self._scope.title or t("report.inspector_scope_title", "Scope & Methodik"))
            self.txt_appr_details.setText(self._scope.approach_details)

            self._set_approach(self._scope.approach)

            self._populate_in_table()
            self._populate_out_table()

            # Checkboxes
            self.chk_no_dos.setChecked("no_dos" in self._scope.restrictions)
            self.chk_no_social.setChecked("no_social_engineering" in self._scope.restrictions)
            self.chk_no_data.setChecked("no_data_destruction" in self._scope.restrictions)
            self.chk_service_window.setChecked("business_hours_only" in self._scope.restrictions)

            self.txt_custom_rules.setPlainText(self._scope.custom_rules)
            self._update_badge()
        finally:
            self._loading = False

    def _set_approach(self, approach: str) -> None:
        norm = (approach or "greybox").lower()
        if norm == "blackbox":
            self.btn_blackbox.setChecked(True)
            self.lbl_appr_desc.setText(
                t("report.desc_blackbox", "Blackbox: Keine Vorkenntnisse über interne Systeme / externer Angreiferperspektive.")
            )
        elif norm == "whitebox":
            self.btn_whitebox.setChecked(True)
            self.lbl_appr_desc.setText(
                t("report.desc_whitebox", "Whitebox: Vollständige Vorkenntnisse, Quellcode-Einsicht und Architekturmodelle.")
            )
        else:
            norm = "greybox"
            self.btn_greybox.setChecked(True)
            self.lbl_appr_desc.setText(
                t("report.desc_greybox", "Greybox: Teilweise Vorkenntnisse, Standard-Benutzerrollen und Systemzugänge.")
            )
        self._scope.approach = norm
        self._on_field_changed()

    def _update_badge(self) -> None:
        in_cnt = len(self._scope.in_scope_targets)
        out_cnt = len(self._scope.out_of_scope_targets)
        text = f"{in_cnt} In-Scope | {out_cnt} Out-of-Scope"
        self.lbl_badge.setText(text)

    def _populate_in_table(self) -> None:
        self.tbl_in_targets.setRowCount(len(self._scope.in_scope_targets))
        for row, item in enumerate(self._scope.in_scope_targets):
            self._build_in_table_row(row, item)

    def _build_in_table_row(self, row: int, item: ScopeTargetItem) -> None:
        # Col 0: Target input
        edit_tgt = QLineEdit(item.target)
        edit_tgt.setPlaceholderText("z. B. 10.10.10.0/24")
        edit_tgt.setStyleSheet("background: transparent; border: 1px solid transparent; color: #f0f6fc; padding: 2px 4px;")
        edit_tgt.textChanged.connect(lambda t, idx=row: self._on_in_target_changed(idx, t))
        self.tbl_in_targets.setCellWidget(row, 0, edit_tgt)

        # Col 1: Type Combo
        cmb_type = QComboBox()
        types = [
            ("network", t("report.type_network", "Netzwerk / Subnetz")),
            ("host", t("report.type_host", "Host / Server")),
            ("webapp", t("report.type_webapp", "Web-Anwendung")),
            ("api", t("report.type_api", "API / Web-Service")),
            ("cloud", t("report.type_cloud", "Cloud-Ressource")),
            ("other", t("report.type_other", "Sonstige")),
        ]
        cur_type_idx = 0
        for idx, (k, lbl) in enumerate(types):
            cmb_type.addItem(lbl, k)
            if item.target_type == k:
                cur_type_idx = idx
        cmb_type.setCurrentIndex(cur_type_idx)
        cmb_type.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 3px; color: #c9d1d9; font-size: 11px;")
        cmb_type.currentIndexChanged.connect(lambda _, c=cmb_type, idx=row: self._on_in_type_changed(idx, str(c.currentData())))
        self.tbl_in_targets.setCellWidget(row, 1, cmb_type)

        # Col 2: Environment Combo
        cmb_env = QComboBox()
        envs = [
            ("production", t("report.env_production", "Produktion")),
            ("staging", t("report.env_staging", "Staging")),
            ("development", t("report.env_development", "Entwicklung")),
            ("other", t("report.env_other", "Sonstige")),
        ]
        cur_env_idx = 0
        for idx, (k, lbl) in enumerate(envs):
            cmb_env.addItem(lbl, k)
            if item.environment == k:
                cur_env_idx = idx
        cmb_env.setCurrentIndex(cur_env_idx)
        cmb_env.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 3px; color: #c9d1d9; font-size: 11px;")
        cmb_env.currentIndexChanged.connect(lambda _, c=cmb_env, idx=row: self._on_in_env_changed(idx, str(c.currentData())))
        self.tbl_in_targets.setCellWidget(row, 2, cmb_env)

        # Col 3: Description input
        edit_desc = QLineEdit(item.description)
        edit_desc.setPlaceholderText(t("report.scope_desc_placeholder", "Zweck / Notiz..."))
        edit_desc.setStyleSheet("background: transparent; border: 1px solid transparent; color: #c9d1d9; padding: 2px 4px;")
        edit_desc.textChanged.connect(lambda d, idx=row: self._on_in_desc_changed(idx, d))
        self.tbl_in_targets.setCellWidget(row, 3, edit_desc)

        # Col 4: Delete button
        btn_del = QPushButton()
        btn_del.setIcon(icon("fa5s.trash-alt", color="#f85149"))
        btn_del.setToolTip(t("report.delete_row", "Zeile löschen"))
        btn_del.setStyleSheet(
            "QPushButton { background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.3); border-radius: 3px; padding: 2px 6px; } "
            "QPushButton:hover { background: rgba(248, 81, 73, 0.25); }"
        )
        btn_del.clicked.connect(lambda _, idx=row: self._on_delete_in_target(idx))
        self.tbl_in_targets.setCellWidget(row, 4, btn_del)

    def _populate_out_table(self) -> None:
        self.tbl_out_targets.setRowCount(len(self._scope.out_of_scope_targets))
        for row, item in enumerate(self._scope.out_of_scope_targets):
            self._build_out_table_row(row, item)

    def _build_out_table_row(self, row: int, item: ScopeExclusionItem) -> None:
        # Col 0: Excluded target
        edit_tgt = QLineEdit(item.target)
        edit_tgt.setPlaceholderText("z. B. 10.10.10.1 Gateway")
        edit_tgt.setStyleSheet("background: transparent; border: 1px solid transparent; color: #f0f6fc; padding: 2px 4px;")
        edit_tgt.textChanged.connect(lambda t, idx=row: self._on_out_target_changed(idx, t))
        self.tbl_out_targets.setCellWidget(row, 0, edit_tgt)

        # Col 1: Reason input
        edit_rsn = QLineEdit(item.reason)
        edit_rsn.setPlaceholderText(t("report.scope_reason_placeholder", "Ausschlussgrund (z. B. Produktives Routing, Fremdhosting)..."))
        edit_rsn.setStyleSheet("background: transparent; border: 1px solid transparent; color: #c9d1d9; padding: 2px 4px;")
        edit_rsn.textChanged.connect(lambda r, idx=row: self._on_out_reason_changed(idx, r))
        self.tbl_out_targets.setCellWidget(row, 1, edit_rsn)

        # Col 2: Delete button
        btn_del = QPushButton()
        btn_del.setIcon(icon("fa5s.trash-alt", color="#f85149"))
        btn_del.setToolTip(t("report.delete_row", "Zeile löschen"))
        btn_del.setStyleSheet(
            "QPushButton { background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.3); border-radius: 3px; padding: 2px 6px; } "
            "QPushButton:hover { background: rgba(248, 81, 73, 0.25); }"
        )
        btn_del.clicked.connect(lambda _, idx=row: self._on_delete_out_target(idx))
        self.tbl_out_targets.setCellWidget(row, 2, btn_del)

    # In-target event handlers
    def _on_in_target_changed(self, row: int, text: str) -> None:
        if 0 <= row < len(self._scope.in_scope_targets):
            self._scope.in_scope_targets[row].target = text.strip()
            self._on_field_changed()

    def _on_in_type_changed(self, row: int, val: str) -> None:
        if 0 <= row < len(self._scope.in_scope_targets):
            self._scope.in_scope_targets[row].target_type = val
            self._on_field_changed()

    def _on_in_env_changed(self, row: int, val: str) -> None:
        if 0 <= row < len(self._scope.in_scope_targets):
            self._scope.in_scope_targets[row].environment = val
            self._on_field_changed()

    def _on_in_desc_changed(self, row: int, text: str) -> None:
        if 0 <= row < len(self._scope.in_scope_targets):
            self._scope.in_scope_targets[row].description = text.strip()
            self._on_field_changed()

    def _on_delete_in_target(self, row: int) -> None:
        if 0 <= row < len(self._scope.in_scope_targets):
            self._scope.in_scope_targets.pop(row)
            self._populate_in_table()
            self._update_badge()
            self._on_field_changed()

    def _on_add_in_target_clicked(self) -> None:
        new_item = ScopeTargetItem(target="", target_type="network", environment="production", description="")
        self._scope.in_scope_targets.append(new_item)
        self._populate_in_table()
        self._update_badge()
        self._on_field_changed()

    # Out-target event handlers
    def _on_out_target_changed(self, row: int, text: str) -> None:
        if 0 <= row < len(self._scope.out_of_scope_targets):
            self._scope.out_of_scope_targets[row].target = text.strip()
            self._on_field_changed()

    def _on_out_reason_changed(self, row: int, text: str) -> None:
        if 0 <= row < len(self._scope.out_of_scope_targets):
            self._scope.out_of_scope_targets[row].reason = text.strip()
            self._on_field_changed()

    def _on_delete_out_target(self, row: int) -> None:
        if 0 <= row < len(self._scope.out_of_scope_targets):
            self._scope.out_of_scope_targets.pop(row)
            self._populate_out_table()
            self._update_badge()
            self._on_field_changed()

    def _on_add_out_target_clicked(self) -> None:
        new_item = ScopeExclusionItem(target="", reason="")
        self._scope.out_of_scope_targets.append(new_item)
        self._populate_out_table()
        self._update_badge()
        self._on_field_changed()

    def _on_import_target_clicked(self) -> None:
        """Imports project target IP or metadata scope into in-scope targets if not present."""
        tgt = self._project_target_ip.strip()
        if not tgt:
            return

        exists = any(item.target.strip() == tgt for item in self._scope.in_scope_targets)
        if not exists:
            t_type = "network" if "/" in tgt else "host"
            new_item = ScopeTargetItem(target=tgt, target_type=t_type, environment="production", description="Primäres Assessment-Ziel")
            self._scope.in_scope_targets.append(new_item)
            self._populate_in_table()
            self._update_badge()
            self._on_field_changed()

    def _on_field_changed(self) -> None:
        if self._loading:
            return
        self._debounce_timer.start()

    def _emit_changed(self) -> None:
        self._scope.approach_details = self.txt_appr_details.text().strip()

        # Gather restrictions
        rests: List[str] = []
        if self.chk_no_dos.isChecked():
            rests.append("no_dos")
        if self.chk_no_social.isChecked():
            rests.append("no_social_engineering")
        if self.chk_no_data.isChecked():
            rests.append("no_data_destruction")
        if self.chk_service_window.isChecked():
            rests.append("business_hours_only")
        self._scope.restrictions = rests

        self._scope.custom_rules = self.txt_custom_rules.toPlainText().strip()
        self.scope_changed.emit(self._scope)
