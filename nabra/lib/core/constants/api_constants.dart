abstract final class ApiConstants {
  /// Default local Meet-ASR base URL.
  static const String defaultBaseUrl = 'http://127.0.0.1:8000';

  static const String authRegister = '/auth/register';
  static const String authLogin = '/auth/login';
  static const String authLogout = '/auth/logout';

  static const String asrTranscribe = '/asr/transcribe';
  static const String nlpSummarize = '/nlp/summarize';
  static const String tts = '/tts';
  static const String ttsVoices = '/tts/voices';
  static const String download = '/download';
  static const String health = '/health';
}
