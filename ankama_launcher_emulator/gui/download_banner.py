import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, ProgressBar

from ankama_launcher_emulator.gui.consts import BORDER_HEXA, PANEL_ALT_HEXA, TEXT_MUTED_HEXA

_STEP_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


class DownloadBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusStrip")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = CaptionLabel("Launcher Status")
        title.setObjectName("statusStripTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        self._title_label = BodyLabel("Game is not up to date, downloading update...")
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._title_label)

        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(6)
        layout.addWidget(self._progress_bar)

        self._progress_label = BodyLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._progress_label)

        self.setStyleSheet(
            "DownloadBanner {"
            f"background-color: {PANEL_ALT_HEXA};"
            f"border: 1px solid {BORDER_HEXA};"
            "border-radius: 16px;"
            "}"
            f"DownloadBanner #statusStripTitle {{ color: {TEXT_MUTED_HEXA}; }}"
        )
        self.setVisible(False)

    def set_status(self, text: str) -> None:
        if not text:
            self.setVisible(False)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._progress_label.setText("")
            return
        self.setVisible(True)
        self._progress_label.setText(text)
        match = _STEP_RE.search(text)
        if match:
            current, total = int(match.group(1)), int(match.group(2))
            if total > 0:
                self._progress_bar.setRange(0, total)
                self._progress_bar.setValue(current)
                return
        self._progress_bar.setRange(0, 0)
