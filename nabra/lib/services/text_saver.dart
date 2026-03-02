import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

class FileSaver {
  static Future<void> saveAnalyzedText({
    required BuildContext context,
    required String analyzedText,
    String folderName = "My Analyzed Texts",
    String? customFileName,
  }) async {
    try {
      if (analyzedText.trim().isEmpty) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('لا يوجد نص محلل للحفظ')));
        return;
      }

      final Directory? baseDir = await getExternalStorageDirectory();

      if (baseDir == null) {
        throw Exception("لا يمكن الوصول إلى التخزين");
      }

      final rootPath = baseDir.path.split('Android')[0];

      final directory = Directory('$rootPath/Documents/$folderName');

      if (!await directory.exists()) {
        await directory.create(recursive: true);
      }

      final fileName =
          customFileName ??
          'analyzed_text_${DateTime.now().millisecondsSinceEpoch}.txt';

      final file = File('${directory.path}/$fileName');

      await file.writeAsString(analyzedText);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('تم حفظ النص المحلل في:\n${file.path}')),
      );
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('حدث خطأ أثناء الحفظ: $e')));
    }
  }
}
