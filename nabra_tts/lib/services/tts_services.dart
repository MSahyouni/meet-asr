import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:nabra/core/constants/api_constants.dart';

class TtsService {
  /// يحول النص إلى صوت ويعيد رابط الملف الصوتي القادم من الـ Backend.
  static Future<String> convertTextToSpeech({
    required String apiUrl,
    required String text,
    required String voiceId,
    required String engine,
    String? userEmail,
    String? authorization,
  }) async {
    final payload = <String, dynamic>{
      'text': text,
      'voice': voiceId,
      'voice_id': voiceId,
      'engine': engine,
    };

    if (userEmail != null && userEmail.isNotEmpty) {
      payload['user_email'] = userEmail;
    }

    final response = await http.post(
      ApiConstants.apiUri(
        apiUrl,
        ApiConstants.tts,
      ),
      headers: {
        ..._authorizationHeaders(authorization),
        'Content-Type': 'application/json',
      },
      body: jsonEncode(payload),
    );

    if (response.statusCode != 200) {
      throw Exception(
        'TTS conversion failed: '
        '${response.statusCode} ${response.body}',
      );
    }

    final decoded = jsonDecode(response.body);

    if (decoded is! Map<String, dynamic>) {
      throw Exception('Invalid TTS response');
    }

    final audioUrl =
        decoded['download_url'] ??
        decoded['audio_url'];

    if (audioUrl is! String || audioUrl.isEmpty) {
      throw Exception(
        'TTS response missing download_url',
      );
    }

    return audioUrl;
  }

  /// يبني Authorization Header عند وجود JWT.
  static Map<String, String> _authorizationHeaders(
    String? authorization,
  ) {
    if (authorization == null ||
        authorization.trim().isEmpty) {
      return {};
    }

    final token = authorization.trim();

    return {
      'Authorization': token.startsWith('Bearer ')
          ? token
          : 'Bearer $token',
    };
  }
}