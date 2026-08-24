import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/widgets/app_snackbar.dart';
import 'package:nabra/core/widgets/geometric_background.dart';
import 'package:nabra/core/widgets/primary_button.dart';
import 'package:nabra/features/auth/presentation/providers/auth_provider.dart';

class AppDrawer extends ConsumerWidget {
  const AppDrawer({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(authProvider);

    return Drawer(
      width: 300,
      backgroundColor: Colors.transparent,
      child: GeometricBackground(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Image.asset(
                      'assets/images/logo_gradient.png',
                      width: 52,
                      height: 52,
                      errorBuilder: (context, error, stackTrace) => const Icon(
                        Icons.graphic_eq_rounded,
                        color: AppTheme.gold,
                        size: 44,
                      ),
                    ),

                    const SizedBox(width: 12),

                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'نبرة',
                            style: AppTheme.text(
                              color: AppTheme.primary,
                              fontSize: 26,
                              fontWeight: FontWeight.w800,
                            ),
                          ),

                          const SizedBox(height: 2),

                          Text(
                            'تحويل الصوت إلى نص وتحليل المحتوى',
                            style: AppTheme.text(
                              color: AppTheme.textSecondary,
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 20),

                Divider(
                  color: AppTheme.cardBorder.withValues(alpha: 0.9),
                ),

                const SizedBox(height: 16),

                Text(
                  'الوصف',
                  textAlign: TextAlign.right,
                  style: AppTheme.text(
                    color: AppTheme.primary,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),

                const SizedBox(height: 8),

                Text(
                  'تطبيق ذكي يعتمد على تقنيات الذكاء الاصطناعي لتحويل الصوت إلى نص بدقة عالية، مع إمكانية تفريغ التسجيلات الصوتية وتحليل محتواها وتلخيصها بسهولة.',
                  textAlign: TextAlign.right,
                  style: AppTheme.text(
                    color: AppTheme.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    height: 1.65,
                  ),
                ),

                const Spacer(),

                if (state.isLoggedIn) ...[
                  Text(
                    state.user?.fullName?.isNotEmpty == true
                        ? state.user!.fullName!
                        : state.user?.email ?? '',
                    textAlign: TextAlign.center,
                    style: AppTheme.text(
                      color: AppTheme.textSecondary,
                      fontSize: 13,
                    ),
                  ),

                  const SizedBox(height: 12),

                  PrimaryButton(
                    label: 'تسجيل خروج',
                    icon: Icons.logout_rounded,
                    loading: state.loading,
                    backgroundColor: AppTheme.error,
                    onPressed: () async {
                      await ref.read(authProvider.notifier).logout();

                      if (!context.mounted) return;

                      Navigator.of(context).pop();

                      AppSnackbar.show(
                        context,
                        message: 'تم تسجيل الخروج',
                      );

                      context.go('/home');
                    },
                  ),
                ] else ...[
                  PrimaryButton(
                    label: 'تسجيل الدخول',
                    icon: Icons.login_rounded,
                    onPressed: () {
                      Navigator.of(context).pop();
                      context.push('/login');
                    },
                  ),

                  const SizedBox(height: 10),

                  PrimaryButton(
                    label: 'إنشاء حساب جديد',
                    icon: Icons.person_add_alt_1_rounded,
                    backgroundColor: AppTheme.primaryLight,
                    onPressed: () {
                      Navigator.of(context).pop();
                      context.push('/register');
                    },
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}