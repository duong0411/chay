from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ai.fire_detector import FireDetector
from core.config import AppConfig
from core.models import Detection
from .styles import COLORS


class CameraWorker(QThread):
    frame_ready = pyqtSignal(int, object, list, float, float, bool)  # id, rgb, dets, fps, ms, fire
    status = pyqtSignal(int, str)

    def __init__(self, camera_id: int, detector: FireDetector, parent=None) -> None:
        super().__init__(parent)
        self.camera_id = camera_id
        self.detector = detector
        self._running = False
        self._source: int | str = camera_id

    def set_source(self, source: int | str) -> None:
        self._source = source

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        self._running = True
        cap = cv2.VideoCapture(self._source, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self._source)
        if not cap.isOpened():
            self.status.emit(self.camera_id, f"Không mở được camera {self._source}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, AppConfig.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, AppConfig.CAMERA_HEIGHT)
        self.status.emit(self.camera_id, f"Camera {self._source} OK")

        t_fps = time.perf_counter()
        frames = 0
        fps = 0.0

        while self._running:
            ok, frame = cap.read()
            if not ok or frame is None:
                self.msleep(30)
                continue

            dets: list[Detection] = []
            infer_ms = 0.0
            if self.detector.ready:
                dets, infer_ms = self.detector.infer(frame)
                frame = self.detector.draw(frame, dets)

            fire = any(FireDetector.is_fire_label(d.label) for d in dets)
            frames += 1
            now = time.perf_counter()
            if now - t_fps >= 1.0:
                fps = frames / (now - t_fps)
                frames = 0
                t_fps = now

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.frame_ready.emit(self.camera_id, rgb.copy(), dets, fps, infer_ms, fire)
            self.msleep(1)

        cap.release()
        self.status.emit(self.camera_id, "Đã dừng")


class CameraPanel(QFrame):
    def __init__(self, title: str, camera_id: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.camera_id = camera_id
        self._fire = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        head = QHBoxLayout()
        self.title = QLabel(title.upper())
        self.title.setObjectName("camTitle")
        self.badge = QLabel("STANDBY")
        self.badge.setObjectName("badge")
        self.meta = QLabel("— FPS · — ms")
        self.meta.setObjectName("muted")
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.meta)
        head.addWidget(self.badge)
        layout.addLayout(head)

        self.view = QLabel("Chưa bật camera")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumHeight(260)
        self.view.setStyleSheet(
            "background: #0A0E17; border-radius: 14px; color: #64748B;"
            "border: 1px dashed rgba(255,255,255,28);"
        )
        layout.addWidget(self.view, 1)

    def show_frame(
        self,
        rgb: np.ndarray,
        fps: float,
        infer_ms: float,
        fire: bool,
        backend: str,
    ) -> None:
        self._fire = fire
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.view.width(),
            self.view.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.view.setPixmap(pix)
        self.meta.setText(f"{fps:.1f} FPS · {infer_ms:.0f} ms · {backend}")
        if fire:
            self.badge.setText("FIRE")
            self.badge.setObjectName("badgeWarn")
        else:
            self.badge.setText("LIVE")
            self.badge.setObjectName("badgeOk")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

    def set_status(self, text: str) -> None:
        if self.view.pixmap() is None:
            self.view.setText(text)
        self.badge.setText("OFF" if "Không" in text or "dừng" in text.lower() else "READY")
        self.badge.setObjectName("badge")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
