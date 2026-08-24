import 'package:nabra/core/utils/url_utils.dart';
import 'package:nabra/services/tts_services.dart';

class TtsRepositoryImpl {
  Future<String> convert({
    required String apiBaseUrl,
    required String text,
    required String voiceId,
    required String engine,
    String? userEmail,
    String? authorization,
  }) async {
    final audioUrl = await TtsService.convertTextToSpeech(
      apiUrl: UrlUtils.normalizeBase(apiBaseUrl),
      text: text,
      voiceId: voiceId,
      engine: engine,
      userEmail: userEmail,
      authorization: authorization,
    );

    return UrlUtils.resolveDownloadUrl(
      apiBaseUrl,
      audioUrl,
    );
  }
}