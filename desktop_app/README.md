# Safety Remote Desktop (Windows · PyQt5)

Giao diện laptop giám sát mạch **Safety Remote** + **2 camera AI nhận diện cháy** (YOLO → OpenVINO).

## Giao diện

- Theme tối industrial (đồng bộ app mobile): cyan / đỏ cảnh báo / xanh an toàn
- Tile cảm biến: 12V, nhiệt/ẩm, gas, cháy
- Banner cảnh báo nhấp nháy khi cháy / gas / AI phát hiện lửa
- GPS · SMS · điều khiển còi
- 2 khung camera live + FPS / ms / backend OpenVINO

## Chạy dev

```bat
cd desktop_app
py -3.12 -m pip install -r requirements.txt
py -3.12 ai\download_model.py
py -3.12 main.py
```

## Kết nối thiết bị

| Mode | Cách dùng |
|------|-----------|
| **Từ xa (MQTT)** | Chip ID (mặc định `888`), broker `wss://mqtt.duynguyen.io.vn/mqtt` |
| **Gần máy** | Vào Wi‑Fi `Safety Remote` / `1234567890` → IP `192.168.4.8` |

## Camera AI → cảnh báo điện thoại (MQTT)

**Có — dùng MQTT WSS broker `mqtt.duynguyen.io.vn`** (cùng mobile / ESP32).

```
Laptop camera YOLO phát hiện lửa
   → publish tele/{chip}_vision/status
   → mobile (MQTT + nền) nhận → notification
   → (tuỳ chọn) bật còi cmnd/{chip}_buzzer/POWER = ON
```

1. Chip ID trên desktop = Chip ID trên app ĐT (vd `888`)
2. Desktop có Internet → kết nối MQTT
3. Bật 2 Camera AI — khi có lửa, ĐT nhận cảnh báo ngay cả khi app ở nền

## Camera AI

1. Chọn **Cam A / Cam B** (máy bạn có 2 camera)
2. Bấm **Bật 2 Camera AI**
3. Model ưu tiên OpenVINO (`models/yolov8n_fire.xml` + `.bin`); fallback `.pt` qua Ultralytics

> Để nhận diện cháy tốt: thay `models/yolov8n_fire.pt` bằng weight YOLO đã train fire/smoke, rồi chạy lại `ai\download_model.py`.

## Đóng gói EXE (gửi khách)

```bat
build_exe.bat
```

File: `dist\SafetyRemoteDesktop.exe`
