from typing import Dict, List, Any, Optional
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)
from core.template_engine import TemplateEngine, SMART_PRESETS
from ui.base_dialog import BaseHudDialog


class ParamPromptDialog(BaseHudDialog):
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
        parent: Optional[QWidget] = None,
    ):
        super().__init__(title="SPECTRE // PARAMETER AUSFÜLLEN", parent=parent)
        self.setMinimumWidth(540)
        self.resize(560, 380)

        self.template = template
        self.variables = variables
        self.unresolved_params = unresolved_params
        self.cached_params = cached_params or {}

        self.param_inputs: Dict[str, QLineEdit] = {}
        self._init_form()
        self._update_preview()

    def _init_form(self) -> None:
        layout = self.body_layout

        # Dynamic Inputs for each parameter
        for param in self.unresolved_params:
            row = QVBoxLayout()
            row.setSpacing(2)

            lbl = QLabel(f"Wert für {{{{{param}}}}}:")
            lbl.setProperty("class", "FormLabel")
            row.addWidget(lbl)

            # Determine default value (cached -> preset -> empty)
            default_val = self.cached_params.get(param, SMART_PRESETS.get(param, ""))

            txt = QLineEdit(default_val)
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
        lbl_preview.setProperty("class", "FormLabel")
        layout.addWidget(lbl_preview)

        self.txt_preview = QPlainTextEdit()
        self.txt_preview.setObjectName("CommandBox")
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setFixedHeight(75)
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

        self.btn_copy = QPushButton("Übernehmen & Kopieren")
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
