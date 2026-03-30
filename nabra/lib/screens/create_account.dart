import 'package:flutter/material.dart';
import 'package:flutter_app/controllers/auth_controller.dart';
import 'package:flutter_app/widgets/auth_card.dart';
import 'package:flutter_app/widgets/auth_gradientbutton.dart';
import 'package:flutter_app/widgets/labeled_filed.dart';
import 'package:flutter_app/widgets/soft_text_filed.dart';
import 'package:gap/gap.dart';

class CreateAccountScreen extends StatefulWidget {
  const CreateAccountScreen({super.key});

  @override
  State<CreateAccountScreen> createState() => _CreateAccountScreenState();
}

class _CreateAccountScreenState extends State<CreateAccountScreen> {
  final firstNameCtrl = TextEditingController();

  final emailCtrl = TextEditingController();
  final passCtrl = TextEditingController();
  final confirmCtrl = TextEditingController();

  bool obscurePass = true;
  bool obscureConfirm = true;

  @override
  void dispose() {
    firstNameCtrl.dispose();

    emailCtrl.dispose();
    passCtrl.dispose();
    confirmCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;

    return Scaffold(
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],

            begin: Alignment.centerRight,
            end: Alignment.centerLeft,
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 18),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: AuthCard(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          "انشاء حساب جديد",
                          textAlign: TextAlign.center,
                          style: t.titleLarge?.copyWith(
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                          ),
                        ),
                        const Gap(10),
                        Text(
                          "املأ التفاصيل التالية لإنشاء حسابك",
                          textAlign: TextAlign.center,
                          style: t.bodySmall?.copyWith(
                            color: Colors.white70,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const Gap(20),

                        Row(
                          children: [
                            const Gap(12),
                            Expanded(
                              child: AuthLabeledField(
                                text: "الاسم الأول",
                                requiredStar: true,
                                child: AuthSoftTextField(
                                  controller: firstNameCtrl,
                                  hint: '... الاسم الأول',
                                  prefix: Icons.person_outline,
                                ),
                              ),
                            ),
                          ],
                        ),

                        const Gap(20),

                        AuthLabeledField(
                          text: "البريد الإلكتروني",
                          requiredStar: true,
                          child: AuthSoftTextField(
                            controller: emailCtrl,
                            hint: 'example@email.com',
                            prefix: Icons.mail_outline,
                            keyboardType: TextInputType.emailAddress,
                          ),
                        ),

                        const Gap(20),

                        AuthLabeledField(
                          text: "كلمة المرور",
                          requiredStar: true,
                          child: AuthSoftTextField(
                            controller: passCtrl,
                            hint: "... أدخل كلمة المرور ",
                            prefix: Icons.lock_outline,
                            obscureText: obscurePass,
                            suffix: obscurePass
                                ? Icons.visibility_off_outlined
                                : Icons.visibility_outlined,
                            onSuffixTap: () =>
                                setState(() => obscurePass = !obscurePass),
                          ),
                        ),

                        const Gap(20),

                        AuthLabeledField(
                          text: "تأكيد كلمة المرور",
                          requiredStar: true,
                          child: AuthSoftTextField(
                            controller: confirmCtrl,
                            hint: "... أدخل تأكيد كلمة المرور",
                            prefix: Icons.lock_outline,
                            obscureText: obscureConfirm,
                            suffix: obscureConfirm
                                ? Icons.visibility_off_outlined
                                : Icons.visibility_outlined,
                            onSuffixTap: () => setState(
                              () => obscureConfirm = !obscureConfirm,
                            ),
                          ),
                        ),

                        const Gap(50),

                        SizedBox(
                          height: 46,
                          child: AuthGradientButton(
                            text: "انشاء حساب جديد",
                            icon: Icons.check_circle_outline,
                            onPressed: () {
                              AuthController.handleRegister(
                                context: context,
                                firstName: firstNameCtrl.text.trim(),
                                email: emailCtrl.text.trim(),
                                password: passCtrl.text.trim(),
                                confirmPassword: confirmCtrl.text.trim(),
                                apiUrl: "",
                              );
                            },
                          ),
                        ),

                        const Gap(30),

                        Text(
                          "بإنشاء حساب، فإنك توافق على شروط الاستخدام وسياسة الخصوصية الخاصة بنا",
                          textAlign: TextAlign.center,
                          style: t.labelSmall?.copyWith(
                            color: const Color.fromARGB(255, 149, 177, 165),
                            fontWeight: FontWeight.w600,
                            fontSize: 12,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
