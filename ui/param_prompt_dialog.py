from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPlainTextEdit, QPushButton, QWidget
)
from PyQt6.QtCore import Qt
from typing import Dict, List, Any
from core.template_engine import TemplateEngine, SMART_PRESETS
from ui.styles import CYBER_DARK_QSS

class ParamPromptDialog(QDialog):
    """
    Focused modal dialog asking for missing command-specific inline parameters
    with live command preview and session cache.
    """

    def __init__(
        self, 
        template: str, 
        variables: Dict[str, Any], 
        unresolved_params: List[str], 
        cached_params: Dict[str, str] = None,
        parent: QWidget = None
    ):
        super().__init__(parent)
        self.setWindowTitle("⚡ Parameter ausfüllen")
        self.setMinimumWidth(520)
        self.resize(540, 360)
        
        self.template = template
        self.variables = variables
        self.unresolved_params = unresolved_params
        self.cached_params = cached_params or {}
        
        self.param_inputs: Dict[str, QLineEdit] = {}
        self.setStyleSheet(CYBER_DARK_QSS)
        self._init_ui()
        self._update_preview()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Header Title
        lbl_header = QLabel("🎯 Befehls-Parameter eingeben:")
        lbl_header.setStyleSheet("color: #00e5ff; font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl_header)

        # Dynamic Inputs for each parameter
        for param in self.unresolved_params:
            row = QVBoxLayout()
            row.setSpacing(2)
            
            lbl = QLabel(f"Wert für {{{{{param}}}}}:")
            lbl.setStyleSheet("color: #c9d1d9; font-weight: 600; font-size: 12px;")
            row.addWidget(lbl)

            # Determine default value (cached -> preset -> empty)
            default_val = self.cached_params.get(param, SMART_PRESETS.get(param, ""))
            
            txt = QLineEdit(default_val)
            txt.setObjectName("SpotlightSearch")
            txt.setPlaceholderText(f"Wert für {param}...")
            txt.textChanged.connect(self._update_preview)
            self.param_inputs[param] = txt
            row.addWidget(txt)

            layout.addLayout(row)

        # Focus first input
        if self.unresolved_params:
            first_param = self.unresolved_params[0]
            self.param_inputs[first_param].setFocus()
            self.param_inputs[first_param].selectAll()

        # Live Command Preview Box
        lbl_preview = QLabel("Live-Befehlsvorschau:")
        lbl_preview.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600; margin-top: 4px;")
        layout.addWidget(lbl_preview)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setObjectName("CommandBox")
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFixedHeight(70)
        layout.addWidget(self.txt_preview)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        lbl_hint = QLabel("↵ Enter: Kopieren | Esc: Abbrechen")
        lbl_hint.setStyleSheet("color: #6e7681; font-size: 11px;")
        btn_layout.addWidget(lbl_hint)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setProperty("class", "SecondaryBtn")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_copy = QPushButton("📋 Übernehmen & Kopieren")
        self.btn_copy.setProperty("class", "PrimaryBtn")
        self.btn_copy.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_copy)

        layout.addLayout(btn_layout)

    def _update_preview(self) -> None:
        """Renders live command preview as the user types."""
        custom_values = self.get_values()
        rendered = TemplateEngine.render_with_custom(self.template, self.variables, custom_values)
        self.txt_preview.setPlainText(rendered)

    def get_values(self) -> Dict[str, str]:
        """Returns dict of current parameter values."""
        values = {}
        for param, txt_edit in self.param_inputs.items():
            values[param] = txt_edit.text().strip()
        return values
