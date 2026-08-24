import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

abstract final class ApiConstants {
  /// `true` = هاتف حقيقي على نفس الواي فاي
  /// `false` = محاكي أندرويد (يستخدم 10.0.2.2)
  static const bool usePhysicalAndroidDevice = true;

  /// IP جهاز الكمبيوتر على الشبكة المحلية (نفس واي فاي الهاتف).
  static const String lanHost = '192.168.1.123';

  static const String androidEmulatorHost = '10.0.2.2';
  static const String desktopHost = '127.0.0.1';
  static const int apiPort = 8000;

  static String get defaultHost {
    if (!kIsWeb && Platform.isAndroid) {
      return usePhysicalAndroidDevice ? lanHost : androidEmulatorHost;
    }
    return desktopHost;
  }

  /// Default local Meet-ASR base URL (platform-aware).
  static String get defaultBaseUrl => 'http://$defaultHost:$apiPort';

  /// Always returns a clean http base URL for the current platform.
  static String resolveBaseUrl(String? raw) {
    // On Android always force the correct host for the current test mode.
    if (!kIsWeb && Platform.isAndroid) {
      return defaultBaseUrl;
    }

    final cleaned = (raw ?? '')
        .replaceAll(RegExp(r'[\u200E\u200F\u202A-\u202E\u2066-\u2069]'), '')
        .trim();
    final match =
        RegExp(r'https?://[^\s]+', caseSensitive: false).firstMatch(cleaned);
    if (match == null) return defaultBaseUrl;

    final parsed = Uri.tryParse(match.group(0)!);
    if (parsed == null || parsed.host.isEmpty) return defaultBaseUrl;

    return Uri(
      scheme: parsed.scheme == 'https' ? 'https' : 'http',
      host: parsed.host,
      port: parsed.hasPort ? parsed.port : apiPort,
    ).toString().replaceAll(RegExp(r'/+$'), '');
  }

  /// Builds an absolute API [Uri] safely (no fragile string concatenation).
  static Uri apiUri(String baseUrl, String path) {
    final base = resolveBaseUrl(baseUrl);
    final parsed = Uri.tryParse(base);
    final host =
        (parsed != null && parsed.host.isNotEmpty) ? parsed.host : defaultHost;
    final port = (parsed != null && parsed.hasPort) ? parsed.port : apiPort;
    final scheme = (parsed != null && parsed.scheme.isNotEmpty)
        ? parsed.scheme
        : 'http';
    final normalizedPath = path.startsWith('/') ? path : '/$path';

    return Uri(
      scheme: scheme,
      host: host,
      port: port,
      path: normalizedPath,
    );
  }

  static const String authRegister = '/auth/register';
  static const String authLogin = '/auth/login';
  static const String authLogout = '/auth/logout';

  static const String asrTranscribe = '/asr/transcribe';
  static const String nlpSummarize = '/nlp/summarize';

  static const String health = '/health';
}
