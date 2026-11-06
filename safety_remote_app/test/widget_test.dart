import 'package:flutter_test/flutter_test.dart';
import 'package:safety_remote_app/core/monitor_provider.dart';
import 'package:safety_remote_app/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('App shows connect gate', (tester) async {
    final device = MonitorProvider();
    await tester.pumpWidget(SafetyRemoteApp(device: device));
    await tester.pump();
    expect(find.textContaining('SAFETY'), findsWidgets);
    // Default mode = local → nút "Kết nối gần"; MQTT → "Kết nối MQTT"
    expect(
      find.textContaining('Kết nối'),
      findsWidgets,
    );
  });
}
