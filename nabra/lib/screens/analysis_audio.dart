import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:nabra/services/text_saver.dart';
import 'package:nabra/widgets/animated_list_item.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
//  استيراد الأنيميشن اللي عندك
import 'package:nabra/widgets/staggered_fade_slide.dart';

class AnalysisAudioScreen extends StatefulWidget {
  const AnalysisAudioScreen({super.key});

  @override
  State<AnalysisAudioScreen> createState() => _AnalysisAudioScreenState();
}

class _AnalysisAudioScreenState extends State<AnalysisAudioScreen> {
  String? selectedModel;
  bool isLoading = false;
  String? selectedSummaryModel = "Light";

  // قائمة لتخزين نتائج التحليل لكل الملفات
  List<Map<String, String>> transcriptionSegments = [];

  Future<List<Map<String, String>>> sendAudio(
    File file,
    String apiUrl,
    String selectedModel,
  ) async {
    final request = http.MultipartRequest('POST', Uri.parse(apiUrl));

    request.files.add(
      await http.MultipartFile.fromPath(
        'file',
        file.path,
        contentType: MediaType('audio', 'wav'),
      ),
    );

    request.fields['model'] = selectedModel;

    final response = await request.send();

    if (response.statusCode == 200) {
      final respStr = await response.stream.bytesToString();
      final decoded = json.decode(respStr);

      if (decoded is Map<String, dynamic>) {
        return [
          {
            "text": decoded["text"]?.toString() ?? "",
            "summary": decoded["summary"]?.toString() ?? "",
            "keywords": decoded["keywords"]?.toString() ?? "",
          },
        ];
      } else {
        throw Exception("الاستجابة غير متوقعة: ليست Map");
      }
    } else {
      throw Exception(
        'فشل في تحليل الملف ${file.path.split('/').last} (status: ${response.statusCode})',
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final extra = GoRouterState.of(context).extra as Map<String, dynamic>?;

    final List<File> files =
        (extra?["files"] as List<dynamic>?)?.map((e) => e as File).toList() ??
        [];

    final apiUrl = extra?["apiUrl"] as String? ?? '';

    if (files.isEmpty) {
      return Scaffold(body: Center(child: Text('لا يوجد ملف صوتي')));
    }

    return Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: Colors.transparent,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: const Text(
          "تحليل الصوت",
          style: TextStyle(
            color: Colors.white,
            fontSize: 26,
            fontWeight: FontWeight.w500,
          ),
        ),
        actions: [
          PopupMenuButton<String>(
            color: const Color.fromARGB(255, 17, 80, 65),
            icon: const Icon(Icons.more_vert, size: 28, color: Colors.white),
            onSelected: (value) async {
              if (value == 'save_txt') {
                if (transcriptionSegments.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('لا يوجد نص محلل للحفظ'),
                      backgroundColor: Colors.red,
                      behavior: SnackBarBehavior.floating,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                      margin: EdgeInsets.all(16),
                    ),
                  );
                  return;
                }

                final analyzedText = transcriptionSegments
                    .map((e) => e['text'] ?? '')
                    .where((e) => e.trim().isNotEmpty)
                    .join('\n\n');

                await FileSaver.saveAnalyzedText(
                  context: context,
                  analyzedText: analyzedText,
                );
              }
            },
            itemBuilder: (context) => const [
              PopupMenuItem(
                value: 'save_txt',
                child: Row(
                  children: [
                    Icon(Icons.save_alt, size: 20, color: Colors.white),
                    SizedBox(width: 10),
                    Text(
                      'Save analyzed text as txt',
                      style: TextStyle(fontSize: 16, color: Colors.white),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: Image.asset("assets/images/image_5.png", fit: BoxFit.cover),
          ),
          Container(color: Colors.black.withOpacity(0.25)),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 140, 20, 20),
            child: Column(
              children: [
                //  أنيميشن للعناصر العلوية فقط
                StaggeredFadeSlide(
                  children: [
                    buildMainButton(
                      icon: Icons.play_arrow,
                      text: "إرسال وتحويل الصوت إلى نص",
                      onTap: () async {
                        setState(() {
                          isLoading = true;
                          transcriptionSegments.clear();
                        });

                        try {
                          for (final file in files) {
                            final result = await sendAudio(
                              file,
                              apiUrl,
                              selectedModel ?? "medium",
                            );

                            transcriptionSegments.add({
                              'speaker': ' الملف: ${file.path.split('/').last}',
                              'text': '',
                            });

                            transcriptionSegments.addAll(result);
                          }
                        } catch (e) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('حدث خطأ: $e'),

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
                              margin: EdgeInsets.all(16),
                            ),
                          );
                        } finally {
                          setState(() {
                            isLoading = false;
                          });
                        }
                      },
                    ),
                    const SizedBox(height: 20),
                    buildSmallButton(
                      text: "تلخيص النص",
                      onTap: () {
                        final fullText = transcriptionSegments
                            .map((seg) => seg['text'] ?? '')
                            .where((t) => t.trim().isNotEmpty)
                            .join("\n\n");

                        context.push(
                          '/summary',
                          extra: {
                            'text': fullText,
                            'model': selectedModel,
                            'apiUrl': apiUrl,
                          },
                        );
                      },
                    ),
                    const SizedBox(height: 30),
                    buildSummaryModelDropdown(),
                    const SizedBox(height: 10),
                  ],
                ),

                //  نحافظ على التصميم
                if (isLoading)
                  const Expanded(
                    child: Center(child: CircularProgressIndicator()),
                  )
                else
                  Expanded(
                    child: ListView.builder(
                      itemCount: transcriptionSegments.length,
                      itemBuilder: (context, index) {
                        final segment = transcriptionSegments[index];
                        final speaker = segment['speaker'] ?? '';
                        final text = segment['text'] ?? '';

                        //  أنيميشن لكل عنصر ListView
                        return AnimatedListItem(
                          index: index > 25
                              ? 25
                              : index, // حماية من التأخير الكبير
                          child: Container(
                            margin: const EdgeInsets.symmetric(vertical: 5),
                            padding: const EdgeInsets.all(12),
                            decoration: const BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  Color(0xFF0C3A34),
                                  Color(0xFF125B4A),
                                  Color(0xFF1A7B6A),
                                ],
                              ),
                              borderRadius: BorderRadius.only(
                                topLeft: Radius.circular(12),
                                topRight: Radius.circular(12),
                              ),
                            ),
                            child: Column(
                              crossAxisAlignment: speaker.contains('متكلم')
                                  ? CrossAxisAlignment.start
                                  : CrossAxisAlignment.end,
                              children: [
                                Text(
                                  speaker,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                                const SizedBox(height: 5),
                                Text(
                                  text,
                                  style: const TextStyle(
                                    fontSize: 16,
                                    color: Colors.white,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // 🔹 زر رئيسي كبير
  Widget buildMainButton({
    required IconData icon,
    required String text,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(40),
      child: Container(
        height: 65,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(40),
          gradient: const LinearGradient(
            colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF2AA876).withOpacity(0.25),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: Colors.white, size: 30),
            const SizedBox(width: 12),
            Text(
              text,
              style: const TextStyle(color: Colors.white, fontSize: 18),
            ),
          ],
        ),
      ),
    );
  }

  // 🔹 زر متوسط
  Widget buildSmallButton({required String text, required VoidCallback onTap}) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(30),
      child: Container(
        height: 55,
        width: 220,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(30),
          gradient: const LinearGradient(
            colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF2AA876).withOpacity(0.25),
              blurRadius: 8,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Text(
          text,
          style: const TextStyle(color: Colors.white, fontSize: 17),
        ),
      ),
    );
  }

  // 🔹 Dropdown
  Widget buildSummaryModelDropdown() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Center(
          child: Text(
            "اختر نموذج التلخيص",
            style: TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(30),
            gradient: const LinearGradient(
              colors: [Color(0xFF0C3A34), Color(0xFF125B4A)],
            ),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF2AA876).withOpacity(0.25),
                blurRadius: 8,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: selectedSummaryModel,
              dropdownColor: const Color(0xFF125B4A),
              iconEnabledColor: Colors.white,
              isExpanded: true,
              style: const TextStyle(color: Colors.white),
              items: const [
                DropdownMenuItem(
                  value: "Light",
                  child: Text("Light Model (سريع وأخف)"),
                ),
                DropdownMenuItem(
                  value: "Large",
                  child: Text("Large Model (أدق وأقوى)"),
                ),
              ],
              onChanged: (value) {
                setState(() {
                  selectedSummaryModel = value!;
                });
              },
            ),
          ),
        ),
      ],
    );
  }
}
