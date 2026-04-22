import re

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QMovie
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ProgressBar

from ankama_launcher_emulator.consts import RESOURCES
from ankama_launcher_emulator.gui.consts import (
    BORDER_HEXA,
    ORANGE_HEXA,
    PANEL_ALT_HEXA,
)

_STEP_RE = re.compile(r"\(?\s*(\d+)\s*/\s*(\d+)\s*\)?")


def _strip_step_text(text: str, match: re.Match[str]) -> str:
    stripped = f"{text[:match.start()]}{text[match.end():]}".strip()
    stripped = re.sub(r"\s{2,}", " ", stripped)
    return re.sub(r"\s+([,.;:])", r"\1", stripped)


class DownloadBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusStrip")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)

        self._loading_label = QLabel()
        self._loading_label.setFixedSize(28, 28)
        self._loading_movie = QMovie(str(RESOURCES / "load.gif"))
        self._loading_movie.setScaledSize(QSize(28, 28))
        self._loading_label.setMovie(self._loading_movie)
        progress_row.addWidget(self._loading_label)

        self._progress_bar = ProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(10)
        self._progress_bar.setCustomBarColor(ORANGE_HEXA, ORANGE_HEXA)
        self._progress_bar.setCustomBackgroundColor(BORDER_HEXA, BORDER_HEXA)
        progress_row.addWidget(self._progress_bar, 1)
        layout.addLayout(progress_row)

        self._progress_label = CaptionLabel("")
        self._progress_label.setObjectName("statusStripText")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._progress_label.setWordWrap(True)
        layout.addWidget(self._progress_label)

        self.setStyleSheet(
            "DownloadBanner {"
            f"background-color: {PANEL_ALT_HEXA};"
            f"border: 1px solid {BORDER_HEXA};"
            "border-radius: 16px;"
            "}"
            "DownloadBanner #statusStripText { color: #d6d6d6; }"
        )
        self.setVisible(False)

    def set_status(self, text: str) -> None:
        if not text:
            self._loading_movie.stop()
            self.setVisible(False)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(0)
            self._progress_label.setText("")
            return
        self.setVisible(True)
        self._loading_movie.start()
        match = _STEP_RE.search(text)
        if match:
            self._progress_label.setText(_strip_step_text(text, match))
            current, total = int(match.group(1)), int(match.group(2))
            if total > 0:
                self._progress_bar.setRange(0, total)
                self._progress_bar.setValue(current)
                return
        self._progress_label.setText(text)
        self._progress_bar.setRange(0, 0)
