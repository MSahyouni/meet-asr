import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class AudioDownloadService {
  static Future<String> downloadAudio({
    required String audioUrl,
    String? authorization,
    String folderName = 'My Generated Audios',
  }) async {
    final directory = await _getAudioDirectory(folderName);

    final file = File(
      '${directory.path}/${_generateFileName()}',
    );

    final response = await http.get(
      Uri.parse(audioUrl),
      headers: _buildHeaders(authorization),
    );

    if (response.statusCode != 200) {
      throw Exception(
        'فشل تنزيل الملف الصوتي: ${response.statusCode}',
      );
    }

    await file.writeAsBytes(
      response.bodyBytes,
      flush: true,
    );

    return file.path;
  }

  static Future<Directory> _getAudioDirectory(
    String folderName,
  ) async {
    final baseDirectory = await getExternalStorageDirectory();

    if (baseDirectory == null) {
      throw Exception(
        'لا يمكن الوصول إلى مساحة التخزين',
      );
    }

    final directory = Directory(
      '${baseDirectory.path}/$folderName',
    );

    if (!await directory.exists()) {
      await directory.create(
        recursive: true,
      );
    }

    return directory;
  }

  static Map<String, String> _buildHeaders(
    String? authorization,
  ) {
    final token = authorization?.trim();

    if (token == null || token.isEmpty) {
      return {};
    }

    return {
      'Authorization': token.startsWith('Bearer ')
          ? token
          : 'Bearer $token',
    };
  }

  static String _generateFileName() {
    return 'audio_${DateTime.now().millisecondsSinceEpoch}.wav';
  }
}