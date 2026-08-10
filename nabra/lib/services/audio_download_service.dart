// import 'dart:io';
// import 'package:http/http.dart' as http;
// import 'package:permission_handler/permission_handler.dart';

// class AudioDownloadService {
//   // إنشاء مجلد الصوتيات داخل Download
//   static Future<Directory> getAudioFolder() async {
//     final downloadsDir = Directory("/storage/emulated/0/Download");

//     final audioDir = Directory("${downloadsDir.path}/الصوتيات");

//     if (!await audioDir.exists()) {
//       await audioDir.create(recursive: true);
//     }

//     return audioDir;
//   }

//   // تنزيل الصوت وحفظه
//   static Future<String> downloadAudioToDownloads({
//     required String audioUrl,
//   }) async {
//     // طلب الصلاحيات
//     final storageStatus = await Permission.storage.request();
//     final manageStatus = await Permission.manageExternalStorage.request();

//     if (!storageStatus.isGranted && !manageStatus.isGranted) {
//       throw Exception("لم يتم منح صلاحية الوصول إلى التخزين");
//     }

//     // الحصول على مجلد الصوتيات
//     final dir = await getAudioFolder();

//     // إنشاء اسم ملف تلقائي
//     final fileName = "audio_${DateTime.now().millisecondsSinceEpoch}.wav";

//     final file = File("${dir.path}/$fileName");

//     // تنزيل الملف من الرابط
//     final response = await http.get(Uri.parse(audioUrl));

//     if (response.statusCode == 200) {
//       await file.writeAsBytes(response.bodyBytes);

//       return file.path; // يرجع مسار الملف المحفوظ
//     } else {
//       throw Exception("فشل تنزيل الملف: ${response.statusCode}");
//     }
//   }
// }

import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class AudioDownloadService {
  static Future<String> downloadAudio({
    required String audioUrl,
    String? authorization,
    String folderName = "My Generated Audios",
  }) async {
    // الحصول على مسار التخزين الخارجي للتطبيق
    final Directory? baseDir = await getExternalStorageDirectory();

    if (baseDir == null) {
      throw Exception("لا يمكن الوصول إلى التخزين");
    }

    // الوصول لجذر التخزين
    final rootPath = baseDir.path.split('Android')[0];

    // إنشاء مجلد الصوتيات
    final directory = Directory('$rootPath/Documents/$folderName');

    if (!await directory.exists()) {
      await directory.create(recursive: true);
    }

    // إنشاء اسم ملف تلقائي
    final fileName = "audio_${DateTime.now().millisecondsSinceEpoch}.wav";

    final file = File('${directory.path}/$fileName');

    final headers = <String, String>{};
    final token = authorization?.trim();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] =
          token.startsWith('Bearer ') ? token : 'Bearer $token';
    }

    // تنزيل الصوت (يتطلب JWT على /download)
    final response = await http.get(Uri.parse(audioUrl), headers: headers);

    if (response.statusCode == 200) {
      await file.writeAsBytes(response.bodyBytes);

      return file.path;
    } else {
      throw Exception("فشل تنزيل الملف: ${response.statusCode}");
    }
  }
}
