import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_app/screens/buildVoiceRecorderSection.dart';
import 'package:flutter_app/screens/loading_files.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';

import 'package:voice_note_kit/player/utils/audio_player_controller.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreen();
}

class _HomeScreen extends State<HomeScreen> {
  File? recordedFile; // Variable to hold the recorded audio file locally
  File? selectedAudioFile;
  String recordedAudioBlobUrl = "";
  final TextEditingController _controller = TextEditingController();

  // final List<String> modelLevels = [
  //   'small',
  //   'tiny',
  //   'large-v3',
  //   'medium',
  //   'base',
  // ];

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
                Gap(18),
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
                              offset: Offset(0, 3), // مكان الظل
                            ),
                          ],
                        ),
                        width: 170,
                        height: 110,
                        child: Image.asset("assets/images/image6.png"),
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

                        final files =
                            result1.files
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
                              offset: Offset(0, 3), // مكان الظل
                            ),
                          ],
                        ),
                        width: 170,
                        height: 110,
                        child: Image.asset("assets/images/image7.png"),
                      ),
                    ),
                  ],
                ),
                Gap(25),
                Row(
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(left: 40),
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          elevation: 9,
                          backgroundColor: Color.fromARGB(200, 68, 138, 255),
                          fixedSize: Size(310, 50),
                        ),
                        onPressed: () {
                          final apiUrl = _controller.text.trim();
                          if (selectedAudioFile == null) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(
                                content: Text("الرجاء رفع الملف الصوتي أولاًً"),
                              ),
                            );
                            return;
                          }
                          if (apiUrl.isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text("الرجاء ادخال رابط api")),
                            );
                            return;
                          }

                          context.push(
                            "/analysis_audio",
                            extra: {
                              "files": <File>[selectedAudioFile!],
                              "apiUrl": apiUrl,
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
                    Gap(25),
                    // DropdownButton<String>(
                    //   hint: Text('اختر نموذجًا'),
                    //   value: selectedModel,
                    //   items:
                    //       modelLevels.map((String model) {
                    //         return DropdownMenuItem<String>(
                    //           value: model,
                    //           child: Text(model),
                    //         );
                    //       }).toList(),
                    //   onChanged: (String? newValue) {
                    //     setState(() {
                    //       selectedModel = newValue;
                    //     });
                    //   },
                    // ),
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
                  padding: EdgeInsets.all(20),
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

                          color: Colors.blue,
                        ),
                        width: 400,
                        height: 80,

                        child: Row(
                          children: [
                            Padding(
                              padding: const EdgeInsets.only(left: 15),
                              child: Image.asset(
                                "assets/images/image2.png",
                                height: 100,
                                width: 110,
                                fit: BoxFit.contain,
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
                Gap(100),
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
