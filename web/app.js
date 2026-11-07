(() => {
  const DEFAULT_HOST = "192.168.4.1";
  const WIFI_NAME = "Safety Remote";
  const POLL_MS = 1500;
  const STORAGE_KEY = "safety_remote_host";

  const $ = (id) => document.getElementById(id);

  const state = {
    host: localStorage.getItem(STORAGE_KEY) || DEFAULT_HOST,
    connected: false,
    polling: null,
    live: false,
    failCount: 0,
  };

  function baseUrl() {
    let h = state.host.trim().replace(/^https?:\/\//, "").replace(/\/+$/, "");
    if (!h) h = DEFAULT_HOST;
    // Cùng máy SoftAP → gọi relative (ổn định hơn trên một số trình duyệt ĐT)
    const pageHost = location.hostname || "";
    if (
      location.protocol.startsWith("http") &&
      pageHost &&
      (h === pageHost || h.startsWith(pageHost + ":"))
    ) {
      return "";
    }
    return `http://${h}`;
  }

  function toast(msg, ok) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.remove("hidden", "ok", "err");
    el.classList.add(ok ? "ok" : "err");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2800);
  }

  function showConnect() {
    state.connected = false;
    stopPoll();
    $("page-home").classList.add("hidden");
    $("page-connect").classList.remove("hidden");
  }

  function showHome() {
    state.connected = true;
    $("page-connect").classList.add("hidden");
    $("page-home").classList.remove("hidden");
    startPoll();
  }

  function stopPoll() {
    if (state.polling) {
      clearInterval(state.polling);
      state.polling = null;
    }
  }

  function startPoll() {
    stopPoll();
    refresh();
    state.polling = setInterval(refresh, POLL_MS);
  }

  function setBadge(el, text, kind) {
    el.textContent = text;
    el.className = "badge" + (kind ? " " + kind : "");
  }

  function isValidCoord(v) {
    if (!v) return false;
    const bad = [
      "Chưa có dữ liệu",
      "Đang tìm tín hiệu...",
      "Đang kích hoạt GPS...",
      "Đang khởi động...",
      "Module tắt",
      "Lỗi kết nối",
      "--",
    ];
    return bad.indexOf(v) === -1 && !Number.isNaN(parseFloat(v));
  }

  async function api(path, opts = {}, timeoutMs = 4000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch(`${baseUrl()}${path}`, {
        signal: ctrl.signal,
        cache: "no-store",
        ...opts,
      });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try {
          const j = await res.json();
          if (j && j.message) msg = j.message;
        } catch (_) {}
        throw new Error(msg);
      }
      return await res.json();
    } finally {
      clearTimeout(t);
    }
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function escapeAttr(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  let lastStaToast = "";

  function applyStaUi(d) {
    const box = $("wifi-sta-status");
    const banner = $("wifi-ok-banner");
    if (!box) return;
    const status = d.staStatus || (d.staConnected ? "Thành công" : "Chưa kết nối");
    const detail = d.staDetail || "";
    const ok = status.indexOf("Thành công") >= 0 || !!d.staConnected;
    const fail = status.indexOf("Thất bại") >= 0;
    const connecting = status.indexOf("Đang") >= 0;

    setBadge(
      $("badge-sta"),
      ok ? "THÀNH CÔNG" : fail ? "THẤT BẠI" : connecting ? "ĐANG KẾT NỐI" : "CHƯA KẾT NỐI",
      ok ? "ok" : fail ? "bad" : "warn"
    );
    box.className = "wifi-sta-box " + (ok ? "ok" : fail ? "bad" : connecting ? "warn" : "");
    box.innerHTML =
      `<div><b>${escapeAttr(status)}</b></div>` +
      `<div>${escapeAttr(detail || ("Wi‑Fi: " + (d.staSsid || "(chưa)") + " · IP " + (d.staIp || "-")))}</div>` +
      `<div style="margin-top:4px;opacity:.85">MQTT: <b>${d.mqttConnected ? "online" : "offline"}</b> · Chip ${escapeAttr(d.chipId || "?")}</div>`;

    if (banner) {
      if (ok) {
        banner.textContent = detail || ("✅ Kết nối Wi‑Fi thành công: " + (d.staSsid || ""));
        banner.classList.remove("hidden");
      } else {
        banner.classList.add("hidden");
      }
    }

    if (ok && lastStaToast !== detail) {
      lastStaToast = detail || status;
      toast("✅ Kết nối Wi‑Fi thành công", true);
    }
  }

  async function refreshWifiStatus() {
    if (!$("wifi-sta-status")) return;
    try {
      const d = await api("/api/wifi", {}, 5000);
      const chipEl = $("wifi-chip");
      const ssidEl = $("wifi-ssid");
      if (chipEl && document.activeElement !== chipEl) chipEl.value = d.chipId || "888";
      if (ssidEl && !ssidEl.value && d.staSsid) ssidEl.value = d.staSsid;
      applyStaUi(d);
    } catch (_) {
      setBadge($("badge-sta"), "LỖI", "bad");
    }
  }

  async function scanWifiNetworks() {
    const btn = $("btn-wifi-scan");
    const list = $("wifi-scan-list");
    if (!btn || !list) return;
    btn.disabled = true;
    btn.textContent = "Đang quét...";
    list.textContent = "Đang quét mạng xung quanh…";
    try {
      // fresh=1 bắt đầu quét mới (task nền)
      await api("/api/wifi/scan?fresh=1", {}, 8000);
      let data = null;
      for (let i = 0; i < 45; i++) {
        await sleep(800);
        data = await api("/api/wifi/scan", {}, 8000);
        if (data && data.status === "done") break;
        list.textContent = `Đang quét… (${i + 1})`;
      }
      const nets = (data && data.networks) || [];
      if (!nets.length) {
        list.textContent = "Không thấy mạng. Thử quét lại (đứng gần router).";
      } else {
        list.innerHTML = nets
          .map((n) => {
            const ssid = n.ssid || "";
            const lock = n.secure ? "🔒 " : "";
            return `<div class="wifi-net" data-ssid="${escapeAttr(ssid)}"><span>${lock}${escapeAttr(ssid)}</span><span class="rssi">${n.rssi} dBm</span></div>`;
          })
          .join("");
        list.querySelectorAll(".wifi-net").forEach((el) => {
          el.addEventListener("click", () => {
            list.querySelectorAll(".wifi-net").forEach((x) => x.classList.remove("sel"));
            el.classList.add("sel");
            $("wifi-ssid").value = el.getAttribute("data-ssid") || "";
            $("wifi-pass").focus();
          });
        });
      }
    } catch (e) {
      list.textContent = e.message || "Quét lỗi — thử lại.";
    } finally {
      btn.disabled = false;
      btn.textContent = "Quét lại Wi‑Fi";
    }
  }

  async function saveWifiConfig() {
    const ssid = ($("wifi-ssid").value || "").trim();
    if (!ssid) {
      toast("Chọn hoặc nhập tên Wi‑Fi", false);
      return;
    }
    const btn = $("btn-wifi-save");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Đang kết nối...";
    }
    lastStaToast = "";
    try {
      const body = new URLSearchParams({
        ssid,
        pass: $("wifi-pass").value || "",
        chip: $("wifi-chip").value || "888",
      });
      await api(
        "/api/wifi",
        {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
        },
        8000
      );
      toast("Đã lưu — đang kết nối Wi‑Fi nhà...", true);
      // Chờ GOT_IP / thất bại rồi báo rõ
      for (let i = 0; i < 25; i++) {
        await sleep(1000);
        const d = await api("/api/wifi", {}, 5000);
        applyStaUi(d);
        if (d.staConnected || (d.staStatus && d.staStatus.indexOf("Thành công") >= 0)) {
          toast("✅ Kết nối Wi‑Fi thành công", true);
          break;
        }
        if (d.staStatus && d.staStatus.indexOf("Thất bại") >= 0 && i > 3) {
          toast("Kết nối Wi‑Fi thất bại — kiểm tra mật khẩu", false);
          break;
        }
      }
    } catch (e) {
      toast(e.message || "Không lưu được Wi‑Fi", false);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Lưu & kết nối Wi‑Fi";
      }
    }
  }

  async function connect() {
    const input = $("host-input");
    state.host = (input.value || DEFAULT_HOST).trim();
    localStorage.setItem(STORAGE_KEY, state.host);
    $("btn-connect").disabled = true;
    $("connect-status").textContent = "Đang kiểm tra máy...";
    try {
      await api("/api/sensors");
      $("connect-status").textContent = `Đã vào máy ${state.host}`;
      toast(`Đã vào máy ${state.host}`, true);
      showHome();
    } catch (e) {
      $("connect-status").textContent =
        `Không kết nối được ${state.host}. Bật thiết bị và vào Wi‑Fi ${WIFI_NAME}.`;
      toast("Kết nối thất bại — kiểm tra Wi‑Fi SoftAP", false);
    } finally {
      $("btn-connect").disabled = false;
    }
  }

  function disconnect() {
    stopPoll();
    state.live = false;
    state.failCount = 0;
    $("connect-status").textContent = "Đã ngắt kết nối";
    showConnect();
    toast("Đã ngắt kết nối", true);
  }

  function render(data) {
    state.live = true;
    state.failCount = 0;
    $("live-dot").classList.add("live");
    $("live-text").textContent = `Gần máy · ${state.host}`;

    $("val-volt").textContent = Number(data.volt).toFixed(2);
    setBadge($("badge-volt"), data.volt >= 11.2 ? "Ổn định" : "Thấp", data.volt >= 11.2 ? "ok" : "bad");

    if (data.temp !== -999) {
      $("val-temp").textContent = `${Number(data.temp).toFixed(1)} °C`;
      $("val-hum").textContent = `${Number(data.hum).toFixed(1)} %RH`;
      setBadge($("badge-sht"), "I2C OK", "ok");
      $("tile-sht").classList.toggle("alert", data.temp > 40);
    } else {
      $("val-temp").textContent = "LỖI";
      $("val-hum").textContent = "-- %RH";
      setBadge($("badge-sht"), "LỖI I2C", "bad");
    }

    $("val-gas").textContent = String(data.gas);
    setBadge($("badge-gas"), data.gasAlert ? "CẢNH BÁO" : "An toàn", data.gasAlert ? "bad" : "ok");
    $("tile-gas").classList.toggle("alert", !!data.gasAlert);

    $("val-fire").textContent = data.fireAlert ? "PHÁT HIỆN CHÁY" : "An toàn";
    setBadge($("badge-fire"), data.fireAlert ? "BÁO ĐỘNG" : "OK", data.fireAlert ? "bad" : "ok");
    $("tile-fire").classList.toggle("alert", !!data.fireAlert);

    const alarm = $("alarm-banner");
    if (data.gasAlert || data.fireAlert) {
      const parts = [];
      if (data.fireAlert) parts.push("Phát hiện cháy");
      if (data.gasAlert) parts.push("Rò gas/khói");
      alarm.textContent = "⚠ " + parts.join(" · ");
      alarm.classList.remove("hidden");
    } else {
      alarm.classList.add("hidden");
    }

    const gnss = data.gpsGnss || "";
    $("val-gnss").textContent = gnss || "--";
    $("val-lat").textContent = data.gpsLat || "--";
    $("val-lon").textContent = data.gpsLon || "--";
    if (!data.gpsPower) {
      setBadge($("badge-gps"), "TẮT", "");
    } else if (gnss.indexOf("FIX") !== -1) {
      setBadge($("badge-gps"), "FIX", "ok");
    } else if (/Lỗi|thất bại|Không phản hồi/i.test(gnss)) {
      setBadge($("badge-gps"), "LỖI", "bad");
    } else {
      setBadge($("badge-gps"), "ON", "ok");
    }

    const map = $("map-link");
    if (data.gpsPower && isValidCoord(data.gpsLat) && isValidCoord(data.gpsLon)) {
      map.href = `https://maps.google.com/?q=${data.gpsLat},${data.gpsLon}`;
      map.classList.remove("hidden");
    } else {
      map.classList.add("hidden");
    }

    $("wifi-meta").textContent =
      `SoftAP CH${data.wifiChannel ?? "?"} · ${data.wifiTxDbm ?? "--"}dBm · ${data.wifiClients ?? 0} ĐT` +
      (data.staConnected ? ` · Nhà: ${data.staSsid || "OK"} ${data.staIp || ""}` : "");
    if (data.staStatus || data.staConnected) {
      applyStaUi(data);
    }

    const btnGps = $("btn-gps");
    if (data.gpsPower) {
      btnGps.classList.add("on");
      btnGps.textContent = "Tắt Module SIM/GPS";
    } else {
      btnGps.classList.remove("on");
      btnGps.textContent = "Bật Module SIM/GPS";
    }

    const btnBz = $("btn-buzzer");
    if (data.buzzer) {
      btnBz.classList.add("danger-on");
      btnBz.textContent = "Còi: BẬT";
    } else {
      btnBz.classList.remove("danger-on");
      btnBz.textContent = "Còi: TẮT";
    }

    $("val-sms-to").textContent = data.smsTo || "(chưa cấu hình)";
    const smsInput = $("sms-numbers");
    if (smsInput && document.activeElement !== smsInput) {
      const next = data.smsTo || "";
      if (smsInput.dataset.synced !== next) {
        smsInput.value = next;
        smsInput.dataset.synced = next;
      }
    }
    const smsStatus = data.smsStatus || "Chưa gửi";
    $("val-sms-status").textContent = smsStatus;
    $("val-sms-stats").textContent =
      `OK ${data.smsSentCount || 0} · Lỗi ${data.smsFailCount || 0}` +
      (data.smsAgeSec > 0 ? ` · ${data.smsAgeSec}s trước` : "");
    $("val-sms-text").textContent = data.smsText || "Chưa có tin nhắn";

    const reason = $("sms-reason");
    reason.textContent = data.smsResult || "--";
    reason.className = "reason";
    const badgeSms = $("badge-sms");
    const btnSms = $("btn-sms");
    if (data.smsSending || /Đang/.test(smsStatus)) {
      setBadge(badgeSms, "ĐANG GỬI", "warn");
      reason.classList.add("warn");
      btnSms.disabled = true;
      btnSms.textContent = "Đang gửi...";
    } else if (/Thành công|Đã gửi/.test(smsStatus)) {
      setBadge(badgeSms, "OK", "ok");
      reason.classList.add("ok");
      btnSms.disabled = false;
      btnSms.textContent = "Gửi SMS test";
    } else if (/Thất bại/.test(smsStatus)) {
      setBadge(badgeSms, "LỖI", "bad");
      reason.classList.add("bad");
      btnSms.disabled = false;
      btnSms.textContent = "Gửi SMS test";
    } else {
      setBadge(badgeSms, "CHỜ", "");
      btnSms.disabled = false;
      btnSms.textContent = "Gửi SMS test";
    }
  }

  async function refresh() {
    if (!state.connected) return;
    try {
      const data = await api("/api/sensors");
      render(data);
      // Không gọi refreshWifiStatus mỗi poll để tránh đè form khi đang gõ
    } catch (e) {
      state.failCount += 1;
      state.live = false;
      $("live-dot").classList.remove("live");
      $("live-text").textContent = `Mất kết nối · thử lại (${state.failCount})`;
      if (state.failCount >= 8) {
        toast("Mất liên lạc với máy — quay lại màn hình kết nối", false);
        disconnect();
      }
    }
  }

  async function act(path, okMsg) {
    try {
      const data = await api(path);
      if (data && data.success === false) {
        toast(data.error || "Thao tác thất bại", false);
      } else if (okMsg) {
        toast(okMsg, true);
      }
      await refresh();
    } catch (e) {
      toast("Không gửi được lệnh tới máy", false);
    }
  }

  function boot() {
    // Nếu đang mở trực tiếp từ SoftAP ESP32 thì dùng hostname hiện tại
    if (location.protocol.startsWith("http") && location.hostname && location.hostname !== "localhost") {
      state.host = location.hostname + (location.port && location.port !== "80" ? `:${location.port}` : "");
    }
    $("host-input").value = state.host || DEFAULT_HOST;

    $("btn-connect").addEventListener("click", connect);
    $("host-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") connect();
    });
    $("btn-disconnect").addEventListener("click", disconnect);
    $("btn-buzzer").addEventListener("click", () => act("/api/toggleBuzzer"));
    $("btn-gps").addEventListener("click", () => act("/api/toggleGps"));
    $("btn-sms").addEventListener("click", () => act("/api/sendTestSms", "Đã xếp hàng SMS test"));
    $("btn-save-sms").addEventListener("click", async () => {
      const numbers = ($("sms-numbers").value || "").trim();
      if (!numbers) {
        toast("Nhập ít nhất 1 số điện thoại", false);
        return;
      }
      try {
        const body = new URLSearchParams({ numbers });
        const data = await api("/api/smsNumbers", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body,
        });
        toast(data.message || "Đã lưu số nhận SMS", true);
        $("sms-numbers").dataset.synced = "";
        await refresh();
      } catch (e) {
        toast(e.message || "Không lưu được số nhận", false);
      }
    });
    $("btn-wifi-scan").addEventListener("click", () => scanWifiNetworks());
    $("btn-wifi-save").addEventListener("click", () => saveWifiConfig());

    // SoftAP 192.168.4.1 → một trang duy nhất (dashboard + portal WiFi)
    if (location.protocol.startsWith("http") && location.hostname === "192.168.4.1") {
      connect().then(() => {
        refreshWifiStatus();
        scanWifiNetworks();
        setInterval(refreshWifiStatus, 4000);
      });
    } else {
      showConnect();
    }
  }

  boot();
})();
