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
    this.visionFire = false,
    this.visionLabel = '',
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
  final bool visionFire;
  final String visionLabel;

  bool get shtOk => temp > -900;
  bool get blazeAlert => fireAlert || visionFire;
  bool get alarmActive => gasAlert || blazeAlert;

  /// Khói → Có khói · Camera/GPIO lửa → Báo cháy · Cả hai → Hỏa hoạn cháy to
  String get alarmLabel {
    if (gasAlert && blazeAlert) return 'Hỏa hoạn cháy to';
    if (blazeAlert) return 'Báo cháy';
    if (gasAlert) return 'Có khói';
    return 'An toàn';
  }

  DeviceSnapshot withVision({required bool fire, String label = ''}) {
    return DeviceSnapshot(
      temp: temp,
      hum: hum,
      volt: volt,
      gas: gas,
      gasAlert: gasAlert,
      fireAlert: fireAlert,
      buzzer: buzzer,
      gpsPower: gpsPower,
      gpsGnss: gpsGnss,
      gpsLat: gpsLat,
      gpsLon: gpsLon,
      smsTo: smsTo,
      smsStatus: smsStatus,
      smsText: smsText,
      smsResult: smsResult,
      smsSending: smsSending,
      smsSentCount: smsSentCount,
      smsFailCount: smsFailCount,
      smsAgeSec: smsAgeSec,
      wifiClients: wifiClients,
      wifiTxDbm: wifiTxDbm,
      wifiChannel: wifiChannel,
      visionFire: fire,
      visionLabel: label,
    );
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
