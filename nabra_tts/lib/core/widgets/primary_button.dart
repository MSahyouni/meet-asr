import 'package:flutter/material.dart';
import 'package:nabra/core/theme/app_theme.dart';

class PrimaryButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final Color? backgroundColor;
  final Color? foregroundColor;
  final IconData? icon;

  const PrimaryButton({
    super.key,
    required this.label,
    this.onPressed,
    this.loading = false,
    this.backgroundColor,
    this.foregroundColor,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final contentColor = foregroundColor ?? AppTheme.goldLight;

    return SizedBox(
      width: double.infinity,
      height: 52,
      child: ElevatedButton(
        onPressed: loading ? null : onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: backgroundColor ?? AppTheme.primary,
          foregroundColor: foregroundColor ?? AppTheme.textOnPrimary,
          disabledBackgroundColor:
              AppTheme.primary.withValues(alpha: 0.45),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(
              AppTheme.radiusField,
            ),
          ),
        ),
        child: loading
            ? const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(
                  strokeWidth: 2.4,
                  color: Colors.white,
                ),
              )
            : Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (icon != null) ...[
                    Icon(
                      icon,
                      size: 20,
                      color: contentColor,
                    ),
                    const SizedBox(width: 8),
                  ],
                  Text(
                    label,
                    style: AppTheme.text(
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      color: contentColor,
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}