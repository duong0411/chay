import 'package:flutter/material.dart';

class SafetyTheme {
  static const Color deep = Color(0xFF0A0E17);
  static const Color panel = Color(0xFF121928);
  static const Color mist = Color(0xFF1C2638);
  static const Color soft = Color(0xFFF8FAFC);
  static const Color muted = Color(0xFF94A3B8);
  static const Color pulse = Color(0xFFFF2A5F);
  static const Color cyan = Color(0xFF00E5FF);
  static const Color force = Color(0xFFFF9F1C);
  static const Color safe = Color(0xFF10B981);

  static ThemeData dark() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: deep,
      colorScheme: const ColorScheme.dark(
        primary: cyan,
        secondary: pulse,
        surface: panel,
        onPrimary: deep,
        onSecondary: soft,
        onSurface: soft,
      ),
      textTheme: const TextTheme(
        displayMedium: TextStyle(
          color: soft,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.8,
        ),
        titleLarge: TextStyle(color: soft, fontWeight: FontWeight.w700),
        bodyLarge: TextStyle(color: soft),
        bodyMedium: TextStyle(color: soft),
      ),
    );
  }
}
