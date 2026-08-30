from typing import Optional
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame
)
from core.i18n import t


class BaseHudDialog(QDialog):
    """
    Base frameless modal dialog styled identically to SpectreHUD Main Window
    with a draggable header bar, glowing border, translucent background, and clean controls.
    """

    def __init__(self, title: str = "SPECTRE // DIALOG", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.dialog_title_text = title
        
        # Frameless translucent dialog window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        from ui.styles import get_app_icon
        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        # Dragging state
        self._is_dragging = False
        self._drag_position = QPoint()

        # Build outer layout and HUD shell
        self._build_base_shell()

        # Keyboard shortcuts
        QShortcut(QKeySequence("Esc"), self, activated=self.reject)

    def _build_base_shell(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.setSpacing(0)

        # Main HUD frame with cyan border and dark acrylic background
        self.hud_frame = QFrame()
        self.hud_frame.setObjectName("DialogHudFrame")
        
        frame_layout = QVBoxLayout(self.hud_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # Header bar with title and close button
        self.header_bar = QFrame()
        self.header_bar.setObjectName("DialogHeaderBar")
        header_layout = QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(14, 8, 10, 8)
        header_layout.setSpacing(8)

        self.lbl_dialog_title = QLabel(self.dialog_title_text)
        self.lbl_dialog_title.setObjectName("DialogTitle")
        header_layout.addWidget(self.lbl_dialog_title)

        header_layout.addStretch()

        self.btn_dialog_close = QPushButton("✕")
        self.btn_dialog_close.setProperty("class", "DangerBtn")
        self.btn_dialog_close.setToolTip(t("dialog.close_tip", "Close (Esc)"))
        self.btn_dialog_close.clicked.connect(self.reject)
        header_layout.addWidget(self.btn_dialog_close)

        frame_layout.addWidget(self.header_bar)

        # Container for subclass content
        self.content_container = QWidget()
        self.body_layout = QVBoxLayout(self.content_container)
        self.body_layout.setContentsMargins(18, 14, 18, 16)
        self.body_layout.setSpacing(10)
        frame_layout.addWidget(self.content_container, stretch=1)

        outer_layout.addWidget(self.hud_frame)

    def set_dialog_title(self, title: str) -> None:
        self.dialog_title_text = title
        self.lbl_dialog_title.setText(title)
        self.setWindowTitle(title)

    # --------------------------------------------------------
    # Mouse Dragging Support
    # -------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            header_rect = self.header_bar.rect()
            header_global_pos = self.header_bar.mapToGlobal(QPoint(0, 0))
            if event.globalPosition().toPoint().y() < header_global_pos.y() + header_rect.height() + 10:
                self._is_dragging = True
                self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._is_dragging = False
        super().mouseReleaseEvent(event)
