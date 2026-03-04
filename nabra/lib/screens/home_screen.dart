import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_app/screens/buildVoiceRecorderSection.dart';
import 'package:flutter_app/screens/loading_files.dart';
import 'package:flutter_app/widgets/staggered_fade_slide.dart';
import 'package:flutter_app/widgets/standerd.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_note_kit/player/utils/audio_player_controller.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreen();
}

class _HomeScreen extends State<HomeScreen> {
  File? recordedFile;
  File? selectedAudioFile;
  String recordedAudioBlobUrl = "";
  String selectedModel = "large-v3";

  final TextEditingController _controller = TextEditingController();

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
    return Builder(
      builder: (context) {
        final screenWidth = MediaQuery.of(context).size.width;
        final screenHeight = MediaQuery.of(context).size.height;
        return Standerd(
          widget: SingleChildScrollView(
            child: StaggeredFadeSlide(
              children: [
                Divider(
                  color: Color(0xFF125B4A),
                  thickness: 1.5,
                  indent: 20,
                  endIndent: 20,
                ),
                Gap(25),
                Row(
                  children: [
                    Gap(18),
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
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(10),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.2),
                              spreadRadius: 2,
                              blurRadius: 7,
                              offset: Offset(0, 3),
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
                        width: 170,
                        height: 110,
                        child: Image.asset(
                          "assets/images/image_2.png",
                          color: const Color.fromARGB(255, 206, 182, 111),
                        ),
                      ),
                    ),

                    Gap(15),
                    InkWell(
                      onTap: () async {
                        final apiUrl = _controller.text.trim();
                        final result1 = await FilePicker.platform.pickFiles(
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
                        if (result1 == null) return;

                        final files = result1.files
                            .where((f) => f.path != null)
                            .map((f) => File(f.path!))
                            .toList();

                        if (files.isEmpty) return;
                        if (apiUrl.isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text("الرجاء ادخال رابط api")),
                          );
                          return;
                        }

                        context.push(
                          "/analysis_audio",
                          extra: {"files": files, "apiUrl": apiUrl},
                        );
                      },
                      child: Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(10),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.2),
                              spreadRadius: 2,
                              blurRadius: 7,
                              offset: Offset(0, 3),
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
                        width: 170,
                        height: 110,
                        child: Image.asset(
                          "assets/images/image_3.png",
                          color: const Color.fromARGB(255, 206, 182, 111),
                        ),
                      ),
                    ),
                  ],
                ),
                Gap(25),
                Row(
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(left: 40),
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [
                              Color(0xFF0C3A34), // اللون الغامق الأساسي
                              Color(0xFF125B4A), // لون متوسط
                              Color(0xFF1A7B6A), // لون أفتح لإضافة لمعة
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.all(Radius.circular(30)),
                        ),
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            elevation: 9,
                            backgroundColor: Colors.transparent,
                            fixedSize: Size(310, 50),
                          ),
                          onPressed: () {
                            final apiUrl = _controller.text.trim();
                            if (selectedAudioFile == null) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    "الرجاء رفع الملف الصوتي أولاًً",
                                  ),
                                ),
                              );
                              return;
                            }
                            if (apiUrl.isEmpty) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text("الرجاء ادخال رابط api"),
                                ),
                              );
                              return;
                            }

                            context.push(
                              "/analysis_audio",
                              extra: {
                                "files": <File>[selectedAudioFile!],
                                "apiUrl": apiUrl,
                                "selectedModel": selectedModel,
                              },
                            );
                          },
                          child: Text(
                            "قم بتحويل الملف الصوتي المخزن إلى نص ",
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                    ),
                    Gap(25),
                  ],
                ),

                Gap(50),
                VoiceRecorderSection(
                  onRecordedFile: (file) {
                    setState(() {
                      recordedFile = file;
                    });
                  },
                ),

                Padding(
                  padding: EdgeInsets.all(10),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(10),
                    child: InkWell(
                      onTap: () {
                        final apiUrl = _controller.text.trim();
                        if (apiUrl.isEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('الرجاء كتابة الرابط'),
                            ),
                          );
                        }
                        if (recordedFile != null) {
                          context.push(
                            "/analysis_audio",
                            extra: {
                              "files": <File>[recordedFile!],
                              "apiUrl": apiUrl,
                            },
                          );
                        } else if (recordedFile == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('الرجاء تسجيل صوت أولاً'),
                            ),
                          );
                        }
                      },

                      child: Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(25),
                          gradient: LinearGradient(
                            colors: [
                              const Color(0xFF0C3A34),
                              const Color(0xFF125B4A), // أخضر أغمق
                              const Color(0xFF1A7B6A), // أخضر متوسط
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                        ),
                        width: 400,
                        height: 80,

                        child: Row(
                          children: [
                            Padding(
                              padding: const EdgeInsets.only(left: 15),
                              child: Image.asset(
                                "assets/images/image_4.png",
                                height: 100,
                                width: 110,
                                fit: BoxFit.contain,
                                color: Colors.white.withOpacity(0.5),
                              ),
                            ),
                            Gap(15),
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
                                    " تحويل الصوت المسجل إلى نص ",
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
                Gap(10),
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
                      fixedSize: Size(200, 50),
                    ),
                    onPressed: () {
                      final apiUrl = _controller.text.trim();

                      if (apiUrl.isEmpty) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text("الرجاء إدخال رابط api"),
                          ),
                        );
                        return;
                      }

                      context.push(
                        "/text_to_speech",
                        extra: {"apiUrl": apiUrl},
                      );
                    },
                    child: Row(
                      children: [
                        Text(
                          "تحويل النص إلى صوت",
                          style: TextStyle(color: Colors.white, fontSize: 16),
                        ),
                        Gap(25),
                        Icon(Icons.volume_up, color: Colors.white, size: 20),
                      ],
                    ),
                  ),
                ),
                Gap(10),
                // Container(
                //   width: 200,
                //   decoration: BoxDecoration(
                //     gradient: LinearGradient(
                //       colors: [
                //         const Color(0xFF0C3A34),
                //         const Color(0xFF125B4A),
                //         const Color(0xFF1A7B6A),
                //       ],
                //       begin: Alignment.topLeft,
                //       end: Alignment.bottomRight,
                //     ),
                //     borderRadius: BorderRadius.circular(15),
                //   ),
                //   child: DropdownButton<String>(
                //     value: selectedModel,
                //     dropdownColor: const Color(0xff124B44),
                //     isExpanded: true,
                //     underline: const SizedBox(),
                //     icon: const Icon(
                //       Icons.arrow_drop_down,
                //       color: Colors.white,
                //     ),
                //     style: const TextStyle(color: Colors.white),
                //     items: modelLevels.map((model) {
                //       return DropdownMenuItem(value: model, child: Text(model));
                //     }).toList(),
                //     onChanged: (value) {
                //       setState(() {
                //         selectedModel = value!;
                //       });
                //     },
                //   ),
                // ),
                TextField(
                  controller: _controller,
                  decoration: InputDecoration(
                    border: OutlineInputBorder(),
                    hintText: 'ادخل رابطapi هنا ',
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
