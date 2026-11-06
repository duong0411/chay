#ifndef INDEX_HTML_H
#define INDEX_HTML_H

// Auto-generated from web/index.html — text/html
const char HTML_CONTENT[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#0A0E17" />
  <title>Safety Remote</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <div id="app">
    <!-- CONNECT -->
    <section id="page-connect" class="page">
      <div class="orb orb-a"></div>
      <div class="orb orb-b"></div>
      <div class="connect-inner">
        <h1 class="brand">SAFETY<br/>REMOTE</h1>
        <p class="lead">Theo dõi gas, cháy, GPS và SMS qua Wi‑Fi SoftAP của mạch.</p>

        <div class="panel tip">
          <div class="tip-title">Kết nối gần máy</div>
          <div>Tên mạng: <b>Safety Remote</b></div>
          <div>Mật khẩu: <b>1234567890</b></div>
          <div class="muted" style="margin-top:8px">Điện thoại phải đứng trong Wi‑Fi của mạch, rồi mở app / trình duyệt.</div>
        </div>

        <label class="field-label">Địa chỉ máy</label>
        <input id="host-input" class="field" type="url" autocomplete="off" spellcheck="false" value="192.168.4.8" />
        <p id="connect-status" class="status-line">Chưa kết nối</p>

        <button id="btn-connect" class="btn btn-primary" type="button">Kết nối gần</button>
      </div>
    </section>

    <!-- HOME -->
    <section id="page-home" class="page hidden">
      <header class="topbar">
        <div>
          <div class="top-title">SAFETY REMOTE</div>
          <div class="live-row">
            <span id="live-dot" class="dot"></span>
            <span id="live-text" class="muted">Đang kết nối…</span>
          </div>
        </div>
        <button id="btn-disconnect" class="icon-btn" title="Ngắt kết nối" type="button">⏏</button>
      </header>

      <div id="alarm-banner" class="alarm hidden"></div>

      <div class="grid2">
        <article class="tile" id="tile-volt">
          <div class="tile-head"><span>Nguồn 12V</span><span class="badge" id="badge-volt">--</span></div>
          <div class="tile-value" id="val-volt">--</div>
          <div class="tile-unit">V</div>
        </article>
        <article class="tile" id="tile-sht">
          <div class="tile-head"><span>Nhiệt / ẩm</span><span class="badge" id="badge-sht">--</span></div>
          <div class="tile-value sm" id="val-temp">--</div>
          <div class="tile-detail" id="val-hum">-- %RH</div>
        </article>
        <article class="tile" id="tile-gas">
          <div class="tile-head"><span>Gas / Khói</span><span class="badge" id="badge-gas">--</span></div>
          <div class="tile-value sm" id="val-gas">--</div>
          <div class="tile-detail">ADC / 4095</div>
        </article>
        <article class="tile" id="tile-fire">
          <div class="tile-head"><span>Báo cháy</span><span class="badge" id="badge-fire">--</span></div>
          <div class="tile-value sm" id="val-fire">--</div>
          <div class="tile-detail">GPIO26 · Signal</div>
        </article>
      </div>

      <article class="card">
        <div class="card-head">
          <span>SIM 4G &amp; GPS</span>
          <span class="badge" id="badge-gps">--</span>
        </div>
        <div class="kv">GNSS: <b id="val-gnss">--</b></div>
        <div class="kv">Vĩ độ: <b id="val-lat">--</b></div>
        <div class="kv">Kinh độ: <b id="val-lon">--</b></div>
        <a id="map-link" class="map-link hidden" href="#" target="_blank" rel="noopener">Mở Google Maps</a>
        <div class="wifi-meta muted" id="wifi-meta">Wi‑Fi --</div>
      </article>

      <article class="card" id="sms-card">
        <div class="card-head">
          <span>SMS cảnh báo</span>
          <span class="badge" id="badge-sms">--</span>
        </div>
        <div class="kv">Số nhận: <b id="val-sms-to">--</b></div>
        <div class="kv">Trạng thái: <b id="val-sms-status">--</b></div>
        <div id="sms-reason" class="reason">--</div>
        <div class="muted" id="val-sms-stats">OK 0 · Lỗi 0</div>
        <div class="sms-body" id="val-sms-text">Chưa có tin nhắn</div>
      </article>

      <div class="actions">
        <button id="btn-buzzer" class="btn btn-ghost" type="button">Còi: TẮT</button>
        <button id="btn-gps" class="btn btn-ghost" type="button">Bật Module SIM/GPS</button>
        <button id="btn-sms" class="btn btn-accent" type="button">Gửi SMS test</button>
      </div>
    </section>
  </div>
  <div id="toast" class="toast hidden"></div>
  <script src="/app.js"></script>
</body>
</html>
)rawliteral";

#endif
