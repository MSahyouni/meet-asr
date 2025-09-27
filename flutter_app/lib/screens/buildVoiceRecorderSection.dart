import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:voice_note_kit/player/audio_player_widget.dart';
import 'package:voice_note_kit/player/player_enums/player_enums.dart';
import 'package:voice_note_kit/recorder/voice_enums/voice_enums.dart';
import 'package:voice_note_kit/recorder/voice_recorder_widget.dart';

Widget buildVoiceRecorderSection({
  required BuildContext context,
  required Function(File) onRecorded,
  required Function(String) onRecordedWeb,
  required Function(String) onError,
  required VoidCallback onCancel,
  required dynamic playerController,
  File? recordedFile,
  String recordedAudioBlobUrl = "",
}) {
  return Column(
    children: [
      VoiceRecorderWidget(
        showTimerText: true,
        showSwipeLeftToCancel: true,
        onRecordedWeb: (url) {
          onRecordedWeb(url);
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('تم حفظ التسجيل (ويب)')));
        },
        onRecorded: (file) async {
          final appDir = await getApplicationDocumentsDirectory();
          final savedFile = await file.copy(
            '${appDir.path}/${DateTime.now().millisecondsSinceEpoch}.m4a',
          );

          onRecorded(savedFile);
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('تم حفظ التسجيل')));
        },
        onError: (error) {
          onError(error);
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(SnackBar(content: Text('Error: $error')));
        },
        actionWhenCancel: () {
          onCancel();
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
      const SizedBox(height: 10),

      // إذا في ملف صوت مسجل
      if (recordedFile != null)
        Column(
          children: [
            AudioPlayerWidget(
              controller: playerController,
              autoLoad: true,
              audioPath: recordedFile.path,
              size: 60,
              progressBarHeight: 5,
              backgroundColor: Colors.blueAccent,
              progressBarColor: Colors.blue,
              progressBarBackgroundColor: Colors.white,
              iconColor: Colors.white,
              shapeType: PlayIconShapeType.circular,
              playerStyle: PlayerStyle.style2,
              width: 300,
              showProgressBar: true,
              showTimer: true,
            ),
            const SizedBox(height: 10),
          ],
        ),

      // إذا في تسجيل بصيغة blob (ويب)
      if (recordedAudioBlobUrl.isNotEmpty)
        AudioPlayerWidget(
          autoPlay: false,
          autoLoad: true,
          audioPath: recordedAudioBlobUrl,
          audioType: AudioType.blobforWeb,
          playerStyle: PlayerStyle.style1,
          textDirection: TextDirection.rtl,
          size: 60,
          progressBarHeight: 5,
          backgroundColor: Colors.blueAccent,
          progressBarColor: Colors.blue,
          progressBarBackgroundColor: Colors.white,
          iconColor: Colors.white,
          shapeType: PlayIconShapeType.circular,
          showProgressBar: true,
          showTimer: true,
          width: 300,
          audioSpeeds: const [0.5, 1.0, 1.5, 2.0, 3.0],
          onSeek: (value) => print('Seeked to: $value'),
          onError: (message) => print('Error: $message'),
          onPause: () => print("Paused"),
          onPlay: (isPlaying) => print("Playing: $isPlaying"),
          onSpeedChange: (speed) => print("Speed: $speed"),
        ),
    ],
  );
}
