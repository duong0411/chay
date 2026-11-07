from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _d(v: Any, fallback: float = 0.0) -> float:
    try:
        if v is None:
            return fallback
        return float(v)
    except (TypeError, ValueError):
        return fallback


def _i(v: Any, fallback: int = 0) -> int:
    try:
        if v is None:
            return fallback
        return int(float(v))
    except (TypeError, ValueError):
        return fallback


def _b(v: Any) -> bool:
    return v is True or v == 1 or str(v).lower() == "true"


@dataclass
class DeviceSnapshot:
    temp: float = -999.0
    hum: float = 0.0
    volt: float = 0.0
    gas: int = 0
    gas_alert: bool = False
    fire_alert: bool = False
    buzzer: bool = False
    gps_power: bool = False
    gps_gnss: str = ""
    gps_lat: str = "--"
    gps_lon: str = "--"
    sms_to: str = ""
    sms_status: str = "Chưa gửi"
    sms_text: str = ""
    sms_result: str = ""
    sms_sending: bool = False
    sms_sent_count: int = 0
    sms_fail_count: int = 0
    sms_age_sec: int = 0
    wifi_clients: int = 0
    wifi_tx_dbm: float = 0.0
    wifi_channel: int = 1
    vision_fire: bool = False
    vision_label: str = ""

    @property
    def sht_ok(self) -> bool:
        return self.temp > -900

    @property
    def blaze_alert(self) -> bool:
        return self.fire_alert or self.vision_fire

    @property
    def alarm_active(self) -> bool:
        return self.gas_alert or self.blaze_alert

    @property
    def alarm_label(self) -> str:
        # Khói → Có khói · Camera/GPIO lửa → Báo cháy · Cả hai → Hỏa hoạn cháy to
        if self.gas_alert and self.blaze_alert:
            return "Hỏa hoạn cháy to"
        if self.blaze_alert:
            return "Báo cháy"
        if self.gas_alert:
            return "Có khói"
        return "An toàn"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "DeviceSnapshot":
        return cls(
            temp=_d(data.get("temp"), -999.0),
            hum=_d(data.get("hum")),
            volt=_d(data.get("volt")),
            gas=_i(data.get("gas")),
            gas_alert=_b(data.get("gasAlert")),
            fire_alert=_b(data.get("fireAlert")),
            buzzer=_b(data.get("buzzer")),
            gps_power=_b(data.get("gpsPower")),
            gps_gnss=str(data.get("gpsGnss") or ""),
            gps_lat=str(data.get("gpsLat") or "--"),
            gps_lon=str(data.get("gpsLon") or "--"),
            sms_to=str(data.get("smsTo") or ""),
            sms_status=str(data.get("smsStatus") or "Chưa gửi"),
            sms_text=str(data.get("smsText") or ""),
            sms_result=str(data.get("smsResult") or ""),
            sms_sending=_b(data.get("smsSending")),
            sms_sent_count=_i(data.get("smsSentCount")),
            sms_fail_count=_i(data.get("smsFailCount")),
            sms_age_sec=_i(data.get("smsAgeSec")),
            wifi_clients=_i(data.get("wifiClients")),
            wifi_tx_dbm=_d(data.get("wifiTxDbm")),
            wifi_channel=_i(data.get("wifiChannel"), 1),
        )


@dataclass
class Detection:
    label: str
    conf: float
    xyxy: tuple[int, int, int, int]


@dataclass
class CameraResult:
    camera_id: int
    frame_bgr: Any = None
    detections: list[Detection] = field(default_factory=list)
    fps: float = 0.0
    infer_ms: float = 0.0
    fire_detected: bool = False
