import 'package:flutter/material.dart';
import 'package:flutter_app/core/theme/app_theme.dart';

/// طبقة توافق — الألوان الرسمية من [AppTheme].
abstract final class AppColors {
  static const Color primary = AppTheme.primary;
  static const Color primaryDark = AppTheme.primaryDark;
  static const Color primaryDeep = AppTheme.primaryDeep;
  static const Color primaryLight = AppTheme.primaryLight;
  static const Color primarySoft = AppTheme.primaryLight; // للأزرار/هيدر أخضر
  static const Color primaryMuted = AppTheme.primaryMuted;
  static const Color primaryTint = AppTheme.primarySoft;

  static const Color gold = AppTheme.gold;
  static const Color goldSoft = AppTheme.goldLight;
  static const Color goldMuted = AppTheme.goldDark;
  static const Color goldCream = AppTheme.goldSoft;

  static const Color iconAccent = AppTheme.iconAccent;
  static const Color iconAccentSoft = AppTheme.iconAccentSoft;
  static const Color accentLine = AppTheme.accentLine;

  static const Color surface = AppTheme.background;
  static const Color surfaceCard = AppTheme.surface;
  static const Color border = AppTheme.cardBorder;
  static const Color borderStrong = AppTheme.accentLine;

  static const Color textPrimary = AppTheme.textPrimary;
  static const Color textSecondary = AppTheme.textSecondary;
  static const Color textOnPrimary = AppTheme.textOnPrimary;
  static const Color textHint = AppTheme.textMuted;

  static const Color danger = AppTheme.error;
  static const Color success = AppTheme.success;
  static const Color stop = AppTheme.burgundy;

  static const LinearGradient primaryGradient = AppTheme.primaryGradient;
  static const LinearGradient headerGradient = AppTheme.headerGradient;
}
