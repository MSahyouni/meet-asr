class TtsState {
  final bool converting;
  final bool playing;
  final String? localAudioPath;

  const TtsState({
    this.converting = false,
    this.playing = false,
    this.localAudioPath,
  });

  TtsState copyWith({
    bool? converting,
    bool? playing,
    String? localAudioPath,
    bool clearAudioPath = false,
  }) {
    return TtsState(
      converting: converting ?? this.converting,
      playing: playing ?? this.playing,
      localAudioPath: clearAudioPath
          ? null
          : localAudioPath ?? this.localAudioPath,
    );
  }
}