import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

import 'config.dart';

class MqttService {
  MqttServerClient? _client;
  StreamSubscription<List<MqttReceivedMessage<MqttMessage?>>>? _updatesSub;
  bool _connecting = false;
  bool _isConnected = false;

  bool get isConnected =>
      _isConnected &&
      _client?.connectionStatus?.state == MqttConnectionState.connected;

  String lastError = '';
  String clientId = '';

  final _messageController = StreamController<Map<String, dynamic>>.broadcast();
  Stream<Map<String, dynamic>> get messages => _messageController.stream;

  Future<bool> connect({
    String brokerUrl = AppConfig.brokerUrl,
    bool force = false,
  }) async {
    if (_connecting) return false;
    if (!force && isConnected) {
      _subscribeAll();
      return true;
    }

    _connecting = true;
    lastError = '';
    await _safeDisconnect();

    final uri = Uri.parse(brokerUrl);
    final scheme = uri.scheme.isNotEmpty ? uri.scheme : 'wss';
    final host = uri.host.isNotEmpty ? uri.host : 'mqtt.duynguyen.io.vn';
    final port = uri.port != 0 ? uri.port : 443;
    final path = uri.path.isNotEmpty ? uri.path : '/mqtt';
    clientId = 'safety_app_${DateTime.now().millisecondsSinceEpoch}';

    final wsUrl = '$scheme://$host$path';
    if (kDebugMode) print('MQTT: connecting $wsUrl');

    final client = MqttServerClient.withPort(wsUrl, clientId, port);
    _client = client;
    client.useWebSocket = true;
    client.websocketProtocols = MqttClientConstants.protocolsSingleDefault;
    client.logging(on: false);
    client.setProtocolV311();
    client.keepAlivePeriod = 60;
    client.connectTimeoutPeriod = 15000;
    client.autoReconnect = true;
    client.resubscribeOnAutoReconnect = true;

    client.onConnected = () {
      _isConnected = true;
      _subscribeAll();
    };
    client.onDisconnected = () => _isConnected = false;
    client.onAutoReconnected = () {
      _isConnected = true;
      _listen();
      _subscribeAll();
    };

    client.connectionMessage = MqttConnectMessage()
        .withClientIdentifier(clientId)
        .startClean()
        .withWillTopic('tele/safety_app/status')
        .withWillMessage('offline')
        .withWillQos(MqttQos.atLeastOnce);

    try {
      await client.connect().timeout(const Duration(seconds: 18));
    } catch (e) {
      lastError = e.toString();
      _isConnected = false;
      _connecting = false;
      await _safeDisconnect();
      return false;
    }

    final ok = client.connectionStatus?.state == MqttConnectionState.connected;
    _isConnected = ok;
    _connecting = false;
    if (!ok) {
      lastError = client.connectionStatus?.toString() ?? 'connect failed';
      await _safeDisconnect();
      return false;
    }

    _listen();
    _subscribeAll();
    return true;
  }

  void _subscribeAll() {
    final client = _client;
    if (client == null || !isConnected) return;
    for (final topic in AppConfig.subscribeTopics) {
      try {
        client.subscribe(topic, MqttQos.atLeastOnce);
      } catch (_) {}
    }
  }

  void _listen() {
    _updatesSub?.cancel();
    final updates = _client?.updates;
    if (updates == null) return;

    _updatesSub = updates.listen((events) {
      for (final event in events) {
        final rec = event.payload as MqttPublishMessage;
        final payload =
            MqttPublishPayload.bytesToStringAsString(rec.payload.message);
        final topic = event.topic;

        dynamic value;
        try {
          final decoded = jsonDecode(payload);
          if (decoded is Map && decoded.containsKey('value')) {
            value = decoded['value'];
          } else {
            value = decoded;
          }
        } catch (_) {
          value = payload.trim();
        }

        if (!_messageController.isClosed) {
          _messageController.add({
            'topic': topic,
            'value': value,
            'raw': payload,
          });
        }
      }
    });
  }

  void publish(String topic, String message) {
    if (!isConnected || _client == null) return;
    final builder = MqttClientPayloadBuilder()..addString(message);
    _client!.publishMessage(topic, MqttQos.atLeastOnce, builder.payload!);
  }

  void toggleBuzzer() => publish(AppConfig.cmndBuzzer, 'TOGGLE');
  void toggleGps() => publish(AppConfig.cmndGps, 'ON'); // GPS luôn bật
  void ensureGpsOn() => publish(AppConfig.cmndGps, 'ON');
  void sendTestSms() => publish(AppConfig.cmndSms, 'ON');
  void setSmsNumbers(String numbers) =>
      publish(AppConfig.cmndSmsNumbers, numbers.trim());

  Future<void> _safeDisconnect() async {
    _updatesSub?.cancel();
    _updatesSub = null;
    _isConnected = false;
    final client = _client;
    _client = null;
    if (client == null) return;
    try {
      client.autoReconnect = false;
      client.disconnect();
    } catch (_) {}
  }

  Future<void> disconnect() => _safeDisconnect();

  Future<void> dispose() async {
    await _safeDisconnect();
    if (!_messageController.isClosed) {
      await _messageController.close();
    }
  }
}
