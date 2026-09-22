"""Small first-run entry point using existing project actions."""

from typing import Optional

from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QWidget

from core.i18n import t
from ui.base_dialog import BaseHudDialog


class GettingStartedDialog(BaseHudDialog):
    """Introduce the shortest workflow without turning startup into a tutorial."""

    def __init__(self, quick_ip_shortcut: str, parent: Optional[QWidget] = None):
        super().__init__(title=t("getting_started.title", "SPECTRE // GETTING STARTED"), parent=parent)
        self.setMinimumWidth(500)
        self.selected_action: Optional[str] = None

        intro = QLabel(t("getting_started.intro", "Start with a project. You can explore the rest as you work."))
        intro.setWordWrap(True)
        self.body_layout.addWidget(intro)

        workflow = QLabel(
            t(
                "getting_started.workflow",
                "Clip is optional and off by default: enable it only when you want copied text captured.\n"
                "SpectreHUD can stay minimized. {hotkey} opens Quick IP globally to set Target and Attacker IP.\n"
                "Then copy a command from the Cheatsheet. With Clip on, copied output appears in History.",
                hotkey=quick_ip_shortcut,
            )
        )
        workflow.setWordWrap(True)
        self.body_layout.addWidget(workflow)

        self.dont_show_again = QCheckBox(t("getting_started.dont_show_again", "Don't show again"))
        self.dont_show_again.setChecked(True)
        self.body_layout.addWidget(self.dont_show_again)

        actions = QHBoxLayout()
        self.btn_new_project = QPushButton(t("getting_started.new_project", "New Project"))
        self.btn_new_project.setProperty("class", "PrimaryBtn")
        self.btn_new_project.clicked.connect(lambda: self._choose("new_project"))
        actions.addWidget(self.btn_new_project)

        self.btn_open_project = QPushButton(t("getting_started.open_project", "Open Project"))
        self.btn_open_project.setProperty("class", "SecondaryBtn")
        self.btn_open_project.clicked.connect(lambda: self._choose("open_project"))
        actions.addWidget(self.btn_open_project)

        actions.addStretch()
        self.btn_continue = QPushButton(t("getting_started.continue", "Continue"))
        self.btn_continue.setProperty("class", "SecondaryBtn")
        self.btn_continue.clicked.connect(self.accept)
        actions.addWidget(self.btn_continue)
        self.body_layout.addLayout(actions)

    def _choose(self, action: str) -> None:
        self.selected_action = action
        self.accept()
