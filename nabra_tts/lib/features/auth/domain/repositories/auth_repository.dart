import 'package:nabra/features/auth/domain/entities/user_entity.dart';

abstract class AuthRepository {
  Future<UserEntity> login({
    required String email,
    required String password,
    required String baseUrl,
  });

  Future<void> register({
    required String fullName,
    required String email,
    required String password,
    required String baseUrl,
  });

  Future<void> logout({required String baseUrl, String? token});

  Future<UserEntity?> getCurrentUser();

  Future<void> clearSession();
}
