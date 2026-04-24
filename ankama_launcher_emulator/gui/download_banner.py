import re

from PyQt6.QtCore import QPointF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QMovie, QPainter, QPainterPath, QPolygonF
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel

from ankama_launcher_emulator.consts import RESOURCES
from ankama_launcher_emulator.gui.consts import (
    BORDER_HEXA,
    ORANGE_HEXA,
    PANEL_ALT_HEXA,
    PANEL_BG_HEXA,
    TEXT_MUTED_HEXA,
)

_STEP_RE = re.compile(r"\(?\s*(\d+)\s*/\s*(\d+)\s*\)?")

_STRIPE_STEP = 24  # pixels per stripe pair
_STRIPE_ALPHA = 45  # white overlay alpha (0-255)
_TICK_MS = 25


def _strip_step_text(text: str, match: re.Match[str]) -> str:
    stripped = f"{text[:match.start()]}{text[match.end():]}".strip()
    stripped = re.sub(r"\s{2,}", " ", stripped)
    return re.sub(r"\s+([,.;:])", r"\1", stripped)


class StripedProgressBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._min = 0
        self._max = 100
        self._value = 0
        self._offset = 0
        self._bar_color = QColor(ORANGE_HEXA)
        self._bg_color = QColor(PANEL_BG_HEXA)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(_TICK_MS)

    def _tick(self):
        self._offset = (self._offset + 1) % _STRIPE_STEP
        self.update()

    def setRange(self, min_val: int, max_val: int) -> None:
        self._min = min_val
        self._max = max_val
        self.update()

    def setValue(self, value: int) -> None:
        self._value = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h / 2.0

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(0, 0, w, h, radius, radius)

        # Fill width
        indeterminate = self._max <= self._min
        if indeterminate:
            fill_w = w
        else:
            ratio = max(0.0, min(1.0, (self._value - self._min) / (self._max - self._min)))
            fill_w = int(w * ratio)

        if fill_w <= 0:
            painter.end()
            return

        # Clip to filled rounded rect
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, fill_w, h, radius, radius)
        painter.setClipPath(clip)

        # Orange base
        painter.setBrush(self._bar_color)
        painter.drawRect(0, 0, fill_w, h)

        # 45° white stripes moving right
        stripe_color = QColor(255, 255, 255, _STRIPE_ALPHA)
        painter.setBrush(stripe_color)
        x = -h * 2 + self._offset
        while x < fill_w + h:
            # Parallelogram: bottom-left, top-left+h, top-right+h, bottom-right
            half = _STRIPE_STEP // 2
            poly = QPolygonF([
                QPointF(x,          h),
                QPointF(x + h,      0),
                QPointF(x + h + half, 0),
                QPointF(x + half,   h),
            ])
            painter.drawPolygon(poly)
            x += _STRIPE_STEP

        painter.end()


class DownloadBanner(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusStrip")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)

        self._loading_label = QLabel()
        self._loading_label.setFixedSize(40, 40)
        self._loading_movie = QMovie(str(RESOURCES / "load.gif"))
        self._loading_movie.setScaledSize(QSize(40, 40))
        self._loading_label.setMovie(self._loading_movie)
        main_layout.addWidget(self._loading_label)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)

        self._progress_bar = StripedProgressBar()
        self._progress_bar.setFixedHeight(10)
        right_layout.addWidget(self._progress_bar)

        self._progress_label = CaptionLabel("")
        self._progress_label.setObjectName("statusStripText")
        self._progress_label.setStyleSheet(f"color: {TEXT_MUTED_HEXA}; font-weight: bold;")
        right_layout.addWidget(self._progress_label)

        main_layout.addLayout(right_layout)

        self.setStyleSheet(
            "DownloadBanner {"
            f"background-color: {PANEL_ALT_HEXA};"
            f"border: 1px solid {BORDER_HEXA};"
            "border-radius: 16px;"
            "}"
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
