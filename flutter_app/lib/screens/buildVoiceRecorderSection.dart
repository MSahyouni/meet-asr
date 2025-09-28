import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:voice_note_kit/player/player_enums/player_enums.dart';
import 'package:voice_note_kit/recorder/voice_recorder_widget.dart';
import 'package:voice_note_kit/recorder/voice_enums/voice_enums.dart';

class VoiceRecorderSection extends StatefulWidget {
  final Function(File)? onRecordedFile; // Callback لإرسال الملف للصفحة الرئيسية

  const VoiceRecorderSection({super.key, this.onRecordedFile});

  @override
  State<VoiceRecorderSection> createState() => _VoiceRecorderSectionState();
}

class _VoiceRecorderSectionState extends State<VoiceRecorderSection> {
  File? recordedFile;

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

  void handleRecorded(File file) async {
    final savedFile = await saveRecordingToDownloads(file);

    setState(() {
      recordedFile = savedFile;
    });

    // إرسال الملف للصفحة الرئيسية
    if (widget.onRecordedFile != null) {
      widget.onRecordedFile!(savedFile);
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('تم حفظ التسجيل في ${savedFile.path}')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        VoiceRecorderWidget(
          showTimerText: true,
          showSwipeLeftToCancel: true,
          onRecorded: handleRecorded,
          onError: (error) {
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(SnackBar(content: Text('Error: $error')));
          },
          actionWhenCancel: () {
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(const SnackBar(content: Text('تم إلغاء التسجيل')));
          },
          maxRecordDuration: const Duration(seconds: 60),
          permissionNotGrantedMessage: 'Microphone permission required',
          dragToLeftText: 'يتم الآن التسجيل',
          dragToLeftTextStyle: const TextStyle(
            color: Colors.blueAccent,
            fontSize: 18,
          ),
          cancelDoneText: 'Recording cancelled',
          backgroundColor: Colors.blueAccent,
          cancelHintColor: Colors.red,
          iconColor: Colors.white,
          timerFontSize: 16,
          timerTextStyle: const TextStyle(color: Colors.blueAccent),
          style: VoiceUIStyle.compact,
          borderColor: Colors.blue,
          containerColor: Colors.blue,
          borderRadius: 16,
          idleWavesColor: Colors.white,
          recordingWavesColor: Colors.white,
          wavesSpeed: const Duration(milliseconds: 500),
        ),
        const SizedBox(height: 20),
      ],
    );
  }
}
