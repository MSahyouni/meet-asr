import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nabra/core/di/injector.dart';
import 'package:nabra/features/auth/presentation/providers/auth_provider.dart';
import 'package:nabra/features/tts/presentation/providers/tts_state.dart';
import 'package:nabra/services/audio_download_service.dart';
import 'package:nabra/services/audio_player_service.dart';

final ttsProvider =
    NotifierProvider<TtsNotifier, TtsState>(
  TtsNotifier.new,
);

class TtsNotifier extends Notifier<TtsState> {
  static const String _defaultVoice = 'habibi_unified';
  static const String _defaultEngine = 'habibi';

  late final AudioPlayerService _audioPlayer;

  StreamSubscription<void>? _playerSubscription;

  @override
  TtsState build() {
    _audioPlayer = AudioPlayerService();

    _playerSubscription =
        _audioPlayer.onComplete.listen((_) {
      state = state.copyWith(
        playing: false,
      );
    });

    ref.onDispose(() {
      _playerSubscription?.cancel();
      _audioPlayer.dispose();
    });

    return const TtsState();
  }

  Future<void> convert(String text) async {
    final cleanText = text.trim();

    if (cleanText.isEmpty) {
      throw ArgumentError(
        'الرجاء إدخال نص أولاً',
      );
    }

    if (state.playing) {
      await _audioPlayer.stop();
    }

    state = state.copyWith(
      converting: true,
      playing: false,
      clearAudioPath: true,
    );

    try {
      final auth = ref.read(authProvider);

      final token = auth.user?.accessToken;

      final audioUrl =
          await AppInjector.ttsRepository.convert(
        apiBaseUrl: auth.apiBaseUrl,
        text: cleanText,
        voiceId: _defaultVoice,
        engine: _defaultEngine,
        authorization: token,
        userEmail: auth.user?.email,
      );

      final localPath =
          await AudioDownloadService.downloadAudio(
        audioUrl: audioUrl,
        authorization: token,
      );

      state = state.copyWith(
        converting: false,
        localAudioPath: localPath,
      );
    } catch (_) {
      state = state.copyWith(
        converting: false,
      );

      rethrow;
    }
  }

  Future<void> togglePlay() async {
    final path = state.localAudioPath;

    if (path == null) return;

    if (state.playing) {
      await _audioPlayer.stop();

      state = state.copyWith(
        playing: false,
      );

      return;
    }

    await _audioPlayer.play(path);

    state = state.copyWith(
      playing: true,
    );
  }
}