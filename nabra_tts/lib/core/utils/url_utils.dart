import 'package:nabra/core/constants/api_constants.dart';

abstract final class UrlUtils {
  static String normalizeBase(String raw) {
    var base = ApiConstants.resolveBaseUrl(raw);

    const suffixes = [
   
      '/auth/login',
      '/auth/register',
      '/auth/logout',
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
    return ApiConstants.apiUri(base, path).toString();
  }

  static Uri uri(String base, String path) => ApiConstants.apiUri(base, path);

  static String resolveDownloadUrl(String apiBase, String downloadUrl) {
    final url = downloadUrl.trim();
    if (url.startsWith('http://') || url.startsWith('https://')) {
      return url;
    }
    final root = normalizeBase(apiBase);
    if (url.startsWith('/')) return '$root$url';
    return '$root/$url';
  }


}
