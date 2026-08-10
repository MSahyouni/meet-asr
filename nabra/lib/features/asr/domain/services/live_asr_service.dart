import 'dart:io';
import 'package:nabra/core/di/injector.dart';
import 'package:nabra/core/error/failures.dart';

/// تفريغ مباشر على مستوى Flutter عبر إرسال مقاطع صوتية متتالية.
/// جاهز للربط لاحقاً بـ WebSocket/streaming عندما يصبح الـ backend جاهزاً.
class LiveAsrService {
  const LiveAsrService();

  Future<String> transcribeChunk({
    required File file,
    required String apiBaseUrl,
    String? authorization,
    String model = 'light',
  }) async {
    try {
      final result = await AppInjector.asrRepository
          .transcribe(
            file: file,
            apiBaseUrl: apiBaseUrl,
            authorization: authorization,
            model: model,
            diarize: false,
          )
          .timeout(const Duration(seconds: 180));
      return result.text.trim();
    } on Failure {
      rethrow;
    } catch (e) {
      throw Failure('تعذر تفريغ المقطع: $e');
    }
  }
}
