import 'package:flutter/material.dart';
import 'package:flutter_app/widgets/log_in_card.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final emailCtrl = TextEditingController();
  final passCtrl = TextEditingController();

  bool obscure = true;

  @override
  void dispose() {
    emailCtrl.dispose();
    passCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isRTL = Directionality.of(context) == TextDirection.rtl;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        // خلفية مشابهة للصورة (غامق + لمسة لون)
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
                child: LoginCard(
                  isRTL: isRTL,
                  emailCtrl: emailCtrl,
                  passCtrl: passCtrl,
                  obscure: obscure,
                  onToggleObscure: () => setState(() => obscure = !obscure),
                  onLogin: () {
                    // TODO: login action
                  },
                  onForgot: () {
                    // TODO: forgot password
                  },

                  onCreateAccount: () {
                    context.push('/create_account');
                  },
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}



// class _LoginCard extends StatelessWidget {
//   const _LoginCard({
//     required this.isRTL,
//     required this.emailCtrl,
//     required this.passCtrl,
//     required this.obscure,
//     required this.onToggleObscure,
//     required this.onLogin,
//     required this.onForgot,
//     required this.onCreateAccount,
//   });
//   final bool isRTL;
//   final TextEditingController emailCtrl;
//   final TextEditingController passCtrl;
//   final bool obscure;
//   final VoidCallback onToggleObscure;
//   final VoidCallback onLogin;
//   final VoidCallback onForgot;
//   final VoidCallback onCreateAccount;
//   @override
//   Widget build(BuildContext context) {
//     const textSub = Color(0xFFB7C2C8);
//     const accent = Color(0xFF2BB39D);
//     final isDark = Theme.of(context).brightness == Brightness.dark;
//     return Container(
//       height: 600,
//       padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
//       decoration: BoxDecoration(
//         gradient: LinearGradient(
//           colors: isDark
//               ? [Color(0xFF2C2C2C), Color(0xFF1A1A1A)]
//               : [Color(0xFFFFFFFF), Color(0xFFF7F7F7)],
//           begin: Alignment.topCenter,
//           end: Alignment.bottomCenter,
//         ),
//         borderRadius: BorderRadius.circular(18),
//         border: Border.all(color: Colors.white.withOpacity(0.06)),
//         boxShadow: [
//           BoxShadow(
//             color: Colors.black.withOpacity(0.45),
//             blurRadius: 26,
//             offset: const Offset(0, 18),
//           ),
//         ],
//       ),
//       child: Column(
//         crossAxisAlignment: CrossAxisAlignment.stretch,
//         children: [
//           const Gap(2),
//           Text(
//             'Login',
//             textAlign: TextAlign.center,
//             style: TextStyle(
//               color: isDark ? Colors.white : Colors.black,
//               fontSize: 18,
//               fontWeight: FontWeight.w900,
//             ),
//           ),
//           const Gap(20),
//           Text(
//             'Enter your credentials to access your account',
//             textAlign: TextAlign.center,
//             style: TextStyle(
//               color: isDark ? Colors.white70 : Colors.black87,
//               fontSize: 12,
//               fontWeight: FontWeight.w600,
//               height: 1.3,
//             ),
//           ),
//           const Gap(25),
//           _FieldLabel(text: 'Email Address'),
//           const Gap(15),
//           AnimatedLiftTextField(
//             controller: emailCtrl,
//             hint: 'Enter your email...',
//             prefix: Icons.mail_outline,
//             keyboardType: TextInputType.emailAddress,
//             // الأيقونة يمين/يسار حسب RTL
//             mirrorPrefixWhenRTL: isRTL,
//           ),
//           const Gap(25),
//           Row(
//             mainAxisAlignment: MainAxisAlignment.spaceBetween,
//             children: [
//               _FieldLabel(text: 'Password'),
//               InkWell(
//                 onTap: onForgot,
//                 child: Text(
//                   'Forgot password?',
//                   style: TextStyle(
//                     color: isDark ? Colors.white70 : Colors.black87,
//                     fontSize: 11,
//                     fontWeight: FontWeight.w800,
//                   ),
//                 ),
//               ),
//             ],
//           ),
//           const Gap(15),
//           AnimatedLiftTextField(
//             controller: passCtrl,
//             hint: 'Enter your password...',
//             prefix: Icons.lock_outline,
//             keyboardType: TextInputType.text,
//             obscureText: obscure,
//             suffix: obscure
//                 ? Icons.visibility_off_outlined
//                 : Icons.visibility_outlined,
//             onSuffixTap: onToggleObscure,
//             mirrorPrefixWhenRTL: isRTL,
//           ),
//           const Gap(40),
//           _LoginButton(text: 'Login', isRTL: isRTL, onPressed: onLogin),
//           const Gap(25),
//           _OrDivider(),
//           const Gap(30),
//           Row(
//             mainAxisAlignment: MainAxisAlignment.center,
//             children: [
//               Text(
//                 "Don't have an account?",
//                 style: TextStyle(
//                   color: isDark ? Colors.white70 : Colors.black87,
//                   fontSize: 13,
//                   fontWeight: FontWeight.w700,
//                 ),
//               ),
//               const Gap(8),
//               InkWell(
//                 onTap: onCreateAccount,
//                 child: Text(
//                   'Create a new account',
//                   style: TextStyle(
//                     color: accent,
//                     fontSize: 13,
//                     fontWeight: FontWeight.w900,
//                   ),
//                 ),
//               ),
//             ],
//           ),
//         ],
//       ),
//     );
//   }
// }





// /// ===== Label فوق الحقل =====
// class _FieldLabel extends StatelessWidget {
//   const _FieldLabel({required this.text});
//   final String text;
//   @override
//   Widget build(BuildContext context) {
//     final isDark = Theme.of(context).brightness == Brightness.dark;
//     return Align(
//       alignment: Alignment.centerLeft,
//       child: Text(
//         text,
//         style: TextStyle(
//           color: isDark ? Colors.white : Colors.black,
//           fontSize: 11,
//           fontWeight: FontWeight.w800,
//         ),
//       ),
//     );
//   }
// }

/// ===== Divider OR =====
// class _OrDivider extends StatelessWidget {
//   @override
//   Widget build(BuildContext context) {
//     return Row(
//       children: [
//         Expanded(
//           child: Divider(color: Colors.white.withOpacity(0.10), height: 1),
//         ),
//         Padding(
//           padding: const EdgeInsets.symmetric(horizontal: 10),
//           child: Text(
//             'Or',
//             style: TextStyle(
//               color: Colors.white.withOpacity(0.55),
//               fontSize: 11,
//               fontWeight: FontWeight.w700,
//             ),
//           ),
//         ),
//         Expanded(
//           child: Divider(color: Colors.white.withOpacity(0.10), height: 1),
//         ),
//       ],
//     );
//   }
// }




// class _LoginButton extends StatelessWidget {
//   const _LoginButton({
//     required this.text,
//     required this.isRTL,
//     required this.onPressed,
//   });
//   final String text;
//   final bool isRTL;
//   final VoidCallback onPressed;
//   @override
//   Widget build(BuildContext context) {
//     return SizedBox(
//       height: 44,
//       child: ElevatedButton(
//         onPressed: onPressed,
//         style: ElevatedButton.styleFrom(
//           backgroundColor: Colors.transparent, // مهم
//           foregroundColor: Colors.white,
//           shadowColor: Colors.transparent, // نلغي شادو الافتراضي
//           elevation: 0,
//           padding: EdgeInsets.zero, // مهم
//           shape: RoundedRectangleBorder(
//             borderRadius: BorderRadius.circular(10),
//           ),
//         ),
//         child: Ink(
//           decoration: BoxDecoration(
//             gradient: const LinearGradient(
//               begin: Alignment.centerLeft,
//               end: Alignment.centerRight,
//               colors: [
//                 Color.fromARGB(125, 58, 174, 122),
//                 Color.fromARGB(237, 31, 180, 96),
//               ],
//             ),
//             borderRadius: BorderRadius.circular(10),
//             boxShadow: [
//               BoxShadow(
//                 color: const Color(0xFF1FB45F).withOpacity(0.25),
//                 blurRadius: 18,
//                 offset: const Offset(0, 10),
//               ),
//             ],
//           ),
//           child: Container(
//             alignment: Alignment.center,
//             child: Row(
//               mainAxisAlignment: MainAxisAlignment.center,
//               children: [
//                 Icon(
//                   isRTL ? Icons.arrow_back : Icons.arrow_forward,
//                   size: 18,
//                   color: Colors.white,
//                 ),
//                 const Gap(10),
//                 Text(
//                   text,
//                   style: const TextStyle(
//                     fontSize: 13,
//                     fontWeight: FontWeight.w900,
//                     color: Colors.white,
//                   ),
//                 ),
//               ],
//             ),
//           ),
//         ),
//       ),
//     );
//   }
// }




// class AnimatedLiftTextField extends StatefulWidget {
//   const AnimatedLiftTextField({
//     super.key,
//     required this.controller,
//     required this.hint,
//     required this.prefix,
//     this.keyboardType = TextInputType.text,
//     this.obscureText = false,
//     this.suffix,
//     this.onSuffixTap,
//     this.mirrorPrefixWhenRTL = false,
//   });
//   final TextEditingController controller;
//   final String hint;
//   final IconData prefix;
//   final TextInputType keyboardType;
//   final bool obscureText;
//   final IconData? suffix;
//   final VoidCallback? onSuffixTap;
//   final bool mirrorPrefixWhenRTL;
//   @override
//   State<AnimatedLiftTextField> createState() => _AnimatedLiftTextFieldState();
// }
// class _AnimatedLiftTextFieldState extends State<AnimatedLiftTextField> {
//   final FocusNode _focusNode = FocusNode();
//   bool _focused = false;
//   @override
//   void initState() {
//     super.initState();
//     _focusNode.addListener(() {
//       if (!mounted) return;
//       setState(() => _focused = _focusNode.hasFocus);
//     });
//   }
//   @override
//   void dispose() {
//     _focusNode.dispose();
//     super.dispose();
//   }
//   @override
//   Widget build(BuildContext context) {
//     const hintColor = Color(0xFF9AA6AE);
//     const iconColor = Color(0xFFB7C2C8);
//     const accent = Color(0xFF2BB39D);
//     final isRTL = Directionality.of(context) == TextDirection.rtl;
//     final isDark = Theme.of(context).brightness == Brightness.dark;
//     return AnimatedContainer(
//       duration: const Duration(milliseconds: 220),
//       curve: Curves.easeOutCubic,
//       transform: Matrix4.translationValues(0, _focused ? -4 : 0, 0),
//       decoration: BoxDecoration(
//         gradient: isDark
//             ? const LinearGradient(
//                 colors: [
//                   Color.fromARGB(30, 7, 14, 13), // أخضر مزرق خفيف
//                   Color.fromARGB(255, 30, 85, 77), // أخضر أغمق
//                 ],
//                 begin: Alignment.centerRight,
//                 end: Alignment.centerLeft,
//               )
//             : const LinearGradient(
//                 colors: [
//                   Color.fromARGB(0, 104, 196, 182), // خفيف جداً
//                   Color.fromARGB(255, 141, 196, 187), // أغمق
//                 ],
//                 begin: Alignment.centerRight,
//                 end: Alignment.centerLeft,
//               ),
//         borderRadius: BorderRadius.circular(12),
//         border: Border.all(
//           color: _focused
//               ? accent.withOpacity(0.60)
//               : Colors.white.withOpacity(0.10),
//           width: 1,
//         ),
//         boxShadow: [
//           BoxShadow(
//             color: _focused
//                 ? const Color(0xFF2AA876).withOpacity(0.22)
//                 : const Color(0xFF2AA876).withOpacity(0.10),
//             blurRadius: _focused ? 22 : 14,
//             offset: const Offset(0, 8),
//           ),
//         ],
//       ),
//       child: TextField(
//         focusNode: _focusNode,
//         controller: widget.controller,
//         keyboardType: widget.keyboardType,
//         obscureText: widget.obscureText,
//         style: const TextStyle(
//           color: Color(0xFFE9EEF1),
//           fontSize: 12.5,
//           fontWeight: FontWeight.w700,
//         ),
//         cursorColor: accent,
//         decoration: InputDecoration(
//           border: InputBorder.none,
//           isDense: true,
//           contentPadding: const EdgeInsets.symmetric(
//             horizontal: 12,
//             vertical: 12,
//           ),
//           hintText: widget.hint,
//           hintStyle: const TextStyle(
//             color: hintColor,
//             fontSize: 12,
//             fontWeight: FontWeight.w700,
//           ),
//           prefixIcon: Transform(
//             alignment: Alignment.center,
//             transform: (isRTL && widget.mirrorPrefixWhenRTL)
//                 ? Matrix4.diagonal3Values(-1.0, 1.0, 1.0)
//                 : Matrix4.identity(),
//             child: Icon(widget.prefix, size: 18, color: iconColor),
//           ),
//           suffixIcon: widget.suffix == null
//               ? null
//               : InkWell(
//                   onTap: widget.onSuffixTap,
//                   borderRadius: BorderRadius.circular(999),
//                   child: Padding(
//                     padding: const EdgeInsets.all(12),
//                     child: Icon(widget.suffix, size: 18, color: iconColor),
//                   ),
//                 ),
//         ),
//       ),
//     );
//   }
// }
