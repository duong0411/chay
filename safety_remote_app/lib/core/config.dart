/// SoftAP gần máy hoặc MQTT từ xa (cùng broker LenMen / First AID).
class AppConfig {
  static const String defaultHost = '192.168.4.8';
  static const String wifiName = 'Safety Remote';
  static const String wifiPassword = '1234567890';
  static const String deviceName = 'Safety Remote';

  static const String brokerUrl = 'wss://mqtt.duynguyen.io.vn/mqtt';
  static const String defaultChipId = '888';

  static const String hostPrefKey = 'safety_device_host';
  static const String chipPrefKey = 'safety_device_chip';
  static const String modePrefKey = 'safety_connect_mode';
  static const String bgEnabledPrefKey = 'safety_bg_enabled';

  static const Duration pollInterval = Duration(milliseconds: 1500);
  static const Duration requestTimeout = Duration(seconds: 4);

  static String chipId = defaultChipId;

  static void setChipId(String id) {
    final cleaned = id.trim();
    chipId = cleaned.isEmpty ? defaultChipId : cleaned;
  }

  static String get topicOnline => 'tele/$chipId/status';
  static String get topicVitals => 'tele/${chipId}_vitals/status';
  /// Cảnh báo camera AI từ laptop (Safety Remote Desktop → MQTT duynguyen).
  static String get topicVision => 'tele/${chipId}_vision/status';
  static String get cmndBuzzer => 'cmnd/${chipId}_buzzer/POWER';
  static String get cmndGps => 'cmnd/${chipId}_gps/POWER';
  static String get cmndSms => 'cmnd/${chipId}_sms/POWER';

  static List<String> get subscribeTopics =>
      [topicOnline, topicVitals, topicVision];
}
