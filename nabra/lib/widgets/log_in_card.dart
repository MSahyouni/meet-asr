import 'package:flutter/material.dart';
import 'package:flutter_app/widgets/animated_lift_text_filed.dart';
import 'package:flutter_app/widgets/divider.dart';
import 'package:flutter_app/widgets/field_lable.dart';
import 'package:flutter_app/widgets/log_in_button.dart';
import 'package:gap/gap.dart';

class LoginCard extends StatelessWidget {
  const LoginCard({
    required this.isRTL,
    required this.emailCtrl,
    required this.passCtrl,
    required this.obscure,
    required this.onToggleObscure,
    required this.onLogin,
    required this.onForgot,

    required this.onCreateAccount,
  });

  final bool isRTL;
  final TextEditingController emailCtrl;
  final TextEditingController passCtrl;
  final bool obscure;
  final VoidCallback onToggleObscure;
  final VoidCallback onLogin;
  final VoidCallback onForgot;
  final VoidCallback onCreateAccount;

  @override
  Widget build(BuildContext context) {
    const accent = Color(0xFF2BB39D);

    return Container(
      height: 600,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],

          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.white.withOpacity(0.06)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.45),
            blurRadius: 26,
            offset: const Offset(0, 18),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Gap(2),
          Text(
            "تسجيل الدخول",
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w900,
            ),
          ),
          const Gap(20),
          Text(
            "ادخل بياناتك للوصول إلى حسابك",
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              height: 1.3,
            ),
          ),
          const Gap(25),

          FieldLabel(text: "عنوان البريد الإلكتروني"),
          const Gap(15),
          AnimatedLiftTextField(
            controller: emailCtrl,
            hint: '... أدخل بريدك الإلكتروني',
            prefix: Icons.mail_outline,
            keyboardType: TextInputType.emailAddress,
            // الأيقونة يمين/يسار حسب RTL
            mirrorPrefixWhenRTL: isRTL,
          ),

          const Gap(25),

          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              FieldLabel(text: "كلمة المرور"),
              InkWell(
                onTap: onForgot,
                child: Text(
                  "هل نسيت كلمة المرور؟",
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const Gap(15),

          AnimatedLiftTextField(
            controller: passCtrl,
            hint: '...أدخل كلمة المرور',
            prefix: Icons.lock_outline,
            keyboardType: TextInputType.text,
            obscureText: obscure,
            suffix: obscure
                ? Icons.visibility_off_outlined
                : Icons.visibility_outlined,
            onSuffixTap: onToggleObscure,
            mirrorPrefixWhenRTL: isRTL,
          ),

          const Gap(40),

          LoginButton(text: "تسجيل الدخول", isRTL: isRTL, onPressed: onLogin),

          const Gap(25),

          OrDivider(),

          const Gap(30),

          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                "ليس لديك حساب؟",
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Gap(8),
              InkWell(
                onTap: onCreateAccount,
                child: Text(
                  "انشاء حساب جديد",
                  style: TextStyle(
                    color: accent,
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
