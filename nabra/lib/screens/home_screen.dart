import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:nabra/screens/buildVoiceRecorderSection.dart';
import 'package:nabra/widgets/staggered_fade_slide.dart';
import 'package:nabra/widgets/standerd.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_note_kit/player/utils/audio_player_controller.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  File? recordedFile;
  File? selectedAudioFile;

  String recordedAudioBlobUrl = "";
  String selectedModel = "large-v3";

  final TextEditingController _controller = TextEditingController();

  late final VoiceNotePlayerController playerController;

  @override
  void initState() {
    super.initState();
    playerController = VoiceNotePlayerController();
  }

  @override
  void dispose() {
    _controller.dispose();
    playerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Builder(
      builder: (context) {
        return Standerd(
          widget: SingleChildScrollView(
            child: StaggeredFadeSlide(
              children: [
                const Divider(
                  color: Color(0xFF125B4A),
                  thickness: 1.5,
                  indent: 20,
                  endIndent: 20,
                ),

                const Gap(5),

                const Text(
                  "نبرة",
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 35,
                    color: Color.fromARGB(255, 214, 204, 204),
                  ),
                ),

                const Gap(20),

                // =====================================================
                // اختيار ملف صوتي أو أكثر
                // =====================================================

                InkWell(
                  onTap: () async {
                    final apiUrl = _controller.text.trim();

                    final result = await FilePicker.platform.pickFiles(
                      type: FileType.custom,
                      allowedExtensions: [
                        'mp3',
                        'wav',
                        'm4a',
                        'aac',
                        'opus',
                      ],
                      allowMultiple: true,
                    );

                    if (result == null) {
                      return;
                    }

                    final files = result.files
                        .where((file) => file.path != null)
                        .map((file) => File(file.path!))
                        .toList();

                    if (files.isEmpty) {
                      return;
                    }

                    if (apiUrl.isEmpty) {
                      if (!context.mounted) {
                        return;
                      }

                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: const Text(
                            "الرجاء ادخال رابط api",
                          ),
                          backgroundColor: const Color.fromARGB(
                            255,
                            75,
                            151,
                            78,
                          ),
                          behavior: SnackBarBehavior.floating,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(10),
                          ),
                          margin: const EdgeInsets.all(16),
                        ),
                      );

                      return;
                    }

                    if (!context.mounted) {
                      return;
                    }

                    context.push(
                      "/analysis_audio",
                      extra: {
                        "files": files,
                        "apiUrl": apiUrl,
                      },
                    );
                  },
                  child: Container(
                    alignment: Alignment.center,
                    width: 350,
                    height: 110,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(25),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.2),
                          spreadRadius: 2,
                          blurRadius: 7,
                          offset: const Offset(0, 3),
                        ),
                      ],
                      gradient: const LinearGradient(
                        colors: [
                          Color(0xFF0C3A34),
                          Color(0xFF125B4A),
                          Color(0xFF1A7B6A),
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                    ),
                    child: Row(
                      children: [
                        const Gap(20),

                        Image.asset(
                          "assets/images/icon_file.png",
                          height: 70,
                          width: 110,
                          fit: BoxFit.contain,
                        ),

                        const Gap(40),

                        const Text(
                          "قم بتحميل ملف صوتي \n           أو أكثر",
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const Gap(30),

                // =====================================================
                // تسجيل الصوت
                // =====================================================

                VoiceRecorderSection(
                  onRecordedFile: (file) {
                    setState(() {
                      recordedFile = file;
                    });
                  },
                ),

                // =====================================================
                // تحويل التسجيل الصوتي إلى نص
                // =====================================================

                Padding(
                  padding: const EdgeInsets.all(10),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: InkWell(
                      onTap: () {
                        final apiUrl = _controller.text.trim();

                        if (apiUrl.isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: const Text(
                                'الرجاء كتابة الرابط',
                              ),
                              backgroundColor: const Color.fromARGB(
                                255,
                                158,
                                75,
                                69,
                              ),
                              behavior: SnackBarBehavior.floating,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                              margin: const EdgeInsets.all(16),
                            ),
                          );

                          return;
                        }

                        if (recordedFile == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: const Text(
                                'الرجاء تسجيل صوت أولاً',
                              ),
                              backgroundColor: const Color.fromARGB(
                                255,
                                158,
                                75,
                                69,
                              ),
                              behavior: SnackBarBehavior.floating,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                              margin: const EdgeInsets.all(16),
                            ),
                          );

                          return;
                        }

                        context.push(
                          "/analysis_audio",
                          extra: {
                            "files": <File>[
                              recordedFile!,
                            ],
                            "apiUrl": apiUrl,
                          },
                        );
                      },
                      child: Container(
                        width: 380,
                        height: 80,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(25),
                          gradient: const LinearGradient(
                            colors: [
                              Color(0xFF0C3A34),
                              Color(0xFF125B4A),
                              Color(0xFF1A7B6A),
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                        ),
                        child: Row(
                          children: [
                            Padding(
                              padding: const EdgeInsets.only(
                                left: 15,
                              ),
                              child: Image.asset(
                                "assets/images/image_4.png",
                                height: 100,
                                width: 110,
                                fit: BoxFit.contain,
                                color: Colors.white.withOpacity(0.5),
                              ),
                            ),

                            const Gap(10),

                            const Text(
                              " تحويل الصوت المسجل إلى نص ",
                              style: TextStyle(
                                fontSize: 18,
                                color: Colors.white,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),

                const Gap(25),

                // =====================================================
                // تحويل النص إلى صوت
                // =====================================================

                Container(
                  width: 230,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(25),
                    gradient: const LinearGradient(
                      colors: [
                        Color(0xFF0C3A34),
                        Color(0xFF125B4A),
                        Color(0xFF1A7B6A),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      elevation: 5,
                      backgroundColor: Colors.transparent,
                      fixedSize: const Size(
                        200,
                        50,
                      ),
                    ),
                    onPressed: () {
                      final apiUrl = _controller.text.trim();

                      if (apiUrl.isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: const Text(
                              "الرجاء إدخال رابط api",
                            ),
                            backgroundColor: const Color.fromARGB(
                              255,
                              158,
                              75,
                              69,
                            ),
                            behavior: SnackBarBehavior.floating,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                            margin: const EdgeInsets.all(16),
                          ),
                        );

                        return;
                      }

                      context.push(
                        "/text_to_speech",
                        extra: {
                          "apiUrl": apiUrl,
                        },
                      );
                    },
                    child: const Row(
                      children: [
                        Text(
                          "تحويل النص إلى صوت",
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                          ),
                        ),

                        Gap(25),

                        Icon(
                          Icons.volume_up,
                          color: Colors.white,
                          size: 20,
                        ),
                      ],
                    ),
                  ),
                ),

                const Gap(40),

                // =====================================================
                // رابط API
                // =====================================================

                TextField(
                  controller: _controller,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    hintText: 'ادخل رابط api هنا',
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}