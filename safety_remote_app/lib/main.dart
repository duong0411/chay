import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import 'core/alert_notifications.dart';
import 'core/background_monitor.dart';
import 'core/monitor_provider.dart';
import 'ui/connect_page.dart';
import 'ui/home_page.dart';
import 'ui/theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );

  await AlertNotifications.instance.init();
  await BackgroundMonitor.configure();

  final device = MonitorProvider();
  await device.loadSavedHost();
  runApp(SafetyRemoteApp(device: device));
}

class SafetyRemoteApp extends StatefulWidget {
  const SafetyRemoteApp({super.key, required this.device});

  final MonitorProvider device;

  @override
  State<SafetyRemoteApp> createState() => _SafetyRemoteAppState();
}

class _SafetyRemoteAppState extends State<SafetyRemoteApp> {
  late final MonitorProvider _device = widget.device;

  @override
  void dispose() {
    _device.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider.value(
      value: _device,
      child: MaterialApp(
        title: 'Safety Remote',
        debugShowCheckedModeBanner: false,
        theme: SafetyTheme.dark(),
        home: const _Gate(),
      ),
    );
  }
}

class _Gate extends StatelessWidget {
  const _Gate();

  @override
  Widget build(BuildContext context) {
    final device = context.watch<MonitorProvider>();
    if (!device.canEnterSystem) return const ConnectPage();
    return const HomePage();
  }
}
