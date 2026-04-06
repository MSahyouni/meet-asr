import 'dart:convert';
import 'package:http/http.dart' as http;

class AuthService {
  //create account
  static Future<Map<String, dynamic>> register({
    required String fullName,
    required String email,
    required String password,
    required String confirmPassword,
    required String apiUrl,
  }) async {
    final response = await http.post(
      Uri.parse(apiUrl),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({
        "full_name": fullName,
        "email": email,
        "password": password,
        "confirm_password": confirmPassword,
      }),
    );

    final data = jsonDecode(response.body);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return data;
    } else {
      throw Exception(data["message"] ?? "فشل إنشاء الحساب");
    }
  }

  //login
  static Future<Map<String, dynamic>> login({
    required String email,
    required String password,
    required String apiUrl,
  }) async {
    final response = await http.post(
      Uri.parse(apiUrl),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({"email": email, "password": password}),
    );

    final data = jsonDecode(response.body);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return data;
    } else {
      throw Exception(data["message"] ?? "فشل تسجيل الدخول");
    }
  }

  //logout
  static Future<Map<String, dynamic>> logout({required String apiUrl}) async {
    final apiUrl_logout = apiUrl.replaceAll("register", "logout");
    final response = await http.post(
      Uri.parse(apiUrl_logout),
      headers: {"Content-Type": "application/json"},
    );

    final data = jsonDecode(response.body);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return data;
    } else {
      throw Exception(data["message"] ?? "فشل تسجيل الخروج");
    }
  }
}
