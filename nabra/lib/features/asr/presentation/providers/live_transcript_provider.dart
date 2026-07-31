import 'package:equatable/equatable.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

enum LiveTranscriptStatus {
  idle,
  recording,
  transcribing,
  ready,
  offline, // backend not reachable / not ready
}

class LiveTranscriptState extends Equatable {
  final String text;
  final LiveTranscriptStatus status;
  final bool isRecording;
  final String? lastError;

  const LiveTranscriptState({
    this.text = '',
    this.status = LiveTranscriptStatus.idle,
    this.isRecording = false,
    this.lastError,
  });

  bool get hasText => text.trim().isNotEmpty;

  LiveTranscriptState copyWith({
    String? text,
    LiveTranscriptStatus? status,
    bool? isRecording,
    String? lastError,
    bool clearError = false,
  }) {
    return LiveTranscriptState(
      text: text ?? this.text,
      status: status ?? this.status,
      isRecording: isRecording ?? this.isRecording,
      lastError: clearError ? null : (lastError ?? this.lastError),
    );
  }

  @override
  List<Object?> get props => [text, status, isRecording, lastError];
}

final liveTranscriptProvider =
    NotifierProvider<LiveTranscriptNotifier, LiveTranscriptState>(
  LiveTranscriptNotifier.new,
);

class LiveTranscriptNotifier extends Notifier<LiveTranscriptState> {
  @override
  LiveTranscriptState build() => const LiveTranscriptState();

  void startSession() {
    state = const LiveTranscriptState(
      status: LiveTranscriptStatus.recording,
      isRecording: true,
    );
  }

  void markTranscribing() {
    if (!state.isRecording) return;
    // لا نخفي خطأ الخادم أثناء إعادة المحاولة
    if (state.status == LiveTranscriptStatus.offline) return;
    state = state.copyWith(
      status: LiveTranscriptStatus.transcribing,
      clearError: true,
    );
  }

  void appendText(String chunk) {
    final piece = chunk.trim();
    if (piece.isEmpty) {
      if (state.isRecording) {
        state = state.copyWith(
          status: LiveTranscriptStatus.recording,
          clearError: true,
        );
      }
      return;
    }
    final merged =
        state.text.trim().isEmpty ? piece : '${state.text.trim()} $piece';
    state = state.copyWith(
      text: merged,
      status: state.isRecording
          ? LiveTranscriptStatus.recording
          : LiveTranscriptStatus.ready,
      clearError: true,
    );
  }

  /// يرجع `true` إذا كانت أول مرة ندخل حالة عدم الاتصال في هذه الجلسة.
  bool markOffline([String? message]) {
    final alreadyOffline = state.status == LiveTranscriptStatus.offline;
    state = state.copyWith(
      status: LiveTranscriptStatus.offline,
      lastError: message ?? 'التفريغ المباشر غير جاهز من الخادم',
    );
    return !alreadyOffline;
  }

  void stopSession() {
    // نُبقي حالة الخادم غير الجاهز ظاهرة بعد الإيقاف
    if (state.status == LiveTranscriptStatus.offline) {
      state = state.copyWith(isRecording: false);
      return;
    }
    state = state.copyWith(
      isRecording: false,
      status: state.hasText
          ? LiveTranscriptStatus.ready
          : LiveTranscriptStatus.idle,
    );
  }

  void clear() {
    state = const LiveTranscriptState();
  }
}
