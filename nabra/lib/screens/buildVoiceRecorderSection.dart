import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

class VoiceRecorderSection extends StatefulWidget {
  final Function(File)? onRecordedFile; // callback لإرسال الملف

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

  Future<File> saveRecordingToMyRecording(File file) async {
    final myRecordingDir = Directory(
      '/storage/emulated/0/Download/MyRecording',
    );

    if (!await myRecordingDir.exists()) {
      await myRecordingDir.create(recursive: true);
    }

    final newPath =
        '${myRecordingDir.path}/recording_${DateTime.now().millisecondsSinceEpoch}.m4a';

    final savedFile = await file.copy(newPath);
    return savedFile;
  }

  Future<void> _toggleRecording() async {
    try {
      if (!isRecording) {
        // بداية التسجيل
        final hasPerm = await _audioRecorder.hasPermission();
        if (!hasPerm) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Microphone permission required'),
              backgroundColor: const Color.fromARGB(255, 75, 151, 78),
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
              margin: EdgeInsets.all(16),
            ),
          );
          return;
        }

        final tempDir = await getTemporaryDirectory();
        final tempPath =
            '${tempDir.path}/rec_${DateTime.now().millisecondsSinceEpoch}.m4a';

        // ابدأ التسجيل (يمكن تمرير RecordConfig مخصص إذا أردت)
        await _audioRecorder.start(const RecordConfig(), path: tempPath);

        setState(() => isRecording = true);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('بدأ التسجيل...'),
            backgroundColor: Color.fromARGB(255, 75, 151, 78),
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
            margin: EdgeInsets.all(16),
          ),
        );
      } else {
        // إيقاف التسجيل
        final path = await _audioRecorder.stop(); // يعيد المسار أو null
        setState(() => isRecording = false);

        if (path != null) {
          final file = File(path);
          final savedFile = await saveRecordingToMyRecording(file);

          setState(() {
            recordedFile = savedFile;
          });

          if (widget.onRecordedFile != null) {
            widget.onRecordedFile!(savedFile);
          }

          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('تم حفظ التسجيل في ${savedFile.path}'),
              backgroundColor: const Color.fromARGB(255, 75, 151, 78),
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
              margin: EdgeInsets.all(16),
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('لم يتم تسجيل ملف'),
              backgroundColor: const Color.fromARGB(255, 75, 151, 78),
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
              margin: EdgeInsets.all(16),
            ),
          );
        }
      }
    } catch (e) {
      setState(() => isRecording = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('خطأ أثناء التسجيل: $e'),
          backgroundColor: const Color.fromARGB(255, 75, 151, 78),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            gradient: isRecording
                ? const LinearGradient(
                    colors: [Colors.redAccent, Colors.red],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  )
                : const LinearGradient(
                    colors: [
                      Color.fromARGB(255, 12, 58, 52), // اللون الأساسي الغامق
                      Color.fromARGB(255, 18, 75, 68), // أفتح قليلاً
                      Color.fromARGB(255, 25, 90, 82), // لمعة خفيفة
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
            borderRadius: BorderRadius.all(Radius.circular(30)),
          ),
          child: ElevatedButton.icon(
            onPressed: _toggleRecording,
            icon: Icon(
              isRecording ? Icons.stop : Icons.mic,
              size: 30,
              color: Colors.white,
            ),
            label: Text(
              isRecording ? 'إيقاف' : ' تسجيل صوتي ',
              style: const TextStyle(fontSize: 25, color: Colors.white),
            ),
            style: ElevatedButton.styleFrom(
              elevation: 8,
              backgroundColor: Colors.transparent, // شفاف لأن التدرج بالخلف
              shadowColor: Colors.black54,
              padding: const EdgeInsets.symmetric(horizontal: 30, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(30),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),

        const SizedBox(height: 20),
      ],
    );
  }
}
