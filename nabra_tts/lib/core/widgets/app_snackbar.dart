import 'package:flutter/material.dart';
import 'package:nabra/core/theme/app_theme.dart';

abstract final class AppSnackbar {
  static void show(
    BuildContext context, {
    required String message,
    bool isError = false,
    Duration? duration,
  }) {
    final gradient =
        isError ? AppTheme.snackErrorGradient : AppTheme.snackSuccessGradient;

    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        behavior: SnackBarBehavior.floating,
        padding: EdgeInsets.zero,
        margin: const EdgeInsets.all(16),
        duration: duration ??
            (isError
                ? const Duration(seconds: 5)
                : const Duration(seconds: 3)),
        content: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          decoration: BoxDecoration(
            gradient: gradient,
            borderRadius: BorderRadius.circular(AppTheme.radiusField),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.14),
            ),
            boxShadow: [
              BoxShadow(
                color: (isError ? AppTheme.error : AppTheme.primary)
                    .withValues(alpha: 0.32),
                blurRadius: 16,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          child: Text(
            message,
            textAlign: TextAlign.right,
            style: AppTheme.text(
              color: AppTheme.textOnPrimary,
              fontSize: 14,
              fontWeight: FontWeight.w600,
              height: 1.4,
            ),
          ),
        ),
      ),
    );
  }
}
