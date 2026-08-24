import 'package:nabra/features/auth/infrastructure/datasources/auth_remote_datasource.dart';
import 'package:nabra/features/auth/infrastructure/datasources/session_local_datasource.dart';
import 'package:nabra/features/auth/domain/entities/user_entity.dart';
import 'package:nabra/features/auth/domain/repositories/auth_repository.dart';

class AuthRepositoryImpl implements AuthRepository {
  final AuthRemoteDataSource remote;
  final SessionLocalDataSource local;

  const AuthRepositoryImpl({
    required this.remote,
    required this.local,
  });

  @override
  Future<UserEntity> login({
    required String email,
    required String password,
    required String baseUrl,
  }) async {
    final user = await remote.login(
      email: email,
      password: password,
      baseUrl: baseUrl,
    );
    await local.saveSession(user);
    await local.saveApiBaseUrl(baseUrl);
    return user;
  }

  @override
  Future<void> register({
    required String fullName,
    required String email,
    required String password,
    required String baseUrl,
  }) {
    return remote.register(
      fullName: fullName,
      email: email,
      password: password,
      baseUrl: baseUrl,
    );
  }

  @override
  Future<void> logout({required String baseUrl, String? token}) async {
    try {
      await remote.logout(baseUrl: baseUrl, token: token);
    } finally {
      await local.clearSession();
    }
  }

  @override
  Future<UserEntity?> getCurrentUser() => local.readSession();

  @override
  Future<void> clearSession() => local.clearSession();
}
