from __future__ import annotations

import threading
import time
from collections import deque

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ai.fire_detector import FireDetector
from core.camera_enum import CameraDevice, backend_status, open_capture, open_device
from core.config import AppConfig
from core.models import Detection

_INFER_LOCK = threading.Lock()


class CameraWorker(QThread):
    """
    Capture mượt (USB-friendly):
      - Thread grab liên tục + chỉ giữ frame mới nhất (giống appsink drop=1)
      - USB: res/FPS/AI thấp hơn laptop
      - GStreamer nếu OpenCV có GST; không thì DirectShow MJPG
    """

    frame_ready = pyqtSignal(int, object, list, float, float, bool)
    status = pyqtSignal(int, str)

    def __init__(self, camera_id: int, detector: FireDetector | None = None, parent=None) -> None:
        super().__init__(parent)
        self.camera_id = camera_id
        self.detector = detector or FireDetector()
        self._running = False
        self._source: int | str = camera_id
        self._backend: int | None = None
        self._label: str = ""
        self._path: str = ""
        self._name: str = ""
        self._device: CameraDevice | None = None
        self._usb = False

        self._lock = threading.Lock()
        self._latest: np.ndarray | None = None
        self._latest_id = 0
        self._infer_id = 0
        self._dets: list[Detection] = []
        self._infer_ms = 0.0
        self._fire = False
        self._fire_votes: deque[bool] = deque(maxlen=max(1, AppConfig.FIRE_CONFIRM_WINDOW))
        self._grab_thread: threading.Thread | None = None
        self._infer_thread: threading.Thread | None = None
        self._cap_fps = 0.0

    def set_source(
        self,
        source: int | str,
        backend: int | None = None,
        label: str = "",
        *,
        path: str = "",
        name: str = "",
        device: CameraDevice | None = None,
    ) -> None:
        self._source = source
        self._backend = backend
        self._label = label or str(source)
        self._path = path
        self._name = name
        self._device = device
        self._usb = bool(device.is_usb) if device is not None else (
            "usb" in (label or "").lower() or "general" in (label or "").lower()
        )

    def stop(self) -> None:
        self._running = False

    def _confirm_fire(self, raw_fire: bool) -> bool:
        self._fire_votes.append(raw_fire)
        need = max(1, AppConfig.FIRE_CONFIRM_HITS)
        return sum(1 for v in self._fire_votes if v) >= need

    def _grab_loop(self, cap: cv2.VideoCapture) -> None:
        """Chỉ đọc camera — luôn giữ frame mới, bỏ frame cũ (anti-lag USB)."""
        t0 = time.perf_counter()
        n = 0
        while self._running:
            ok, frame = cap.read()
            if not ok or frame is None:
                try:
                    cap.grab()
                except Exception:
                    pass
                time.sleep(0.01)
                continue
            # BẮT BUỘC copy — OpenCV DSHOW hay tái sử dụng buffer → không copy = ảnh nhiễu/rác
            frame = frame.copy()
            with self._lock:
                self._latest = frame
                self._latest_id += 1
            n += 1
            now = time.perf_counter()
            if now - t0 >= 1.0:
                self._cap_fps = n / (now - t0)
                n = 0
                t0 = now
            # USB: nhường CPU một nhịp nhỏ để không starve AI/UI
            if self._usb:
                time.sleep(0.001)

    def _infer_loop(self) -> None:
        min_interval = 1.0 / max(
            1,
            AppConfig.USB_INFER_MAX_FPS if self._usb else AppConfig.INFER_MAX_FPS,
        )
        time.sleep(min_interval * 0.5 * self.camera_id)
        last_t = 0.0
        while self._running:
            now = time.perf_counter()
            wait = min_interval - (now - last_t)
            if wait > 0:
                time.sleep(wait)

            with self._lock:
                if self._latest is None or self._latest_id == self._infer_id:
                    time.sleep(0.008)
                    continue
                frame = self._latest.copy()
                fid = self._latest_id

            mean = float(frame.mean()) if frame.size else 0.0
            if mean < AppConfig.INFER_MIN_MEAN:
                with self._lock:
                    self._infer_id = fid
                last_t = time.perf_counter()
                continue

            dets: list[Detection] = []
            infer_ms = 0.0
            if self.detector.ready:
                with _INFER_LOCK:
                    if not self._running:
                        break
                    dets, infer_ms = self.detector.infer(frame)

            raw_fire = any(FireDetector.is_fire_label(d.label) for d in dets)
            fire = self._confirm_fire(raw_fire)
            with self._lock:
                self._dets = dets
                self._infer_ms = infer_ms
                self._fire = fire
                self._infer_id = fid
            last_t = time.perf_counter()

    def _open_cap(self):
        if self._device is not None:
            return open_device(self._device)
        if isinstance(self._source, int):
            return open_capture(
                self._source,
                preferred_backend=self._backend,
                path=self._path,
                name=self._name,
                usb_like=self._usb,
            )
        cap = cv2.VideoCapture(self._source)
        return cap if cap.isOpened() else None

    def run(self) -> None:
        self._running = True
        # Mở USB trước/sau: cam USB index>0 chờ nhẹ; laptop mở sau vẫn OK
        if self._usb:
            time.sleep(0.15)
        elif self.camera_id > 0:
            time.sleep(0.5)

        cap = self._open_cap()
        if cap is None or not cap.isOpened():
            self.status.emit(
                self.camera_id,
                f"Không mở được {self._label or self._source} — đóng Zoom/Teams, rút USB, Quét cam",
            )
            return

        mode = backend_status()
        kind = "USB" if self._usb else "Laptop"
        self.status.emit(self.camera_id, f"{self._label or self._source} OK · {kind}/{mode}")

        self._grab_thread = threading.Thread(
            target=self._grab_loop, args=(cap,), name=f"grab-cam-{self.camera_id}", daemon=True
        )
        self._infer_thread = threading.Thread(
            target=self._infer_loop, name=f"infer-cam-{self.camera_id}", daemon=True
        )
        self._grab_thread.start()
        self._infer_thread.start()

        preview_fps = AppConfig.USB_PREVIEW_MAX_FPS if self._usb else AppConfig.PREVIEW_MAX_FPS
        preview_interval = 1.0 / max(1, preview_fps)
        max_w = AppConfig.USB_PREVIEW_MAX_WIDTH if self._usb else AppConfig.PREVIEW_MAX_WIDTH
        last_emit = 0.0
        last_shown_id = -1

        while self._running:
            time.sleep(0.005)
            now = time.perf_counter()
            if now - last_emit < preview_interval:
                continue

            with self._lock:
                if self._latest is None or self._latest_id == last_shown_id:
                    continue
                frame = self._latest.copy()
                last_shown_id = self._latest_id
                dets = list(self._dets)
                infer_ms = self._infer_ms
                fire = self._fire
                fps = self._cap_fps

            shown = self.detector.draw(frame, dets, inplace=False) if dets else frame
            h, w = shown.shape[:2]
            if w > max_w:
                nh = int(h * (max_w / w))
                shown = cv2.resize(shown, (max_w, nh), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(shown, cv2.COLOR_BGR2RGB)
            last_emit = now
            self.frame_ready.emit(self.camera_id, rgb, dets, fps, infer_ms, fire)

        self._running = False
        if self._grab_thread is not None:
            self._grab_thread.join(timeout=1.5)
        if self._infer_thread is not None:
            self._infer_thread.join(timeout=2.0)
        self._grab_thread = None
        self._infer_thread = None
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
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        pix = QPixmap.fromImage(qimg).scaled(
            max(1, self.view.width()),
            max(1, self.view.height()),
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )
        self.view.setPixmap(pix)
        self.meta.setText(f"{fps:.0f} FPS · AI {infer_ms:.0f} ms · {backend}")
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
        low = text.lower()
        self.badge.setText("OFF" if ("không" in low) or ("dừng" in low) else "READY")
        self.badge.setObjectName("badge")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
