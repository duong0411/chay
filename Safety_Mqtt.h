/**
 * Safety Remote — MQTT từ xa (cùng broker LenMen / Smart First AID)
 * Broker WSS: mqtt.duynguyen.io.vn/mqtt
 *
 * Thư viện Arduino cần cài:
 *  - WebSockets by Markus Sattler (Links2004)
 *  - MQTTPubSubClient by hideakitai
 *
 * Topic:
 *  tele/{chip}/status          online|offline
 *  tele/{chip}_vitals/status   JSON cảm biến (giống /api/sensors)
 *  cmnd/{chip}_buzzer/POWER    ON|OFF|TOGGLE
 *  cmnd/{chip}_gps/POWER       TOGGLE|ON|OFF
 *  cmnd/{chip}_sms/POWER       bất kỳ → gửi SMS test
 */
#pragma once

#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <WebSocketsClient.h>
#include <MQTTPubSubClient.h>

#ifndef SAFETY_DEFAULT_CHIP
#define SAFETY_DEFAULT_CHIP "888"
#endif

#define SAFETY_MQTT_HOST "mqtt.duynguyen.io.vn"
#define SAFETY_MQTT_PORT 443
#define SAFETY_MQTT_PATH "/mqtt"

extern Preferences prefs;

// Cung cấp từ SafetyRemote.ino
extern String buildSensorJson();
extern void mqttApplyBuzzerCommand(const String& raw);
extern void mqttApplyGpsCommand(const String& raw);
extern void mqttApplySmsCommand(const String& raw);

static WebSocketsClient* safetyWs = nullptr;
static MQTTPubSubClient* safetyMqtt = nullptr;
static bool safetyMqttReady = false;
static char safetyChipId[24] = SAFETY_DEFAULT_CHIP;
static char safetyStaSsid[33] = "";
static char safetyStaPass[65] = "";
static uint32_t safetyLastMqttTele = 0;
static uint32_t safetyLastWifiTry = 0;
static uint32_t safetyLastMqttTry = 0;
static bool safetyStaWanted = false;

inline const char* getSafetyChipId() { return safetyChipId; }
inline bool safetyMqttConnected() { return safetyMqtt && safetyMqtt->isConnected(); }
inline bool safetyStaConnected() { return WiFi.status() == WL_CONNECTED; }
inline String safetyStaIp() {
  return safetyStaConnected() ? WiFi.localIP().toString() : String("-");
}
inline bool safetyHasStaConfig() { return safetyStaWanted; }
inline const char* getSafetyStaSsid() { return safetyStaSsid; }

inline void safetyLoadWifiPrefs() {
  prefs.begin("safety", true);
  String chip = prefs.getString("chipId", SAFETY_DEFAULT_CHIP);
  String ssid = prefs.getString("staSsid", "");
  String pass = prefs.getString("staPass", "");
  prefs.end();

  chip.trim();
  if (chip.length() == 0) chip = SAFETY_DEFAULT_CHIP;
  chip.toCharArray(safetyChipId, sizeof(safetyChipId));
  ssid.toCharArray(safetyStaSsid, sizeof(safetyStaSsid));
  pass.toCharArray(safetyStaPass, sizeof(safetyStaPass));
  safetyStaWanted = (strlen(safetyStaSsid) > 0);
  Serial.printf("[MQTT] Chip=%s STA SSID=%s\n",
                safetyChipId, safetyStaWanted ? safetyStaSsid : "(chua cau hinh)");
}

inline void safetySaveWifiPrefs(const String& ssid, const String& pass, const String& chip) {
  String c = chip.length() ? chip : String(SAFETY_DEFAULT_CHIP);
  prefs.begin("safety", false);
  prefs.putString("staSsid", ssid);
  prefs.putString("staPass", pass);
  prefs.putString("chipId", c);
  prefs.end();
  ssid.toCharArray(safetyStaSsid, sizeof(safetyStaSsid));
  pass.toCharArray(safetyStaPass, sizeof(safetyStaPass));
  c.toCharArray(safetyChipId, sizeof(safetyChipId));
  safetyStaWanted = (strlen(safetyStaSsid) > 0);
}

inline void safetyMqttPub(const String& topicTail, const String& payload, bool retained = false) {
  if (!safetyMqttConnected()) return;
  safetyMqtt->publish(String("tele/") + topicTail + "/status", payload, retained, 0);
}

inline void safetyPublishOnline() {
  safetyMqttPub(String(safetyChipId), "online", true);
}

inline void safetyPublishVitals() {
  safetyMqttPub(String(safetyChipId) + "_vitals", buildSensorJson(), false);
}

inline void safetyHandleCmd(const String& kind, const String& raw) {
  Serial.printf("[MQTT] CMD %s = %s\n", kind.c_str(), raw.c_str());
  if (kind == "buzzer") {
    mqttApplyBuzzerCommand(raw);
    safetyPublishVitals();
  } else if (kind == "gps") {
    mqttApplyGpsCommand(raw);
    safetyPublishVitals();
  } else if (kind == "sms") {
    mqttApplySmsCommand(raw);
    safetyPublishVitals();
  }
}

inline void safetyMqttEnsureConnected() {
  if (!safetyMqtt || !safetyWs) return;
  if (safetyMqtt->isConnected()) return;
  if (!safetyWs->isConnected()) return;
  if (millis() - safetyLastMqttTry < 4000) return;
  safetyLastMqttTry = millis();

  String id = String("SR") + String((uint32_t)ESP.getEfuseMac(), HEX);
  safetyMqtt->setWill(String("tele/") + safetyChipId + "/status", "offline", true, 1);
  if (!safetyMqtt->connect(id, "", "")) {
    Serial.println("[MQTT] Ket noi broker that bai");
    return;
  }
  Serial.println("[MQTT] Da ket noi broker");
  safetyPublishOnline();
  safetyPublishVitals();

  String buzzerTopic = String("cmnd/") + safetyChipId + "_buzzer/POWER";
  String gpsTopic = String("cmnd/") + safetyChipId + "_gps/POWER";
  String smsTopic = String("cmnd/") + safetyChipId + "_sms/POWER";

  safetyMqtt->subscribe(buzzerTopic, [](const char* p, unsigned int n) {
    String s;
    for (unsigned i = 0; i < n; i++) s += p[i];
    safetyHandleCmd("buzzer", s);
  });
  delay(20);
  safetyMqtt->subscribe(gpsTopic, [](const char* p, unsigned int n) {
    String s;
    for (unsigned i = 0; i < n; i++) s += p[i];
    safetyHandleCmd("gps", s);
  });
  delay(20);
  safetyMqtt->subscribe(smsTopic, [](const char* p, unsigned int n) {
    String s;
    for (unsigned i = 0; i < n; i++) s += p[i];
    safetyHandleCmd("sms", s);
  });
}

inline void safetyTryStaConnect(bool force = false) {
  if (!safetyStaWanted) return;
  if (safetyStaConnected()) return;
  if (!force && millis() - safetyLastWifiTry < 15000) return;
  safetyLastWifiTry = millis();
  Serial.printf("[WIFI] STA dang ket noi %s ...\n", safetyStaSsid);
  WiFi.setSleep(false);
  WiFi.begin(safetyStaSsid, safetyStaPass);
}

inline void initSafetyMqtt() {
  safetyLoadWifiPrefs();
  if (safetyMqttReady) return;
  safetyMqttReady = true;

  safetyWs = new WebSocketsClient();
  safetyMqtt = new MQTTPubSubClient();
  safetyWs->beginSSL(SAFETY_MQTT_HOST, SAFETY_MQTT_PORT, SAFETY_MQTT_PATH);
  safetyWs->setExtraHeaders("Sec-WebSocket-Protocol: mqtt");
  safetyWs->setReconnectInterval(5000);
  safetyMqtt->begin(*safetyWs);
  safetyMqtt->setTimeout(8000);
  Serial.println("[MQTT] Client san sang (cho WiFi nha)");
  safetyTryStaConnect(true);
}

inline void handleMqttClient() {
  if (!safetyMqttReady) return;

  if (safetyStaWanted && !safetyStaConnected()) {
    safetyTryStaConnect(false);
  }

  if (safetyStaConnected()) {
    safetyWs->loop();
    safetyMqtt->update();
    safetyMqttEnsureConnected();

    if (safetyMqttConnected() && millis() - safetyLastMqttTele >= 2000) {
      safetyLastMqttTele = millis();
      safetyPublishVitals();
      static uint32_t lastOnline = 0;
      if (millis() - lastOnline > 20000) {
        lastOnline = millis();
        safetyPublishOnline();
      }
    }
  }
}
