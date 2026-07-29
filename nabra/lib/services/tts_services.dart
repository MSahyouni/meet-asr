import 'dart:convert';
import 'package:flutter_app/model/voice_model.dart';
import 'package:http/http.dart' as http;


class TtsService {
  static Uri _ttsUri(String apiUrl, {String suffix = ''}) {
    final base = apiUrl.trim().replaceAll(RegExp(r'/+$'), '');
    // Support callers that still pass an ASR transcribe URL.
    final root = base
        .replaceAll('/asr/transcribe', '')
        .replaceAll('/transcribe', '')
        .replaceAll(RegExp(r'/tts$'), '');
    final path = suffix.isEmpty ? '/tts' : '/tts$suffix';
    return Uri.parse('$root$path');
  }

  static Future<List<VoiceModel>> fetchVoices({
    required String apiUrl,
    String? authorization,
    String? apiKey,
  }) async {
    final response = await http.get(
      _ttsUri(apiUrl, suffix: '/voices'),
      headers: _headers(authorization: authorization, apiKey: apiKey),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to load voices: ${response.statusCode}');
    }

    final decoded = json.decode(response.body);

    if (decoded is List) {
      return decoded.map((v) => VoiceModel.fromDynamic(v)).toList();
    }

    if (decoded is Map<String, dynamic>) {
      final detailed = decoded['voices_detailed'];
      if (detailed is List && detailed.isNotEmpty) {
        return detailed.map((v) => VoiceModel.fromDynamic(v)).toList();
      }
      final list = decoded['voices'] ?? decoded['data'];
      if (list is List) {
        return list.map((v) => VoiceModel.fromDynamic(v)).toList();
      }
    }

    return [];
  }

  /// Convert text to speech. Returns relative `download_url` from the API.
  static Future<String> convertTextToSpeech({
    required String apiUrl,
    required String text,
    required String voiceId,
    String engine = 'auto',
    double speed = 1.0,
    String? speakerRef,
    String? refText,
    String? dialect,
    String? userEmail,
    int? seed,
    String? authorization,
    String? apiKey,
  }) async {
    final payload = <String, dynamic>{
      'text': text,
      'voice': voiceId,
      // Legacy alias kept for older backends.
      'voice_id': voiceId,
      'engine': engine,
      'speed': speed,
    };
    if (speakerRef != null && speakerRef.isNotEmpty) {
      payload['speaker_ref'] = speakerRef;
    }
    if (refText != null && refText.isNotEmpty) {
      payload['ref_text'] = refText;
    }
    if (dialect != null && dialect.isNotEmpty) {
      payload['dialect'] = dialect;
    }
    if (userEmail != null && userEmail.isNotEmpty) {
      payload['user_email'] = userEmail;
    }
    if (seed != null) {
      payload['seed'] = seed;
    }

    final response = await http.post(
      _ttsUri(apiUrl),
      headers: {
        ..._headers(authorization: authorization, apiKey: apiKey),
        'Content-Type': 'application/json',
      },
      body: jsonEncode(payload),
    );

    if (response.statusCode != 200) {
      throw Exception('TTS conversion failed: ${response.statusCode} ${response.body}');
    }

    final data = json.decode(response.body);
    final url = data['download_url'] ?? data['audio_url'];
    if (url is! String || url.isEmpty) {
      throw Exception('TTS response missing download_url');
    }
    return url;
  }

  static Map<String, String> _headers({String? authorization, String? apiKey}) {
    final headers = <String, String>{};
    if (authorization != null && authorization.isNotEmpty) {
      headers['Authorization'] = authorization.startsWith('Bearer ')
          ? authorization
          : 'Bearer $authorization';
    }
    if (apiKey != null && apiKey.isNotEmpty) {
      headers['X-API-Key'] = apiKey;
    }
    return headers;
  }
}
