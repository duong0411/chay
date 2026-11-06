from __future__ import annotations

import json
import ssl
import threading
import time
from typing import Callable

import paho.mqtt.client as mqtt

from .config import AppConfig


MessageHandler = Callable[[str, object, str], None]


class MqttService:
    def __init__(self) -> None:
        self._client: mqtt.Client | None = None
        self._chip = AppConfig.DEFAULT_CHIP_ID
        self._connected = False
        self._handler: MessageHandler | None = None
        self._lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_handler(self, handler: MessageHandler | None) -> None:
        self._handler = handler

    def connect(self, chip_id: str) -> bool:
        self.disconnect()
        self._chip = (chip_id or AppConfig.DEFAULT_CHIP_ID).strip() or AppConfig.DEFAULT_CHIP_ID
        client_id = f"safety_desktop_{int(time.time() * 1000)}"

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            transport="websockets",
            protocol=mqtt.MQTTv311,
        )
        if AppConfig.MQTT_USE_TLS:
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            client.tls_insecure_set(False)
        client.ws_set_options(path=AppConfig.MQTT_PATH)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(min_delay=1, max_delay=30)

        try:
            client.connect(AppConfig.MQTT_HOST, AppConfig.MQTT_PORT, keepalive=60)
            client.loop_start()
            # Wait briefly for CONNACK
            for _ in range(40):
                if self._connected:
                    break
                time.sleep(0.1)
            if not self._connected:
                client.loop_stop()
                client.disconnect()
                return False
            self._client = client
            return True
        except Exception:
            try:
                client.loop_stop()
            except Exception:
                pass
            self._connected = False
            self._client = None
            return False

    def disconnect(self) -> None:
        with self._lock:
            client = self._client
            self._client = None
            self._connected = False
        if client is None:
            return
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass

    @property
    def chip_id(self) -> str:
        return self._chip

    def publish(self, topic: str, payload: str, retain: bool = False) -> None:
        client = self._client
        if not client or not self._connected:
            return
        client.publish(topic, payload, qos=1, retain=retain)

    def publish_vision_alert(
        self,
        *,
        fire: bool,
        label: str = "",
        cameras: str = "A,B",
        sound_buzzer: bool = True,
    ) -> bool:
        """Đẩy cảnh báo camera AI lên MQTT để điện thoại nhận."""
        if not self._connected:
            return False
        payload = json.dumps(
            {
                "fireAlert": fire,
                "gasAlert": False,
                "source": "desktop_ai",
                "label": label
                or ("Camera AI phát hiện lửa/khói" if fire else "Camera AI hết cảnh báo"),
                "cameras": cameras,
            },
            ensure_ascii=False,
        )
        self.publish(AppConfig.topic_vision(self._chip), payload, retain=True)
        # Bật còi trên mạch khi vừa phát hiện (edge do caller quyết định)
        if fire and sound_buzzer:
            self.publish(AppConfig.cmnd_buzzer(self._chip), "ON")
        return True

    def ensure_connected(self, chip_id: str | None = None) -> bool:
        chip = (chip_id or self._chip or AppConfig.DEFAULT_CHIP_ID).strip()
        if self._connected and self._chip == chip:
            return True
        return self.connect(chip)

    def toggle_buzzer(self) -> None:
        self.publish(AppConfig.cmnd_buzzer(self._chip), "TOGGLE")

    def toggle_gps(self) -> None:
        self.publish(AppConfig.cmnd_gps(self._chip), "TOGGLE")

    def send_test_sms(self) -> None:
        self.publish(AppConfig.cmnd_sms(self._chip), "ON")

    def _on_connect(self, client: mqtt.Client, *_args) -> None:
        self._connected = True
        topics = [
            (AppConfig.topic_online(self._chip), 1),
            (AppConfig.topic_vitals(self._chip), 1),
            (AppConfig.topic_vision(self._chip), 1),
        ]
        client.subscribe(topics)

    def _on_disconnect(self, *_args) -> None:
        self._connected = False

    def _on_message(self, _client, _userdata, msg: mqtt.MQTTMessage) -> None:
        raw = msg.payload.decode("utf-8", errors="replace")
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, dict) and "value" in decoded:
                value = decoded["value"]
            else:
                value = decoded
        except json.JSONDecodeError:
            value = raw.strip()
        if self._handler:
            self._handler(msg.topic, value, raw)
