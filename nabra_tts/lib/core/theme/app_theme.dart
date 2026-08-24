import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// نظام تصميم نبرة — أخضر طبي + ذهب النمط الهندسي
class AppTheme {
  AppTheme._();

  /// خط الواجهة — قمرة (Qomra)
  static const String fontFamily = 'Qomra';

  /// مساعد لإنشاء TextStyle بخط قمرة
  static TextStyle text({
    double? fontSize,
    FontWeight? fontWeight,
    Color? color,
    double? height,
  }) {
    return TextStyle(
      fontFamily: fontFamily,
      fontSize: fontSize,
      fontWeight: fontWeight,
      color: color,
      height: height,
    );
  }

  // ============================================================
  // Brand Colors — أخضر طبي + ذهب النمط الهندسي
  // ============================================================

  /// Primary — أخضر طبي عميق (الأزرار + العناوين القوية)
  static const Color primary = Color(0xFF054239);
  static const Color primaryLight = Color(0xFF0B5E51);
  static const Color primaryDark = Color(0xFF03352C);
  static const Color primaryDeep = Color(0xFF02241E);
  static const Color primarySoft = Color(0xFFECF3F1);
  static const Color primaryMuted = Color(0xFF5F7F76);

  /// Gold — مطابق لخطوط خلفية النمط الهندسي
  static const Color gold = Color(0xFFC5A367);
  static const Color goldLight = Color(0xFFD4BC8E);
  static const Color goldDark = Color(0xFF9A7F4A);
  static const Color goldSoft = Color(0xFFF6F2E8);

  /// Accent Burgundy — للأخطاء والخروج فقط
  static const Color burgundy = Color(0xFF6B1F2A);
  static const Color burgundyLight = Color(0xFF8A2E3B);
  static const Color burgundySoft = Color(0xFFF5E8EA);

  static const Color patternBlack = Color(0xFF0A0A0A);
  static const Color ink = Color(0xFF1A2421);

  // Surfaces — كريم دافئ يبرز الذهب مع لمسة خضراء خفيفة
  static const Color background = Color(0xFFF6F5F0);
  static const Color backgroundSoft = Color(0xFFF0EDE4);
  static const Color surface = Color(0xFFFFFDF9);
  static const Color surfaceMuted = Color(0xFFF4F1E9);
  static const Color cardBorder = Color(0xFFE6DFD0);

  // Text
  static const Color textPrimary = ink;
  static const Color textSecondary = Color(0xFF5E675C);
  static const Color textOnPrimary = Colors.white;
  static const Color textMuted = Color(0xFF8E9588);

  // Semantic
  static const Color success = primary;
  static const Color warning = goldDark;
  static const Color error = burgundy;
  static const Color secondary = gold;
  static const Color secondaryStrong = goldDark;
  static const Color accent = burgundy;

  /// أيقونات الواجهة — ذهب مخفّف قليلاً (بدون المساس بالخلفية)
  static const Color iconAccent = Color(0xFFA8925E);
  static const Color iconAccentSoft = Color(0xFFF7F3EA);

  /// حدود وزخارف ذهبية مخفّفة
  static const Color accentLine = Color(0xFFB9A67A);

  // Action card tints
  static const Color cardAddPatientBg = iconAccentSoft;
  static const Color cardAddPatientIcon = iconAccent;
  static const Color cardPatientsBg = iconAccentSoft;
  static const Color cardPatientsIcon = iconAccent;
  static const Color cardXrayBg = iconAccentSoft;
  static const Color cardXrayIcon = iconAccent;
  static const Color cardAnalysisBg = iconAccentSoft;
  static const Color cardAnalysisIcon = iconAccent;

  // ============================================================
  // Radius
  // ============================================================

  static const double radiusSm = 12;
  static const double radiusField = 15;
  static const double radiusMd = 18;
  static const double radiusCard = 20;
  static const double radiusLg = 24;
  static const double radiusXl = 28;
  static const double radiusHero = 32;

  // ============================================================
  // Spacing
  // ============================================================

  static const double space4 = 4;
  static const double space8 = 8;
  static const double space12 = 12;
  static const double space16 = 16;
  static const double space20 = 20;
  static const double space24 = 24;
  static const double space32 = 32;

  // ============================================================
  // Gradients
  // ============================================================

  static const LinearGradient primaryGradient = LinearGradient(
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
    colors: [primaryLight, primary, primaryDark],
    stops: [0.0, 0.5, 1.0],
  );

  static const LinearGradient headerGradient = LinearGradient(
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
    colors: [Color(0xFF0A5C4F), primary, primaryDeep],
    stops: [0.0, 0.55, 1.0],
  );

  static const LinearGradient splashGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [primaryLight, primary, primaryDeep],
    stops: [0.0, 0.45, 1.0],
  );

  static const LinearGradient softBackgroundGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0xFFF2EEE4), background, Color(0xFFFAF8F3)],
  );

  static const LinearGradient adminGradient = LinearGradient(
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
    colors: [primary, primaryDeep],
  );

  static const LinearGradient goldAccentGradient = LinearGradient(
    begin: Alignment.centerRight,
    end: Alignment.centerLeft,
    colors: [goldLight, gold, goldDark],
  );

  /// شريط ترقية: ذهب أوضح مع لمسة خضراء
  static const LinearGradient brandAccentGradient = LinearGradient(
    begin: Alignment.centerRight,
    end: Alignment.centerLeft,
    colors: [goldLight, gold, Color(0xFF7A8F6A)],
  );

  static const LinearGradient errorGradient = LinearGradient(
    begin: Alignment.topRight,
    end: Alignment.bottomLeft,
    colors: [burgundyLight, burgundy, Color(0xFF4A1520)],
  );

  /// تدرج SnackBar نجاح — تباين أوضح
  static const LinearGradient snackSuccessGradient = LinearGradient(
    begin: Alignment.centerRight,
    end: Alignment.centerLeft,
    colors: [
      Color(0xFF1A8F78),
      primary,
      primaryDeep,
    ],
    stops: [0.0, 0.45, 1.0],
  );

  /// تدرج SnackBar خطأ — تباين أوضح
  static const LinearGradient snackErrorGradient = LinearGradient(
    begin: Alignment.centerRight,
    end: Alignment.centerLeft,
    colors: [
      Color(0xFFA83A4A),
      burgundy,
      Color(0xFF3A1018),
    ],
    stops: [0.0, 0.45, 1.0],
  );

  // ============================================================
  // Shadows
  // ============================================================

  static List<BoxShadow> softShadow({Color? color}) => [
        BoxShadow(
          color: (color ?? primary).withValues(alpha: 0.07),
          blurRadius: 22,
          offset: const Offset(0, 8),
        ),
      ];

  static List<BoxShadow> cardShadow() => [
        BoxShadow(
          color: primary.withValues(alpha: 0.045),
          blurRadius: 18,
          offset: const Offset(0, 6),
        ),
      ];

  static List<BoxShadow> navShadow() => [
        BoxShadow(
          color: primary.withValues(alpha: 0.08),
          blurRadius: 26,
          offset: const Offset(0, 10),
        ),
      ];

  // ============================================================
  // Typography
  // ============================================================

  static TextTheme _textTheme(TextTheme base) {
    TextStyle style({
      required double size,
      required FontWeight weight,
      Color color = textPrimary,
      double height = 1.35,
    }) {
      return TextStyle(
        fontFamily: fontFamily,
        fontSize: size,
        fontWeight: weight,
        color: color,
        height: height,
      );
    }

    return base.copyWith(
      displayLarge: style(size: 36, weight: FontWeight.w800),
      displayMedium: style(size: 32, weight: FontWeight.w800),
      displaySmall: style(size: 28, weight: FontWeight.w700),
      headlineLarge: style(size: 26, weight: FontWeight.w700),
      headlineMedium: style(size: 22, weight: FontWeight.w700),
      headlineSmall: style(size: 20, weight: FontWeight.w700),
      titleLarge: style(size: 18, weight: FontWeight.w700),
      titleMedium: style(size: 16, weight: FontWeight.w600),
      titleSmall: style(size: 14, weight: FontWeight.w600),
      bodyLarge: style(size: 16, weight: FontWeight.w400, height: 1.55),
      bodyMedium: style(
        size: 14,
        weight: FontWeight.w400,
        color: textSecondary,
        height: 1.55,
      ),
      bodySmall: style(
        size: 12,
        weight: FontWeight.w400,
        color: textMuted,
        height: 1.45,
      ),
      labelLarge: style(size: 15, weight: FontWeight.w600),
      labelMedium: style(size: 13, weight: FontWeight.w500),
      labelSmall: style(
        size: 11,
        weight: FontWeight.w500,
        color: textMuted,
      ),
    );
  }

  // ============================================================
  // Light Theme
  // ============================================================

  static ThemeData get lightTheme {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: fontFamily,
    );
    final textTheme = _textTheme(base.textTheme);

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: fontFamily,
      textTheme: textTheme,
      scaffoldBackgroundColor: Colors.transparent,
      colorScheme: const ColorScheme.light(
        primary: primary,
        onPrimary: textOnPrimary,
        primaryContainer: primarySoft,
        onPrimaryContainer: primaryDark,
        secondary: gold,
        onSecondary: ink,
        secondaryContainer: goldSoft,
        onSecondaryContainer: goldDark,
        tertiary: burgundy,
        onTertiary: textOnPrimary,
        tertiaryContainer: burgundySoft,
        onTertiaryContainer: burgundy,
        surface: surface,
        onSurface: textPrimary,
        error: error,
        onError: textOnPrimary,
        outline: cardBorder,
        outlineVariant: Color(0xFFD6CBB4),
      ),
      appBarTheme: AppBarTheme(
        centerTitle: true,
        elevation: 0,
        scrolledUnderElevation: 0,
        backgroundColor: surface.withValues(alpha: 0.94),
        foregroundColor: textPrimary,
        surfaceTintColor: Colors.transparent,
        systemOverlayStyle: SystemUiOverlayStyle.dark,
        titleTextStyle: textTheme.titleLarge,
        iconTheme: const IconThemeData(color: iconAccent, size: 22),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        color: surface,
        surfaceTintColor: Colors.transparent,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusCard),
          side: BorderSide(color: cardBorder.withValues(alpha: 0.95)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        hintStyle: textTheme.bodyMedium?.copyWith(color: textMuted),
        labelStyle: textTheme.labelMedium?.copyWith(color: textSecondary),
        errorStyle: textTheme.bodySmall?.copyWith(color: error),
        prefixIconColor: iconAccent,
        suffixIconColor: textSecondary,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 16,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusField),
          borderSide: const BorderSide(color: cardBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusField),
          borderSide: const BorderSide(color: cardBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusField),
          borderSide: BorderSide(
            color: accentLine.withValues(alpha: 0.55),
            width: 1.3,
          ),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusField),
          borderSide: const BorderSide(color: error),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(radiusField),
          borderSide: const BorderSide(color: error, width: 1.5),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: textOnPrimary,
          disabledBackgroundColor: primary.withValues(alpha: 0.4),
          disabledForegroundColor: textOnPrimary.withValues(alpha: 0.8),
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusField),
          ),
          textStyle: const TextStyle(
            fontFamily: fontFamily,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primary,
          side: BorderSide(color: primary.withValues(alpha: 0.28)),
          backgroundColor: surface,
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 15),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radiusField),
          ),
          textStyle: const TextStyle(
            fontFamily: fontFamily,
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primary,
          textStyle: const TextStyle(
            fontFamily: fontFamily,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: primary,
        foregroundColor: textOnPrimary,
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusMd),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusField),
        ),
        contentTextStyle: const TextStyle(
          fontFamily: fontFamily,
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: textOnPrimary,
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: cardBorder,
        thickness: 1,
        space: 1,
      ),
      checkboxTheme: CheckboxThemeData(
        fillColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) return primary;
          return Colors.transparent;
        }),
        checkColor: const WidgetStatePropertyAll(textOnPrimary),
        side: const BorderSide(color: cardBorder, width: 1.5),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(6),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: primary,
        linearTrackColor: primarySoft,
        circularTrackColor: primarySoft,
      ),
      iconTheme: const IconThemeData(color: iconAccent, size: 22),
      chipTheme: ChipThemeData(
        backgroundColor: surfaceMuted,
        selectedColor: primarySoft,
        labelStyle: textTheme.labelMedium!,
        side: const BorderSide(color: cardBorder),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(radiusSm),
        ),
      ),
    );
  }

  /// توافق مع الاستدعاء القديم
  static ThemeData get light => lightTheme;
}
