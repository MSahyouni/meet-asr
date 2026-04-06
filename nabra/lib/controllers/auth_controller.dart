import 'package:flutter/material.dart';
import 'package:flutter_app/services/auth_service.dart';
import 'package:flutter_app/services/session_service.dart';

class AuthController {
  //create account handler
  static Future<void> handleRegister({
    required BuildContext context,
    required String fullName,
    required String email,
    required String password,
    required String confirmPassword,
    required String apiUrl,
    VoidCallback? onSuccess,
  }) async {
    if (fullName.isEmpty ||
        email.isEmpty ||
        password.isEmpty ||
        confirmPassword.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("يرجى ملء جميع الحقول"),
          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );

      return;
    }

    if (password != confirmPassword) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("كلمة المرور وتأكيدها غير متطابقين"),
          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
      return;
    }

    try {
      final result = await AuthService.register(
        fullName: fullName,
        email: email,
        password: password,
        confirmPassword: confirmPassword,
        apiUrl: apiUrl,
      );
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result["message"] ?? "تم إنشاء الحساب بنجاح"),
          backgroundColor: const Color.fromARGB(255, 75, 151, 78),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );

      if (onSuccess != null) {
        onSuccess();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("فشل إنشاء الحساب: $e"),
          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
    }
  }

  //login handler

  static Future<void> handleLogin({
    required BuildContext context,
    required String email,
    required String password,
    required String apiUrl_login,
    VoidCallback? onSuccess,
  }) async {
    if (email.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text("يرجى ملء جميع الحقول"),
          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: const EdgeInsets.all(16),
        ),
      );
      return;
    }

    try {
      final result = await AuthService.login(
        email: email,
        password: password,
        apiUrl: apiUrl_login,
      );

      //  حفظ حالة تسجيل الدخول
      await SessionService.saveLoginStatus(true);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result["message"] ?? "تم تسجيل الدخول بنجاح"),
          backgroundColor: const Color.fromARGB(255, 75, 151, 78),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: const EdgeInsets.all(16),
        ),
      );

      if (onSuccess != null) {
        onSuccess();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("فشل تسجيل الدخول: $e"),
          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: const EdgeInsets.all(16),
        ),
      );
    }
  }

  //   //logout handler

  static Future<void> handleLogout({
    required BuildContext context,
    required String apiUrl,
    VoidCallback? onSuccess,
  }) async {
    try {
      final result = await AuthService.logout();
      await SessionService.clearSession(); // مسح حالة الجلسة عند تسجيل الخروج
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(result["message"] ?? "تم تسجيل الخروج بنجاح"),
          backgroundColor: const Color.fromARGB(255, 75, 151, 78),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );

      if (onSuccess != null) {
        onSuccess();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("فشل تسجيل الخروج: $e"),
          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
    }
  }
}
