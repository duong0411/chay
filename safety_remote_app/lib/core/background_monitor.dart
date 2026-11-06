import 'dart:async';
import 'dart:convert';
import 'dart:ui';

import 'package:flutter/widgets.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:http/http.dart' as http;
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'alert_notifications.dart';
import 'config.dart';
import 'device_api.dart';

/// Keeps MQTT / SoftAP polling alive after the UI is closed (Android FG service).
class BackgroundMonitor {
  static const String notifyChannelId = AlertNotifications.monitorChannelId;
  static const int notifyId = AlertNotifications.monitorId;

  static Future<void> configure() async {
    final service = FlutterBackgroundService();
    await service.configure(
      androidConfiguration: AndroidConfiguration(
        onStart: onStart,
        autoStart: false,
        isForegroundMode: true,
        notificationChannelId: notifyChannelId,
        initialNotificationTitle: 'Safety Remote đang giám sát',
        initialNotificationContent: 'Đang chờ dữ liệu cảm biến...',
        foregroundServiceNotificationId: notifyId,
        foregroundServiceTypes: [AndroidForegroundType.dataSync],
      ),
      iosConfiguration: IosConfiguration(
        autoStart: false,
        onForeground: onStart,
        onBackground: onIosBackground,
      ),
    );
  }

  static Future<void> start({
    required ConnectMode mode,
    required String host,
    required String chipId,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.modePrefKey, mode == ConnectMode.mqtt ? 'mqtt' : 'local');
    await prefs.setString(AppConfig.hostPrefKey, host);
    await prefs.setString(AppConfig.chipPrefKey, chipId);
    await prefs.setBool(AppConfig.bgEnabledPrefKey, true);

    final service = FlutterBackgroundService();
    final running = await service.isRunning();
    if (running) {
      service.invoke('reload');
      return;
    }
    await service.startService();
  }

  static Future<void> stop() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(AppConfig.bgEnabledPrefKey, false);
    final service = FlutterBackgroundService();
    final running = await service.isRunning();
    if (running) {
      service.invoke('stop');
    }
    await AlertNotifications.instance.cancelMonitor();
  }

  @pragma('vm:entry-point')
  static Future<bool> onIosBackground(ServiceInstance service) async {
    WidgetsFlutterBinding.ensureInitialized();
    DartPluginRegistrant.ensureInitialized();
    return true;
  }

  @pragma('vm:entry-point')
  static void onStart(ServiceInstance service) async {
    DartPluginRegistrant.ensureInitialized();
    WidgetsFlutterBinding.ensureInitialized();

    final alerts = AlertNotifications.instance;
    await alerts.init();

    if (service is AndroidServiceInstance) {
      await service.setAsForegroundService();
    }

    final runner = _BgRunner(service: service, alerts: alerts);
    await runner.start();

    service.on('stop').listen((_) async {
      await runner.dispose();
      await service.stopSelf();
    });
    service.on('reload').listen((_) async {
      await runner.reload();
    });
  }
}

class _BgRunner {
  _BgRunner({required this.service, required this.alerts});

  final ServiceInstance service;
  final AlertNotifications alerts;

  Timer? _poll;
  MqttServerClient? _mqtt;
  StreamSubscription? _mqttSub;
  bool _disposed = false;

  Future<void> start() async {
    await reload();
  }

  Future<void> reload() async {
    await _tearDownLinks();
    if (_disposed) return;

    final prefs = await SharedPreferences.getInstance();
    final enabled = prefs.getBool(AppConfig.bgEnabledPrefKey) ?? false;
    if (!enabled) {
      await service.stopSelf();
      return;
    }

    final mode = prefs.getString(AppConfig.modePrefKey) == 'mqtt'
        ? ConnectMode.mqtt
        : ConnectMode.local;
    final host = prefs.getString(AppConfig.hostPrefKey) ?? AppConfig.defaultHost;
    final chip = prefs.getString(AppConfig.chipPrefKey) ?? AppConfig.defaultChipId;
    AppConfig.setChipId(chip);

    final android = service is AndroidServiceInstance
        ? service as AndroidServiceInstance
        : null;
    if (android != null) {
      await android.setForegroundNotificationInfo(
        title: 'Safety Remote đang giám sát',
        content: mode == ConnectMode.mqtt
            ? 'MQTT chip $chip'
            : 'Gần máy · $host',
      );
    }

    if (mode == ConnectMode.mqtt) {
      await _connectMqtt();
    } else {
      _poll = Timer.periodic(AppConfig.pollInterval, (_) => _pollLocal(host));
      await _pollLocal(host);
    }
  }

  Future<void> _pollLocal(String host) async {
    try {
      var cleaned = host.trim().replaceFirst(RegExp(r'^https?://'), '');
      cleaned = cleaned.replaceAll(RegExp(r'/+$'), '');
      if (cleaned.isEmpty) cleaned = AppConfig.defaultHost;
      final res = await http
          .get(Uri.parse('http://$cleaned/api/sensors'))
          .timeout(AppConfig.requestTimeout);
      if (res.statusCode < 200 || res.statusCode >= 300) return;
      final map = jsonDecode(res.body);
      if (map is! Map) return;
      await _onVitals(Map<String, dynamic>.from(map));
    } catch (_) {}
  }

  Future<void> _connectMqtt() async {
    final uri = Uri.parse(AppConfig.brokerUrl);
    final scheme = uri.scheme.isNotEmpty ? uri.scheme : 'wss';
    final host = uri.host.isNotEmpty ? uri.host : 'mqtt.duynguyen.io.vn';
    final port = uri.port != 0 ? uri.port : 443;
    final path = uri.path.isNotEmpty ? uri.path : '/mqtt';
    final clientId =
        'safety_bg_${DateTime.now().millisecondsSinceEpoch}';

    final client = MqttServerClient.withPort('$scheme://$host$path', clientId, port);
    _mqtt = client;
    client.useWebSocket = true;
    client.websocketProtocols = MqttClientConstants.protocolsSingleDefault;
    client.logging(on: false);
    client.setProtocolV311();
    client.keepAlivePeriod = 45;
    client.connectTimeoutPeriod = 15000;
    client.autoReconnect = true;
    client.resubscribeOnAutoReconnect = true;
    client.connectionMessage = MqttConnectMessage()
        .withClientIdentifier(clientId)
        .startClean()
        .withWillQos(MqttQos.atLeastOnce);

    try {
      await client.connect().timeout(const Duration(seconds: 18));
    } catch (_) {
      final android = service is AndroidServiceInstance
          ? service as AndroidServiceInstance
          : null;
      if (android != null) {
        await android.setForegroundNotificationInfo(
          title: 'Safety Remote',
          content: 'Mất MQTT — đang thử lại...',
        );
      }
      return;
    }

    if (client.connectionStatus?.state != MqttConnectionState.connected) {
      return;
    }

    for (final topic in AppConfig.subscribeTopics) {
      client.subscribe(topic, MqttQos.atLeastOnce);
    }

    _mqttSub = client.updates?.listen((events) async {
      for (final event in events) {
        final rec = event.payload as MqttPublishMessage;
        final payload =
            MqttPublishPayload.bytesToStringAsString(rec.payload.message);
        if (event.topic != AppConfig.topicVitals) continue;
        try {
          final decoded = jsonDecode(payload);
          if (decoded is Map) {
            await _onVitals(Map<String, dynamic>.from(decoded));
          }
        } catch (_) {}
      }
    });
  }

  Future<void> _onVitals(Map<String, dynamic> map) async {
    bool b(dynamic v) => v == true || v == 1 || '$v' == 'true';
    final fire = b(map['fireAlert']);
    final gas = b(map['gasAlert']);
    final temp = map['temp'];
    final gasVal = map['gas'];

    final detail = [
      if (fire) 'Cảm biến cháy GPIO26',
      if (gas) 'Gas/khói: $gasVal',
      if (temp != null) 'Nhiệt: $temp°C',
    ].join(' · ');

    await alerts.handleSensorAlerts(
      fireAlert: fire,
      gasAlert: gas,
      detail: detail,
    );

    final android = service is AndroidServiceInstance
        ? service as AndroidServiceInstance
        : null;
    if (android != null) {
      final status = (fire || gas)
          ? (fire ? '🔥 CẢNH BÁO CHÁY' : '⚠ RÒ GAS/KHÓI')
          : 'An toàn · Temp $temp · Gas $gasVal';
      await android.setForegroundNotificationInfo(
        title: 'Safety Remote đang giám sát',
        content: status,
      );
    }

    service.invoke('vitals', map);
  }

  Future<void> _tearDownLinks() async {
    _poll?.cancel();
    _poll = null;
    await _mqttSub?.cancel();
    _mqttSub = null;
    try {
      _mqtt?.autoReconnect = false;
      _mqtt?.disconnect();
    } catch (_) {}
    _mqtt = null;
    alerts.resetAlertEdge();
  }

  Future<void> dispose() async {
    _disposed = true;
    await _tearDownLinks();
  }
}
