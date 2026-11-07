# Safety Remote Web App

Giao diện web theo phong cách app **Smart First AID** (màn hình Kết nối → Dashboard).

## Thư mục

| File | Mô tả |
|------|--------|
| `index.html` | Cấu trúc trang Connect + Home |
| `style.css` | Theme tối (đỏ / cyan) |
| `app.js` | Kết nối SoftAP, poll `/api/sensors`, điều khiển |
| `_gen_headers.py` | Đồng bộ sang `index_html.h`, `style_css.h`, `app_js.h` cho ESP32 |

## Dùng trên mạch

1. Sửa file trong `web/` nếu cần
2. Chạy: `python web/_gen_headers.py`
3. Flash lại `SafetyRemote.ino`
4. Điện thoại vào Wi‑Fi `Safety Remote` (không mật khẩu)
5. Mở `http://192.168.4.8`

## API mạch

- `GET /api/sensors`
- `GET /api/toggleBuzzer`
- `GET /api/toggleGps`
- `GET /api/sendTestSms`
