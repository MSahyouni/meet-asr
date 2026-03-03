import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/voice_model.dart';

class TtsService {
  static Future<List<VoiceModel>> fetchVoices({required String apiUrl}) async {
    // final apiUrlVoices = apiUrl.replaceAll("transcribe", "tts/voices");
    final response = await http.get(
      Uri.parse('http://127.0.0.1:8000/tts/voices'),
    );
    //
    if (response.statusCode == 200) {
      final List data = json.decode(response.body);

      return data.map((voiceJson) => VoiceModel.fromJson(voiceJson)).toList();
    } else {
      throw Exception("Failed to load voices");
    }
  }

  // ✅ إرسال النص للتحويل إلى صوت
  static Future<String> convertTextToSpeech({
    required String apiUrl,
    required String text,
    required String voiceId,
  }) async {
    final apiUrlTTs = apiUrl.replaceAll("transcribe", "tts");
    final response = await http.post(
      Uri.parse(apiUrlTTs),
      headers: {"Content-Type": "application/json"},
      body: jsonEncode({"text": text, "voice_id": voiceId}),
    );

    if (response.statusCode == 200) {
      final data = json.decode(response.body);

      // نفترض أن الباك يرجع رابط الصوت
      return data["audio_url"];
    } else {
      throw Exception("TTS conversion failed");
    }
  }
}
