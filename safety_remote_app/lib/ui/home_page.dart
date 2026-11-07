import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/device_api.dart';
import '../core/monitor_provider.dart';
import 'theme.dart';
import 'widgets/feedback.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final device = context.watch<MonitorProvider>();
    final data = device.data;
    if (data == null) {
      return Scaffold(
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF070B12), SafetyTheme.deep, Color(0xFF171022)],
            ),
          ),
          child: SafeArea(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(28),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const CircularProgressIndicator(color: SafetyTheme.cyan),
                    const SizedBox(height: 18),
                    Text(
                      device.status,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 18),
                    TextButton(
                      onPressed: () => context.read<MonitorProvider>().disconnect(),
                      child: const Text('Ngắt kết nối'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF070B12), SafetyTheme.deep, Color(0xFF171022)],
          ),
        ),
        child: SafeArea(
          child: RefreshIndicator(
            color: SafetyTheme.cyan,
            onRefresh: device.refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 36),
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'SAFETY REMOTE',
                            style: TextStyle(
                              fontWeight: FontWeight.w800,
                              letterSpacing: 0.4,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(
                                  color: device.live ? SafetyTheme.safe : SafetyTheme.force,
                                  shape: BoxShape.circle,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  device.live
                                      ? 'Từ xa · chip ${device.chipId}'
                                      : device.status,
                                  style: const TextStyle(
                                    color: SafetyTheme.muted,
                                    fontSize: 12,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Ngắt kết nối',
                      onPressed: () => context.read<MonitorProvider>().disconnect(),
                      icon: const Icon(Icons.link_off_rounded, color: SafetyTheme.soft),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                _AlarmBanner(active: data.alarmActive, label: data.alarmLabel),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: _MetricTile(
                        label: 'Nguồn 12V',
                        value: data.volt.toStringAsFixed(2),
                        unit: 'V',
                        detail: data.volt >= 11.2 ? 'Ổn định' : 'Điện áp thấp',
                        icon: Icons.battery_charging_full_rounded,
                        color: SafetyTheme.cyan,
                        alert: data.volt < 11.2,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _MetricTile(
                        label: 'Nhiệt / ẩm',
                        value: data.shtOk ? data.temp.toStringAsFixed(1) : 'LỖI',
                        unit: data.shtOk ? '°C' : '',
                        detail: data.shtOk
                            ? '${data.hum.toStringAsFixed(1)} %RH'
                            : 'Lỗi I2C SHT31',
                        icon: Icons.thermostat_rounded,
                        color: SafetyTheme.force,
                        alert: data.shtOk && data.temp > 40,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: _MetricTile(
                        label: 'Khói / Gas / CO',
                        value: '${data.gas}',
                        unit: '',
                        detail: data.gasAlert ? 'CÓ KHÓI' : 'An toàn · /4095',
                        icon: Icons.cloud_rounded,
                        color: SafetyTheme.pulse,
                        alert: data.gasAlert,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _MetricTile(
                        label: 'Báo cháy',
                        value: data.blazeAlert ? 'CHÁY' : 'OK',
                        unit: '',
                        detail: data.visionFire
                            ? 'Camera AI phát hiện lửa'
                            : (data.fireAlert ? 'Cảm biến cháy' : 'GPIO26 · Signal'),
                        icon: Icons.local_fire_department_rounded,
                        color: SafetyTheme.pulse,
                        alert: data.blazeAlert,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                _GpsCard(device: device),
                const SizedBox(height: 12),
                _SmsCard(device: device),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      child: _ActionButton(
                        label: data.buzzer ? 'Còi: BẬT' : 'Còi: TẮT',
                        icon: data.buzzer
                            ? Icons.notifications_active_rounded
                            : Icons.notifications_off_rounded,
                        color: data.buzzer ? SafetyTheme.pulse : SafetyTheme.soft,
                        onTap: () => _act(context, device.toggleBuzzer),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _ActionButton(
                        label: 'Định vị: LUÔN BẬT',
                        icon: Icons.satellite_alt_rounded,
                        color: SafetyTheme.cyan,
                        onTap: () => _act(
                          context,
                          device.ensureGpsOn,
                          ok: 'Đã giữ GPS luôn bật',
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                _ActionButton(
                  label: data.smsSending ? 'Đang gửi SMS...' : 'Gửi SMS test',
                  icon: Icons.sms_rounded,
                  color: SafetyTheme.force,
                  onTap: data.smsSending
                      ? () {}
                      : () => _act(
                            context,
                            device.sendTestSms,
                            ok: 'Đã xếp hàng SMS test',
                          ),
                ),
                const SizedBox(height: 10),
                _ActionButton(
                  label: 'Test cảnh báo nền',
                  icon: Icons.notification_important_rounded,
                  color: SafetyTheme.pulse,
                  onTap: () => _act(
                    context,
                    device.testAlarmNotification,
                    ok: 'Đã gửi thông báo test',
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  device.backgroundOn
                      ? 'Cảnh báo nền: BẬT (tắt app vẫn giám sát như Shopee)'
                      : 'Cảnh báo nền: TẮT',
                  style: TextStyle(
                    color: device.backgroundOn ? SafetyTheme.safe : SafetyTheme.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Wi‑Fi CH${data.wifiChannel} · ${data.wifiTxDbm.toStringAsFixed(1)} dBm · ${data.wifiClients} ĐT',
                  style: const TextStyle(color: SafetyTheme.muted, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _act(
    BuildContext context,
    Future<void> Function() run, {
    String? ok,
  }) async {
    try {
      await run();
      if (context.mounted && ok != null) {
        showAppSnack(context, message: ok, success: true);
      }
    } on DeviceException catch (e) {
      if (context.mounted) showAppSnack(context, message: e.message);
    }
  }
}

class _AlarmBanner extends StatelessWidget {
  const _AlarmBanner({required this.active, required this.label});
  final bool active;
  final String label;

  @override
  Widget build(BuildContext context) {
    final color = active ? SafetyTheme.pulse : SafetyTheme.safe;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.45)),
      ),
      child: Row(
        children: [
          Icon(
            active ? Icons.warning_rounded : Icons.verified_user_rounded,
            color: color,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              active ? label : 'Các chỉ số đang trong ngưỡng an toàn',
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _GpsCard extends StatelessWidget {
  const _GpsCard({required this.device});
  final MonitorProvider device;

  @override
  Widget build(BuildContext context) {
    final data = device.data!;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SafetyTheme.panel.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'SIM 4G & GPS',
                  style: TextStyle(
                    color: SafetyTheme.muted,
                    fontWeight: FontWeight.w800,
                    fontSize: 12,
                    letterSpacing: 0.4,
                  ),
                ),
              ),
              _chip(
                data.gpsPower
                    ? (data.gpsGnss.contains('FIX') ? 'FIX' : 'ON')
                    : 'TẮT',
                data.gpsPower ? SafetyTheme.safe : SafetyTheme.muted,
              ),
            ],
          ),
          const SizedBox(height: 10),
          _kv('GNSS', data.gpsGnss.isEmpty ? '--' : data.gpsGnss),
          _kv('Vĩ độ', data.gpsLat),
          _kv('Kinh độ', data.gpsLon),
          if (data.hasFix) ...[
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () async {
                final uri = Uri.parse(
                  'https://maps.google.com/?q=${data.gpsLat},${data.gpsLon}',
                );
                await launchUrl(uri, mode: LaunchMode.externalApplication);
              },
              icon: const Icon(Icons.map_rounded, color: SafetyTheme.cyan),
              label: const Text(
                'Mở Google Maps',
                style: TextStyle(
                  color: SafetyTheme.cyan,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _kv(String k, String v) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: RichText(
        text: TextSpan(
          style: const TextStyle(color: SafetyTheme.muted, fontSize: 14),
          children: [
            TextSpan(text: '$k: '),
            TextSpan(
              text: v,
              style: const TextStyle(
                color: SafetyTheme.cyan,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _SmsCard extends StatefulWidget {
  const _SmsCard({required this.device});
  final MonitorProvider device;

  @override
  State<_SmsCard> createState() => _SmsCardState();
}

class _SmsCardState extends State<_SmsCard> {
  late final TextEditingController _numbers;
  late final FocusNode _focus;
  String _syncedTo = '';
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final current = widget.device.data?.smsTo ?? '';
    _numbers = TextEditingController(text: current);
    _focus = FocusNode();
    _syncedTo = current;
  }

  @override
  void dispose() {
    _numbers.dispose();
    _focus.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant _SmsCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    final next = widget.device.data?.smsTo ?? '';
    if (_focus.hasFocus || _saving || next == _syncedTo) return;
    _numbers.text = next;
    _syncedTo = next;
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await widget.device.saveSmsNumbers(_numbers.text);
      _syncedTo = widget.device.data?.smsTo ?? _numbers.text.trim();
      if (!mounted) return;
      showAppSnack(context, message: 'Đã lưu số nhận SMS', success: true);
    } on DeviceException catch (e) {
      if (!mounted) return;
      showAppSnack(context, message: e.message);
    } catch (_) {
      if (!mounted) return;
      showAppSnack(context, message: 'Không lưu được số SMS');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final data = widget.device.data!;
    final failed = data.smsStatus.contains('Thất bại');
    final ok = data.smsStatus.contains('Thành công') || data.smsStatus.contains('Đã gửi');
    final reasonColor = failed
        ? SafetyTheme.pulse
        : ok
            ? SafetyTheme.safe
            : SafetyTheme.force;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: SafetyTheme.panel.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: failed
              ? SafetyTheme.pulse.withValues(alpha: 0.45)
              : Colors.white.withValues(alpha: 0.08),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'SMS CẢNH BÁO',
            style: TextStyle(
              color: SafetyTheme.muted,
              fontWeight: FontWeight.w800,
              fontSize: 12,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            'Số nhận (tối đa 5, cách nhau bằng dấu phẩy)',
            style: TextStyle(color: SafetyTheme.muted, fontSize: 12),
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _numbers,
            focusNode: _focus,
            keyboardType: TextInputType.phone,
            minLines: 1,
            maxLines: 3,
            style: const TextStyle(fontWeight: FontWeight.w700),
            decoration: InputDecoration(
              hintText: '0377...,0988...',
              filled: true,
              fillColor: Colors.white.withValues(alpha: 0.04),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(12),
                borderSide: const BorderSide(color: SafetyTheme.cyan),
              ),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            ),
          ),
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _saving ? null : _save,
              icon: _saving
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save_rounded, size: 18),
              label: Text(_saving ? 'Đang lưu...' : 'Lưu số nhận'),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Đang dùng: ${data.smsTo.isEmpty ? '(chưa cấu hình)' : data.smsTo}',
            style: const TextStyle(color: SafetyTheme.muted),
          ),
          Text(
            'Trạng thái: ${data.smsStatus}',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: reasonColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              data.smsResult.isEmpty ? '--' : data.smsResult,
              style: TextStyle(color: reasonColor, fontWeight: FontWeight.w700),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'OK ${data.smsSentCount} · Lỗi ${data.smsFailCount}'
            '${data.smsAgeSec > 0 ? ' · ${data.smsAgeSec}s trước' : ''}',
            style: const TextStyle(color: SafetyTheme.muted, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.04),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              data.smsText.isEmpty ? 'Chưa có tin nhắn' : data.smsText,
              style: const TextStyle(fontSize: 12, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricTile extends StatelessWidget {
  const _MetricTile({
    required this.label,
    required this.value,
    required this.unit,
    required this.detail,
    required this.icon,
    required this.color,
    required this.alert,
  });

  final String label;
  final String value;
  final String unit;
  final String detail;
  final IconData icon;
  final Color color;
  final bool alert;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: SafetyTheme.panel.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: alert ? color.withValues(alpha: 0.8) : Colors.white.withValues(alpha: 0.08),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  label.toUpperCase(),
                  style: const TextStyle(
                    color: SafetyTheme.muted,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.4,
                  ),
                ),
              ),
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 18),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Flexible(
                child: Text(
                  value,
                  style: TextStyle(
                    fontSize: value.length > 6 ? 22 : 28,
                    fontWeight: FontWeight.w800,
                    height: 1,
                    color: alert ? color : SafetyTheme.soft,
                  ),
                ),
              ),
              if (unit.isNotEmpty) ...[
                const SizedBox(width: 4),
                Padding(
                  padding: const EdgeInsets.only(bottom: 2),
                  child: Text(unit, style: const TextStyle(color: SafetyTheme.muted)),
                ),
              ],
            ],
          ),
          const SizedBox(height: 8),
          Text(detail, style: const TextStyle(color: SafetyTheme.muted, fontSize: 12)),
        ],
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: SafetyTheme.panel,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: color, size: 18),
              const SizedBox(width: 8),
              Flexible(
                child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
