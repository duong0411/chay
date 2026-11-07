import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:provider/provider.dart';

import '../core/config.dart';
import '../core/device_api.dart';
import '../core/monitor_provider.dart';
import 'theme.dart';
import 'widgets/feedback.dart';

class ConnectPage extends StatefulWidget {
  const ConnectPage({super.key});

  @override
  State<ConnectPage> createState() => _ConnectPageState();
}

class _ConnectPageState extends State<ConnectPage> {
  late final TextEditingController _host;
  late final TextEditingController _chip;
  late ConnectMode _mode;

  @override
  void initState() {
    super.initState();
    final device = context.read<MonitorProvider>();
    _mode = device.mode;
    _host = TextEditingController(text: device.host);
    _chip = TextEditingController(text: device.chipId);
  }

  @override
  void dispose() {
    _host.dispose();
    _chip.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final device = context.read<MonitorProvider>();
    final ok = _mode == ConnectMode.mqtt
        ? await device.connectMqtt(_chip.text)
        : await device.connectLocal(_host.text);
    if (!mounted) return;
    if (!ok) {
      showAppSnack(context, message: device.status);
      return;
    }
    showAppSnack(
      context,
      message: _mode == ConnectMode.mqtt
          ? 'Đã vào MQTT chip ${device.chipId}'
          : 'Đã vào máy ${device.host}',
      success: true,
    );
  }

  @override
  Widget build(BuildContext context) {
    final device = context.watch<MonitorProvider>();
    final remote = _mode == ConnectMode.mqtt;

    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF070B12), SafetyTheme.deep, Color(0xFF1A1020)],
          ),
        ),
        child: Stack(
          children: [
            Positioned(
              top: -80,
              right: -40,
              child: _orb(220, SafetyTheme.pulse.withValues(alpha: 0.16))
                  .animate(onPlay: (c) => c.repeat(reverse: true))
                  .scale(
                    begin: const Offset(0.96, 0.96),
                    end: const Offset(1.06, 1.06),
                    duration: 5.seconds,
                  ),
            ),
            Positioned(
              bottom: 80,
              left: -50,
              child: _orb(180, SafetyTheme.cyan.withValues(alpha: 0.08)),
            ),
            SafeArea(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(28, 28, 28, 32),
                children: [
                  Text(
                    'SAFETY\nREMOTE',
                    style: Theme.of(context).textTheme.displayMedium?.copyWith(
                          fontSize: 36,
                          height: 0.95,
                          letterSpacing: -1,
                        ),
                  ).animate().fadeIn(duration: 400.ms).slideY(begin: 0.08),
                  const SizedBox(height: 10),
                  Text(
                    remote
                        ? 'Theo dõi từ xa qua MQTT. Tắt app vẫn cảnh báo cháy/gas nền.'
                        : 'Theo dõi gần máy qua SoftAP. Sau khi kết nối, cảnh báo chạy nền.',
                    style: TextStyle(
                      color: SafetyTheme.soft.withValues(alpha: 0.82),
                      height: 1.45,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 18),
                  SegmentedButton<ConnectMode>(
                    segments: const [
                      ButtonSegment(
                        value: ConnectMode.mqtt,
                        label: Text('Từ xa'),
                        icon: Icon(Icons.cloud_outlined, size: 18),
                      ),
                      ButtonSegment(
                        value: ConnectMode.local,
                        label: Text('Gần máy'),
                        icon: Icon(Icons.wifi_rounded, size: 18),
                      ),
                    ],
                    selected: {_mode},
                    onSelectionChanged: (s) => setState(() => _mode = s.first),
                  ),
                  const SizedBox(height: 18),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: SafetyTheme.panel.withValues(alpha: 0.9),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
                    ),
                    child: remote
                        ? const Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Cấu hình trên mạch (một lần)',
                                  style: TextStyle(fontWeight: FontWeight.w800)),
                              SizedBox(height: 8),
                              Text(
                                '1. Vào SoftAP Safety Remote\n'
                                '2. Mở http://192.168.4.1/\n'
                                '3. Điền Wi‑Fi nhà + Chip ID (mặc định 888)\n'
                                '4. Quay lại Internet thường, mở app, bấm Kết nối',
                                style: TextStyle(height: 1.45, color: SafetyTheme.muted),
                              ),
                            ],
                          )
                        : const Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Kết nối gần',
                                  style: TextStyle(fontWeight: FontWeight.w800)),
                              SizedBox(height: 8),
                              Text('Tên mạng: ${AppConfig.wifiName}'),
                              Text('Mật khẩu: Không (mạng mở)'),
                              SizedBox(height: 8),
                              Text(
                                'Điện thoại phải đứng trong Wi‑Fi của mạch.',
                                style: TextStyle(height: 1.4, color: SafetyTheme.muted),
                              ),
                            ],
                          ),
                  ),
                  const SizedBox(height: 18),
                  TextField(
                    controller: remote ? _chip : _host,
                    keyboardType: remote ? TextInputType.text : TextInputType.url,
                    autocorrect: false,
                    style: const TextStyle(
                      color: SafetyTheme.soft,
                      fontWeight: FontWeight.w700,
                    ),
                    decoration: InputDecoration(
                      labelText: remote ? 'Chip ID' : 'Địa chỉ máy',
                      labelStyle: const TextStyle(color: SafetyTheme.muted),
                      filled: true,
                      fillColor: SafetyTheme.mist,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    device.status,
                    style: const TextStyle(color: SafetyTheme.muted, fontSize: 13),
                  ),
                  const SizedBox(height: 18),
                  FilledButton(
                    onPressed: device.connecting ? null : _connect,
                    style: FilledButton.styleFrom(
                      backgroundColor: SafetyTheme.pulse,
                      foregroundColor: Colors.white,
                      minimumSize: const Size.fromHeight(52),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    child: device.connecting
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.4,
                              color: Colors.white,
                            ),
                          )
                        : Text(
                            remote ? 'Kết nối MQTT' : 'Kết nối gần',
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              fontSize: 16,
                            ),
                          ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

Widget _orb(double size, Color color) {
  return Container(
    width: size,
    height: size,
    decoration: BoxDecoration(shape: BoxShape.circle, color: color),
  );
}
