import 'package:flutter/material.dart';
import 'package:flutter_app/core/theme/app_theme.dart';

/// Curved brand header matching the Nabra mockups.
class NabraHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? leading;
  final List<Widget>? actions;
  final bool showLogo;
  final double height;

  const NabraHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.actions,
    this.showLogo = true,
    this.height = 168,
  });

  @override
  Widget build(BuildContext context) {
    final top = MediaQuery.paddingOf(context).top;

    return Container(
      width: double.infinity,
      height: height + top,
      decoration: const BoxDecoration(
        gradient: AppTheme.headerGradient,
        borderRadius: BorderRadius.vertical(
          bottom: Radius.circular(AppTheme.radiusXl),
        ),
      ),
      child: Stack(
        children: [
          if (leading != null)
            Positioned(
              top: top + 8,
              left: 8,
              child: leading!,
            ),
          if (actions != null)
            Positioned(
              top: top + 8,
              right: 8,
              child: Row(mainAxisSize: MainAxisSize.min, children: actions!),
            ),
          Positioned.fill(
            child: Padding(
              padding: EdgeInsets.only(top: top + 12, bottom: 20),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (showLogo) ...[
                    Image.asset(
                      'assets/images/logo.png',
                      height: 56,
                      fit: BoxFit.contain,
                      errorBuilder: (context, error, stackTrace) => const Icon(
                        Icons.shield_moon_outlined,
                        color: AppTheme.gold,
                        size: 48,
                      ),
                    ),
                    const SizedBox(height: 8),
                  ],
                  Text(
                    title,
                    textAlign: TextAlign.center,
                    style: AppTheme.text(
                      color: AppTheme.goldLight,
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      height: 1.2,
                    ),
                  ),
                  if (subtitle != null) ...[
                    const SizedBox(height: 6),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 28),
                      child: Text(
                        subtitle!,
                        textAlign: TextAlign.center,
                        style: AppTheme.text(
                          color: AppTheme.textOnPrimary.withValues(alpha: 0.88),
                          fontSize: 13,
                          fontWeight: FontWeight.w400,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
