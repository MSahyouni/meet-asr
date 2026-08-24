import 'package:nabra/features/auth/domain/entities/user_entity.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SessionLocalDataSource {
  static const _emailKey = 'session_email';
  static const _fullNameKey = 'session_full_name';
  static const _tokenKey = 'session_access_token';
  static const _apiBaseUrlKey = 'session_api_base_url';
  static const _isLoggedInKey = 'is_logged_in';

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  Future<void> saveSession(UserEntity user) async {
    final prefs = await _prefs;
    await prefs.setString(_emailKey, user.email);
    await prefs.setString(_fullNameKey, user.fullName ?? '');
    await prefs.setString(_tokenKey, user.accessToken ?? '');
    await prefs.setBool(_isLoggedInKey, user.isAuthenticated);
  }

  Future<UserEntity?> readSession() async {
    final prefs = await _prefs;
    final email = prefs.getString(_emailKey)?.trim() ?? '';
    final token = prefs.getString(_tokenKey)?.trim() ?? '';
    if (email.isEmpty || token.isEmpty) return null;

    final fullName = prefs.getString(_fullNameKey)?.trim();
    return UserEntity(
      email: email,
      fullName: (fullName == null || fullName.isEmpty) ? null : fullName,
      accessToken: token,
    );
  }

  Future<void> saveApiBaseUrl(String url) async {
    final prefs = await _prefs;
    await prefs.setString(_apiBaseUrlKey, url.trim());
  }

  Future<String?> readApiBaseUrl() async {
    final prefs = await _prefs;
    final value = prefs.getString(_apiBaseUrlKey)?.trim();
    if (value == null || value.isEmpty) return null;
    return value;
  }

  Future<void> clearSession() async {
    final prefs = await _prefs;
    await prefs.remove(_emailKey);
    await prefs.remove(_fullNameKey);
    await prefs.remove(_tokenKey);
    await prefs.remove(_isLoggedInKey);
  }
}
