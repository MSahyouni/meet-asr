import 'dart:io';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:path_provider/path_provider.dart';

/// يحفظ ملف تسجيل صوتي في المستندات ضمن مجلد `myrecording`.
abstract final class RecordingSaver {
  static const folderName = 'myrecording';

  /// يعيد مسار المجلد العام للمستندات/myrecording (أو مجلد التطبيق كاحتياط).
  static Future<Directory> resolveMyRecordingDirectory() async {
    if (!kIsWeb && Platform.isAndroid) {
      final baseDir = await getExternalStorageDirectory();
      if (baseDir != null) {
        final rootPath = baseDir.path.split('Android')[0];
        final directory = Directory('$rootPath/Documents/$folderName');
        if (!await directory.exists()) {
          await directory.create(recursive: true);
        }
        return directory;
      }
    }

    final docs = await getApplicationDocumentsDirectory();
    final directory = Directory('${docs.path}/$folderName');
    if (!await directory.exists()) {
      await directory.create(recursive: true);
    }
    return directory;
  }

  /// ينسخ [source] إلى Documents/myrecording ويعيد الملف المحفوظ.
  static Future<File> saveToMyRecording(File source) async {
    if (!await source.exists()) {
      throw Exception('ملف التسجيل غير موجود');
    }

    final directory = await resolveMyRecordingDirectory();
    final stamp = DateTime.now().millisecondsSinceEpoch;
    final destination = File('${directory.path}/recording_$stamp.wav');
    return source.copy(destination.path);
  }
}
