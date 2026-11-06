import 'package:flutter_test/flutter_test.dart';
import 'package:safety_remote_app/core/monitor_provider.dart';
import 'package:safety_remote_app/main.dart';

void main() {
  testWidgets('App shows connect gate', (tester) async {
    final device = MonitorProvider();
    await tester.pumpWidget(SafetyRemoteApp(device: device));
    expect(find.textContaining('SAFETY'), findsWidgets);
    expect(find.text('Kết nối gần'), findsOneWidget);
  });
}
