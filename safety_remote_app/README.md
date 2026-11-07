# Safety Remote App

App Flutter giám sát mạch **Safety Remote**: nhiệt/ẩm, gas, cháy, GPS, SMS.

## Cảnh báo nền (kiểu Shopee)

Sau khi **Kết nối** (Gần máy hoặc MQTT):

1. App xin quyền thông báo
2. Android chạy **Foreground Service** — thanh thông báo: *"Safety Remote đang giám sát"*
3. Tắt / vuốt app khỏi recent: vẫn nhận MQTT/poll và **đẩy cảnh báo cháy/gas**
4. Nút **Test cảnh báo nền** trên màn hình chính để kiểm tra

> Android: hoạt động khi app bị đóng UI (không force-stop).  
> iOS: hạn chế nền của hệ thống; unsigned IPA build qua GitHub Actions; signed IPA cần Apple cert.

## Dùng

### Gần máy
1. Kết nối Wi‑Fi `Safety Remote` (không mật khẩu)
2. App → **Gần máy** → `192.168.4.1`

### Từ xa (MQTT)
1. Cấu hình Wi‑Fi nhà + Chip ID trên `http://192.168.4.1/`
2. App → **Từ xa** → Chip ID (mặc định `888`)

Broker: `wss://mqtt.duynguyen.io.vn/mqtt`

## Build

```bat
flutter pub get
flutter build apk --release
```

GitHub Actions (repo root): artifact APK + IPA unsigned sau mỗi push `main`.
