import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/core/theme/app_colors.dart';
import 'package:flutter_app/core/theme/app_theme.dart';
import 'package:flutter_app/core/widgets/app_snackbar.dart';
import 'package:flutter_app/core/widgets/app_text_field.dart';
import 'package:flutter_app/core/widgets/nabra_scaffold.dart';
import 'package:flutter_app/core/widgets/primary_button.dart';
import 'package:flutter_app/core/widgets/staggered_entrance.dart';
import 'package:flutter_app/features/auth/presentation/providers/auth_provider.dart';

class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key});

  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _obscurePass = true;
  bool _obscureConfirm = true;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final ok = await ref.read(authProvider.notifier).register(
          fullName: _name.text,
          email: _email.text,
          password: _password.text,
          confirmPassword: _confirm.text,
        );
    if (!mounted) return;
    final state = ref.read(authProvider);
    if (ok) {
      AppSnackbar.show(
        context,
        message: state.successMessage ?? 'تم إنشاء الحساب',
      );
      context.go('/login');
    } else {
      AppSnackbar.show(
        context,
        message: state.error ?? 'فشل إنشاء الحساب',
        isError: true,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authProvider);
    return NabraScaffold(
          title: 'إنشاء حساب جديد',
          subtitle: 'املأ التفاصيل التالية لإنشاء حسابك',
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
                      controller: _name,
                      label: 'الاسم الكامل',
                      hint: '...الاسم الكامل',
                      prefixIcon: Icons.person_outline_rounded,
                    ),
                    const SizedBox(height: 14),
                    AppTextField(
                      controller: _email,
                      label: 'البريد الإلكتروني',
                      hint: 'example@gmail.com',
                      prefixIcon: Icons.email_outlined,
                      keyboardType: TextInputType.emailAddress,
                      textAlign: TextAlign.left,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              EntranceItem(
                index: 1,
                child: Column(
                  children: [
                    AppTextField(
                      controller: _password,
                      label: 'كلمة المرور',
                      hint: '...أدخل كلمة المرور',
                      prefixIcon: Icons.lock_outline_rounded,
                      obscureText: _obscurePass,
                      suffix: IconButton(
                        icon: Icon(
                          _obscurePass
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined,
                          color: AppColors.textHint,
                        ),
                        onPressed: () =>
                            setState(() => _obscurePass = !_obscurePass),
                      ),
                    ),
                    const SizedBox(height: 14),
                    AppTextField(
                      controller: _confirm,
                      label: 'تأكيد كلمة المرور',
                      hint: '...أدخل تأكيد كلمة المرور',
                      prefixIcon: Icons.lock_outline_rounded,
                      obscureText: _obscureConfirm,
                      suffix: IconButton(
                        icon: Icon(
                          _obscureConfirm
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined,
                          color: AppColors.textHint,
                        ),
                        onPressed: () => setState(
                          () => _obscureConfirm = !_obscureConfirm,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 22),
              EntranceItem(
                index: 2,
                child: PrimaryButton(
                  label: 'إنشاء حساب جديد',
                  loading: state.loading,
                  onPressed: _submit,
                ),
              ),
              const SizedBox(height: 14),
              EntranceItem(
                index: 3,
                child: Text(
                  'بإنشاء حساب، فإنك توافق على شروط الاستخدام وسياسة الخصوصية الخاصة بنا',
                  textAlign: TextAlign.center,
                  style: AppTheme.text(
                    color: AppTheme.textMuted,
                    fontSize: 12,
                    height: 1.45,
                  ),
                ),
              ),
            ],
          ),
        );
  }
}
