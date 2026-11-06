from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure package imports work both from source and PyInstaller
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> int:
    # HiDPI
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Safety Remote Desktop")
    app.setOrganizationName("SafetyRemote")
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
