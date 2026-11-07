"""Enumerate + open laptop/USB webcams (GStreamer ưu tiên → DirectShow an toàn)."""
from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from core.config import AppConfig
from core.gst_capture import gstreamer_available, open_gstreamer


@dataclass(frozen=True)
class CameraDevice:
    index: int
    name: str
    backend: int = cv2.CAP_DSHOW
    path: str = ""

    @property
    def label(self) -> str:
        kind = _classify(self.name)
        return f"{kind} · {self.name}  [{self.index}]"

    @property
    def is_usb(self) -> bool:
        return _classify(self.name) == "USB"


def _classify(name: str) -> str:
    low = (name or "").lower()
    if any(k in low for k in ("integrated", "built-in", "builtin", "laptop", "facetime", "ir camera")):
        return "Laptop"
    if any(
        k in low
        for k in (
            "usb",
            "general",
            "logitech",
            "hd webcam",
            "external",
            "webcam",
            "720p",
            "1080p",
        )
    ):
        if "integrated" in low:
            return "Laptop"
        return "USB"
    return "Camera"


def _from_cv2_enumerate() -> list[CameraDevice]:
    try:
        from cv2_enumerate_cameras import enumerate_cameras
    except Exception:
        return []

    devices: list[CameraDevice] = []
    seen_names: set[str] = set()
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
        try:
            cams = list(enumerate_cameras(backend))
        except Exception:
            continue
        for cam in cams:
            idx = int(getattr(cam, "index", -1))
            name = str(getattr(cam, "name", "") or "").strip() or f"Camera {idx}"
            path = str(getattr(cam, "path", "") or "").strip()
            key = name.lower()
            if any(k in key for k in ("infrared", " ir", "ir camera", "metadata")):
                continue
            if key in seen_names or idx < 0:
                continue
            seen_names.add(key)
            devices.append(CameraDevice(index=idx, name=name, backend=backend, path=path))
        if devices:
            break
    return devices


def _probe_fallback(max_index: int = 6) -> list[CameraDevice]:
    found: list[CameraDevice] = []
    for i in range(max_index):
        cap = open_capture(i, preferred_backend=cv2.CAP_DSHOW, warm_reads=6, settle_s=0.1)
        if cap is None:
            continue
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            continue
        mean = float(frame.mean()) if frame.size else 0.0
        suffix = " (yếu/đen)" if mean < 5.0 else ""
        found.append(CameraDevice(index=i, name=f"Camera index {i}{suffix}", backend=cv2.CAP_DSHOW))
    return found


def list_cameras() -> list[CameraDevice]:
    devices = _from_cv2_enumerate()
    return devices if devices else _probe_fallback()


def _target_size(usb_like: bool) -> tuple[int, int, int]:
    if usb_like:
        return AppConfig.USB_CAMERA_WIDTH, AppConfig.USB_CAMERA_HEIGHT, AppConfig.USB_CAMERA_FPS
    return AppConfig.CAMERA_WIDTH, AppConfig.CAMERA_HEIGHT, AppConfig.CAMERA_FPS


def _frame_ok(frame: np.ndarray | None) -> bool:
    """Loại frame rác (ép MJPG sai → nhiễu màu)."""
    if frame is None or getattr(frame, "size", 0) == 0:
        return False
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = float(g.mean())
    std = float(g.std())
    lap = float(cv2.Laplacian(g, cv2.CV_64F).var())
    return 4.0 < mean < 250.0 and 3.0 < std < 95.0 and lap < 1200.0


def _try_open_dshow(
    source: int | str,
    backend: int,
    *,
    usb_like: bool,
    use_mjpg: bool,
    width: int,
    height: int,
    fps: int,
    warm_reads: int = 12,
    settle_s: float = 0.2,
) -> cv2.VideoCapture | None:
    cap = cv2.VideoCapture(source, backend)
    if not cap.isOpened():
        cap.release()
        return None
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    # Chỉ set MJPG khi cần — ép sai gây ảnh nhiễu như screenshot Camera B
    if use_mjpg:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    if settle_s > 0:
        time.sleep(settle_s)
    for _ in range(max(1, warm_reads)):
        ok, frame = cap.read()
        if ok and _frame_ok(frame):
            return cap
        time.sleep(0.03)
    cap.release()
    return None


def open_capture(
    index: int,
    preferred_backend: int | None = None,
    *,
    path: str = "",
    name: str = "",
    warm_reads: int = 12,
    settle_s: float = 0.15,
    usb_like: bool = False,
) -> cv2.VideoCapture | None:
    w, h, fps = _target_size(usb_like)

    if AppConfig.PREFER_GSTREAMER:
        gst = open_gstreamer(index, width=w, height=h, fps=fps, usb_like=usb_like)
        if gst is not None:
            return gst

    backends: list[int] = []
    order = (cv2.CAP_DSHOW, cv2.CAP_MSMF)
    if preferred_backend is not None:
        backends.append(preferred_backend)
    for b in order:
        if b not in backends:
            backends.append(b)

    sources: list[int | str] = [index]
    if name:
        sources.append(name)
    if path:
        sources.append(path)

    # USB: thử DEFAULT trước (an toàn), rồi MJPG; laptop: DEFAULT rồi MJPG
    attempts = [
        {"use_mjpg": False, "width": w, "height": h, "fps": fps},
        {"use_mjpg": True, "width": w, "height": h, "fps": fps},
    ]
    if usb_like:
        attempts.extend(
            [
                {"use_mjpg": False, "width": 320, "height": 240, "fps": 15},
                {"use_mjpg": True, "width": 320, "height": 240, "fps": 15},
                {"use_mjpg": False, "width": 640, "height": 480, "fps": 15},
            ]
        )

    seen: set[str] = set()
    for source in sources:
        key = f"{type(source).__name__}:{source}"
        if key in seen:
            continue
        seen.add(key)
        for backend in backends:
            for cfg in attempts:
                cap = _try_open_dshow(
                    source,
                    backend,
                    usb_like=usb_like,
                    warm_reads=warm_reads,
                    settle_s=settle_s,
                    **cfg,
                )
                if cap is not None:
                    return cap
    return None


def open_device(device: CameraDevice) -> cv2.VideoCapture | None:
    return open_capture(
        device.index,
        preferred_backend=cv2.CAP_DSHOW if device.is_usb else device.backend,
        path=device.path,
        name=device.name,
        warm_reads=15,
        settle_s=0.2 if device.is_usb else 0.1,
        usb_like=device.is_usb,
    )


def backend_status() -> str:
    return "GStreamer" if gstreamer_available() else "DirectShow"
