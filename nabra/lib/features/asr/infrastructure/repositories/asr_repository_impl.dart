import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:nabra/core/constants/api_constants.dart';
import 'package:nabra/core/error/failures.dart';
import 'package:nabra/core/utils/url_utils.dart';

class TranscriptionResult {
  final String text;
  final String summary;
  final String keywords;

  const TranscriptionResult({
    required this.text,
    this.summary = '',
    this.keywords = '',
  });

  factory TranscriptionResult.fromJson(Map<String, dynamic> json) {
    return TranscriptionResult(
      text: (json['text'] ?? '').toString(),
      summary: (json['summary'] ?? '').toString(),
      keywords: (json['keywords'] ?? '').toString(),
    );
  }
}

class AsrRepositoryImpl {
  Future<TranscriptionResult> transcribe({
    required File file,
    required String apiBaseUrl,
    String? authorization,
    String model = 'light',
    bool diarize = false,
  }) async {
    final uri = UrlUtils.uri(apiBaseUrl, ApiConstants.asrTranscribe);
    final request = http.MultipartRequest('POST', uri);

    final auth = authorization?.trim();
    if (auth != null && auth.isNotEmpty) {
      request.headers['Authorization'] =
          auth.startsWith('Bearer ') ? auth : 'Bearer $auth';
    }

    request.files.add(
      await http.MultipartFile.fromPath(
        'file',
        file.path,
        contentType: _mediaTypeFor(file.path),
      ),
    );

    request.fields['model_name'] = model;
    request.fields['model'] = model;
    request.fields['diarize'] = diarize.toString();
    request.fields['summary_mode'] = 'off';

    final streamed = await request.send().timeout(const Duration(minutes: 10));
    final body = await streamed.stream.bytesToString();

    if (streamed.statusCode != 200) {
      throw Failure(_errorMessage(body, 'فشل تحويل الصوت إلى نص'));
    }

    final decoded = _decode(body);
    if (decoded is Map<String, dynamic>) {
      return TranscriptionResult.fromJson(decoded);
    }
    if (decoded is Map) {
      return TranscriptionResult.fromJson(Map<String, dynamic>.from(decoded));
    }

    throw const Failure('استجابة تحويل الصوت غير متوقعة');
  }

  MediaType _mediaTypeFor(String path) {
    final lower = path.toLowerCase();
    if (lower.endsWith('.mp3')) return MediaType('audio', 'mpeg');
    if (lower.endsWith('.m4a')) return MediaType('audio', 'mp4');
    if (lower.endsWith('.ogg')) return MediaType('audio', 'ogg');
    if (lower.endsWith('.webm')) return MediaType('audio', 'webm');
    return MediaType('audio', 'wav');
  }

  dynamic _decode(String body) {
    if (body.trim().isEmpty) return null;
    try {
      return jsonDecode(body);
    } catch (_) {
      return null;
    }
  }

  String _errorMessage(String body, String fallback) {
    final decoded = _decode(body);
    if (decoded is Map) {
      final detail = decoded['detail'];
      if (detail is String && detail.trim().isNotEmpty) return detail;
      final message = decoded['message']?.toString();
      if (message != null && message.trim().isNotEmpty) return message;
      final error = decoded['error']?.toString();
      if (error != null && error.trim().isNotEmpty) return error;
    }
    return fallback;
  }
}
