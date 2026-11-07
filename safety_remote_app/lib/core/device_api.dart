import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'device_snapshot.dart';

class DeviceException implements Exception {
  DeviceException(this.message);
  final String message;

  @override
  String toString() => message;
}

enum ConnectMode { local, mqtt }

class DeviceApi {
  DeviceApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Future<DeviceSnapshot> fetchSensors(String host) {
    return _guard(host, () async {
      final res = await _client
          .get(_uri(host, '/api/sensors'))
          .timeout(AppConfig.requestTimeout);
      return DeviceSnapshot.fromJson(_decode(res));
    });
  }

  Future<Map<String, dynamic>> toggleBuzzer(String host) =>
      _getAction(host, '/api/toggleBuzzer');

  Future<Map<String, dynamic>> toggleGps(String host) =>
      _getAction(host, '/api/toggleGps');

  Future<Map<String, dynamic>> sendTestSms(String host) =>
      _getAction(host, '/api/sendTestSms');

  Future<Map<String, dynamic>> setSmsNumbers(String host, String numbers) {
    return _guard(host, () async {
      final res = await _client
          .post(
            _uri(host, '/api/smsNumbers'),
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: {'numbers': numbers},
          )
          .timeout(AppConfig.requestTimeout);
      return _decode(res);
    });
  }

  Future<Map<String, dynamic>> _getAction(String host, String path) {
    return _guard(host, () async {
      final res = await _client
          .get(_uri(host, path))
          .timeout(AppConfig.requestTimeout);
      return _decode(res);
    });
  }

  Future<T> _guard<T>(String host, Future<T> Function() run) async {
    try {
      return await run();
    } on DeviceException {
      rethrow;
    } on TimeoutException {
      throw DeviceException(
        'Máy $host không phản hồi. Kiểm tra Wi-Fi ${AppConfig.wifiName}.',
      );
    } catch (_) {
      throw DeviceException(
        'Không kết nối được $host. Bật thiết bị và vào Wi-Fi ${AppConfig.wifiName}.',
      );
    }
  }

  Map<String, dynamic> _decode(http.Response res) {
    Map<String, dynamic> json = {};
    try {
      final decoded = jsonDecode(res.body);
      if (decoded is Map<String, dynamic>) {
        json = decoded;
      } else if (decoded is Map) {
        json = decoded.map((k, v) => MapEntry(k.toString(), v));
      }
    } catch (_) {
      throw DeviceException('Máy trả về dữ liệu không đọc được.');
    }
    if (res.statusCode < 200 || res.statusCode >= 300) {
      final message = json['message']?.toString() ?? json['error']?.toString();
      throw DeviceException(
        (message == null || message.isEmpty)
            ? 'Máy trả về mã ${res.statusCode}'
            : message,
      );
    }
    return json;
  }

  Uri _uri(String host, String path) {
    var cleaned = host.trim().replaceFirst(RegExp(r'^https?://'), '');
    cleaned = cleaned.replaceAll(RegExp(r'/+$'), '');
    if (cleaned.isEmpty) cleaned = AppConfig.defaultHost;
    return Uri.parse('http://$cleaned$path');
  }
}

class HostStore {
  Future<String?> readHost() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(AppConfig.hostPrefKey);
  }

  Future<void> writeHost(String host) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.hostPrefKey, host);
  }

  Future<String?> readChip() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(AppConfig.chipPrefKey);
  }

  Future<void> writeChip(String chip) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConfig.chipPrefKey, chip);
  }

  Future<ConnectMode> readMode() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(AppConfig.modePrefKey);
    return raw == 'mqtt' ? ConnectMode.mqtt : ConnectMode.local;
  }

  Future<void> writeMode(ConnectMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      AppConfig.modePrefKey,
      mode == ConnectMode.mqtt ? 'mqtt' : 'local',
    );
  }
}
