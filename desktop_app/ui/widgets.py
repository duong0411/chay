from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QLinearGradient, QPainterPath
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .styles import COLORS


class GradientBackground(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor("#070B12"))
        grad.setColorAt(0.45, QColor("#0A0E17"))
        grad.setColorAt(1.0, QColor("#171022"))
        painter.fillRect(self.rect(), grad)

        # Soft ambient orbs
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 42, 95, 28))
        painter.drawEllipse(self.width() - 260, -80, 320, 320)
        painter.setBrush(QColor(0, 229, 255, 18))
        painter.drawEllipse(-120, self.height() - 220, 280, 280)
        super().paintEvent(event)


class MetricTile(QFrame):
    def __init__(self, label: str, icon_text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("metric")
        self.setMinimumHeight(118)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self.lbl = QLabel(label.upper())
        self.lbl.setObjectName("metricLabel")
        self.icon = QLabel(icon_text)
        self.icon.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 16px; font-weight: 800;")
        top.addWidget(self.lbl)
        top.addStretch(1)
        top.addWidget(self.icon)
        layout.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.value = QLabel("--")
        self.value.setObjectName("metricValue")
        self.unit = QLabel("")
        self.unit.setObjectName("metricUnit")
        self.unit.setAlignment(Qt.AlignBottom)
        row.addWidget(self.value)
        row.addWidget(self.unit)
        row.addStretch(1)
        layout.addLayout(row)

        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        layout.addWidget(self.detail)
        layout.addStretch(1)

    def set_value(self, value: str, unit: str = "", detail: str = "", alert: bool = False) -> None:
        self.value.setText(value)
        self.unit.setText(unit)
        self.detail.setText(detail)
        self.setObjectName("metricHot" if alert else "metric")
        color = COLORS["pulse"] if alert else COLORS["soft"]
        self.value.setStyleSheet(f"color: {color}; font-size: 30px; font-weight: 800;")
        self.style().unpolish(self)
        self.style().polish(self)


class AlarmBanner(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panelSafe")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self.icon = QLabel("OK")
        self.icon.setFixedWidth(42)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setStyleSheet(
            f"background: rgba(16,185,129,40); color: {COLORS['safe']};"
            "border-radius: 12px; font-weight: 800;"
        )
        self.text = QLabel("Các chỉ số đang trong ngưỡng an toàn")
        self.text.setStyleSheet("font-weight: 700; font-size: 15px;")
        layout.addWidget(self.icon)
        layout.addWidget(self.text, 1)

    def set_state(self, active: bool, label: str) -> None:
        if active:
            self.setObjectName("panelAlert")
            self.icon.setText("!")
            self.icon.setStyleSheet(
                f"background: rgba(255,42,95,40); color: {COLORS['pulse']};"
                "border-radius: 12px; font-weight: 800;"
            )
            self.text.setText(label)
        else:
            self.setObjectName("panelSafe")
            self.icon.setText("OK")
            self.icon.setStyleSheet(
                f"background: rgba(16,185,129,40); color: {COLORS['safe']};"
                "border-radius: 12px; font-weight: 800;"
            )
            self.text.setText("Các chỉ số đang trong ngưỡng an toàn")
        self.style().unpolish(self)
        self.style().polish(self)


class InfoCard(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        head = QHBoxLayout()
        self.title = QLabel(title.upper())
        self.title.setObjectName("metricLabel")
        self.badge = QLabel("")
        self.badge.setObjectName("badge")
        self.badge.hide()
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.badge)
        layout.addLayout(head)
        self.body = QLabel("--")
        self.body.setWordWrap(True)
        self.body.setStyleSheet("color: #CBD5E1; line-height: 1.4;")
        layout.addWidget(self.body)

    def set_badge(self, text: str, kind: str = "cyan") -> None:
        self.badge.setText(text)
        self.badge.setObjectName({"ok": "badgeOk", "warn": "badgeWarn"}.get(kind, "badge"))
        self.badge.show()
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

    def set_body(self, text: str) -> None:
        self.body.setText(text)


class LiveDot(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.set_live(False)

    def set_live(self, live: bool) -> None:
        color = COLORS["safe"] if live else COLORS["pulse"]
        self.setStyleSheet(f"background: {color}; border-radius: 5px;")
