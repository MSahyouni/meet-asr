import 'package:nabra/core/utils/url_utils.dart';
import 'package:nabra/model/voice_model.dart';
import 'package:nabra/services/tts_services.dart';

class TtsRepositoryImpl {
  Future<List<VoiceModel>> fetchVoices({
    required String apiBaseUrl,
    String? authorization,
    String? apiKey,
  }) {
    return TtsService.fetchVoices(
      apiUrl: UrlUtils.normalizeBase(apiBaseUrl),
      authorization: authorization,
      apiKey: apiKey,
    );
  }

  Future<String> convert({
    required String apiBaseUrl,
    required String text,
    required String voiceId,
    String engine = 'auto',
    double speed = 1.0,
    String? speakerRef,
    String? refText,
    String? dialect,
    String? userEmail,
    int? seed,
    bool? diacritize,
    String? authorization,
    String? apiKey,
  }) async {
    final relativeOrAbsolute = await TtsService.convertTextToSpeech(
      apiUrl: UrlUtils.normalizeBase(apiBaseUrl),
      text: text,
      voiceId: voiceId,
      engine: engine,
      speed: speed,
      speakerRef: speakerRef,
      refText: refText,
      dialect: dialect,
      userEmail: userEmail,
      seed: seed,
      diacritize: diacritize,
      authorization: authorization,
      apiKey: apiKey,
    );

    return UrlUtils.resolveDownloadUrl(apiBaseUrl, relativeOrAbsolute);
  }
}
