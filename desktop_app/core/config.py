from __future__ import annotations

import os
from pathlib import Path


def app_root() -> Path:
    if getattr(os.sys, "frozen", False):
        return Path(os.sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def _has_ov_model(folder: Path) -> bool:
    if not folder.exists():
        return False
    return any(folder.glob("*.xml")) and any(folder.glob("*.bin"))


def models_dir() -> Path:
    """Resolve model folder: beside EXE (if has xml) → bundled → beside EXE writable."""
    if getattr(os.sys, "frozen", False):
        beside = Path(os.sys.executable).resolve().parent / "models"
        bundled = app_root() / "models"
        if _has_ov_model(beside):
            return beside
        if _has_ov_model(bundled):
            return bundled
        if any(beside.glob("*.pt")):
            return beside
        if any(bundled.glob("*")):
            return bundled
        beside.mkdir(parents=True, exist_ok=True)
        return beside
    return app_root() / "models"


class AppConfig:
    APP_NAME = "Safety Remote Desktop"
    APP_VERSION = "1.0.7"

    DEFAULT_HOST = "192.168.4.1"
    WIFI_NAME = "Safety Remote"
    WIFI_PASSWORD = ""  # SoftAP mở — không mật khẩu
    DEFAULT_CHIP_ID = "888"

    MQTT_HOST = "mqtt.duynguyen.io.vn"
    MQTT_PORT = 443
    MQTT_PATH = "/mqtt"
    MQTT_USE_TLS = True

    POLL_MS = 1500
    REQUEST_TIMEOUT = 4.0

    CAMERA_0 = 0
    CAMERA_1 = 1
    # Laptop cam
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    CAMERA_FPS = 18
    # USB Shopee: 640x480 DEFAULT (không ép MJPG trước) — tránh ảnh nhiễu
    USB_CAMERA_WIDTH = 640
    USB_CAMERA_HEIGHT = 480
    USB_CAMERA_FPS = 15
    PREVIEW_MAX_FPS = 15
    USB_PREVIEW_MAX_FPS = 12
    INFER_MAX_FPS = 6
    USB_INFER_MAX_FPS = 4
    PREVIEW_MAX_WIDTH = 480
    USB_PREVIEW_MAX_WIDTH = 420
    # Ưu tiên GStreamer nếu OpenCV build có GST
    PREFER_GSTREAMER = True
    INFER_CONF = 0.30
    INFER_IOU = 0.45
    FIRE_CONFIRM_HITS = 2
    FIRE_CONFIRM_WINDOW = 3
    INFER_MIN_MEAN = 8.0
    OPENVINO_THREADS = 2

    MODEL_NAME = "yolov8n_fire"
    FIRE_CLASSES = {"fire", "smoke", "flame", "Fire", "Smoke", "Flame"}

    @staticmethod
    def topic_online(chip: str) -> str:
        return f"tele/{chip}/status"

    @staticmethod
    def topic_vitals(chip: str) -> str:
        return f"tele/{chip}_vitals/status"

    @staticmethod
    def topic_vision(chip: str) -> str:
        return f"tele/{chip}_vision/status"

    @staticmethod
    def cmnd_buzzer(chip: str) -> str:
        return f"cmnd/{chip}_buzzer/POWER"

    @staticmethod
    def cmnd_gps(chip: str) -> str:
        return f"cmnd/{chip}_gps/POWER"

    @staticmethod
    def cmnd_sms(chip: str) -> str:
        return f"cmnd/{chip}_sms/POWER"
