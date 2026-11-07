from __future__ import annotations

import json
import time
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ai.fire_detector import FireDetector
from core.camera_enum import CameraDevice, backend_status, list_cameras
from core.config import AppConfig
from core.device_api import DeviceApi, DeviceException
from core.models import DeviceSnapshot
from core.mqtt_client import MqttService
from .camera_widget import CameraPanel, CameraWorker
from .styles import THEME, COLORS
from .widgets import AlarmBanner, GradientBackground, InfoCard, LiveDot, MetricTile


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{AppConfig.APP_NAME}  ·  v{AppConfig.APP_VERSION}")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(THEME)

        self.api = DeviceApi()
        self.mqtt = MqttService()
        self.mqtt.set_handler(self._on_mqtt)
        self.detector = FireDetector()
        self.mode = "mqtt"
        self.live = False
        self.data: Optional[DeviceSnapshot] = None
        self.chip = AppConfig.DEFAULT_CHIP_ID
        self.host = AppConfig.DEFAULT_HOST
        self._vision_fire = False
        self._vision_published = False
        self._workers: list[CameraWorker] = []

        self._build_ui()
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._poll_local)
        self._alarm_blink = QTimer(self)
        self._alarm_blink.timeout.connect(self._blink_alarm)
        self._blink_on = False

        self._refresh_ai_badge()

    # ── UI ────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = GradientBackground()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 18, 22, 12)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_connect_bar())
        self.alarm = AlarmBanner()
        outer.addWidget(self.alarm)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(10)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_left_panel())
        split.addWidget(self._build_camera_panel())
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 6)
        outer.addWidget(split, 1)

        bar = QStatusBar()
        self.setStatusBar(bar)
        self.status_label = QLabel("Chưa kết nối thiết bị")
        bar.addWidget(self.status_label, 1)
        self.ai_status = QLabel("")
        bar.addPermanentWidget(self.ai_status)

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        col = QVBoxLayout()
        brand = QLabel("SAFETY REMOTE")
        brand.setObjectName("brand")
        sub = QLabel("Giám sát cháy · gas · GPS  ·  AI Camera OpenVINO")
        sub.setObjectName("subtitle")
        col.addWidget(brand)
        col.addWidget(sub)
        row.addLayout(col, 1)

        live_wrap = QHBoxLayout()
        self.live_dot = LiveDot()
        self.live_text = QLabel("Offline")
        self.live_text.setObjectName("muted")
        live_wrap.addWidget(self.live_dot)
        live_wrap.addWidget(self.live_text)
        live_wrap.addSpacing(12)
        row.addLayout(live_wrap)
        return row

    def _build_connect_bar(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.mode_box = QComboBox()
        self.mode_box.addItem("Từ xa (MQTT)", "mqtt")
        self.mode_box.addItem("Gần máy (SoftAP)", "local")
        self.mode_box.setMinimumWidth(180)
        self.mode_box.currentIndexChanged.connect(self._on_mode_changed)

        self.input = QLineEdit(AppConfig.DEFAULT_CHIP_ID)
        self.input.setPlaceholderText("Chip ID hoặc IP")
        self.input.setMinimumWidth(160)

        self.btn_connect = QPushButton("Kết nối")
        self.btn_connect.setObjectName("primary")
        self.btn_connect.clicked.connect(self.connect_device)

        self.btn_disconnect = QPushButton("Ngắt")
        self.btn_disconnect.setObjectName("ghost")
        self.btn_disconnect.clicked.connect(self.disconnect_device)

        self.btn_cam = QPushButton("Bật 2 Camera AI")
        self.btn_cam.setObjectName("cyan")
        self.btn_cam.clicked.connect(self.toggle_cameras)

        self.btn_refresh_cams = QPushButton("Quét cam")
        self.btn_refresh_cams.setObjectName("ghost")
        self.btn_refresh_cams.setToolTip("Quét lại webcam laptop / camera USB vừa cắm")
        self.btn_refresh_cams.clicked.connect(self.refresh_camera_list)

        self.cam0 = QComboBox()
        self.cam1 = QComboBox()
        self.cam0.setMinimumWidth(220)
        self.cam1.setMinimumWidth(220)
        self._camera_devices: list[CameraDevice] = []
        self.refresh_camera_list()

        layout.addWidget(self.mode_box)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.btn_connect)
        layout.addWidget(self.btn_disconnect)
        layout.addSpacing(8)
        layout.addWidget(QLabel("CAM A"))
        layout.addWidget(self.cam0)
        layout.addWidget(QLabel("CAM B"))
        layout.addWidget(self.cam1)
        layout.addWidget(self.btn_refresh_cams)
        layout.addWidget(self.btn_cam)
        return bar

    def _build_left_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setSpacing(10)
        self.metric_volt = MetricTile("Nguồn 12V", "⚡")
        self.metric_temp = MetricTile("Nhiệt / ẩm", "°C")
        self.metric_gas = MetricTile("Gas / Khói", "☁")
        self.metric_fire = MetricTile("Báo cháy", "🔥")
        grid.addWidget(self.metric_volt, 0, 0)
        grid.addWidget(self.metric_temp, 0, 1)
        grid.addWidget(self.metric_gas, 1, 0)
        grid.addWidget(self.metric_fire, 1, 1)
        layout.addLayout(grid)

        self.gps_card = InfoCard("SIM 4G & GPS")
        self.sms_card = InfoCard("SMS cảnh báo")
        layout.addWidget(self.gps_card)
        layout.addWidget(self.sms_card)

        actions = QHBoxLayout()
        self.btn_buzzer = QPushButton("Còi: —")
        self.btn_gps = QPushButton("SIM/GPS")
        self.btn_sms = QPushButton("SMS test")
        self.btn_buzzer.setObjectName("primary")
        self.btn_gps.setObjectName("cyan")
        self.btn_sms.setObjectName("ghost")
        self.btn_buzzer.clicked.connect(self._toggle_buzzer)
        self.btn_gps.clicked.connect(self._toggle_gps)
        self.btn_sms.clicked.connect(self._send_sms)
        actions.addWidget(self.btn_buzzer)
        actions.addWidget(self.btn_gps)
        actions.addWidget(self.btn_sms)
        layout.addLayout(actions)

        self.wifi_line = QLabel("Wi‑Fi · chờ dữ liệu")
        self.wifi_line.setObjectName("muted")
        layout.addWidget(self.wifi_line)
        layout.addStretch(1)

        scroll.setWidget(wrap)
        return scroll

    def _build_camera_panel(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        t = QLabel("AI CAMERA · NHẬN DIỆN CHÁY")
        t.setObjectName("metricLabel")
        self.ai_badge = QLabel("MODEL")
        self.ai_badge.setObjectName("badge")
        title_row.addWidget(t)
        title_row.addStretch(1)
        title_row.addWidget(self.ai_badge)
        layout.addLayout(title_row)

        conf_row = QHBoxLayout()
        conf_row.setSpacing(10)
        conf_lbl = QLabel("Confidence")
        conf_lbl.setObjectName("muted")
        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setMinimum(10)
        self.conf_slider.setMaximum(90)
        self.conf_slider.setSingleStep(1)
        self.conf_slider.setPageStep(5)
        self.conf_slider.setValue(int(round(AppConfig.INFER_CONF * 100)))
        self.conf_slider.setMinimumWidth(160)
        self.conf_slider.setToolTip("Ngưỡng phát hiện lửa/khói — thấp = nhạy hơn, cao = ít báo nhầm")
        self.conf_value = QLabel(f"{self.conf_slider.value()}%")
        self.conf_value.setObjectName("badge")
        self.conf_value.setMinimumWidth(48)
        self.conf_value.setAlignment(Qt.AlignCenter)
        self.conf_slider.valueChanged.connect(self._on_conf_changed)
        conf_row.addWidget(conf_lbl)
        conf_row.addWidget(self.conf_slider, 1)
        conf_row.addWidget(self.conf_value)
        layout.addLayout(conf_row)

        self.cam_panel_0 = CameraPanel("Camera A", 0)
        self.cam_panel_1 = CameraPanel("Camera B", 1)
        layout.addWidget(self.cam_panel_0, 1)
        layout.addWidget(self.cam_panel_1, 1)
        return box

    # ── Connect ───────────────────────────────────────────────────────
    def _on_mode_changed(self) -> None:
        mode = self.mode_box.currentData()
        if mode == "mqtt":
            self.input.setText(self.chip or AppConfig.DEFAULT_CHIP_ID)
            self.input.setPlaceholderText("Chip ID")
        else:
            self.input.setText(self.host or AppConfig.DEFAULT_HOST)
            self.input.setPlaceholderText("IP SoftAP 192.168.4.8")

    def connect_device(self) -> None:
        mode = self.mode_box.currentData()
        raw = self.input.text().strip()
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("Đang vào...")
        try:
            if mode == "mqtt":
                chip = raw or AppConfig.DEFAULT_CHIP_ID
                ok = self.mqtt.connect(chip)
                if not ok:
                    raise DeviceException("Không vào được broker MQTT. Kiểm tra Internet.")
                self.mode = "mqtt"
                self.chip = chip
                self.live = False
                self._set_status(f"MQTT OK · chờ chip {chip} online...")
                self._poll.stop()
            else:
                host = raw or AppConfig.DEFAULT_HOST
                snap = self.api.fetch_sensors(host)
                self.mode = "local"
                self.host = host
                self.mqtt.disconnect()
                self.data = snap
                self.live = True
                self._apply_snapshot(snap)
                self._set_status(f"Gần máy · {host}")
                self._poll.start(AppConfig.POLL_MS)
            self.live_dot.set_live(self.live)
            self.live_text.setText("Live" if self.live else "Chờ dữ liệu")
        except DeviceException as e:
            QMessageBox.warning(self, "Kết nối", str(e))
            self._set_status(str(e))
        finally:
            self.btn_connect.setEnabled(True)
            self.btn_connect.setText("Kết nối")

    def disconnect_device(self) -> None:
        self._poll.stop()
        self.mqtt.disconnect()
        self.live = False
        self.data = None
        self.live_dot.set_live(False)
        self.live_text.setText("Offline")
        self.alarm.set_state(False, "")
        self._set_status("Đã ngắt kết nối")

    def _poll_local(self) -> None:
        if self.mode != "local":
            return
        try:
            snap = self.api.fetch_sensors(self.host)
            self.live = True
            self._apply_snapshot(snap)
            self._set_status(f"Gần máy · {self.host}")
        except DeviceException as e:
            self.live = False
            self.live_dot.set_live(False)
            self._set_status(str(e))

    def _on_mqtt(self, topic: str, value, raw: str) -> None:
        # Called from MQTT thread — marshal to UI thread
        QTimer.singleShot(0, lambda: self._handle_mqtt(topic, value, raw))

    def _handle_mqtt(self, topic: str, value, raw: str) -> None:
        if topic.endswith("/status") and "_vitals" not in topic:
            online = str(value).lower() == "online"
            self.live = online or self.data is not None
            self.live_dot.set_live(self.live)
            self.live_text.setText("Live" if self.live else "Offline")
            self._set_status(
                f"Từ xa · chip {self.chip} online" if online else f"Chip {self.chip} offline"
            )
            return
        if "_vitals" in topic:
            try:
                if isinstance(value, dict):
                    data = value
                else:
                    data = json.loads(raw)
                snap = DeviceSnapshot.from_json(data)
                self.live = True
                self.live_dot.set_live(True)
                self.live_text.setText("Live")
                self._apply_snapshot(snap)
                self._set_status(f"Từ xa · chip {self.chip}")
            except Exception as e:
                self._set_status(f"Lỗi vitals: {e}")

    def _apply_snapshot(self, snap: DeviceSnapshot) -> None:
        snap.vision_fire = self._vision_fire
        snap.vision_label = "Camera AI phát hiện lửa" if self._vision_fire else ""
        self.data = snap

        self.metric_volt.set_value(
            f"{snap.volt:.2f}",
            "V",
            "Ổn định" if snap.volt >= 11.2 else "Điện áp thấp",
            alert=snap.volt < 11.2,
        )
        if snap.sht_ok:
            self.metric_temp.set_value(
                f"{snap.temp:.1f}",
                "°C",
                f"{snap.hum:.1f} %RH",
                alert=snap.temp > 40,
            )
        else:
            self.metric_temp.set_value("LỖI", "", "Lỗi I2C SHT31", alert=True)

        self.metric_gas.set_value(
            str(snap.gas),
            "",
            "CẢNH BÁO" if snap.gas_alert else "An toàn · /4095",
            alert=snap.gas_alert,
        )
        fire_txt = "CHÁY" if (snap.fire_alert or snap.vision_fire) else "OK"
        fire_detail = "GPIO26"
        if snap.vision_fire:
            fire_detail += " · AI Camera"
        self.metric_fire.set_value(
            fire_txt,
            "",
            fire_detail,
            alert=snap.fire_alert or snap.vision_fire,
        )

        gnss = snap.gps_gnss or "--"
        self.gps_card.set_badge(
            "FIX" if "FIX" in gnss.upper() else ("ON" if snap.gps_power else "TẮT"),
            "ok" if snap.gps_power else "warn",
        )
        self.gps_card.set_body(
            f"GNSS: {gnss}\nVĩ độ: {snap.gps_lat}\nKinh độ: {snap.gps_lon}"
        )
        self.sms_card.set_badge(snap.sms_status[:18], "ok" if "Thành" in snap.sms_status else "cyan")
        self.sms_card.set_body(
            f"Số nhận: {snap.sms_to or '--'}\n"
            f"{snap.sms_result or '--'}\n"
            f"OK {snap.sms_sent_count} · Lỗi {snap.sms_fail_count}"
            + (f" · {snap.sms_age_sec}s trước" if snap.sms_age_sec else "")
        )
        self.btn_buzzer.setText("Còi: BẬT" if snap.buzzer else "Còi: TẮT")
        self.wifi_line.setText(
            f"Wi‑Fi CH{snap.wifi_channel} · {snap.wifi_tx_dbm:.1f} dBm · {snap.wifi_clients} ĐT"
        )
        self.alarm.set_state(snap.alarm_active, snap.alarm_label)
        if snap.alarm_active and not self._alarm_blink.isActive():
            self._alarm_blink.start(500)
        if not snap.alarm_active:
            self._alarm_blink.stop()
            self._blink_on = False

    def _blink_alarm(self) -> None:
        self._blink_on = not self._blink_on
        if self._blink_on:
            self.alarm.setStyleSheet(
                f"QFrame#panelAlert {{ background: rgba(255,42,95,55);"
                f"border: 1px solid {COLORS['pulse']}; border-radius: 18px; }}"
            )
        else:
            self.alarm.setStyleSheet("")
            self.alarm.style().unpolish(self.alarm)
            self.alarm.style().polish(self.alarm)

    # ── Commands ──────────────────────────────────────────────────────
    def _toggle_buzzer(self) -> None:
        try:
            if self.mode == "mqtt":
                self.mqtt.toggle_buzzer()
            else:
                self.api.toggle_buzzer(self.host)
                self._poll_local()
        except DeviceException as e:
            QMessageBox.warning(self, "Còi", str(e))

    def _toggle_gps(self) -> None:
        try:
            if self.mode == "mqtt":
                self.mqtt.toggle_gps()
            else:
                self.api.toggle_gps(self.host)
                self._poll_local()
        except DeviceException as e:
            QMessageBox.warning(self, "GPS", str(e))

    def _send_sms(self) -> None:
        try:
            if self.mode == "mqtt":
                self.mqtt.send_test_sms()
            else:
                res = self.api.send_test_sms(self.host)
                if res.get("success") is False:
                    raise DeviceException(str(res.get("error") or "Không gửi được SMS"))
                self._poll_local()
            self._set_status("Đã xếp hàng SMS test")
        except DeviceException as e:
            QMessageBox.warning(self, "SMS", str(e))

    # ── Cameras ───────────────────────────────────────────────────────
    def refresh_camera_list(self) -> None:
        """Populate Cam A/B with laptop webcam + USB camera friendly names."""
        prev0 = self.cam0.currentData()
        prev1 = self.cam1.currentData()
        self._camera_devices = list_cameras()
        self.cam0.blockSignals(True)
        self.cam1.blockSignals(True)
        self.cam0.clear()
        self.cam1.clear()
        if not self._camera_devices:
            self.cam0.addItem("Không thấy camera", None)
            self.cam1.addItem("Không thấy camera", None)
            self.cam0.blockSignals(False)
            self.cam1.blockSignals(False)
            self._set_status("Không thấy camera — cắm USB rồi bấm Quét cam")
            return

        for dev in self._camera_devices:
            self.cam0.addItem(dev.label, dev.index)
            self.cam1.addItem(dev.label, dev.index)

        # Prefer distinct devices: Cam A = first, Cam B = second (laptop+USB or 2 USB)
        def _select(box: QComboBox, prefer, fallback: int) -> None:
            if prefer is not None:
                i = box.findData(prefer)
                if i >= 0:
                    box.setCurrentIndex(i)
                    return
            box.setCurrentIndex(min(fallback, box.count() - 1))

        _select(self.cam0, prev0, 0)
        _select(self.cam1, prev1, 1 if len(self._camera_devices) > 1 else 0)
        # If both still same after restore, force Cam B to next device
        if self.cam0.currentData() == self.cam1.currentData() and len(self._camera_devices) > 1:
            self.cam1.setCurrentIndex(1 if self.cam0.currentIndex() == 0 else 0)

        self.cam0.blockSignals(False)
        self.cam1.blockSignals(False)
        names = ", ".join(d.name for d in self._camera_devices)
        self._set_status(f"Đã quét {len(self._camera_devices)} camera: {names}")

    def _device_for_index(self, index: int | None) -> CameraDevice | None:
        if index is None:
            return None
        for d in self._camera_devices:
            if d.index == index:
                return d
        return None

    def toggle_cameras(self) -> None:
        if self._workers:
            self._stop_cameras()
            self.btn_cam.setText("Bật 2 Camera AI")
            return
        self._start_cameras()
        self.btn_cam.setText("Tắt Camera")

    def _start_cameras(self) -> None:
        self._stop_cameras()
        if not self._camera_devices:
            self.refresh_camera_list()
        src0 = self.cam0.currentData()
        src1 = self.cam1.currentData()
        if src0 is None or src1 is None:
            QMessageBox.warning(
                self,
                "Camera",
                "Chưa có camera.\nCắm webcam laptop / USB rồi bấm Quét cam.",
            )
            return
        if src0 == src1:
            QMessageBox.warning(
                self,
                "Camera",
                "Cam A và Cam B đang chọn cùng một thiết bị.\n"
                "Hãy chọn 1 webcam laptop + 1 USB, hoặc 2 camera USB khác nhau.",
            )
            return

        # MQTT bắt buộc để đẩy cảnh báo AI sang điện thoại (broker duynguyen)
        chip = self.input.text().strip() if self.mode_box.currentData() == "mqtt" else self.chip
        chip = chip or self.chip or AppConfig.DEFAULT_CHIP_ID
        self.chip = chip
        if not self.mqtt.ensure_connected(chip):
            QMessageBox.warning(
                self,
                "MQTT",
                "Không kết nối được mqtt.duynguyen.io.vn — camera vẫn chạy local,\n"
                "nhưng điện thoại sẽ KHÔNG nhận cảnh báo AI.\n"
                "Kiểm tra Internet / Chip ID rồi thử lại.",
            )
        else:
            self._set_status(f"Camera AI · MQTT chip {chip} sẵn sàng đẩy cảnh báo về ĐT")

        sources = [src0, src1]
        panels = [self.cam_panel_0, self.cam_panel_1]
        # Mở USB trước laptop — giảm tranh bandwidth / driver trên Windows
        order = sorted(
            range(len(sources)),
            key=lambda i: (0 if (self._device_for_index(sources[i]) and self._device_for_index(sources[i]).is_usb) else 1, i),
        )
        pending: list[CameraWorker | None] = [None, None]
        for idx in order:
            src = sources[idx]
            dev = self._device_for_index(src)
            label = dev.label if dev else f"Camera {src}"
            det = FireDetector(conf=self._current_conf())
            worker = CameraWorker(idx, det)
            worker.set_source(
                src,
                backend=dev.backend if dev else None,
                label=label,
                path=dev.path if dev else "",
                name=dev.name if dev else "",
                device=dev,
            )
            worker.frame_ready.connect(self._on_frame, Qt.QueuedConnection)
            worker.status.connect(self._on_cam_status, Qt.QueuedConnection)
            worker.start()
            pending[idx] = worker
            panels[idx].set_status(f"Đang mở {label}...")
            if dev and dev.is_usb:
                time.sleep(0.35)
        self._workers = [w for w in pending if w is not None]

    def _stop_cameras(self) -> None:
        for w in self._workers:
            w.stop()
            w.wait(1500)
        self._workers.clear()
        if self._vision_fire or self._vision_published:
            self._publish_vision_to_phone(False)
        self._vision_fire = False
        self._vision_published = False
        self.cam_panel_0._fire = False
        self.cam_panel_1._fire = False
        self._refresh_vision_alarm(False)

    def _publish_vision_to_phone(self, fire: bool) -> None:
        """MQTT WSS → tele/{chip}_vision/status → app mobile cảnh báo."""
        ok = self.mqtt.publish_vision_alert(
            fire=fire,
            label="Camera AI laptop phát hiện lửa/khói" if fire else "Camera AI hết cảnh báo",
            cameras="A,B",
            sound_buzzer=fire,
        )
        self._vision_published = fire
        if ok:
            self._set_status(
                "Đã gửi cảnh báo AI → điện thoại (MQTT duynguyen)"
                if fire
                else "Đã gửi hết cảnh báo AI → điện thoại"
            )
        else:
            self._set_status(
                "Camera AI cháy nhưng MQTT chưa kết nối — ĐT không nhận được"
                if fire
                else "Hết cảnh báo AI (MQTT chưa kết nối)"
            )

    def _refresh_vision_alarm(self, any_fire: bool) -> None:
        """Bật/tắt banner + tile cháy theo AI; tôn trọng cảnh báo gas/GPIO nếu đang có."""
        if self.data:
            self._apply_snapshot(self.data)
            return
        # Chỉ chạy camera AI, chưa có dữ liệu thiết bị
        if any_fire:
            self.alarm.set_state(True, "Camera AI phát hiện lửa/khói")
            self.metric_fire.set_value("CHÁY", "", "AI Camera", alert=True)
            if not self._alarm_blink.isActive():
                self._alarm_blink.start(500)
        else:
            self.alarm.set_state(False, "")
            self.metric_fire.set_value("OK", "", "AI Camera", alert=False)
            self._alarm_blink.stop()
            self._blink_on = False
            self.alarm.setStyleSheet("")
            self.alarm.style().unpolish(self.alarm)
            self.alarm.style().polish(self.alarm)

    def _on_frame(self, cam_id: int, rgb, dets, fps: float, infer_ms: float, fire: bool) -> None:
        panel = self.cam_panel_0 if cam_id == 0 else self.cam_panel_1
        backend = self.detector.backend
        if cam_id < len(self._workers):
            backend = self._workers[cam_id].detector.backend or backend
        panel.show_frame(rgb, fps, infer_ms, fire, backend)
        # keep last flags on panels
        if cam_id == 0:
            self.cam_panel_0._fire = fire
        else:
            self.cam_panel_1._fire = fire
        any_fire = bool(self.cam_panel_0._fire or self.cam_panel_1._fire)
        if any_fire != self._vision_fire:
            self._vision_fire = any_fire
            self._publish_vision_to_phone(any_fire)
            self._refresh_vision_alarm(any_fire)

    def _on_cam_status(self, cam_id: int, text: str) -> None:
        panel = self.cam_panel_0 if cam_id == 0 else self.cam_panel_1
        panel.set_status(text)
        self._set_status(text)

    def _current_conf(self) -> float:
        if hasattr(self, "conf_slider"):
            return max(0.05, min(0.95, self.conf_slider.value() / 100.0))
        return AppConfig.INFER_CONF

    def _on_conf_changed(self, value: int) -> None:
        conf = max(0.05, min(0.95, value / 100.0))
        if hasattr(self, "conf_value"):
            self.conf_value.setText(f"{value}%")
        self.detector.conf = conf
        for w in self._workers:
            w.detector.conf = conf
        self._set_status(f"Confidence AI = {value}% ({'nhạy' if value < 40 else 'cân bằng' if value < 60 else 'chặt'})")

    def _refresh_ai_badge(self) -> None:
        if self.detector.ready:
            self.ai_badge.setText(f"AI · {self.detector.backend.upper()}")
            self.ai_badge.setObjectName("badgeOk")
            self.ai_status.setText(
                f"Model sẵn sàng ({self.detector.backend}) · Cam {backend_status()}"
            )
        else:
            self.ai_badge.setText("NO MODEL")
            self.ai_badge.setObjectName("badgeWarn")
            self.ai_status.setText(self.detector.error or "Chưa có model YOLO")
        self.ai_badge.style().unpolish(self.ai_badge)
        self.ai_badge.style().polish(self.ai_badge)
        if hasattr(self, "conf_slider"):
            self._on_conf_changed(self.conf_slider.value())

    def _set_status(self, text: str) -> None:
        if hasattr(self, "status_label") and self.status_label is not None:
            self.status_label.setText(text)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_cameras()
        self.mqtt.disconnect()
        self._poll.stop()
        super().closeEvent(event)
