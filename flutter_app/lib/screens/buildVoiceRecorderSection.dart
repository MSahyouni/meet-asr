import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

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

  Future<File> saveRecordingToDownloads(File file) async {
    final directory = await getExternalStorageDirectory();

    final downloadsDir = Directory(
      "${directory!.parent.parent.parent.parent.path}/Download",
    );

    final newPath =
        '${downloadsDir.path}/recording_${DateTime.now().millisecondsSinceEpoch}.m4a';

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
          final savedFile = await saveRecordingToDownloads(file);

          setState(() {
            recordedFile = savedFile;
          });

          if (widget.onRecordedFile != null) {
            widget.onRecordedFile!(savedFile);
          }

          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('تم حفظ التسجيل في ${savedFile.path}')),
          );
        } else {
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('لم يتم تسجيل ملف')));
        }
      }
    } catch (e) {
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
            isRecording ? 'إيقاف' : 'تسجيل',
            style: TextStyle(fontSize: 25),
          ),
          style: ElevatedButton.styleFrom(
            backgroundColor: isRecording ? Colors.red : Colors.blue,
            foregroundColor: Colors.white,

            padding: const EdgeInsets.symmetric(horizontal: 80, vertical: 12),
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
