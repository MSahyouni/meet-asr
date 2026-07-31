import 'package:flutter_app/features/asr/data/repositories/asr_repository_impl.dart';
import 'package:flutter_app/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:flutter_app/features/auth/data/datasources/session_local_datasource.dart';
import 'package:flutter_app/features/auth/data/repositories/auth_repository_impl.dart';
import 'package:flutter_app/features/auth/domain/usecases/auth_usecases.dart';
import 'package:flutter_app/features/summary/data/repositories/summary_repository_impl.dart';
import 'package:flutter_app/features/tts/data/repositories/tts_repository_impl.dart';

/// Manual DI for data/domain layers. Presentation state uses Riverpod.
class AppInjector {
  AppInjector._();

  static final sessionLocal = SessionLocalDataSource();
  static final authRemote = AuthRemoteDataSource();

  static final authRepository = AuthRepositoryImpl(
    remote: authRemote,
    local: sessionLocal,
  );

  static final loginUseCase = LoginUseCase(authRepository);
  static final registerUseCase = RegisterUseCase(authRepository);
  static final logoutUseCase = LogoutUseCase(authRepository);

  static final asrRepository = AsrRepositoryImpl();
  static final summaryRepository = SummaryRepositoryImpl();
  static final ttsRepository = TtsRepositoryImpl();
}
