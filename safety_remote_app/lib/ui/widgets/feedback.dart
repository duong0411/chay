import 'package:flutter/material.dart';

import '../theme.dart';

void showAppSnack(
  BuildContext context, {
  required String message,
  bool success = false,
}) {
  ScaffoldMessenger.of(context).hideCurrentSnackBar();
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text(message, style: const TextStyle(fontWeight: FontWeight.w700)),
      backgroundColor: success ? SafetyTheme.safe.withValues(alpha: 0.92) : SafetyTheme.panel,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(
          color: success
              ? SafetyTheme.safe.withValues(alpha: 0.5)
              : SafetyTheme.pulse.withValues(alpha: 0.35),
        ),
      ),
    ),
  );
}
