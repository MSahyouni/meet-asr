import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:permission_handler/permission_handler.dart';

class VoiceRecorderSection extends StatefulWidget {
  final Function(File)? onRecordedFile;

  const VoiceRecorderSection({super.key, this.onRecordedFile});

  @override
  State<VoiceRecorderSection> createState() => _VoiceRecorderSectionState();
}

class _VoiceRecorderSectionState extends State<VoiceRecorderSection> {
  final AudioRecorder _audioRecorder = AudioRecorder();
  bool isRecording = false;
  File? recordedFile;

  @override
  void dispose() {
    _audioRecorder.dispose();
    super.dispose();
  }

  /// طلب الصلاحيات المناسبة
  Future<bool> _requestPermissions() async {
    // صلاحية الميكروفون
    var micStatus = await Permission.microphone.request();
    if (!micStatus.isGranted) return false;

    // صلاحية التخزين (حسب نسخة الأندرويد)
    if (Platform.isAndroid) {
      if (await Permission.manageExternalStorage.isGranted ||
          await Permission.storage.isGranted ||
          await Permission.audio.isGranted) {
        return true;
      }

      // جرّب تطلب كل الصلاحيات المرتبطة
      var statuses =
          await [
            Permission.storage,
            Permission.manageExternalStorage,
            Permission.audio,
            Permission.photos,
          ].request();

      return statuses.values.any((s) => s.isGranted);
    }

    return true;
  }

  /// حفظ الملف في مجلد عام يظهر في مدير الملفات
  Future<File?> saveRecordingToPublicFolder(File file) async {
    // تحقق من الصلاحيات
    final granted = await _requestPermissions();
    if (!granted) {
      throw Exception("Storage permission not granted");
    }

    final directory = Directory('/storage/emulated/0/MyRecordings');

    if (!await directory.exists()) {
      await directory.create(recursive: true);
    }

    final newPath =
        '${directory.path}/recording_${DateTime.now().millisecondsSinceEpoch}.m4a';

    return await file.copy(newPath);
  }

  Future<void> _toggleRecording() async {
    try {
      if (!isRecording) {
        // بداية التسجيل
        final hasPerm = await _audioRecorder.hasPermission();
        if (!hasPerm) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Microphone permission required')),
          );
          return;
        }

        final tempDir = await getTemporaryDirectory();
        final tempPath =
            '${tempDir.path}/rec_${DateTime.now().millisecondsSinceEpoch}.m4a';

        await _audioRecorder.start(const RecordConfig(), path: tempPath);

        setState(() => isRecording = true);
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('بدأ التسجيل...')));
      } else {
        // إيقاف التسجيل
        final path = await _audioRecorder.stop();
        setState(() => isRecording = false);

        if (path != null) {
          final file = File(path);
          final savedFile = await saveRecordingToPublicFolder(file);

          setState(() {
            recordedFile = savedFile;
          });

          if (widget.onRecordedFile != null && savedFile != null) {
            widget.onRecordedFile!(savedFile);
          }

          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('تم حفظ التسجيل في ${savedFile?.path}')),
          );
        } else {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('لم يتم تسجيل ملف')));
        }
      }
    } catch (e) {
      print('خطأ أثناء التسجيل: $e');
      setState(() => isRecording = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('خطأ أثناء التسجيل: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        ElevatedButton.icon(
          onPressed: _toggleRecording,
          icon: Icon(isRecording ? Icons.stop : Icons.mic, size: 30),
          label: Text(
            isRecording ? 'إيقاف' : ' تسجيل صوتي ',
            style: const TextStyle(fontSize: 25),
          ),
          style: ElevatedButton.styleFrom(
            elevation: 8,
            backgroundColor: isRecording ? Colors.red : Colors.blue,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 12),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(30),
            ),
          ),
        ),
        const SizedBox(height: 12),
      ],
    );
  }
}
