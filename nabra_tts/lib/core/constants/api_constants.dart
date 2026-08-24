import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;

abstract final class ApiConstants {
  /// true = هاتف أندرويد حقيقي على نفس شبكة Wi-Fi.
  /// false = محاكي أندرويد ويستخدم 10.0.2.2.
  static const bool usePhysicalAndroidDevice = true;

  /// عنوان IP لجهاز الكمبيوتر على الشبكة المحلية.
  static const String lanHost = '192.168.1.123';

  /// عنوان المضيف عند استخدام Android Emulator.
  static const String androidEmulatorHost = '10.0.2.2';

  /// عنوان المضيف عند تشغيل التطبيق على Desktop.
  static const String desktopHost = '127.0.0.1';

  /// منفذ الـ Backend.
  static const int apiPort = 8000;

  /// يحدد عنوان المضيف المناسب حسب المنصة.
  static String get defaultHost {
    if (!kIsWeb && Platform.isAndroid) {
      return usePhysicalAndroidDevice
          ? lanHost
          : androidEmulatorHost;
    }

    return desktopHost;
  }

  /// عنوان الـ API الافتراضي لتطبيق نبرة.
  static String get defaultBaseUrl {
    return 'http://$defaultHost:$apiPort';
  }

  /// ينظف عنوان الـ API ويعيد عنوانًا صالحًا للاستخدام.
  static String resolveBaseUrl(String? raw) {
    // على Android نستخدم إعداد الهاتف الحقيقي أو المحاكي مباشرة.
    if (!kIsWeb && Platform.isAndroid) {
      return defaultBaseUrl;
    }

    final cleaned = (raw ?? '')
        .replaceAll(
          RegExp(
            r'[\u200E\u200F\u202A-\u202E\u2066-\u2069]',
          ),
          '',
        )
        .trim();

    final match = RegExp(
      r'https?://[^\s]+',
      caseSensitive: false,
    ).firstMatch(cleaned);

    if (match == null) {
      return defaultBaseUrl;
    }

    final parsed = Uri.tryParse(
      match.group(0)!,
    );

    if (parsed == null || parsed.host.isEmpty) {
      return defaultBaseUrl;
    }

    return Uri(
      scheme: parsed.scheme == 'https'
          ? 'https'
          : 'http',
      host: parsed.host,
      port: parsed.hasPort
          ? parsed.port
          : apiPort,
    ).toString().replaceAll(
      RegExp(r'/+$'),
      '',
    );
  }

  /// يبني Uri كامل وآمن لأي Endpoint.
  static Uri apiUri(
    String baseUrl,
    String path,
  ) {
    final base = resolveBaseUrl(baseUrl);
    final parsed = Uri.tryParse(base);

    final host =
        parsed != null && parsed.host.isNotEmpty
            ? parsed.host
            : defaultHost;

    final port =
        parsed != null && parsed.hasPort
            ? parsed.port
            : apiPort;

    final scheme =
        parsed != null && parsed.scheme.isNotEmpty
            ? parsed.scheme
            : 'http';

    final normalizedPath =
        path.startsWith('/')
            ? path
            : '/$path';

    return Uri(
      scheme: scheme,
      host: host,
      port: port,
      path: normalizedPath,
    );
  }

  // Authentication
  static const String authRegister = '/auth/register';
  static const String authLogin = '/auth/login';
  static const String authLogout = '/auth/logout';

  // Text To Speech
  static const String tts = '/tts';

  // Server health check
  static const String health = '/health';
}