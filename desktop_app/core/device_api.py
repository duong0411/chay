from __future__ import annotations

import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import AppConfig
from .models import DeviceSnapshot


class DeviceException(Exception):
    pass


class DeviceApi:
    def __init__(self, timeout: float = AppConfig.REQUEST_TIMEOUT) -> None:
        self.timeout = timeout

    def _uri(self, host: str, path: str) -> str:
        cleaned = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
        if not cleaned:
            cleaned = AppConfig.DEFAULT_HOST
        return f"http://{cleaned}{path}"

    def _get(self, host: str, path: str) -> dict[str, Any]:
        url = self._uri(host, path)
        try:
            req = Request(url, headers={"User-Agent": "SafetyRemoteDesktop/1.0"})
            with urlopen(req, timeout=self.timeout) as res:
                body = res.read().decode("utf-8", errors="replace")
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise DeviceException("Máy trả về dữ liệu không đọc được.")
                return data
        except TimeoutError as e:
            raise DeviceException(
                f"Máy {host} không phản hồi. Kiểm tra Wi‑Fi {AppConfig.WIFI_NAME}."
            ) from e
        except (URLError, OSError, json.JSONDecodeError) as e:
            raise DeviceException(
                f"Không kết nối được {host}. Bật thiết bị và vào Wi‑Fi {AppConfig.WIFI_NAME}."
            ) from e

    def fetch_sensors(self, host: str) -> DeviceSnapshot:
        return DeviceSnapshot.from_json(self._get(host, "/api/sensors"))

    def toggle_buzzer(self, host: str) -> dict[str, Any]:
        return self._get(host, "/api/toggleBuzzer")

    def toggle_gps(self, host: str) -> dict[str, Any]:
        return self._get(host, "/api/toggleGps")

    def send_test_sms(self, host: str) -> dict[str, Any]:
        return self._get(host, "/api/sendTestSms")
