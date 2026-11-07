/**
 * ==================================================================================
 *                       VEHICLE SAFETY REMOTE - DEMO PROGRAM
 * ==================================================================================
 * Bo mạch phát triển dựa trên vi điều khiển ESP32-WROOM-32E (4MB).
 * Chương trình demo kiểm tra toàn bộ các tính năng ngoại vi trên mạch thông qua
 * giao diện Serial Monitor tương tác (tốc độ baud 115200) và Web Dashboard.
 *
 * Thiết kế phần cứng:
 * - Cảm biến nhiệt độ & độ ẩm SHT31 (Giao tiếp I2C).
 * - Cảm biến khí gas/khói MQ-2 (Đầu vào Analog + Digital).
 * - Cảm biến báo cháy (chân Signal GPIO26).
 * - Còi báo động (chân điều khiển GPIO25).
 * - Module LTE/GPS EG800K (Giao tiếp UART2 + Chân EN kích hoạt).
 * - Đo điện áp acquy/nguồn cấp 12V qua cầu phân áp ADC.
 * ==================================================================================
 */

#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <esp_adc_cal.h>
#include <esp_wifi.h>
#include "Safety_Mqtt.h"

// ==================================================================================
// 1. ĐỊNH NGHĨA CÁC CHÂN CẤU HÌNH (PIN MAPPING)
// ==================================================================================

// Đo điện áp nguồn & Cảm biến Gas
#define PIN_ADC_12V     34  // Cảm biến đo áp 12V (Cầu phân áp R18 100k, R20 20k -> Hệ số 1/6)
#define PIN_MQ2_AO      35  // Cảm biến Gas MQ-2 Analog Out (Đọc nồng độ khói/gas)
#define PIN_MQ2_DO      32  // Cảm biến Gas MQ-2 Digital Out (Mức cao khi vượt ngưỡng)

// Cảm biến báo cháy & Còi
#define PIN_FIRE_SIGNAL 26  // Chân Signal của module cảm biến báo cháy
#define PIN_BUZZER      25  // Chân OUT bật/tắt còi
// GPIO27 không dùng

// Module di động & định vị (LTE/GPS EG800K)
#define PIN_EN_GPS      15  // Bật nguồn module EG800K (HIGH = Bật, LOW = Tắt)
#define PIN_TX_GPS      17  // ESP32 TX nối tới RX của EG800K (UART2 TX)
#define PIN_RX_GPS      16  // ESP32 RX nối tới TX của EG800K (UART2 RX)

// Giao tiếp I2C cho cảm biến SHT31
#define PIN_SDA         21  // SDA của ESP32
#define PIN_SCL         22  // SCL của ESP32

// Địa chỉ I2C của cảm biến SHT31 (mặc định 0x44)
#define SHT31_I2C_ADDR  0x44

// ==================================================================================
// 2. BIẾN TOÀN CỤC & TRẠNG THÁI
// ==================================================================================

// Cấu hình Wi-Fi Access Point và WebServer
const char* ap_ssid = "Safety Remote";
// SoftAP mở — không mật khẩu (NULL)
const char* ap_password = nullptr;
// Kênh 1/6/11 ít chồng chéo hơn; đổi nếu môi trường nhiễu mạnh
const int WIFI_AP_CHANNEL = 1;
const int WIFI_AP_MAX_CLIENTS = 4;
// Portal SoftAP mặc định (bàn giao khách → vào lại Safety Remote để bắt WiFi mới)
IPAddress local_IP(192, 168, 4, 1);
IPAddress gateway(192, 168, 4, 1);
IPAddress subnet(255, 255, 255, 0);

WebServer server(80);
DNSServer dnsServer;
Preferences prefs;
volatile uint8_t wifiStationCount = 0;
volatile bool wifiScanRunning = false;
volatile bool wifiScanRequest = false;
String wifiScanResultJson = "{\"status\":\"idle\",\"networks\":[]}";
SemaphoreHandle_t wifiScanMutex = NULL;

// Trạng thái kết nối WiFi nhà (STA) — báo thành công trên portal
String staConnStatus = "Chưa kết nối";   // Đang kết nối / Thành công / Thất bại
String staConnDetail = "Chưa cấu hình Wi‑Fi nhà";
uint32_t staConnOkMs = 0;

// SoftAP portal: chỉ bật khi cấu hình / bàn giao / mất WiFi nhà
bool portalApActive = false;
bool portalDnsStarted = false;
uint32_t portalStopAtMs = 0;   // hẹn tắt SoftAP sau khi STA OK (để ĐT kịp thấy "thành công")
uint32_t staFailSinceMs = 0;
const uint32_t PORTAL_STOP_DELAY_MS = 12000; // 12s sau GOT_IP
const uint32_t STA_FAIL_OPEN_PORTAL_MS = 25000;

// Forward decls (arduino-cli không luôn tự tạo prototype)
String jsonEscape(const String &s);
void readAndPrintAll();
void handleCaptiveRedirect();
void handleWifiScan();
void wifiScanTaskCode(void *pv);
void startPortalAP(const char *why);
void stopPortalAP(const char *why);
void mqttApplyPortalCommand(const String &raw);

bool eg800kPower = true;
bool buzzerState = false;
bool streamMode = true;
unsigned long lastStreamTime = 0;
const unsigned long STREAM_INTERVAL = 2000; // Gửi dữ liệu định kỳ mỗi 2 giây

String gpsLatitude = "Chưa có dữ liệu";
String gpsLongitude = "Chưa có dữ liệu";
String gpsGnssStatus = "Chưa kiểm tra"; // OFF / ON / FIX / lỗi AT...
unsigned long lastGpsQueryTime = 0;
const unsigned long GPS_QUERY_INTERVAL = 15000; // Đọc GPS mỗi 15 giây
bool gpsEnabled = false; // GNSS engine đang ON theo AT+QGPS?

// Trạng thái cảnh báo ở chu kỳ trước để phát hiện sự thay đổi trạng thái (tránh spam SMS)
bool lastGasAlert = false;
bool lastTempAlert = false;
bool lastVoltAlert = false;
bool lastFireAlert = false;

// Thời gian (ms) gửi SMS cảnh báo gần nhất để chống spam SMS
unsigned long lastGasSmsTime = 0;
unsigned long lastTempSmsTime = 0;
unsigned long lastVoltSmsTime = 0;
unsigned long lastFireSmsTime = 0;
const unsigned long SMS_COOLDOWN_MS = 30000; // 30s (30,000 ms)

// Hàng đợi và Mutex cho điều khiển SMS / GPS không chặn web
struct SmsMessage {
  char text[160];
};
QueueHandle_t smsQueue = NULL;
SemaphoreHandle_t serialMutex = NULL;
volatile bool isSerialGPSBusy = false;

// Trạng thái SMS hiển thị trên web / app
String smsStatus = "Chưa gửi";       // Chờ / Đang gửi / Thành công / Thất bại
String smsLastText = "";             // Nội dung SMS gần nhất
String smsLastResult = "";           // Phản hồi mạng (OK / ERROR / ...)
unsigned long smsLastSentMs = 0;     // millis() lúc gửi xong
uint32_t smsSentCount = 0;
uint32_t smsFailCount = 0;
volatile bool smsSending = false;

// Số nhận SMS cấu hình từ app/web (NVS) — tối đa 5 số
#define SMS_MAX_NUMBERS 5
#define SMS_PHONE_MAX   20
char smsPhones[SMS_MAX_NUMBERS][SMS_PHONE_MAX];
uint8_t smsPhoneCount = 0;

// Khai báo HardwareSerial cho GPS
HardwareSerial SerialGPS(2);

// ==================================================================================
// 3. CÁC HÀM TIỆN ÍCH CHO TỪNG MODULE
// ==================================================================================

// --- Đo điện áp nguồn 12V ---
float readVoltage12V() {
  // Đọc ADC nhiều lần (20 mẫu) để lấy giá trị trung bình, giảm nhiễu tức thời
  uint32_t adcSum = 0;
  const int NUM_SAMPLES = 20;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    adcSum += analogRead(PIN_ADC_12V);
    delay(1); // Trễ ngắn 1ms giữa các lần đo để lọc nhiễu tần số cao
  }
  uint32_t adcAvg = adcSum / NUM_SAMPLES;

  // 1. Sử dụng thư viện hiệu chuẩn nội bộ của ESP32 để khử sai số phi tuyến và Vref của chip
  esp_adc_cal_characteristics_t adc_chars;
  esp_adc_cal_characterize(ADC_UNIT_1, ADC_ATTEN_DB_11, ADC_WIDTH_BIT_12, 1100, &adc_chars);
  uint32_t voltage_mv = esp_adc_cal_raw_to_voltage(adcAvg, &adc_chars);
  float v_out = voltage_mv / 1000.0; // Quy đổi ra Volt

  // 2. Áp dụng hệ số cầu phân áp hiệu chuẩn thực tế (không cộng bù sụt áp diode)
  // Cầu phân áp R18 (100K) và R20 (20K) có tỷ lệ lý thuyết là 6.0.
  // Khi đo pin thực tế là 12.07V, v_out đo được là 2.027V.
  // Hệ số hiệu chuẩn thực tế = 12.07 / 2.027 = 5.955
  const float DIVIDER_RATIO = 5.955;

  float v_in = v_out * DIVIDER_RATIO;
  return v_in;
}

// --- Cảm biến SHT31 (Đọc trực tiếp không cần thư viện ngoài) ---
bool readSHT31(float &temperature, float &humidity) {
  Wire.beginTransmission(SHT31_I2C_ADDR);
  Wire.write(0x2C); // Lệnh đo Single-shot
  Wire.write(0x06); // Độ chính xác cao (High repeatability)
  if (Wire.endTransmission() != 0) {
    return false; // Lỗi kết nối cảm biến
  }

  delay(20); // Chờ cảm biến thực hiện phép đo (tối đa 15ms)

  if (Wire.requestFrom(SHT31_I2C_ADDR, 6) != 6) {
    return false; // Lỗi đọc gói tin phản hồi
  }

  uint16_t rawTemp = (Wire.read() << 8) | Wire.read();
  uint8_t tempCrc = Wire.read(); // Bỏ qua kiểm tra CRC trong bản demo cơ bản
  uint16_t rawHum = (Wire.read() << 8) | Wire.read();
  uint8_t humCrc = Wire.read();
  (void)tempCrc;
  (void)humCrc;

  // Công thức chuyển đổi từ datasheet của SHT31
  temperature = -45.0 + 175.0 * ((float)rawTemp / 65535.0);
  humidity = 100.0 * ((float)rawHum / 65535.0);

  return true;
}

// --- Đọc Cảm biến Gas MQ-2 ---
#define MQ2_THRESHOLD_ALARM  2000 // Ngưỡng cảnh báo phần mềm (0-4095), khoảng 1.6V
#define MQ2_HYSTERESIS_VAL    200 // Trễ 200 đơn vị ADC để tránh dao động quanh ngưỡng

void readMQ2(int &analogVal, bool &digitalWarning) {
  analogVal = analogRead(PIN_MQ2_AO);

  // Trạng thái cảnh báo kích hoạt khi:
  // - Chân DO phần cứng lên mức HIGH (do mạch so sánh LM393 của module MQ-2 quyết định)
  // - Hoặc giá trị Analog đo được vượt quá ngưỡng phần mềm 2000 (áp dụng trễ hysteresis)
  bool hwAlert = (digitalRead(PIN_MQ2_DO) == HIGH);

  // Trễ Hysteresis: nếu đang cảnh báo thì phải xuống dưới (THRESHOLD - HYSTERESIS) mới hết cảnh báo
  bool swAlert = lastGasAlert;
  if (lastGasAlert) {
    if (analogVal < (MQ2_THRESHOLD_ALARM - MQ2_HYSTERESIS_VAL)) {
      swAlert = false;
    }
  } else {
    if (analogVal > MQ2_THRESHOLD_ALARM) {
      swAlert = true;
    }
  }

  digitalWarning = hwAlert || swAlert;
}

// --- Cảm biến báo cháy ---
// Nhiều module LM393: Signal = LOW khi phát hiện cháy. Đổi thành HIGH nếu module của bạn ngược lại.
bool readFireSensor() {
  return digitalRead(PIN_FIRE_SIGNAL) == LOW;
}

// --- Điều khiển còi ---
void setBuzzer(bool state) {
  buzzerState = state;
  digitalWrite(PIN_BUZZER, state ? HIGH : LOW);
}

// --- Điều khiển bật/tắt module LTE/GPS EG800K ---
void setEG800KPower(bool state) {
  eg800kPower = state;
  if (state) {
    digitalWrite(PIN_EN_GPS, HIGH); // Bật nguồn & sáng LED5
    gpsEnabled = false;
    gpsGnssStatus = "Đang khởi động module...";
    gpsLatitude = "Đang khởi động...";
    gpsLongitude = "Đang khởi động...";
    Serial.println("  [EG800K] Đã bật chân nguồn EN_GPS (LED5 sáng).");
    Serial.println("  [LƯU Ý] Vui lòng chờ khoảng 5-8 giây để module SIM hoàn thành khởi động trước khi gửi lệnh.");
  } else {
    digitalWrite(PIN_EN_GPS, LOW);  // Tắt nguồn & tắt LED5
    gpsEnabled = false;
    gpsGnssStatus = "Module tắt nguồn";
    gpsLatitude = "Module tắt";
    gpsLongitude = "Module tắt";
    Serial.println("  [EG800K] Đã tắt chân nguồn EN_GPS.");
  }
}

String smsNumbersJoined() {
  String s;
  for (uint8_t i = 0; i < smsPhoneCount; i++) {
    if (i) s += ",";
    s += smsPhones[i];
  }
  return s;
}

String normalizePhoneToken(String raw) {
  raw.trim();
  String out;
  out.reserve(raw.length());
  for (size_t i = 0; i < raw.length(); i++) {
    char c = raw.charAt(i);
    if (c >= '0' && c <= '9') out += c;
    else if (c == '+' && out.length() == 0) out += c;
  }
  return out;
}

bool setSmsNumbersFromRaw(const String& raw, String* errOut = nullptr) {
  uint8_t count = 0;
  char tmp[SMS_MAX_NUMBERS][SMS_PHONE_MAX];
  memset(tmp, 0, sizeof(tmp));

  String buf = raw;
  buf.replace('\r', ',');
  buf.replace('\n', ',');
  buf.replace(';', ',');
  buf.replace('|', ',');
  // Giữ khoảng trắng trong từng số — normalizePhoneToken sẽ bỏ ký tự không phải số

  int start = 0;
  while (start <= (int)buf.length() && count < SMS_MAX_NUMBERS) {
    int comma = buf.indexOf(',', start);
    String token = (comma < 0) ? buf.substring(start) : buf.substring(start, comma);
    token = normalizePhoneToken(token);
    if (token.length() >= 8 && token.length() < SMS_PHONE_MAX) {
      bool dup = false;
      for (uint8_t i = 0; i < count; i++) {
        if (token.equals(tmp[i])) { dup = true; break; }
      }
      if (!dup) {
        token.toCharArray(tmp[count], SMS_PHONE_MAX);
        count++;
      }
    }
    if (comma < 0) break;
    start = comma + 1;
  }

  if (count == 0) {
    if (errOut) *errOut = "Chưa có số hợp lệ (cần ≥ 8 chữ số)";
    return false;
  }

  memcpy(smsPhones, tmp, sizeof(smsPhones));
  smsPhoneCount = count;
  return true;
}

void loadSmsNumbers() {
  prefs.begin("safety", true);
  String raw = prefs.getString("smsNums", "");
  prefs.end();
  smsPhoneCount = 0;
  memset(smsPhones, 0, sizeof(smsPhones));
  if (raw.length() > 0) {
    setSmsNumbersFromRaw(raw);
  }
  Serial.print("  [SMS] So nhan: ");
  Serial.println(smsPhoneCount ? smsNumbersJoined() : "(chua cau hinh)");
}

void saveSmsNumbersToPrefs() {
  prefs.begin("safety", false);
  prefs.putString("smsNums", smsNumbersJoined());
  prefs.end();
}

bool applySmsNumbersConfig(const String& raw, String* messageOut = nullptr) {
  String err;
  if (!setSmsNumbersFromRaw(raw, &err)) {
    if (messageOut) *messageOut = err;
    return false;
  }
  saveSmsNumbersToPrefs();
  if (messageOut) {
    *messageOut = "Đã lưu " + String(smsPhoneCount) + " số: " + smsNumbersJoined();
  }
  Serial.print("  [SMS] Cap nhat so nhan: ");
  Serial.println(smsNumbersJoined());
  return true;
}

void sim_at_wait() {
  delay(200);
  while (SerialGPS.available()) {
    Serial.write(SerialGPS.read());
  }
}

bool sim_at_cmd(String cmd) {
  // Xóa sạch bộ đệm nhận để tránh dữ liệu rác cũ
  while (SerialGPS.available()) {
    SerialGPS.read();
  }

  Serial.print("Sending: ");
  Serial.println(cmd);
  SerialGPS.println(cmd);

  unsigned long start = millis();
  String response = "";
  // Đợi phản hồi trong tối đa 1 giây hoặc thoát sớm khi nhận được OK/ERROR
  while (millis() - start < 1000) {
    while (SerialGPS.available()) {
      char c = SerialGPS.read();
      Serial.write(c);
      response += c;
      if (response.indexOf("OK") != -1) {
        return true;
      }
      if (response.indexOf("ERROR") != -1) {
        return false;
      }
    }
    yield();
  }
  return false;
}

bool sim_at_send(char c) {
  SerialGPS.write(c);
  return true;
}

// Đọc phản hồi AT trong timeout (đã giữ mutex)
String smsWaitResponse(unsigned long timeoutMs) {
  String resp = "";
  unsigned long start = millis();
  while (millis() - start < timeoutMs) {
    while (SerialGPS.available()) {
      char c = SerialGPS.read();
      Serial.write(c);
      resp += c;
    }
    if (resp.indexOf("OK") != -1 || resp.indexOf("ERROR") != -1) {
      delay(20);
      while (SerialGPS.available()) {
        char c = SerialGPS.read();
        Serial.write(c);
        resp += c;
      }
      break;
    }
    server.handleClient();
    yield();
  }
  return resp;
}

void smsMarkFail(const String &reason) {
  smsStatus = "Thất bại";
  smsLastResult = reason;
  smsFailCount++;
  smsLastSentMs = millis();
  smsSending = false;
  Serial.print("  [SMS FAIL] ");
  Serial.println(reason);
}

// Gửi 1 SMS tới 1 số (đã sẵn AT/CMGF). Trả true nếu OK.
bool send_sms_one_number(const char* phone, const String& body, int csq, bool netOk, String& detailOut) {
  while (SerialGPS.available()) SerialGPS.read();
  Serial.print("Dang gui toi so: ");
  Serial.println(phone);
  smsLastResult = String("Đang gửi → ") + phone;

  SerialGPS.print("AT+CMGS=\"");
  SerialGPS.print(phone);
  SerialGPS.println("\"");

  unsigned long start = millis();
  bool gotPrompt = false;
  String promptResp = "";
  while (millis() - start < 5000) {
    while (SerialGPS.available()) {
      char c = SerialGPS.read();
      Serial.write(c);
      promptResp += c;
      if (c == '>') {
        gotPrompt = true;
        break;
      }
    }
    if (gotPrompt) break;
    if (promptResp.indexOf("ERROR") != -1) break;
    server.handleClient();
    yield();
  }

  if (!gotPrompt) {
    if (promptResp.indexOf("ERROR") != -1) detailOut = String(phone) + ": AT+CMGS ERROR";
    else if (!netOk) detailOut = String(phone) + ": chưa đăng ký mạng";
    else if (csq > 0 && csq < 5) detailOut = String(phone) + ": sóng yếu CSQ=" + String(csq);
    else detailOut = String(phone) + ": không nhận '>'";
    return false;
  }

  SerialGPS.print(body);
  SerialGPS.write(0x1A);
  smsLastResult = String("Chờ mạng → ") + phone;

  String netResp = "";
  unsigned long waitStart = millis();
  while (millis() - waitStart < 15000) {
    while (SerialGPS.available()) {
      char c = SerialGPS.read();
      Serial.write(c);
      netResp += c;
    }
    if (netResp.indexOf("+CMGS:") != -1 && netResp.indexOf("OK") != -1) break;
    if (netResp.indexOf("ERROR") != -1) break;
    server.handleClient();
    yield();
  }

  if (netResp.indexOf("+CMGS:") != -1) {
    detailOut = String(phone) + ": OK";
    return true;
  }
  if (netResp.indexOf("ERROR") != -1) {
    String errDetail = "ERROR";
    if (netResp.indexOf("CMS ERROR") != -1) {
      int e = netResp.indexOf("CMS ERROR");
      errDetail = netResp.substring(e, min((int)netResp.length(), e + 24));
      errDetail.trim();
    }
    detailOut = String(phone) + ": " + errDetail;
    return false;
  }
  detailOut = String(phone) + ": timeout phản hồi";
  return false;
}

void send_sms_to_target_blocking(String message) {
  smsSending = true;
  smsStatus = "Đang gửi";
  smsLastText = message;
  smsLastResult = "Chuẩn bị...";

  if (smsPhoneCount == 0) {
    smsMarkFail("Chưa cấu hình số nhận SMS trên app/web");
    return;
  }

  if (!eg800kPower) {
    smsMarkFail("Module SIM đang tắt nguồn");
    return;
  }

  if (serialMutex != NULL) {
    if (xSemaphoreTake(serialMutex, pdMS_TO_TICKS(20000)) != pdTRUE) {
      smsMarkFail("UART bận (GPS đang đọc) — thử lại sau");
      return;
    }
  }
  isSerialGPSBusy = true;

  Serial.println("\n--- TIEN HANH GUI SMS (BACKGROUND TASK) ---");
  Serial.print("  [SMS] Gui toi ");
  Serial.print(smsPhoneCount);
  Serial.print(" so: ");
  Serial.println(smsNumbersJoined());

  while (SerialGPS.available()) SerialGPS.read();

  SerialGPS.println("AT");
  String r = smsWaitResponse(1500);
  if (r.indexOf("OK") == -1) {
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    smsMarkFail("Module không trả lời AT — kiểm tra EN/UART/nguồn");
    return;
  }

  while (SerialGPS.available()) SerialGPS.read();
  SerialGPS.println("AT+CPIN?");
  r = smsWaitResponse(2000);
  if (r.indexOf("READY") == -1) {
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    if (r.indexOf("SIM PIN") != -1) smsMarkFail("SIM yêu cầu mã PIN");
    else if (r.indexOf("ERROR") != -1) smsMarkFail("Không đọc được SIM (AT+CPIN?)");
    else smsMarkFail("SIM chưa READY");
    return;
  }

  while (SerialGPS.available()) SerialGPS.read();
  SerialGPS.println("AT+CREG?");
  r = smsWaitResponse(2000);
  bool netOk = (r.indexOf(",1") != -1) || (r.indexOf(",5") != -1);
  if (!netOk) {
    Serial.println("  [SMS] Canh bao: chua dang ky mang (+CREG khong phai 1/5).");
  }

  while (SerialGPS.available()) SerialGPS.read();
  SerialGPS.println("AT+CSQ");
  r = smsWaitResponse(1500);
  int csq = -1;
  int csqIdx = r.indexOf("+CSQ:");
  if (csqIdx != -1) {
    csq = r.substring(csqIdx + 5).toInt();
  }
  if (csq == 99 || csq == 0) {
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    smsMarkFail("Không có sóng mạng (CSQ=" + String(csq) + ")");
    return;
  }

  while (SerialGPS.available()) SerialGPS.read();
  SerialGPS.println("AT+CMGF=1");
  r = smsWaitResponse(1500);
  if (r.indexOf("OK") == -1) {
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    smsMarkFail("AT+CMGF=1 lỗi — module chưa sẵn sàng SMS");
    return;
  }

  while (SerialGPS.available()) SerialGPS.read();
  SerialGPS.println("AT+CSCS=\"GSM\"");
  smsWaitResponse(1500);

  String body = message;
  if (body.length() > 150) body = body.substring(0, 150);

  uint8_t okN = 0;
  uint8_t failN = 0;
  String summary;
  for (uint8_t i = 0; i < smsPhoneCount; i++) {
    String detail;
    bool ok = send_sms_one_number(smsPhones[i], body, csq, netOk, detail);
    if (summary.length()) summary += " | ";
    summary += detail;
    if (ok) {
      okN++;
      smsSentCount++;
    } else {
      failN++;
      smsFailCount++;
    }
    delay(400);
  }

  smsLastSentMs = millis();
  smsLastResult = summary;
  if (okN > 0 && failN == 0) {
    smsStatus = "Thành công";
    smsLastResult = "OK " + String(okN) + "/" + String(smsPhoneCount) + " · CSQ=" + String(csq) + " · " + summary;
  } else if (okN > 0) {
    smsStatus = "Thành công một phần";
    smsLastResult = "OK " + String(okN) + "/" + String(smsPhoneCount) + " · " + summary;
  } else {
    smsStatus = "Thất bại";
    smsLastResult = "Lỗi 0/" + String(smsPhoneCount) + " · " + summary;
  }

  Serial.println("--- KET THUC QUY TRINH GUI SMS ---");
  Serial.println(smsLastResult);

  smsSending = false;
  isSerialGPSBusy = false;
  if (serialMutex != NULL) {
    xSemaphoreGive(serialMutex);
  }
}

void smsTaskCode(void * pvParameters) {
  SmsMessage msg;
  for (;;) {
    if (smsQueue != NULL && xQueueReceive(smsQueue, &msg, portMAX_DELAY) == pdPASS) {
      send_sms_to_target_blocking(String(msg.text));
    }
  }
}

void send_sms_to_target(String message) {
  if (smsPhoneCount == 0) {
    smsStatus = "Thất bại";
    smsLastResult = "Chưa cấu hình số nhận SMS trên app/web";
    smsLastText = message;
    smsFailCount++;
    smsLastSentMs = millis();
    Serial.println("  [SMS] Bo qua — chua co so nhan.");
    return;
  }
  if (smsQueue == NULL) {
    Serial.println("  [ERROR] smsQueue chua duoc khoi tao!");
    smsStatus = "Thất bại";
    smsLastResult = "Queue chưa khởi tạo";
    smsLastText = message;
    smsFailCount++;
    smsLastSentMs = millis();
    return;
  }
  SmsMessage msg;
  strncpy(msg.text, message.c_str(), sizeof(msg.text) - 1);
  msg.text[sizeof(msg.text) - 1] = '\0';
  if (xQueueSend(smsQueue, &msg, 0) != pdPASS) {
    Serial.println("  [WARNING] SMS queue day, tin nhan bi loai bo!");
    smsStatus = "Thất bại";
    smsLastResult = "Hàng đợi SMS đầy";
    smsLastText = message;
    smsFailCount++;
    smsLastSentMs = millis();
  } else {
    Serial.println("  [SMS Queue] Da xep hang tin nhan gui.");
    smsStatus = "Đang chờ gửi";
    smsLastText = message;
    smsLastResult = String("Đã xếp hàng → ") + smsNumbersJoined();
  }
}

void send_test_sms() {
  if (!eg800kPower) {
    Serial.println("  [EG800K] Cảnh báo: Module đang tắt nguồn! Vui lòng bật nguồn trước (nhấn phím 'e').");
    return;
  }
  if (smsPhoneCount == 0) {
    Serial.println("  [SMS] Chua cau hinh so nhan.");
    return;
  }
  send_sms_to_target("Test SMS from Quectel EC800K / Safety Remote");
}

void get_gps_data() {
  if (!eg800kPower) {
    Serial.println("  [EG800K] Cảnh báo: Module đang tắt nguồn! Vui lòng bật nguồn trước (nhấn phím 'e').");
    return;
  }
  Serial.println("  [EG800K] Đang kích hoạt và lấy tọa độ GPS...");
  sim_at_cmd("AT+QGPS=1"); // Bật nguồn GPS
  gpsEnabled = true;
  Serial.println("  Chờ định vị vệ tinh GPS (10 giây)...");
  delay(10000);
  sim_at_cmd("AT+QGPS?");
  sim_at_cmd("AT+QGPSLOC=2"); // Nhận thông tin GPS dạng độ thập phân
}

void check_sim_info() {
  if (!eg800kPower) {
    Serial.println("  [EG800K] Cảnh báo: Module đang tắt nguồn! Vui lòng bật nguồn trước (nhấn phím 'e').");
    return;
  }
  Serial.println("  [EG800K] Kiểm tra thông tin thẻ SIM và mạng di động...");
  sim_at_cmd("AT");
  sim_at_cmd("ATI");
  sim_at_cmd("AT+CPIN?");
  sim_at_cmd("AT+CSQ");
  sim_at_cmd("AT+CIMI");
}

void appendGpsToMessage(String &msg) {
  msg += "\nVi tri: ";
  if (gpsLatitude != "Chưa có dữ liệu" && gpsLatitude != "Đang tìm tín hiệu..." &&
      gpsLatitude != "Đang kích hoạt GPS..." && gpsLatitude != "Đang khởi động..." &&
      gpsLatitude != "Module tắt" &&
      gpsLongitude != "Chưa có dữ liệu" && gpsLongitude != "Đang tìm tín hiệu..." &&
      gpsLongitude != "Đang kích hoạt GPS..." && gpsLongitude != "Đang khởi động..." &&
      gpsLongitude != "Module tắt") {
    msg += "https://maps.google.com/?q=" + gpsLatitude + "," + gpsLongitude;
  } else {
    msg += gpsLatitude;
  }
}

void checkAlerts() {
  // 1. Đọc cảm biến nhiệt độ & độ ẩm
  float temp = 0, hum = 0;
  bool shtOk = readSHT31(temp, hum);

  // 2. Đọc cảm biến Gas MQ-2
  int rawGas = 0;
  bool gasAlert = false;
  readMQ2(rawGas, gasAlert);

  // 3. Đọc cảm biến báo cháy
  bool fireAlert = readFireSensor();

  // Còi kêu khi có gas hoặc cháy; tắt khi hết cả hai
  setBuzzer(gasAlert || fireAlert);

  // SMS chỉ gửi khi module SIM đang bật
  if (eg800kPower) {
    // Cảnh báo Gas
    if (gasAlert && !lastGasAlert) {
      if (lastGasSmsTime == 0 || (millis() - lastGasSmsTime >= SMS_COOLDOWN_MS)) {
        String msg = "[CANH BAO] Phat hien ro ri Gas/Khoi! Gas: " + String(rawGas) + "/4095.";
        appendGpsToMessage(msg);
        send_sms_to_target(msg);
        lastGasSmsTime = millis();
      } else {
        Serial.println("  [Anti-Spam SMS] Canh bao Gas bi chan do trong thoi gian cooldown.");
      }
    }

    // Cảnh báo Nhiệt độ
    if (shtOk) {
      // Trễ Hysteresis: bật > 40.0, tắt < 38.0
      bool tempAlert = lastTempAlert;
      if (temp > 40.0) {
        tempAlert = true;
      } else if (temp < 38.0) {
        tempAlert = false;
      }

      if (tempAlert && !lastTempAlert) {
        if (lastTempSmsTime == 0 || (millis() - lastTempSmsTime >= SMS_COOLDOWN_MS)) {
          String msg = "[CANH BAO] Nhiet do cao nguy hiem: " + String(temp, 1) + " C (vuot nguong 40 C).";
          appendGpsToMessage(msg);
          send_sms_to_target(msg);
          lastTempSmsTime = millis();
        } else {
          Serial.println("  [Anti-Spam SMS] Canh bao Nhiet do bi chan do trong thoi gian cooldown.");
        }
      }
      lastTempAlert = tempAlert;
    }

    // Cảnh báo cháy
    if (fireAlert && !lastFireAlert) {
      if (lastFireSmsTime == 0 || (millis() - lastFireSmsTime >= SMS_COOLDOWN_MS)) {
        String msg = "[CANH BAO] Phat hien CHAY!";
        appendGpsToMessage(msg);
        send_sms_to_target(msg);
        lastFireSmsTime = millis();
      } else {
        Serial.println("  [Anti-Spam SMS] Canh bao Chay bi chan do trong thoi gian cooldown.");
      }
    }
  }

  lastGasAlert = gasAlert;
  lastFireAlert = fireAlert;
}

// Chuyển ddmm.mmmmN/S hoặc dddmm.mmmmE/W sang độ thập phân (nếu module trả format 0)
String convertNmeaToDecimal(const String &raw) {
  String s = raw;
  s.trim();
  if (s.length() < 3) return "";

  char hemi = s.charAt(s.length() - 1);
  bool southOrWest = (hemi == 'S' || hemi == 'W' || hemi == 's' || hemi == 'w');
  bool hasHemi = (hemi == 'N' || hemi == 'S' || hemi == 'E' || hemi == 'W' ||
                  hemi == 'n' || hemi == 's' || hemi == 'e' || hemi == 'w');

  String numStr = hasHemi ? s.substring(0, s.length() - 1) : s;
  float val = numStr.toFloat();
  if (val == 0.0f && numStr.indexOf('0') == -1) return "";

  // Format 2: đã là (-)dd.ddddd — giữ nguyên
  if (!hasHemi && val <= 180.0f && val >= -180.0f && numStr.indexOf('.') != -1) {
    return String(val, 6);
  }

  // Format 0/1: ddmm.mmmmN/S hoặc dddmm.mmmmE/W
  float absVal = (val < 0) ? -val : val;
  int degrees = (int)(absVal / 100.0f);
  float minutes = absVal - (degrees * 100.0f);
  float decimal = degrees + (minutes / 60.0f);
  if (southOrWest || val < 0) decimal = -decimal;
  return String(decimal, 6);
}

// Gửi AT và chờ phản hồi (cần đã giữ serialMutex)
// Trong lúc chờ vẫn phục vụ HTTP để điện thoại không bị timeout Wi-Fi/web
String gpsAtCommand(const char* cmd, unsigned long timeoutMs = 2000) {
  while (SerialGPS.available()) {
    SerialGPS.read();
  }
  Serial.print("  [GPS AT] >> ");
  Serial.println(cmd);
  SerialGPS.println(cmd);

  String response = "";
  unsigned long start = millis();
  while (millis() - start < timeoutMs) {
    while (SerialGPS.available()) {
      response += (char)SerialGPS.read();
    }
    if (response.indexOf("OK") != -1 || response.indexOf("ERROR") != -1) {
      delay(30);
      while (SerialGPS.available()) {
        response += (char)SerialGPS.read();
      }
      break;
    }
    server.handleClient();
    yield();
  }
  Serial.print("  [GPS AT] << ");
  Serial.println(response.length() ? response : "(không phản hồi)");
  return response;
}

// AT+QGPS? → 0=OFF, 1=ON. Trả -1 nếu module không trả lời
int queryGpsEngineState() {
  String resp = gpsAtCommand("AT+QGPS?", 1500);
  if (resp.length() == 0) return -1;
  int idx = resp.indexOf("+QGPS:");
  if (idx == -1) {
    // Một số firmware trả OK mà không có +QGPS khi lỗi UART
    if (resp.indexOf("OK") != -1) return -1;
    return -1;
  }
  // +QGPS: 0 hoặc +QGPS: 1
  int colon = resp.indexOf(':', idx);
  if (colon == -1) return -1;
  return resp.substring(colon + 1).toInt();
}

void updateGPSData() {
  if (!eg800kPower) {
    gpsGnssStatus = "Module tắt nguồn";
    return;
  }

  if (serialMutex != NULL) {
    if (xSemaphoreTake(serialMutex, pdMS_TO_TICKS(1000)) != pdTRUE) {
      return;
    }
  }
  isSerialGPSBusy = true;

  // 1) Kiểm tra module còn sống không
  String atResp = gpsAtCommand("AT", 1000);
  if (atResp.indexOf("OK") == -1) {
    gpsEnabled = false;
    gpsGnssStatus = "Không phản hồi AT";
    gpsLatitude = "Lỗi kết nối";
    gpsLongitude = "Lỗi kết nối";
    Serial.println("  [GPS] Module EG800K khong tra loi AT — kiem tra EN_GPS, UART TX/RX, nguon.");
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    return;
  }

  // 2) Hỏi trạng thái GNSS thật: AT+QGPS?
  int gnssState = queryGpsEngineState();
  if (gnssState < 0) {
    gpsGnssStatus = "Lỗi đọc AT+QGPS?";
    Serial.println("  [GPS] Khong doc duoc trang thai AT+QGPS?");
  } else if (gnssState == 0) {
    gpsEnabled = false;
    gpsGnssStatus = "GNSS OFF";
    Serial.println("  [GPS] GNSS dang TAT (+QGPS: 0) — bat bang AT+QGPS=1");
  } else {
    gpsEnabled = true;
    gpsGnssStatus = "GNSS ON";
    Serial.println("  [GPS] GNSS dang BAT (+QGPS: 1)");
  }

  // 3) Nếu đang tắt → bật GNSS
  if (!gpsEnabled) {
    String bootResp = gpsAtCommand("AT+QGPS=1", 2000);
    // 504 = already started
    if (bootResp.indexOf("OK") != -1 || bootResp.indexOf("504") != -1) {
      gpsEnabled = true;
      gpsGnssStatus = "GNSS ON (vừa bật)";
      gpsLatitude = "Đang kích hoạt GPS...";
      gpsLongitude = "Đang kích hoạt GPS...";
      Serial.println("  [GPS] Da bat GNSS. Cho chu ky sau de lay toa do.");
    } else {
      gpsGnssStatus = "Bật GNSS thất bại";
      Serial.println("  [GPS] AT+QGPS=1 that bai.");
    }
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    return;
  }

  // 4) Đọc tọa độ dạng thập phân
  String response = gpsAtCommand("AT+QGPSLOC=2", 2500);

  // 505 = GNSS chưa bật
  if (response.indexOf("505") != -1) {
    gpsEnabled = false;
    gpsGnssStatus = "GNSS OFF (505)";
    gpsLatitude = "Đang kích hoạt GPS...";
    gpsLongitude = "Đang kích hoạt GPS...";
    gpsAtCommand("AT+QGPS=1", 2000);
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    return;
  }

  // 516 = đang tìm vệ tinh (engine ON nhưng chưa fix)
  if (response.indexOf("516") != -1) {
    gpsGnssStatus = "GNSS ON · đang tìm vệ tinh";
    gpsLatitude = "Đang tìm tín hiệu...";
    gpsLongitude = "Đang tìm tín hiệu...";
    Serial.println("  [GPS] CME 516: engine OK, chua co fix (dua antena ra troi trong).");
    isSerialGPSBusy = false;
    if (serialMutex != NULL) xSemaphoreGive(serialMutex);
    return;
  }

  // Parse +QGPSLOC: <UTC>,<lat>,<lon>,...
  int idx = response.indexOf("+QGPSLOC:");
  if (idx != -1) {
    String data = response.substring(idx + 9);
    data.trim();
    while (data.length() > 0 && (data.charAt(0) == ' ' || data.charAt(0) == '\t')) {
      data = data.substring(1);
    }

    int comma1 = data.indexOf(',');
    if (comma1 != -1) {
      int comma2 = data.indexOf(',', comma1 + 1);
      if (comma2 != -1) {
        int comma3 = data.indexOf(',', comma2 + 1);
        String latRaw = data.substring(comma1 + 1, comma2);
        String lonRaw = (comma3 != -1) ? data.substring(comma2 + 1, comma3) : data.substring(comma2 + 1);
        latRaw.trim();
        lonRaw.trim();

        String latDec = convertNmeaToDecimal(latRaw);
        String lonDec = convertNmeaToDecimal(lonRaw);

        if (latDec.length() > 0 && lonDec.length() > 0) {
          gpsLatitude = latDec;
          gpsLongitude = lonDec;
        } else {
          gpsLatitude = latRaw;
          gpsLongitude = lonRaw;
        }

        gpsGnssStatus = "GNSS FIX";
        Serial.print("  [GPS] FIX OK Lat=");
        Serial.print(gpsLatitude);
        Serial.print(", Lon=");
        Serial.println(gpsLongitude);

        isSerialGPSBusy = false;
        if (serialMutex != NULL) xSemaphoreGive(serialMutex);
        return;
      }
    }
  }

  gpsGnssStatus = "GNSS ON · chưa có tọa độ";
  gpsLatitude = "Đang tìm tín hiệu...";
  gpsLongitude = "Đang tìm tín hiệu...";
  Serial.println("  [GPS] Chua parse duoc +QGPSLOC.");

  isSerialGPSBusy = false;
  if (serialMutex != NULL) xSemaphoreGive(serialMutex);
}

void handleToggleGps() {
  setEG800KPower(!eg800kPower);
  server.send(200, "application/json", "{\"success\":true}");
}

void handleToggleBuzzer() {
  setBuzzer(!buzzerState);
  server.send(200, "application/json", "{\"success\":true,\"buzzer\":" + String(buzzerState ? "true" : "false") + "}");
}

void handleSendTestSms() {
  if (!eg800kPower) {
    server.send(200, "application/json", "{\"success\":false,\"error\":\"Module SIM đang tắt\"}");
    return;
  }
  if (smsPhoneCount == 0) {
    server.send(200, "application/json", "{\"success\":false,\"error\":\"Chưa cấu hình số nhận SMS\"}");
    return;
  }
  send_sms_to_target("Test SMS from Safety Remote Web");
  server.send(200, "application/json", "{\"success\":true,\"smsTo\":\"" + jsonEscape(smsNumbersJoined()) + "\"}");
}

void handleSmsNumbersGet() {
  String json = "{";
  json += "\"smsTo\":\"" + jsonEscape(smsNumbersJoined()) + "\",";
  json += "\"count\":" + String(smsPhoneCount) + ",";
  json += "\"max\":" + String(SMS_MAX_NUMBERS);
  json += "}";
  server.send(200, "application/json", json);
}

void handleSmsNumbersPost() {
  String raw = "";
  if (server.hasArg("numbers")) raw = server.arg("numbers");
  else if (server.hasArg("smsTo")) raw = server.arg("smsTo");

  String msg;
  if (!applySmsNumbersConfig(raw, &msg)) {
    server.send(400, "application/json",
      "{\"success\":false,\"message\":\"" + jsonEscape(msg) + "\"}");
    return;
  }
  server.send(200, "application/json",
    "{\"success\":true,\"message\":\"" + jsonEscape(msg) +
    "\",\"smsTo\":\"" + jsonEscape(smsNumbersJoined()) +
    "\",\"count\":" + String(smsPhoneCount) + "}");
}

// --- MQTT command hooks (Safety_Mqtt.h) ---
void mqttApplyBuzzerCommand(const String& raw) {
  String s = raw;
  s.trim();
  s.toUpperCase();
  if (s == "ON" || s == "1") setBuzzer(true);
  else if (s == "OFF" || s == "0") setBuzzer(false);
  else setBuzzer(!buzzerState);
}

void mqttApplyGpsCommand(const String& raw) {
  String s = raw;
  s.trim();
  s.toUpperCase();
  if (s == "ON" || s == "1") setEG800KPower(true);
  else if (s == "OFF" || s == "0") setEG800KPower(false);
  else setEG800KPower(!eg800kPower);
}

void mqttApplySmsCommand(const String& raw) {
  (void)raw;
  if (!eg800kPower) {
    smsStatus = "Thất bại";
    smsLastResult = "Module SIM đang tắt (MQTT)";
    return;
  }
  if (smsPhoneCount == 0) {
    smsStatus = "Thất bại";
    smsLastResult = "Chưa cấu hình số nhận SMS (MQTT)";
    return;
  }
  send_sms_to_target("Test SMS from Safety Remote MQTT");
}

void mqttApplySmsNumbersCommand(const String& raw) {
  String msg;
  if (!applySmsNumbersConfig(raw, &msg)) {
    smsLastResult = msg;
    Serial.print("  [SMS MQTT] Loi cau hinh: ");
    Serial.println(msg);
    return;
  }
  smsLastResult = msg;
}

String buildSensorJson() {
  float temp = -999, hum = -999;
  readSHT31(temp, hum);

  int rawGas = 0;
  bool gasAlert = false;
  readMQ2(rawGas, gasAlert);

  float volt = readVoltage12V();
  bool fireAlert = readFireSensor();

  unsigned long smsAgeSec = 0;
  if (smsLastSentMs > 0) {
    smsAgeSec = (millis() - smsLastSentMs) / 1000UL;
  }

  String json = "{";
  json += "\"temp\":" + String(temp, 2) + ",";
  json += "\"hum\":" + String(hum, 2) + ",";
  json += "\"volt\":" + String(volt, 2) + ",";
  json += "\"gas\":" + String(rawGas) + ",";
  json += "\"gasAlert\":" + String(gasAlert ? "true" : "false") + ",";
  json += "\"fireAlert\":" + String(fireAlert ? "true" : "false") + ",";
  json += "\"buzzer\":" + String(buzzerState ? "true" : "false") + ",";
  json += "\"gpsPower\":" + String(eg800kPower ? "true" : "false") + ",";
  json += "\"gpsGnss\":\"" + jsonEscape(gpsGnssStatus) + "\",";
  json += "\"gpsLat\":\"" + jsonEscape(gpsLatitude) + "\",";
  json += "\"gpsLon\":\"" + jsonEscape(gpsLongitude) + "\",";
  json += "\"smsTo\":\"" + jsonEscape(smsNumbersJoined()) + "\",";
  json += "\"smsCount\":" + String(smsPhoneCount) + ",";
  json += "\"smsStatus\":\"" + jsonEscape(smsStatus) + "\",";
  json += "\"smsText\":\"" + jsonEscape(smsLastText) + "\",";
  json += "\"smsResult\":\"" + jsonEscape(smsLastResult) + "\",";
  json += "\"smsSending\":" + String(smsSending ? "true" : "false") + ",";
  json += "\"smsSentCount\":" + String(smsSentCount) + ",";
  json += "\"smsFailCount\":" + String(smsFailCount) + ",";
  json += "\"smsAgeSec\":" + String(smsAgeSec) + ",";
  json += "\"wifiClients\":" + String(WiFi.softAPgetStationNum()) + ",";
  json += "\"wifiTxDbm\":" + String(WiFi.getTxPower() * 0.25f, 1) + ",";
  json += "\"wifiChannel\":" + String(WIFI_AP_CHANNEL) + ",";
  json += "\"mqttConnected\":" + String(safetyMqttConnected() ? "true" : "false") + ",";
  json += "\"chipId\":\"" + String(getSafetyChipId()) + "\",";
  json += "\"staIp\":\"" + safetyStaIp() + "\",";
  json += "\"staSsid\":\"" + jsonEscape(String(getSafetyStaSsid())) + "\",";
  json += "\"staConnected\":" + String(safetyStaConnected() ? "true" : "false") + ",";
  json += "\"staStatus\":\"" + jsonEscape(staConnStatus) + "\",";
  json += "\"staDetail\":\"" + jsonEscape(staConnDetail) + "\",";
  json += "\"portalActive\":" + String(portalApActive ? "true" : "false");
  json += "}";
  return json;
}

void handleCaptiveRedirect() {
  // Gộp portal + dashboard tại http://192.168.4.1/
  server.sendHeader("Cache-Control", "no-cache");
  server.sendHeader("Location", "http://192.168.4.1/", true);
  server.send(302, "text/plain", "Redirect to portal");
}

void handleWifiPage() {
  // Giữ /wifi → trang chính (một UI duy nhất)
  handleCaptiveRedirect();
}

void handleWifiApiGet() {
  String json = "{";
  json += "\"chipId\":\"" + String(getSafetyChipId()) + "\",";
  json += "\"staSsid\":\"" + jsonEscape(String(getSafetyStaSsid())) + "\",";
  json += "\"staIp\":\"" + safetyStaIp() + "\",";
  json += "\"staConnected\":" + String(safetyStaConnected() ? "true" : "false") + ",";
  json += "\"staStatus\":\"" + jsonEscape(staConnStatus) + "\",";
  json += "\"staDetail\":\"" + jsonEscape(staConnDetail) + "\",";
  json += "\"portalActive\":" + String(portalApActive ? "true" : "false") + ",";
  json += "\"mqttConnected\":" + String(safetyMqttConnected() ? "true" : "false") + ",";
  json += "\"portal\":\"http://192.168.4.1/\"";
  json += "}";
  server.sendHeader("Cache-Control", "no-store");
  server.send(200, "application/json", json);
}

void wifiScanTaskCode(void *pv) {
  (void)pv;
  for (;;) {
    while (!wifiScanRequest) {
      vTaskDelay(pdMS_TO_TICKS(50));
    }
    wifiScanRequest = false;
    wifiScanRunning = true;
    if (wifiScanMutex) xSemaphoreTake(wifiScanMutex, portMAX_DELAY);
    wifiScanResultJson = "{\"status\":\"scanning\",\"networks\":[]}";
    if (wifiScanMutex) xSemaphoreGive(wifiScanMutex);

    Serial.println("  [WIFI] Bat dau quet mang (background)...");
    WiFi.setScanMethod(WIFI_ALL_CHANNEL_SCAN);
    WiFi.setSortMethod(WIFI_CONNECT_AP_BY_SIGNAL);
    // Sync scan trong task riêng — không chặn HTTP SoftAP
    int n = WiFi.scanNetworks(/*async=*/false, /*hidden=*/true);
    if (n < 0) n = 0;

    struct Item { int idx; int rssi; };
    Item items[48];
    int count = 0;
    for (int i = 0; i < n && count < 48; i++) {
      if (WiFi.SSID(i).length() == 0) continue;
      items[count].idx = i;
      items[count].rssi = WiFi.RSSI(i);
      count++;
    }
    for (int i = 0; i < count; i++) {
      for (int j = i + 1; j < count; j++) {
        if (items[j].rssi > items[i].rssi) {
          Item t = items[i]; items[i] = items[j]; items[j] = t;
        }
      }
    }
    int outN = count > 24 ? 24 : count;
    String json = "{\"status\":\"done\",\"count\":" + String(outN) + ",\"networks\":[";
    for (int k = 0; k < outN; k++) {
      int i = items[k].idx;
      if (k) json += ",";
      json += "{\"ssid\":\"" + jsonEscape(WiFi.SSID(i)) + "\",";
      json += "\"rssi\":" + String(WiFi.RSSI(i)) + ",";
      json += "\"secure\":" + String(WiFi.encryptionType(i) != WIFI_AUTH_OPEN ? "true" : "false") + "}";
    }
    json += "]}";
    WiFi.scanDelete();

    if (wifiScanMutex) xSemaphoreTake(wifiScanMutex, portMAX_DELAY);
    wifiScanResultJson = json;
    if (wifiScanMutex) xSemaphoreGive(wifiScanMutex);
    wifiScanRunning = false;
    Serial.printf("  [WIFI] Quet xong: %d mang\n", outN);
  }
}

void handleWifiScan() {
  server.sendHeader("Cache-Control", "no-store");
  bool fresh = server.hasArg("fresh") && server.arg("fresh") == "1";

  if (wifiScanRunning) {
    server.send(200, "application/json", "{\"status\":\"scanning\",\"networks\":[]}");
    return;
  }

  String cached;
  if (wifiScanMutex && xSemaphoreTake(wifiScanMutex, pdMS_TO_TICKS(200)) == pdTRUE) {
    cached = wifiScanResultJson;
    xSemaphoreGive(wifiScanMutex);
  } else {
    cached = wifiScanResultJson;
  }

  // Có kết quả → trả về (poll)
  if (!fresh && cached.indexOf("\"status\":\"done\"") >= 0) {
    server.send(200, "application/json", cached);
    return;
  }

  // Chỉ bắt đầu quét khi ?fresh=1
  if (fresh) {
    if (wifiScanMutex && xSemaphoreTake(wifiScanMutex, pdMS_TO_TICKS(50)) == pdTRUE) {
      wifiScanResultJson = "{\"status\":\"scanning\",\"networks\":[]}";
      xSemaphoreGive(wifiScanMutex);
    }
    wifiScanRequest = true;
    server.send(200, "application/json", "{\"status\":\"scanning\",\"networks\":[]}");
    return;
  }

  server.send(200, "application/json", cached.length() ? cached : "{\"status\":\"idle\",\"networks\":[]}");
}

void handleWifiApiPost() {
  if (!server.hasArg("ssid")) {
    server.send(400, "application/json", "{\"success\":false,\"message\":\"Thieu ssid\"}");
    return;
  }
  String ssid = server.arg("ssid");
  String pass = server.hasArg("pass") ? server.arg("pass") : "";
  String chip = server.hasArg("chip") ? server.arg("chip") : SAFETY_DEFAULT_CHIP;
  ssid.trim();
  chip.trim();
  if (ssid.length() == 0) {
    server.send(400, "application/json", "{\"success\":false,\"message\":\"SSID rong\"}");
    return;
  }
  safetySaveWifiPrefs(ssid, pass, chip);
  staConnStatus = "Đang kết nối";
  staConnDetail = "Đang kết nối tới " + ssid + "...";
  staFailSinceMs = 0;
  // Giữ SoftAP đến khi GOT_IP (rồi hẹn tắt) — ĐT còn thấy báo thành công
  if (!portalApActive) startPortalAP("cau hinh WiFi moi");
  WiFi.disconnect(false);
  delay(100);
  safetyTryStaConnect(true);
  server.send(200, "application/json",
    "{\"success\":true,\"message\":\"Đã lưu. Đang kết nối Wi‑Fi nhà... SoftAP sẽ tắt sau khi thành công.\",\"staStatus\":\"Đang kết nối\",\"chipId\":\"" +
    String(getSafetyChipId()) + "\",\"portal\":\"http://192.168.4.1/\"}");
}

void mqttApplyPortalCommand(const String &raw) {
  String s = raw;
  s.trim();
  s.toUpperCase();
  if (s == "ON" || s == "1" || s == "OPEN") {
    startPortalAP("MQTT ban giao");
    staConnDetail = "Portal SoftAP đã mở để bàn giao / đổi Wi‑Fi (Safety Remote)";
  } else if (s == "OFF" || s == "0" || s == "CLOSE") {
    stopPortalAP("MQTT tat portal");
  } else {
    if (portalApActive) stopPortalAP("MQTT toggle");
    else startPortalAP("MQTT toggle ban giao");
  }
}

String jsonEscape(const String &s) {
  String out;
  out.reserve(s.length() + 8);
  for (size_t i = 0; i < s.length(); i++) {
    char c = s.charAt(i);
    if (c == '"' || c == '\\') {
      out += '\\';
      out += c;
    } else if (c == '\n') {
      out += "\\n";
    } else if (c == '\r') {
      out += "\\r";
    } else if (c == '\t') {
      out += "\\t";
    } else {
      out += c;
    }
  }
  return out;
}

// ==================================================================================
// 3.5. CẤU HÌNH WEB SERVER VÀ GIAO DIỆN WEB (HTML/CSS)
// ==================================================================================

#include "index_html.h"
#include "style_css.h"
#include "app_js.h"

void handleRoot() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.send_P(200, "text/html; charset=utf-8", HTML_CONTENT);
}

void handleStyleCss() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.send_P(200, "text/css; charset=utf-8", STYLE_CSS_CONTENT);
}

void handleAppJs() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.send_P(200, "application/javascript; charset=utf-8", APP_JS_CONTENT);
}

void handleSensors() {
  server.send(200, "application/json", buildSensorJson());
}

void startPortalAP(const char *why) {
  portalStopAtMs = 0;
  if (portalApActive) {
    Serial.printf("  [WIFI] SoftAP da mo (%s)\n", why ? why : "");
    return;
  }
  WiFi.mode(WIFI_AP_STA);
  delay(50);
  if (!WiFi.softAPConfig(local_IP, gateway, subnet)) {
    Serial.println("  [WIFI] softAPConfig() that bai");
  }
  bool ok = WiFi.softAP(ap_ssid, ap_password, WIFI_AP_CHANNEL, 0, WIFI_AP_MAX_CLIENTS);
  if (!ok) {
    delay(150);
    ok = WiFi.softAP(ap_ssid, ap_password, WIFI_AP_CHANNEL, 0, WIFI_AP_MAX_CLIENTS);
  }
  portalApActive = ok;
  applyWifiMaxPower();
  if (ok) {
    dnsServer.setErrorReplyCode(DNSReplyCode::NoError);
    dnsServer.start(53, "*", local_IP);
    portalDnsStarted = true;
  }
  Serial.printf("  [WIFI] SoftAP %s (%s) http://192.168.4.1/\n",
                ok ? "ON" : "FAIL", why ? why : "");
}

void stopPortalAP(const char *why) {
  portalStopAtMs = 0;
  if (portalDnsStarted) {
    dnsServer.stop();
    portalDnsStarted = false;
  }
  if (portalApActive || (WiFi.getMode() & WIFI_MODE_AP)) {
    WiFi.softAPdisconnect(true);
  }
  portalApActive = false;
  wifiStationCount = 0;
  if (safetyHasStaConfig() || safetyStaConnected()) {
    WiFi.mode(WIFI_STA);
    delay(30);
  }
  Serial.printf("  [WIFI] SoftAP OFF (%s)\n", why ? why : "");
}

void onWifiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_AP_STACONNECTED:
      wifiStationCount = WiFi.softAPgetStationNum();
      Serial.print("  [WIFI] DT SoftAP ket noi. So client: ");
      Serial.println(wifiStationCount);
      break;
    case ARDUINO_EVENT_WIFI_AP_STADISCONNECTED:
      wifiStationCount = WiFi.softAPgetStationNum();
      Serial.print("  [WIFI] DT SoftAP ngat. So client: ");
      Serial.println(wifiStationCount);
      break;
    case ARDUINO_EVENT_WIFI_STA_START:
      break;
    case ARDUINO_EVENT_WIFI_STA_CONNECTED:
      staConnStatus = "Đang kết nối";
      staConnDetail = String("Đã gắn AP ") + WiFi.SSID() + " — đang lấy IP...";
      Serial.println("  [WIFI] STA connected, waiting DHCP...");
      break;
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      staConnStatus = "Thành công";
      staConnDetail = String("✅ Kết nối thành công: ") + WiFi.SSID() +
                      " · IP " + WiFi.localIP().toString() +
                      " · SoftAP sẽ tắt sau vài giây";
      staConnOkMs = millis();
      staFailSinceMs = 0;
      // Hẹn tắt portal — không tắt ngay để ĐT còn đọc thông báo thành công
      if (portalApActive) {
        portalStopAtMs = millis() + PORTAL_STOP_DELAY_MS;
        Serial.println("  [WIFI] STA OK — hen tat SoftAP portal");
      }
      Serial.print("  [WIFI] STA THANH CONG IP=");
      Serial.println(WiFi.localIP());
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      if (safetyHasStaConfig()) {
        // Không ghi đè ngay sau GOT_IP (một số bản core bắn disconnect ngắn)
        if (staConnStatus == "Thành công" && (millis() - staConnOkMs) < 3000) break;
        staConnStatus = "Thất bại";
        staConnDetail = String("Không kết nối được \"") + String(getSafetyStaSsid()) +
                        "\". Kiểm tra mật khẩu / sóng rồi thử lại.";
        if (staFailSinceMs == 0) staFailSinceMs = millis();
        Serial.println("  [WIFI] STA disconnect / fail");
      }
      break;
    default:
      break;
  }
}

void applyWifiMaxPower() {
  wifi_mode_t mode = WiFi.getMode();
  if (mode == WIFI_MODE_NULL) {
    Serial.println("  [WIFI] skip TX power — WiFi mode chua san sang");
    return;
  }
  // Tắt tiết kiệm năng lượng — giữ RF luôn sẵn sàng phục vụ điện thoại
  WiFi.setSleep(false);
  esp_wifi_set_ps(WIFI_PS_NONE);

  // Công suất phát tối đa theo Arduino API (~19.5 dBm)
  WiFi.setTxPower(WIFI_POWER_19_5dBm);

  // esp_wifi_set_max_tx_power đơn vị 0.25 dBm → 78 = 19.5 dBm, 80 = 20 dBm (trần phần cứng)
  esp_wifi_set_max_tx_power(80);

  if (portalApActive || (mode & WIFI_MODE_AP)) {
    uint8_t protocol = WIFI_PROTOCOL_11B | WIFI_PROTOCOL_11G | WIFI_PROTOCOL_11N;
    esp_wifi_set_protocol(WIFI_IF_AP, protocol);
    esp_wifi_set_bandwidth(WIFI_IF_AP, WIFI_BW_HT20);
    esp_wifi_set_inactive_time(WIFI_IF_AP, 600); // giây
  }

  int txQdbm = WiFi.getTxPower(); // quarter-dBm
  Serial.print("  [WIFI] TX power thuc te: ");
  Serial.print(txQdbm * 0.25f, 2);
  Serial.println(" dBm (max ~20 dBm)");
}

void setupWiFi() {
  Serial.println("  [WIFI] Configuring WiFi...");

  // Đọc prefs trước để quyết định có mở SoftAP portal hay không
  safetyLoadWifiPrefs();

  WiFi.persistent(false);
  WiFi.onEvent(onWifiEvent);

  // Arduino-ESP32 3.x: WebServer::begin() tạo socket lwIP → phải bật WiFi/network
  // stack TRƯỚC, không thì crash xQueueSemaphoreTake (mutex lwIP NULL).
  if (!safetyHasStaConfig()) {
    startPortalAP("chua cau hinh WiFi nha");
  } else {
    portalApActive = false;
    portalDnsStarted = false;
    WiFi.mode(WIFI_STA);
    delay(80);
    applyWifiMaxPower();
  }

  server.on("/", handleRoot);
  server.on("/style.css", handleStyleCss);
  server.on("/app.js", handleAppJs);
  server.on("/wifi", handleWifiPage);
  server.on("/api/sensors", handleSensors);
  server.on("/api/toggleGps", handleToggleGps);
  server.on("/api/toggleBuzzer", handleToggleBuzzer);
  server.on("/api/sendTestSms", handleSendTestSms);
  server.on("/api/smsNumbers", HTTP_GET, handleSmsNumbersGet);
  server.on("/api/smsNumbers", HTTP_POST, handleSmsNumbersPost);
  server.on("/api/wifi", HTTP_GET, handleWifiApiGet);
  server.on("/api/wifi", HTTP_POST, handleWifiApiPost);
  server.on("/api/wifi/scan", HTTP_GET, handleWifiScan);

  // Captive portal probes → trang cấu hình WiFi
  server.on("/generate_204", handleCaptiveRedirect);
  server.on("/gen_204", handleCaptiveRedirect);
  server.on("/hotspot-detect.html", handleCaptiveRedirect);
  server.on("/library/test/success.html", handleCaptiveRedirect);
  server.on("/connecttest.txt", handleCaptiveRedirect);
  server.on("/ncsi.txt", handleCaptiveRedirect);
  server.on("/fwlink", handleCaptiveRedirect);
  server.on("/canonical.html", handleCaptiveRedirect);
  server.on("/success.txt", handleCaptiveRedirect);
  server.onNotFound([]() {
    if (server.method() == HTTP_GET) {
      handleCaptiveRedirect();
    } else {
      server.send(404, "text/plain", "Not found");
    }
  });

  server.begin();

  if (safetyHasStaConfig()) {
    // Đã có WiFi → chỉ STA, SoftAP tắt (portal khi bàn giao / mất WiFi)
    staConnStatus = "Đang kết nối";
    staConnDetail = String("Đang kết nối tới ") + String(getSafetyStaSsid()) + "...";
    safetyTryStaConnect(true);
    Serial.printf("  [WIFI] STA-only toi \"%s\" — SoftAP tat (ban giao: MQTT portal ON / mat WiFi)\n",
                  getSafetyStaSsid());
  }
}

// ==================================================================================
// 4. KHỞI TẠO HỆ THỐNG (SETUP)
// ==================================================================================
void setup() {
  // Khởi tạo Serial Debug với PC
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n==================================================");
  Serial.println("   VEHICLE SAFETY REMOTE BOARD - INITIALIZING...  ");
  Serial.println("==================================================");

  // Cấu hình chân đo áp và cảm biến Gas MQ-2
  pinMode(PIN_ADC_12V, INPUT);
  pinMode(PIN_MQ2_AO, INPUT);
  pinMode(PIN_MQ2_DO, INPUT);

  // Cấu hình cảm biến báo cháy & còi
  pinMode(PIN_FIRE_SIGNAL, INPUT_PULLUP);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);

  // Cấu hình module EG800K
  pinMode(PIN_EN_GPS, OUTPUT);
  digitalWrite(PIN_EN_GPS, HIGH); // Mặc định bật khi khởi động
  // Khởi tạo UART2 cho EG800K (Baud mặc định thường là 115200 bps)
  SerialGPS.begin(115200, SERIAL_8N1, PIN_RX_GPS, PIN_TX_GPS);

  // Khởi tạo I2C cho cảm biến SHT31
  Wire.begin(PIN_SDA, PIN_SCL);

  // Số nhận SMS (NVS) — cấu hình từ app/web
  loadSmsNumbers();

  // Khởi tạo Wi-Fi Access Point và Web Server
  setupWiFi();

  // MQTT từ xa (cần cấu hình WiFi nhà tại /wifi)
  initSafetyMqtt();

  // Khởi tạo hàng đợi và khóa Mutex cho GPS / SMS / WiFi scan không chặn Web
  smsQueue = xQueueCreate(10, sizeof(SmsMessage));
  serialMutex = xSemaphoreCreateMutex();
  wifiScanMutex = xSemaphoreCreateMutex();
  if (smsQueue != NULL) {
    xTaskCreate(
      smsTaskCode,
      "SmsTask",
      4096,
      NULL,
      1,
      NULL
    );
    Serial.println("  [SYSTEM] Da khoi tao background SMS task va queue.");
  }
  xTaskCreate(wifiScanTaskCode, "WifiScan", 8192, NULL, 1, NULL);
  Serial.println("  [SYSTEM] Da khoi tao background WiFi scan task.");

  if (safetyStaConnected()) {
    staConnStatus = "Thành công";
    staConnDetail = String("✅ Kết nối thành công: ") + WiFi.SSID() +
                    " · IP " + WiFi.localIP().toString();
    staConnOkMs = millis();
  } else if (safetyHasStaConfig()) {
    staConnStatus = "Đang kết nối";
    staConnDetail = String("Đang kết nối tới ") + String(getSafetyStaSsid()) + "...";
  }
}

// ==================================================================================
// 5. VÒNG LẶP CHÍNH (LOOP)
// ==================================================================================
void loop() {
  // SoftAP portal: DNS chỉ khi đang mở; hẹn tắt sau khi STA OK
  if (portalApActive) {
    dnsServer.processNextRequest();
  }
  if (portalStopAtMs != 0 && (int32_t)(millis() - portalStopAtMs) >= 0) {
    stopPortalAP("STA connected — het ban giao");
  }
  // Mất WiFi nhà lâu → mở lại portal để cấu hình / bàn giao
  if (safetyHasStaConfig() && !safetyStaConnected()) {
    if (staFailSinceMs == 0) staFailSinceMs = millis();
    else if (!portalApActive && (millis() - staFailSinceMs) >= STA_FAIL_OPEN_PORTAL_MS) {
      startPortalAP("mat WiFi nha — mo portal");
    }
  } else if (safetyStaConnected()) {
    staFailSinceMs = 0;
  }

  handleMqttClient();

  // Phục vụ HTTP ưu tiên — gọi nhiều lần mỗi vòng để DT không bị treo khi GPS/SMS bận
  server.handleClient();

  // Chuyển tiếp cổng Serial (Pass-through) hai chiều cho module EG800K khi module đang bật nguồn.
  if (eg800kPower && !isSerialGPSBusy) {
    while (SerialGPS.available()) {
      Serial.write(SerialGPS.read());
    }
    while (Serial.available()) {
      char c = (char)Serial.peek();
      // Phím 'p' = bật/tắt SoftAP portal bàn giao (không gửi sang module)
      if (c == 'p' || c == 'P') {
        Serial.read();
        if (portalApActive) stopPortalAP("serial p");
        else startPortalAP("serial p — ban giao");
      } else {
        SerialGPS.write(Serial.read());
      }
    }
  }

  server.handleClient();

  // Tự động gửi dữ liệu định kỳ (nếu chế độ streamMode được bật)
  if (streamMode && (millis() - lastStreamTime >= STREAM_INTERVAL)) {
    lastStreamTime = millis();
    readAndPrintAll();
  }

  server.handleClient();

  // Tự động cập nhật tọa độ GPS định kỳ nếu module đang bật nguồn
  if (eg800kPower && (millis() - lastGpsQueryTime >= GPS_QUERY_INTERVAL)) {
    lastGpsQueryTime = millis();
    updateGPSData();
  }

  server.handleClient();

  // Kiểm tra cảnh báo định kỳ mỗi 3 giây
  static unsigned long lastAlertCheckTime = 0;
  if (millis() - lastAlertCheckTime >= 3000) {
    lastAlertCheckTime = millis();
    checkAlerts();
  }

  // Định kỳ xác nhận TX power vẫn ở mức cao (một số bản core reset sau softAP)
  static unsigned long lastWifiPowerCheck = 0;
  if (millis() - lastWifiPowerCheck >= 60000UL) {
    lastWifiPowerCheck = millis();
    if (WiFi.getTxPower() < 70) { // < ~17.5 dBm
      applyWifiMaxPower();
      Serial.println("  [WIFI] Da nap lai TX power max.");
    }
  }
}

// ==================================================================================
// 7. HÀM THU THẬP VÀ HIỂN THỊ DỮ LIỆU TẬP TRUNG
// ==================================================================================
void readAndPrintAll() {
  Serial.println("\n=== BÁO CÁO THÔNG SỐ TOÀN HỆ THỐNG ===");

  // 1. Đọc điện áp nguồn
  Serial.print("  - Nguồn cấp 12V: ");
  Serial.print(readVoltage12V(), 2);
  Serial.println(" V");

  // 2. Đọc cảm biến SHT31
  float temp = 0, hum = 0;
  if (readSHT31(temp, hum)) {
    Serial.print("  - Nhiệt độ: ");
    Serial.print(temp, 1);
    Serial.print(" °C | Độ ẩm: ");
    Serial.print(hum, 1);
    Serial.println(" %RH");
  } else {
    Serial.println("  - Cảm biến SHT31: LỖI KẾT NỐI (I2C)");
  }

  // 3. Đọc cảm biến MQ-2
  int rawGas = 0;
  bool gasAlert = false;
  readMQ2(rawGas, gasAlert);
  Serial.print("  - Cảm biến Gas/Khói MQ-2: ");
  Serial.print(rawGas);
  Serial.print(" / 4095 (Analog) | Ngưỡng báo động: ");
  Serial.println(gasAlert ? "CẢNH BÁO!" : "Bình thường");

  // 4. Cảm biến báo cháy & Còi
  bool fireAlert = readFireSensor();
  Serial.print("  - Cảm biến báo cháy: ");
  Serial.println(fireAlert ? "PHÁT HIỆN CHÁY!" : "Bình thường");
  Serial.print("  - Còi: ");
  Serial.println(buzzerState ? "BẬT" : "TẮT");

  // 5. Trạng thái Module EG800K & GPS
  Serial.print("  - Nguồn EG800K: ");
  Serial.println(eg800kPower ? "Đang Bật" : "Đang Tắt");
  if (eg800kPower) {
    Serial.print("    -> GNSS: "); Serial.println(gpsGnssStatus);
    Serial.print("    -> Vĩ độ (Lat): "); Serial.println(gpsLatitude);
    Serial.print("    -> Kinh độ (Lon): "); Serial.println(gpsLongitude);
  }

  Serial.println("======================================");
}

// Định dạng thu gọn để stream định kỳ
void streamSensorsData() {
  float temp = 0, hum = 0;
  bool hasSHT = readSHT31(temp, hum);
  int rawGas = 0;
  bool gasAlert = false;
  readMQ2(rawGas, gasAlert);
  float volt = readVoltage12V();
  bool fireAlert = readFireSensor();

  // In ra định dạng CSV để dễ biểu diễn đồ thị hoặc truyền đi
  Serial.print("[STREAM],");
  Serial.print("Volt:"); Serial.print(volt, 2); Serial.print(",");
  if (hasSHT) {
    Serial.print("Temp:"); Serial.print(temp, 1); Serial.print(",");
    Serial.print("Hum:"); Serial.print(hum, 1); Serial.print(",");
  } else {
    Serial.print("Temp:ERR,Hum:ERR,");
  }
  Serial.print("Gas:"); Serial.print(rawGas); Serial.print(",");
  Serial.print("GasAlert:"); Serial.print(gasAlert ? 1 : 0); Serial.print(",");
  Serial.print("Fire:"); Serial.print(fireAlert ? 1 : 0); Serial.print(",");
  Serial.print("Buzzer:"); Serial.print(buzzerState ? 1 : 0); Serial.print(",");
  Serial.print("GPS_Lat:"); Serial.print(gpsLatitude); Serial.print(",");
  Serial.print("GPS_Lon:"); Serial.println(gpsLongitude);
}
