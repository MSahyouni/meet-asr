import 'package:flutter_app/features/auth/domain/entities/user_entity.dart';
import 'package:flutter_app/features/auth/domain/repositories/auth_repository.dart';

class LoginUseCase {
  final AuthRepository repository;
  const LoginUseCase(this.repository);

  Future<UserEntity> call({
    required String email,
    required String password,
    required String baseUrl,
  }) {
    return repository.login(
      email: email.trim(),
      password: password,
      baseUrl: baseUrl,
    );
  }
}

class RegisterUseCase {
  final AuthRepository repository;
  const RegisterUseCase(this.repository);

  Future<void> call({
    required String fullName,
    required String email,
    required String password,
    required String confirmPassword,
    required String baseUrl,
  }) {
    if (password != confirmPassword) {
      throw Exception('كلمة المرور وتأكيدها غير متطابقين');
    }
    return repository.register(
      fullName: fullName.trim(),
      email: email.trim(),
      password: password,
      baseUrl: baseUrl,
    );
  }
}

class LogoutUseCase {
  final AuthRepository repository;
  const LogoutUseCase(this.repository);

  Future<void> call({required String baseUrl, String? token}) {
    return repository.logout(baseUrl: baseUrl, token: token);
  }
}
