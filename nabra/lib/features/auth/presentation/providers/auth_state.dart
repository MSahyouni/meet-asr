import 'package:equatable/equatable.dart';
import 'package:nabra/features/auth/domain/entities/user_entity.dart';

class AuthState extends Equatable {
  final UserEntity? user;
  final String apiBaseUrl;
  final bool loading;
  final String? error;
  final String? successMessage;

  const AuthState({
    this.user,
    this.apiBaseUrl = '',
    this.loading = false,
    this.error,
    this.successMessage,
  });

  bool get isLoggedIn => user?.isAuthenticated == true;

  AuthState copyWith({
    UserEntity? user,
    String? apiBaseUrl,
    bool? loading,
    String? error,
    String? successMessage,
    bool clearUser = false,
    bool clearMessages = false,
  }) {
    return AuthState(
      user: clearUser ? null : (user ?? this.user),
      apiBaseUrl: apiBaseUrl ?? this.apiBaseUrl,
      loading: loading ?? this.loading,
      error: clearMessages ? null : (error ?? this.error),
      successMessage:
          clearMessages ? null : (successMessage ?? this.successMessage),
    );
  }

  @override
  List<Object?> get props => [user, apiBaseUrl, loading, error, successMessage];
}
