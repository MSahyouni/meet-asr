import 'package:flutter_app/core/constants/api_constants.dart';

abstract final class UrlUtils {
  static String normalizeBase(String raw) {
    var base = raw.trim().replaceAll(RegExp(r'/+$'), '');
    if (base.isEmpty) return ApiConstants.defaultBaseUrl;

    // Strip known feature suffixes if the user pasted a full endpoint.
    const suffixes = [
      '/asr/transcribe',
      '/transcribe',
      '/nlp/summarize',
      '/summarize',
      '/auth/login',
      '/auth/register',
      '/auth/logout',
      '/tts/voices',
      '/tts',
    ];
    for (final s in suffixes) {
      if (base.endsWith(s)) {
        base = base.substring(0, base.length - s.length);
        break;
      }
    }
    return base.replaceAll(RegExp(r'/+$'), '');
  }

  static String join(String base, String path) {
    final root = normalizeBase(base);
    final p = path.startsWith('/') ? path : '/$path';
    return '$root$p';
  }

  /// Resolve relative download URLs like `/download?path=...` against API root.
  static String resolveDownloadUrl(String apiBase, String downloadUrl) {
    final url = downloadUrl.trim();
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    final root = normalizeBase(apiBase);
    if (url.startsWith('/')) return '$root$url';
    return '$root/$url';
  }

  static String summarizeEndpoint(String apiBaseOrTranscribeUrl) {
    final root = normalizeBase(apiBaseOrTranscribeUrl);
    return '$root${ApiConstants.nlpSummarize}';
  }

  static String transcribeEndpoint(String apiBase) {
    return join(apiBase, ApiConstants.asrTranscribe);
  }
}
