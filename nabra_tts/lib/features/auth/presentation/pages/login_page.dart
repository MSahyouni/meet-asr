import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nabra/core/constants/api_constants.dart';
import 'package:nabra/core/theme/app_colors.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/widgets/app_snackbar.dart';
import 'package:nabra/core/widgets/app_text_field.dart';
import 'package:nabra/core/widgets/nabra_scaffold.dart';
import 'package:nabra/core/widgets/primary_button.dart';
import 'package:nabra/core/widgets/staggered_entrance.dart';
import 'package:nabra/features/auth/presentation/providers/auth_provider.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final ok = await ref.read(authProvider.notifier).login(
          email: _email.text,
          password: _password.text,
        );
    if (!mounted) return;
    final state = ref.read(authProvider);
    if (ok) {
      AppSnackbar.show(context, message: state.successMessage ?? 'تم الدخول');
      context.go('/home');
    } else {
      AppSnackbar.show(
        context,
        message: state.error ?? 'فشل تسجيل الدخول',
        isError: true,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authProvider);
    return NabraScaffold(
          title: 'تسجيل الدخول',
          subtitle: 'أدخل بياناتك للوصول إلى حسابك',
          headerHeight: 178,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
            onPressed: () => context.pop(),
          ),
          body: ListView(
            children: [
              EntranceItem(
                index: 0,
                child: Column(
                  children: [
                    AppTextField(
                      controller: _email,
                      label: 'البريد الإلكتروني',
                      hint: 'أدخل البريد الإلكتروني...',
                      prefixIcon: Icons.email_outlined,
                      keyboardType: TextInputType.emailAddress,
                    ),
                    const SizedBox(height: 16),
                    AppTextField(
                      controller: _password,
                      label: 'كلمة المرور',
                      hint: 'أدخل كلمة المرور...',
                      prefixIcon: Icons.lock_outline_rounded,
                      obscureText: _obscure,
                      suffix: IconButton(
                        icon: Icon(
                          _obscure
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined,
                          color: AppColors.textHint,
                        ),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: () => AppSnackbar.show(
                          context,
                          message: 'قريباً...',
                        ),
                        child: Text(
                          'هل نسيت كلمة المرور؟',
                          style: AppTheme.text(
                            color: AppTheme.textMuted,
                            fontSize: 13,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              EntranceItem(
                index: 1,
                child: PrimaryButton(
                  label: 'تسجيل دخول',
                  loading: state.loading,
                  onPressed: _submit,
                ),
              ),
              const SizedBox(height: 22),
              EntranceItem(
                index: 2,
                child: Column(
                  children: [
                    Row(
                      children: [
                        const Expanded(
                          child: Divider(color: AppTheme.cardBorder),
                        ),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                          child: Text(
                            'أو',
                            style: AppTheme.text(color: AppTheme.textMuted),
                          ),
                        ),
                        const Expanded(
                          child: Divider(color: AppTheme.cardBorder),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: () =>
                          AppSnackbar.show(context, message: 'قريباً...'),
                      icon: const Icon(Icons.facebook, color: Color(0xFF1877F2)),
                      label: Text(
                        'تسجيل الدخول بواسطة فيسبوك',
                        style: AppTheme.text(color: AppTheme.textSecondary),
                      ),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppTheme.textSecondary,
                        side: const BorderSide(color: AppTheme.cardBorder),
                        minimumSize: const Size(double.infinity, 48),
                        shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(AppTheme.radiusField),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: () =>
                          AppSnackbar.show(context, message: 'قريباً...'),
                      icon: const Icon(
                        Icons.g_mobiledata,
                        color: Color(0xFFEA4335),
                        size: 28,
                      ),
                      label: Text(
                        'تسجيل الدخول بواسطة غوغل',
                        style: AppTheme.text(color: AppTheme.textSecondary),
                      ),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppTheme.textSecondary,
                        side: const BorderSide(color: AppTheme.cardBorder),
                        minimumSize: const Size(double.infinity, 48),
                        shape: RoundedRectangleBorder(
                          borderRadius:
                              BorderRadius.circular(AppTheme.radiusField),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              EntranceItem(
                index: 3,
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'ليس لديك حساب؟ ',
                          style: AppTheme.text(color: AppTheme.textSecondary),
                        ),
                        GestureDetector(
                          onTap: () => context.push('/register'),
                          child: Text(
                            'سجل الآن',
                            style: AppTheme.text(
                              color: AppTheme.goldDark,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'الخادم: ${state.apiBaseUrl.isEmpty ? ApiConstants.defaultBaseUrl : state.apiBaseUrl}',
                      textAlign: TextAlign.center,
                      style: AppTheme.text(
                        fontSize: 11,
                        color: AppTheme.textMuted,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
  }
}
