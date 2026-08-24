import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:nabra/core/constants/api_constants.dart';
import 'package:nabra/core/error/failures.dart';
import 'package:nabra/core/utils/url_utils.dart';
import 'package:nabra/features/auth/domain/entities/user_entity.dart';

class AuthRemoteDataSource {
  Future<UserEntity> login({
    required String email,
    required String password,
    required String baseUrl,
  }) async {
    final response = await http.post(
      UrlUtils.uri(baseUrl, ApiConstants.authLogin),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );

    final data = _decodeMap(response.body);
    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Failure(_errorMessage(data, 'فشل تسجيل الدخول'));
    }

    final token = (data['access_token'] ?? '').toString().trim();
    if (token.isEmpty) {
      throw const Failure('استجابة تسجيل الدخول لا تحتوي على رمز الدخول');
    }

    return UserEntity(
      email: (data['email'] ?? email).toString(),
      fullName: data['full_name']?.toString(),
      accessToken: token,
    );
  }

  Future<void> register({
    required String fullName,
    required String email,
    required String password,
    required String baseUrl,
  }) async {
    final response = await http.post(
      UrlUtils.uri(baseUrl, ApiConstants.authRegister),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({
        'full_name': fullName,
        'email': email,
        'password': password,
      }),
    );

    final data = _decodeMap(response.body);
    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Failure(_errorMessage(data, 'فشل إنشاء الحساب'));
    }
  }

  Future<void> logout({
    required String baseUrl,
    String? token,
  }) async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    final auth = token?.trim();
    if (auth != null && auth.isNotEmpty) {
      headers['Authorization'] =
          auth.startsWith('Bearer ') ? auth : 'Bearer $auth';
    }

    final response = await http.post(
      UrlUtils.uri(baseUrl, ApiConstants.authLogout),
      headers: headers,
    );

    if (response.statusCode == 200 || response.statusCode == 201) {
      return;
    }

    final data = _decodeMap(response.body);
    throw Failure(_errorMessage(data, 'فشل تسجيل الخروج'));
  }

  Map<String, dynamic> _decodeMap(String body) {
    if (body.trim().isEmpty) return <String, dynamic>{};
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map<String, dynamic>) return decoded;
      if (decoded is Map) return Map<String, dynamic>.from(decoded);
    } catch (_) {
      // ignore parse errors; caller will use fallback message
    }
    return <String, dynamic>{};
  }

  String _errorMessage(Map<String, dynamic> data, String fallback) {
    final detail = data['detail'];
    if (detail is String && detail.trim().isNotEmpty) return detail;
    if (detail is List && detail.isNotEmpty) {
      final first = detail.first;
      if (first is Map && first['msg'] != null) {
        return first['msg'].toString();
      }
      return first.toString();
    }
    final message = data['message']?.toString();
    if (message != null && message.trim().isNotEmpty) return message;
    return fallback;
  }
}
