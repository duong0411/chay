import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';

import 'alert_notifications.dart';
import 'background_monitor.dart';
import 'config.dart';
import 'device_api.dart';
import 'device_snapshot.dart';
import 'mqtt_service.dart';

class MonitorProvider extends ChangeNotifier {
  MonitorProvider({
    DeviceApi? api,
    HostStore? hosts,
    MqttService? mqtt,
  })  : _api = api ?? DeviceApi(),
        _hosts = hosts ?? HostStore(),
        _mqtt = mqtt ?? MqttService();

  final DeviceApi _api;
  final HostStore _hosts;
  final MqttService _mqtt;
  final AlertNotifications _alerts = AlertNotifications.instance;

  Timer? _timer;
  StreamSubscription? _mqttSub;

  bool connecting = false;
  bool entered = false;
  bool live = false;
  bool backgroundOn = false;
  bool visionFire = false;
  String visionLabel = '';
  ConnectMode mode = ConnectMode.mqtt;
  String host = AppConfig.defaultHost;
  String chipId = AppConfig.defaultChipId;
  String status = 'Nhập Chip ID để theo dõi từ xa';
  DeviceSnapshot? data;

  bool get canEnterSystem => entered && (data != null || isMqtt);
  bool get isMqtt => mode == ConnectMode.mqtt;

  Future<void> loadSavedHost() async {
    // App mobile chỉ theo dõi từ xa (MQTT) — bỏ SoftAP gần máy trên UI.
    mode = ConnectMode.mqtt;
    await _hosts.writeMode(ConnectMode.mqtt);
    final savedHost = await _hosts.readHost();
    final savedChip = await _hosts.readChip();
    if (savedHost != null && savedHost.trim().isNotEmpty) {
      host = savedHost.trim();
    }
    if (savedChip != null && savedChip.trim().isNotEmpty) {
      chipId = savedChip.trim();
      AppConfig.setChipId(chipId);
    }
    status = 'Nhập Chip ID để theo dõi từ xa';
    notifyListeners();
  }

  Future<void> _ensureNotifyPermission() async {
    await _alerts.requestPermission();
    if (await Permission.notification.isDenied) {
      await Permission.notification.request();
    }
  }

  Future<void> _startBackground() async {
    await _ensureNotifyPermission();
    await BackgroundMonitor.start(mode: mode, host: host, chipId: chipId);
    backgroundOn = true;
  }

  Future<bool> connectLocal(String rawHost) async {
    final next = rawHost.trim().isEmpty ? AppConfig.defaultHost : rawHost.trim();
    connecting = true;
    mode = ConnectMode.local;
    status = 'Đang vào máy $next...';
    notifyListeners();

    await _mqtt.disconnect();
    _mqttSub?.cancel();
    _mqttSub = null;

    try {
      final snap = await _api.fetchSensors(next);
      host = next;
      await _hosts.writeHost(next);
      await _hosts.writeMode(ConnectMode.local);
      data = snap;
      entered = true;
      live = true;
      status = 'Gần máy · $next';
      _startPoll();
      await _startBackground();
      await _alerts.handleSensorAlerts(
        fireAlert: snap.fireAlert,
        gasAlert: snap.gasAlert,
        detail: snap.alarmLabel,
      );
      return true;
    } on DeviceException catch (e) {
      entered = false;
      live = false;
      status = e.message;
      return false;
    } finally {
      connecting = false;
      notifyListeners();
    }
  }

  Future<bool> connectMqtt(String rawChip) async {
    final id = rawChip.trim().isEmpty ? AppConfig.defaultChipId : rawChip.trim();
    connecting = true;
    mode = ConnectMode.mqtt;
    AppConfig.setChipId(id);
    chipId = AppConfig.chipId;
    status = 'Đang vào MQTT chip $chipId...';
    data = null;
    notifyListeners();

    _timer?.cancel();
    _timer = null;

    final ok = await _mqtt.connect(force: true);
    if (!ok) {
      connecting = false;
      entered = false;
      live = false;
      status = 'Không vào được broker. Kiểm tra Internet.';
      notifyListeners();
      return false;
    }

    await _hosts.writeChip(chipId);
    await _hosts.writeMode(ConnectMode.mqtt);
    _mqttSub?.cancel();
    _mqttSub = _mqtt.messages.listen(_onMqtt);
    _mqtt.ensureGpsOn();
    await _startBackground();
    connecting = false;
    entered = true;
    live = false;
    status = 'MQTT OK · chờ chip $chipId online...';
    notifyListeners();
    return true;
  }

  void disconnect() {
    _timer?.cancel();
    _timer = null;
    _mqttSub?.cancel();
    _mqttSub = null;
    unawaited(_mqtt.disconnect());
    unawaited(BackgroundMonitor.stop());
    backgroundOn = false;
    visionFire = false;
    visionLabel = '';
    entered = false;
    live = false;
    data = null;
    _alerts.resetAlertEdge();
    mode = ConnectMode.mqtt;
    status = 'Đã ngắt MQTT. Nhập Chip ID để theo dõi từ xa.';
    notifyListeners();
  }

  Future<void> refresh() async {
    if (isMqtt) {
      status = live ? 'MQTT · chip $chipId' : 'Đang chờ chip $chipId...';
      notifyListeners();
      return;
    }
    if (!entered) return;
    try {
      data = await _api.fetchSensors(host);
      live = true;
      status = 'Gần máy · $host';
      await _alerts.handleSensorAlerts(
        fireAlert: data!.fireAlert,
        gasAlert: data!.gasAlert,
        detail: data!.alarmLabel,
      );
    } on DeviceException catch (e) {
      live = false;
      status = e.message;
    }
    notifyListeners();
  }

  Future<void> toggleBuzzer() async {
    if (isMqtt) {
      _mqtt.toggleBuzzer();
      return;
    }
    await _api.toggleBuzzer(host);
    await refresh();
  }

  Future<void> toggleGps() async => ensureGpsOn();

  /// Định vị luôn bật — app không tắt GPS/SIM.
  Future<void> ensureGpsOn() async {
    if (isMqtt) {
      _mqtt.ensureGpsOn();
      return;
    }
    await _api.toggleGps(host);
    await refresh();
  }

  Future<void> sendTestSms() async {
    if (isMqtt) {
      _mqtt.sendTestSms();
      return;
    }
    final res = await _api.sendTestSms(host);
    if (res['success'] == false) {
      throw DeviceException('${res['error'] ?? 'Không gửi được SMS'}');
    }
    await refresh();
  }

  Future<void> saveSmsNumbers(String numbers) async {
    final cleaned = numbers.trim();
    if (cleaned.isEmpty) {
      throw DeviceException('Nhập ít nhất 1 số điện thoại');
    }
    if (isMqtt) {
      _mqtt.setSmsNumbers(cleaned);
      status = 'Đã gửi cấu hình số SMS qua MQTT';
      notifyListeners();
      return;
    }
    final res = await _api.setSmsNumbers(host, cleaned);
    if (res['success'] == false) {
      throw DeviceException('${res['message'] ?? 'Không lưu được số SMS'}');
    }
    await refresh();
  }

  Future<void> testAlarmNotification() async {
    await _ensureNotifyPermission();
    await _alerts.showAlarm(
      title: 'Kiểm tra cảnh báo cháy',
      body: 'Thông báo nền hoạt động — tắt app vẫn nhận được khi giám sát bật.',
    );
  }

  void _onMqtt(Map<String, dynamic> msg) {
    final topic = msg['topic'] as String? ?? '';
    final value = msg['value'];
    final raw = msg['raw']?.toString() ?? '';

    if (topic == AppConfig.topicOnline) {
      final online = value.toString().toLowerCase() == 'online';
      live = online || data != null;
      status = online ? 'Từ xa · chip $chipId online' : 'Chip $chipId offline';
      notifyListeners();
      return;
    }

    if (topic == AppConfig.topicVitals) {
      try {
        final map = value is Map<String, dynamic>
            ? value
            : value is Map
                ? value.map((k, v) => MapEntry(k.toString(), v))
                : jsonDecode(raw) as Map<String, dynamic>;
        data = DeviceSnapshot.fromJson(map).withVision(
          fire: visionFire,
          label: visionLabel,
        );
        live = true;
        status = 'Từ xa · chip $chipId';
        unawaited(
          _alerts.handleSensorAlerts(
            fireAlert: data!.fireAlert || data!.visionFire,
            gasAlert: data!.gasAlert,
            detail: data!.alarmLabel,
          ),
        );
        notifyListeners();
      } catch (e) {
        if (kDebugMode) print('vitals parse: $e');
      }
      return;
    }

    if (topic == AppConfig.topicVision) {
      try {
        final map = value is Map<String, dynamic>
            ? value
            : value is Map
                ? value.map((k, v) => MapEntry(k.toString(), v))
                : jsonDecode(raw) as Map<String, dynamic>;
        final fire = map['fireAlert'] == true ||
            map['fireAlert'] == 1 ||
            '${map['fireAlert']}' == 'true';
        visionFire = fire;
        visionLabel = '${map['label'] ?? ''}'.trim().isEmpty
            ? 'Camera AI laptop phát hiện lửa'
            : '${map['label']}';
        if (data != null) {
          data = data!.withVision(fire: visionFire, label: visionLabel);
        }
        status = fire
            ? 'Camera AI · cảnh báo lửa (MQTT)'
            : 'Camera AI · hết cảnh báo';
        unawaited(
          _alerts.handleSensorAlerts(
            fireAlert: fire || (data?.fireAlert ?? false),
            gasAlert: data?.gasAlert ?? false,
            detail: fire
                ? visionLabel
                : (data?.alarmLabel ?? 'An toàn'),
          ),
        );
        notifyListeners();
      } catch (e) {
        if (kDebugMode) print('vision parse: $e');
      }
    }
  }

  void _startPoll() {
    _timer?.cancel();
    _timer = Timer.periodic(AppConfig.pollInterval, (_) => refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _mqttSub?.cancel();
    unawaited(_mqtt.dispose());
    super.dispose();
  }
}
