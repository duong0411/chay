import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// Local + high-priority fire/gas alerts (works with background isolate).
class AlertNotifications {
  AlertNotifications._();
  static final AlertNotifications instance = AlertNotifications._();

  static const int monitorId = 1001;
  static const int alarmId = 2001;

  static const String monitorChannelId = 'safety_monitor';
  static const String alarmChannelId = 'safety_alarm';

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  bool _ready = false;
  bool? _lastFire;
  bool? _lastGas;

  Future<void> init() async {
    if (_ready) return;

    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    await _plugin.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
    );

    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await android?.createNotificationChannel(
      const AndroidNotificationChannel(
        monitorChannelId,
        'Giám sát an toàn',
        description: 'Thông báo nền khi app đang theo dõi cháy/gas',
        importance: Importance.low,
      ),
    );
    await android?.createNotificationChannel(
      const AndroidNotificationChannel(
        alarmChannelId,
        'Cảnh báo cháy / gas',
        description: 'Cảnh báo khẩn khi phát hiện cháy hoặc rò gas',
        importance: Importance.max,
        playSound: true,
        enableVibration: true,
        enableLights: true,
      ),
    );

    _ready = true;
  }

  Future<void> requestPermission() async {
    await init();
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await android?.requestNotificationsPermission();

    final ios = _plugin.resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin>();
    await ios?.requestPermissions(alert: true, badge: true, sound: true);
  }

  Future<void> showMonitorOngoing({required String status}) async {
    await init();
    const android = AndroidNotificationDetails(
      monitorChannelId,
      'Giám sát an toàn',
      channelDescription: 'Thông báo nền khi app đang theo dõi cháy/gas',
      importance: Importance.low,
      priority: Priority.low,
      ongoing: true,
      autoCancel: false,
      showWhen: false,
      category: AndroidNotificationCategory.service,
    );
    const ios = DarwinNotificationDetails(
      presentAlert: false,
      presentBadge: false,
      presentSound: false,
    );
    await _plugin.show(
      monitorId,
      'Safety Remote đang giám sát',
      status,
      const NotificationDetails(android: android, iOS: ios),
    );
  }

  Future<void> cancelMonitor() async {
    await _plugin.cancel(monitorId);
  }

  /// Edge-triggered: only notify when alert turns on (or worsens).
  Future<void> handleSensorAlerts({
    required bool fireAlert,
    required bool gasAlert,
    String? detail,
  }) async {
    final fireRise = fireAlert && _lastFire != true;
    final gasRise = gasAlert && _lastGas != true;
    _lastFire = fireAlert;
    _lastGas = gasAlert;

    if (!fireRise && !gasRise) return;

    final String title;
    if (fireAlert && gasAlert) {
      title = 'HỎA HOẠN CHÁY TO';
    } else if (fireAlert) {
      title = 'BÁO CHÁY';
    } else {
      title = 'CÓ KHÓI';
    }
    final body = (detail == null || detail.isEmpty)
        ? 'Mở Safety Remote ngay để kiểm tra thiết bị.'
        : detail;

    await showAlarm(title: title, body: body);
  }

  Future<void> showAlarm({
    required String title,
    required String body,
  }) async {
    await init();
    if (kDebugMode) print('ALARM: $title — $body');

    const android = AndroidNotificationDetails(
      alarmChannelId,
      'Cảnh báo cháy / gas',
      channelDescription: 'Cảnh báo khẩn khi phát hiện cháy hoặc rò gas',
      importance: Importance.max,
      priority: Priority.max,
      category: AndroidNotificationCategory.alarm,
      fullScreenIntent: true,
      visibility: NotificationVisibility.public,
      playSound: true,
      enableVibration: true,
      ticker: 'Cảnh báo Safety Remote',
    );
    const ios = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
      interruptionLevel: InterruptionLevel.timeSensitive,
    );

    await _plugin.show(
      alarmId,
      title,
      body,
      const NotificationDetails(android: android, iOS: ios),
    );
  }

  void resetAlertEdge() {
    _lastFire = null;
    _lastGas = null;
  }
}
