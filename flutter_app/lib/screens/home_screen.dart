import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_app/screens/loading_files.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_note_kit/player/utils/audio_player_controller.dart';
import 'package:voice_note_kit/recorder/voice_enums/voice_enums.dart';
import 'package:voice_note_kit/voice_note_kit.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreen();
}

class _HomeScreen extends State<HomeScreen> {
  File? recordedFile; // Variable to hold the recorded audio file locally
  File? selectedAudioFile;
  String recordedAudioBlobUrl = "";
  final List<String> modelLevels = [
    'small',
    'tiny',
    'large-v3',
    'medium',
    'base',
  ];
  String? selectedModel;

  late final VoiceNotePlayerController playerController;

  @override
  void initState() {
    playerController = VoiceNotePlayerController();
    super.initState();
  }

  @override
  void dispose() {
    playerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 140,
        title: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Image.asset(
                "assets/images/image5.png",
                height: 80,
                width: 90,
                fit: BoxFit.contain,
              ),
            ),
            Gap(45),
            Text(
              "الجمهورية العربية السورية  \n        وزارة الدفاع ",
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ],
        ),
      ),

      body: SingleChildScrollView(
        child: Column(
          children: [
            Divider(
              color: const Color.fromARGB(255, 204, 200, 200), // لون الخط
              thickness: 1.5,
              indent: 20,
              endIndent: 20,
            ),

            Padding(
              padding: EdgeInsets.all(30),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: InkWell(
                  onTap: () {
                    if (recordedFile != null && selectedModel != null) {
                      context.push(
                        "/analysis_audio",
                        extra: {
                          "files": <File>[recordedFile!],
                          "model": selectedModel,
                        },
                      );
                    } else if (recordedFile == null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('الرجاء تسجيل صوت أولاً')),
                      );
                    } else if (selectedModel == null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('الرجاء اختيار نموذج التحليل أولاً'),
                        ),
                      );
                    }
                  },

                  child: Container(
                    width: 400,
                    height: 100,

                    color: Colors.blue,
                    child: Row(
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(left: 15),
                          child: Image.asset(
                            "assets/images/image2.png",
                            height: 120,
                            width: 120,
                            fit: BoxFit.contain,
                          ),
                        ),
                        Gap(20),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Padding(
                              padding: const EdgeInsets.only(left: 40),
                              child: Text(
                                "صوت إلى نص",
                                style: TextStyle(
                                  fontSize: 25,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.only(left: 10),
                              child: Text(
                                "خدمة تحويل الصوت إلى نص \n            بين يديك الآن ",
                                style: TextStyle(
                                  fontSize: 15,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            Gap(5),
            Row(
              children: [
                Gap(10),
                InkWell(
                  onTap: () async {
                    final result = await FilePicker.platform.pickFiles();
                    if (result == null) return;
                    final file = result.files.first;
                    openFile(file);
                    final newFile = await saveFilePermanently(file);
                    selectedAudioFile = newFile;
                  },
                  child: Container(
                    width: 170,
                    height: 110,
                    child: Image.asset("assets/images/image6.png"),
                  ),
                ),

                Gap(15),
                InkWell(
                  onTap: () async {
                    if (selectedModel == null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text("الرجاء اختيار نموذج التحليل أولاً"),
                        ),
                      );
                      return;
                    }

                    final result1 = await FilePicker.platform.pickFiles(
                      type: FileType.custom,
                      allowedExtensions: ['mp3', 'wav', 'm4a', 'aac'],
                      allowMultiple: true,
                    );
                    if (result1 == null) return;

                    final files =
                        result1.files
                            .where((f) => f.path != null)
                            .map((f) => File(f.path!))
                            .toList();

                    if (files.isEmpty) return;

                    context.push(
                      "/analysis_audio",
                      extra: {"files": files, "model": selectedModel},
                    );
                  },
                  child: Container(
                    width: 185,
                    height: 114,
                    child: Image.asset("assets/images/image7.png"),
                  ),
                ),
              ],
            ),
            Gap(25),
            Row(
              children: [
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Color.fromARGB(200, 68, 138, 255),
                    fixedSize: Size(250, 30),
                  ),
                  onPressed: () {
                    if (selectedAudioFile == null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text("الرجاء رفع الملف الصوتي أولاًً"),
                        ),
                      );
                      return;
                    }
                    if (selectedModel == null) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text("الرجاء اختيار نموذج التحليل أولاً"),
                        ),
                      );
                      return;
                    }

                    context.push(
                      "/analysis_audio",
                      extra: {
                        "files": <File>[selectedAudioFile!],
                        "model": selectedModel,
                      },
                    );
                  },
                  child: Text(
                    "قم بتحويل الملف الصوتي إلى نص ",
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
                Gap(25),
                DropdownButton<String>(
                  hint: Text('اختر نموذجًا'),
                  value: selectedModel,
                  items:
                      modelLevels.map((String model) {
                        return DropdownMenuItem<String>(
                          value: model,
                          child: Text(model),
                        );
                      }).toList(),
                  onChanged: (String? newValue) {
                    setState(() {
                      selectedModel = newValue;
                    });
                  },
                ),
              ],
            ),

            Gap(50),
            VoiceRecorderWidget(
              showTimerText: true,
              showSwipeLeftToCancel: true,
              onRecordedWeb: (url) {
                setState(() {
                  recordedAudioBlobUrl = url;
                });
              },
              onRecorded: (file) {
                setState(() {
                  recordedFile = file;
                });
                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(SnackBar(content: Text('تم حفظ التسجيل ')));
              },

              onError: (error) {
                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(SnackBar(content: Text('Error: $error')));
              },

              actionWhenCancel: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('تم حفظ التسجيل ')),
                );
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

            recordedFile != null
                ? Column(
                  children: [
                    AudioPlayerWidget(
                      controller: playerController,
                      autoLoad: true,
                      audioPath: recordedFile?.path,
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
                    Wrap(spacing: 10, alignment: WrapAlignment.center),
                  ],
                )
                : const SizedBox.shrink(),
            recordedAudioBlobUrl.isNotEmpty
                ? AudioPlayerWidget(
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
                )
                : const SizedBox.shrink(),
          ],
        ),
      ),
    );
  }
}
