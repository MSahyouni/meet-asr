import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nabra/core/constants/api_constants.dart';
import 'package:nabra/core/di/injector.dart';
import 'package:nabra/features/auth/presentation/providers/auth_state.dart';

final authProvider =
    NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);

class AuthNotifier extends Notifier<AuthState> {
  @override
  AuthState build() => AuthState(apiBaseUrl: ApiConstants.defaultBaseUrl);

  Future<void> bootstrap() async {
    final user = await AppInjector.sessionLocal.readSession();
    final api = ApiConstants.resolveBaseUrl(
      await AppInjector.sessionLocal.readApiBaseUrl(),
    );
    await AppInjector.sessionLocal.saveApiBaseUrl(api);
    state = state.copyWith(user: user, apiBaseUrl: api, clearMessages: true);
  }

  Future<void> setApiBaseUrl(String url) async {
    final trimmed = ApiConstants.resolveBaseUrl(url);
    await AppInjector.sessionLocal.saveApiBaseUrl(trimmed);
    state = state.copyWith(apiBaseUrl: trimmed);
  }

  Future<bool> login({
    required String email,
    required String password,
    String? baseUrl,
  }) async {
    state = state.copyWith(loading: true, clearMessages: true);
    try {
      final api = ApiConstants.resolveBaseUrl(
        baseUrl?.trim().isNotEmpty == true ? baseUrl! : state.apiBaseUrl,
      );
      final user = await AppInjector.loginUseCase(
        email: email,
        password: password,
        baseUrl: api,
      );
      state = state.copyWith(
        loading: false,
        user: user,
        apiBaseUrl: api,
        successMessage: 'تم تسجيل الدخول بنجاح',
      );
      return true;
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
      return false;
    }
  }

  Future<bool> register({
    required String fullName,
    required String email,
    required String password,
    required String confirmPassword,
    String? baseUrl,
  }) async {
    state = state.copyWith(loading: true, clearMessages: true);
    try {
      final api = ApiConstants.resolveBaseUrl(
        baseUrl?.trim().isNotEmpty == true ? baseUrl! : state.apiBaseUrl,
      );
      await AppInjector.registerUseCase(
        fullName: fullName,
        email: email,
        password: password,
        confirmPassword: confirmPassword,
        baseUrl: api,
      );
      state = state.copyWith(
        loading: false,
        apiBaseUrl: api,
        successMessage: 'تم إنشاء الحساب بنجاح',
      );
      return true;
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
      return false;
    }
  }

  Future<void> logout() async {
    state = state.copyWith(loading: true, clearMessages: true);
    try {
      await AppInjector.logoutUseCase(
        baseUrl: state.apiBaseUrl,
        token: state.user?.accessToken,
      );
      state = state.copyWith(
        loading: false,
        clearUser: true,
        successMessage: 'تم تسجيل الخروج بنجاح',
      );
    } catch (e) {
      await AppInjector.sessionLocal.clearSession();
      state = state.copyWith(
        loading: false,
        clearUser: true,
        error: e.toString(),
      );
    }
  }
}
