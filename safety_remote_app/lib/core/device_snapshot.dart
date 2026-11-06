class DeviceSnapshot {
  DeviceSnapshot({
    required this.temp,
    required this.hum,
    required this.volt,
    required this.gas,
    required this.gasAlert,
    required this.fireAlert,
    required this.buzzer,
    required this.gpsPower,
    required this.gpsGnss,
    required this.gpsLat,
    required this.gpsLon,
    required this.smsTo,
    required this.smsStatus,
    required this.smsText,
    required this.smsResult,
    required this.smsSending,
    required this.smsSentCount,
    required this.smsFailCount,
    required this.smsAgeSec,
    required this.wifiClients,
    required this.wifiTxDbm,
    required this.wifiChannel,
  });

  final double temp;
  final double hum;
  final double volt;
  final int gas;
  final bool gasAlert;
  final bool fireAlert;
  final bool buzzer;
  final bool gpsPower;
  final String gpsGnss;
  final String gpsLat;
  final String gpsLon;
  final String smsTo;
  final String smsStatus;
  final String smsText;
  final String smsResult;
  final bool smsSending;
  final int smsSentCount;
  final int smsFailCount;
  final int smsAgeSec;
  final int wifiClients;
  final double wifiTxDbm;
  final int wifiChannel;

  bool get shtOk => temp > -900;
  bool get alarmActive => gasAlert || fireAlert;

  String get alarmLabel {
    final parts = <String>[];
    if (fireAlert) parts.add('Phát hiện cháy');
    if (gasAlert) parts.add('Rò gas/khói');
    return parts.isEmpty ? 'An toàn' : parts.join(' · ');
  }

  bool get hasFix {
    final bad = {
      'Chưa có dữ liệu',
      'Đang tìm tín hiệu...',
      'Đang kích hoạt GPS...',
      'Đang khởi động...',
      'Module tắt',
      'Lỗi kết nối',
      '--',
      '',
    };
    return gpsPower &&
        !bad.contains(gpsLat) &&
        !bad.contains(gpsLon) &&
        double.tryParse(gpsLat) != null &&
        double.tryParse(gpsLon) != null;
  }

  factory DeviceSnapshot.fromJson(Map<String, dynamic> json) {
    double d(dynamic v, [double fallback = 0]) {
      if (v is num) return v.toDouble();
      return double.tryParse('$v') ?? fallback;
    }

    int i(dynamic v, [int fallback = 0]) {
      if (v is num) return v.toInt();
      return int.tryParse('$v') ?? fallback;
    }

    bool b(dynamic v) => v == true || v == 1 || '$v' == 'true';

    return DeviceSnapshot(
      temp: d(json['temp'], -999),
      hum: d(json['hum']),
      volt: d(json['volt']),
      gas: i(json['gas']),
      gasAlert: b(json['gasAlert']),
      fireAlert: b(json['fireAlert']),
      buzzer: b(json['buzzer']),
      gpsPower: b(json['gpsPower']),
      gpsGnss: '${json['gpsGnss'] ?? ''}',
      gpsLat: '${json['gpsLat'] ?? '--'}',
      gpsLon: '${json['gpsLon'] ?? '--'}',
      smsTo: '${json['smsTo'] ?? ''}',
      smsStatus: '${json['smsStatus'] ?? 'Chưa gửi'}',
      smsText: '${json['smsText'] ?? ''}',
      smsResult: '${json['smsResult'] ?? ''}',
      smsSending: b(json['smsSending']),
      smsSentCount: i(json['smsSentCount']),
      smsFailCount: i(json['smsFailCount']),
      smsAgeSec: i(json['smsAgeSec']),
      wifiClients: i(json['wifiClients']),
      wifiTxDbm: d(json['wifiTxDbm']),
      wifiChannel: i(json['wifiChannel'], 1),
    );
  }
}
