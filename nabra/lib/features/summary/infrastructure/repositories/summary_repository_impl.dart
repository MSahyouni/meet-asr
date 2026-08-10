import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:nabra/core/constants/api_constants.dart';
import 'package:nabra/core/error/failures.dart';
import 'package:nabra/core/utils/url_utils.dart';

class SummaryResult {
  final String summary;
  final String keywords;

  const SummaryResult({
    required this.summary,
    this.keywords = '',
  });

  factory SummaryResult.fromJson(Map<String, dynamic> json) {
    return SummaryResult(
      summary: (json['summary'] ?? '').toString(),
      keywords: (json['keywords'] ?? '').toString(),
    );
  }
}

class SummaryRepositoryImpl {
  Future<SummaryResult> summarize({
    required String text,
    required String apiBaseUrl,
    String model = 'jais',
    String? authorization,
  }) async {
    final uri = UrlUtils.uri(apiBaseUrl, ApiConstants.nlpSummarize);

    // Backend accepts light/ultra as non-off modes and maps them to Jais-2.
    final summaryMode = (model.trim().isEmpty || model == 'off') ? 'jais' : model;

    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    final auth = authorization?.trim();
    if (auth != null && auth.isNotEmpty) {
      headers['Authorization'] =
          auth.startsWith('Bearer ') ? auth : 'Bearer $auth';
    }

    final response = await http
        .post(
          uri,
          headers: headers,
          body: jsonEncode({
            'text': text,
            'model': summaryMode,
            'summary_mode': summaryMode,
          }),
        )
        .timeout(const Duration(minutes: 5));

    if (response.statusCode != 200) {
      throw Failure(_errorMessage(response.body, 'فشل تلخيص النص'));
    }

    final decoded = _decode(response.body);
    if (decoded is Map<String, dynamic>) {
      return SummaryResult.fromJson(decoded);
    }
    if (decoded is Map) {
      return SummaryResult.fromJson(Map<String, dynamic>.from(decoded));
    }

    throw const Failure('استجابة التلخيص غير متوقعة');
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
