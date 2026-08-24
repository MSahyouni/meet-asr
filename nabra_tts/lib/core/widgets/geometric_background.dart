import 'package:flutter/material.dart';
import 'package:nabra/core/theme/app_theme.dart';

/// خلفية التطبيق — فاتحة بنمط هندسي هادئ (الوضع الافتراضي).
class GeometricBackground extends StatelessWidget {
  final Widget child;
  final double patternOpacity;
  final bool light;

  const GeometricBackground({
    super.key,
    required this.child,
    this.patternOpacity = 0.14,
    this.light = true,
  });

  /// يفتح صورة النمط الداكنة لخطوط ذهبية خفيفة على خلفية كريمية.
  static const ColorFilter _lightPatternFilter = ColorFilter.matrix(<double>[
    0.85, 0.10, 0.05, 0, 215,
    0.08, 0.82, 0.05, 0, 205,
    0.05, 0.08, 0.75, 0, 190,
    0, 0, 0, 1, 0,
  ]);

  @override
  Widget build(BuildContext context) {
    if (!light) {
      return Stack(
        fit: StackFit.expand,
        children: [
          const ColoredBox(color: AppTheme.patternBlack),
          Opacity(
            opacity: 0.35,
            child: Image.asset(
              'assets/images/background_pattern.png',
              fit: BoxFit.cover,
              width: double.infinity,
              height: double.infinity,
              errorBuilder: (context, error, stackTrace) =>
                  const ColoredBox(color: AppTheme.patternBlack),
            ),
          ),
          ColoredBox(color: Colors.black.withValues(alpha: 0.35)),
          child,
        ],
      );
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        const ColoredBox(color: AppTheme.background),
        Opacity(
          opacity: patternOpacity,
          child: ColorFiltered(
            colorFilter: _lightPatternFilter,
            child: Image.asset(
              'assets/images/background_pattern.png',
              fit: BoxFit.cover,
              width: double.infinity,
              height: double.infinity,
              errorBuilder: (context, error, stackTrace) => const ColoredBox(
                color: AppTheme.backgroundSoft,
              ),
            ),
          ),
        ),
        child,
      ],
    );
  }
}
