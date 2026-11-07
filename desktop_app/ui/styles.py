THEME = """
* {
  font-family: "Segoe UI", "Bahnschrift", "Trebuchet MS", sans-serif;
  color: #F8FAFC;
}
QMainWindow, QWidget#root {
  background: #070B12;
}
QScrollArea {
  border: none;
  background: transparent;
}
QLabel#brand {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 1px;
  color: #F8FAFC;
}
QLabel#subtitle {
  color: #94A3B8;
  font-size: 13px;
}
QLabel#muted {
  color: #94A3B8;
  font-size: 12px;
}
QLabel#metricValue {
  font-size: 30px;
  font-weight: 800;
}
QLabel#metricUnit {
  color: #94A3B8;
  font-size: 13px;
}
QLabel#metricLabel {
  color: #94A3B8;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
}
QFrame#panel {
  background: #121928;
  border: 1px solid rgba(255,255,255,30);
  border-radius: 18px;
}
QFrame#panelAlert {
  background: rgba(255,42,95,28);
  border: 1px solid rgba(255,42,95,160);
  border-radius: 18px;
}
QFrame#panelSafe {
  background: rgba(16,185,129,28);
  border: 1px solid rgba(16,185,129,140);
  border-radius: 18px;
}
QFrame#metric {
  background: #121928;
  border: 1px solid rgba(255,255,255,22);
  border-radius: 18px;
}
QFrame#metricHot {
  background: #121928;
  border: 1px solid rgba(255,42,95,180);
  border-radius: 18px;
}
QPushButton {
  background: #1C2638;
  border: 1px solid rgba(255,255,255,28);
  border-radius: 14px;
  padding: 10px 16px;
  font-weight: 700;
  min-height: 20px;
}
QPushButton:hover {
  background: #243247;
}
QPushButton:pressed {
  background: #182233;
}
QPushButton#primary {
  background: #FF2A5F;
  border: none;
  color: white;
}
QPushButton#primary:hover {
  background: #ff4572;
}
QPushButton#cyan {
  background: rgba(0,229,255,28);
  border: 1px solid rgba(0,229,255,120);
  color: #00E5FF;
}
QPushButton#ghost {
  background: transparent;
  border: 1px solid rgba(255,255,255,40);
}
QLineEdit, QComboBox {
  background: #1C2638;
  border: 1px solid rgba(255,255,255,24);
  border-radius: 12px;
  padding: 10px 12px;
  selection-background-color: #00E5FF;
  selection-color: #070B12;
}
QSlider::groove:horizontal {
  height: 6px;
  background: #1C2638;
  border-radius: 3px;
}
QSlider::sub-page:horizontal {
  background: #00E5FF;
  border-radius: 3px;
}
QSlider::add-page:horizontal {
  background: #243247;
  border-radius: 3px;
}
QSlider::handle:horizontal {
  width: 16px;
  height: 16px;
  margin: -6px 0;
  border-radius: 8px;
  background: #E8EEF8;
  border: 2px solid #00E5FF;
}
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
  background: #121928;
  border: 1px solid #243247;
  selection-background-color: #1C2638;
}
QStatusBar {
  background: #0A0E17;
  color: #94A3B8;
  border-top: 1px solid rgba(255,255,255,18);
}
QLabel#camTitle {
  font-weight: 800;
  letter-spacing: 0.6px;
  color: #94A3B8;
  font-size: 12px;
}
QLabel#badge {
  background: rgba(0,229,255,24);
  color: #00E5FF;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 800;
}
QLabel#badgeWarn {
  background: rgba(255,42,95,28);
  color: #FF2A5F;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 800;
}
QLabel#badgeOk {
  background: rgba(16,185,129,28);
  color: #10B981;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 800;
}
"""

COLORS = {
    "deep": "#0A0E17",
    "panel": "#121928",
    "mist": "#1C2638",
    "soft": "#F8FAFC",
    "muted": "#94A3B8",
    "pulse": "#FF2A5F",
    "cyan": "#00E5FF",
    "force": "#FF9F1C",
    "safe": "#10B981",
}
