# chay — Safety Remote

ESP32 **Safety Remote** (cháy / gas / GPS / SMS) + app Flutter giám sát mobile.

## Phần cứng (firmware)

- ESP32-WROOM-32E
- SHT31 (nhiệt / ẩm)
- MQ-2 (gas / khói)
- Cảm biến cháy GPIO26
- Còi GPIO25
- EG800K LTE/GPS
- SoftAP `Safety Remote` / `1234567890` → `http://192.168.4.8`
- MQTT WSS: `mqtt.duynguyen.io.vn/mqtt`

Nạp `SafetyRemote.ino` (cần WebSockets Links2004 + MQTTPubSubClient).

## App mobile (`safety_remote_app`)

- Hiển thị: điện áp 12V, nhiệt/ẩm, gas, cháy, GPS, SMS
- **Cảnh báo nền kiểu Shopee**: Android Foreground Service giữ MQTT/poll khi tắt UI; notification ưu tiên cao khi cháy/gas
- Kết nối **Gần máy** (SoftAP) hoặc **Từ xa** (MQTT Chip ID, mặc định `888`)

### Chạy local

```bat
cd safety_remote_app
flutter pub get
flutter run
```

### Build APK local

```bat
flutter build apk --release
```

APK: `safety_remote_app/build/app/outputs/flutter-apk/app-release.apk`

## GitHub Actions

Workflow [`.github/workflows/build-mobile.yml`](.github/workflows/build-mobile.yml):

| Job | Artifact |
|-----|----------|
| Android | `safety-remote-apk` (`app-release.apk`) |
| iOS | `safety-remote-ipa-unsigned` |

Signed IPA (tùy chọn): set repo variable `ENABLE_IOS_SIGNING=true` và secrets:

- `IOS_CERTIFICATE_BASE64`
- `IOS_CERTIFICATE_PASSWORD`
- `IOS_PROVISION_BASE64`

Tải artifact trong tab **Actions** sau mỗi push `main`.
