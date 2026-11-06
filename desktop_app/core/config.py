from __future__ import annotations

import os
from pathlib import Path


def app_root() -> Path:
    if getattr(os.sys, "frozen", False):
        return Path(os.sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def models_dir() -> Path:
    # Prefer writable models next to EXE when frozen
    if getattr(os.sys, "frozen", False):
        base = Path(os.sys.executable).resolve().parent / "models"
        base.mkdir(parents=True, exist_ok=True)
        bundled = app_root() / "models"
        return base if any(base.glob("*")) or not bundled.exists() else bundled
    return app_root() / "models"


class AppConfig:
    APP_NAME = "Safety Remote Desktop"
    APP_VERSION = "1.0.0"

    DEFAULT_HOST = "192.168.4.8"
    WIFI_NAME = "Safety Remote"
    WIFI_PASSWORD = "1234567890"
    DEFAULT_CHIP_ID = "888"

    MQTT_HOST = "mqtt.duynguyen.io.vn"
    MQTT_PORT = 443
    MQTT_PATH = "/mqtt"
    MQTT_USE_TLS = True

    POLL_MS = 1500
    REQUEST_TIMEOUT = 4.0

    CAMERA_0 = 0
    CAMERA_1 = 1
    CAMERA_WIDTH = 640
    CAMERA_HEIGHT = 480
    INFER_CONF = 0.35
    INFER_IOU = 0.45

    # YOLOv8n fire/smoke (Roboflow / community) — converted to OpenVINO
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
        """AI camera fire alert → mobile app (cùng broker duynguyen)."""
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
