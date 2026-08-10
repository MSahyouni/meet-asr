import 'package:flutter/material.dart';
import 'package:nabra/core/theme/app_theme.dart';

/// بطاقة إجراء: أيقونة يسار · نص ثم سهم يمين مباشرة.
class OutlinedActionTile extends StatelessWidget {
  final String label;
  final String? subtitle;
  final IconData icon;
  final VoidCallback? onTap;
  final Color? accent;
  final Color? iconBackground;
  final bool dense;
  final bool showChevron;
  final bool highlighted;

  const OutlinedActionTile({
    super.key,
    required this.label,
    required this.icon,
    this.subtitle,
    this.onTap,
    this.accent,
    this.iconBackground,
    this.dense = false,
    this.showChevron = true,
    this.highlighted = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = accent ?? AppTheme.iconAccent;
    final iconBg = iconBackground ?? AppTheme.iconAccentSoft;
    final enabled = onTap != null;

    return AnimatedOpacity(
      duration: const Duration(milliseconds: 180),
      opacity: enabled || highlighted ? 1 : 0.72,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(AppTheme.radiusLg),
          splashColor: AppTheme.primary.withValues(alpha: 0.06),
          highlightColor: AppTheme.gold.withValues(alpha: 0.05),
          child: Ink(
            width: double.infinity,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppTheme.radiusLg),
              gradient: LinearGradient(
                begin: Alignment.topRight,
                end: Alignment.bottomLeft,
                colors: highlighted
                    ? [
                        AppTheme.primarySoft,
                        AppTheme.surface,
                      ]
                    : [
                        AppTheme.surface,
                        AppTheme.goldSoft.withValues(alpha: 0.55),
                      ],
              ),
              border: Border.all(
                color: highlighted
                    ? AppTheme.primary.withValues(alpha: 0.18)
                    : AppTheme.cardBorder.withValues(alpha: 0.85),
              ),
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primary.withValues(alpha: 0.045),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
                BoxShadow(
                  color: AppTheme.gold.withValues(alpha: 0.06),
                  blurRadius: 12,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: AppTheme.space16,
                vertical: dense ? 14 : 18,
              ),
              child: Row(
                textDirection: TextDirection.ltr,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // أيقونة — أقصى اليسار
                  Container(
                    width: dense ? 46 : 52,
                    height: dense ? 46 : 52,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(AppTheme.radiusMd),
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          iconBg,
                          Color.lerp(iconBg, Colors.white, 0.35)!,
                        ],
                      ),
                      border: Border.all(
                        color: color.withValues(alpha: 0.18),
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: color.withValues(alpha: 0.12),
                          blurRadius: 10,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: Icon(icon, color: color, size: dense ? 22 : 24),
                  ),

                  // مسافة معتدلة بين الأيقونة والنص
                  const SizedBox(width: 12),

                  // النص + السهم — أقصى اليمين، والنص مباشرة بعد السهم
                  Expanded(
                    child: Row(
                      textDirection: TextDirection.rtl,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        if (showChevron) ...[
                          Icon(
                            Icons.chevron_left_rounded,
                            color: AppTheme.textMuted.withValues(alpha: 0.75),
                            size: 22,
                          ),
                          const SizedBox(width: 22),
                        ],
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                label,
                                textAlign: TextAlign.right,
                                textDirection: TextDirection.rtl,
                                style: AppTheme.text(
                                  fontSize: dense ? 14.5 : 15.5,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.textPrimary,
                                  height: 1.35,
                                ),
                              ),
                              if (subtitle != null) ...[
                                const SizedBox(height: 3),
                                Text(
                                  subtitle!,
                                  textAlign: TextAlign.right,
                                  textDirection: TextDirection.rtl,
                                  style: AppTheme.text(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w400,
                                    color: AppTheme.textSecondary,
                                    height: 1.35,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
