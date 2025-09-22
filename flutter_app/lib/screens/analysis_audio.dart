import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class AnalysisAudioScreen extends StatefulWidget {
  const AnalysisAudioScreen({super.key});

  @override
  State<AnalysisAudioScreen> createState() => _AnalysisAudioScreenState();
}

class _AnalysisAudioScreenState extends State<AnalysisAudioScreen> {
  bool isLoading = false;

  // قائمة لتخزين نتائج التحليل لكل الملفات
  List<Map<String, String>> transcriptionSegments = [];

  Future<List<Map<String, String>>> sendAudio(File file, String model) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('https://your-backend.com/analyze'), // ضع رابط الباك-إند  هنا
    );
    request.files.add(await http.MultipartFile.fromPath('audio', file.path));
    request.fields['model'] = model;
    final response = await request.send();

    if (response.statusCode == 200) {
      final respStr = await response.stream.bytesToString();
      final decoded = json.decode(respStr);

      return List<Map<String, String>>.from(decoded['transcription']);
    } else {
      throw Exception('فشل في تحليل الملف ${file.path.split('/').last}');
    }
  }

  @override
  Widget build(BuildContext context) {
    final extra = GoRouterState.of(context).extra as Map<String, dynamic>?;

    final List<File> files =
        (extra?["files"] as List<dynamic>?)?.map((e) => e as File).toList() ??
        [];

    final String? selectedModel = extra?["model"];

    if (files.isEmpty) {
      return const Scaffold(body: Center(child: Text('لا يوجد ملف صوتي')));
    }

    return Scaffold(
      appBar: AppBar(
        actions: [
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, size: 30, color: Colors.white),
            onSelected: (value) {
              if (value == 'summary') {
                if (transcriptionSegments.isEmpty) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        ' لم يتم إدخال أي نص بعد، الرجاء التحليل أولاً',
                      ),
                    ),
                  );
                  return;
                }

                final allText = transcriptionSegments
                    .map((e) => e['text'])
                    .join(' ');
                context.push('/summary', extra: allText);
              }
            },
            itemBuilder:
                (context) => [
                  const PopupMenuItem(value: 'summary', child: Text('summary')),
                ],
          ),
        ],
        title: Row(
          children: [
            const Text(
              'تحليل الصوت',
              style: TextStyle(color: Colors.white, fontSize: 25),
            ),
            Gap(130),
          ],
        ),
        backgroundColor: Colors.blueAccent,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                minimumSize: const Size.fromHeight(50),
                backgroundColor: const Color.fromARGB(200, 68, 138, 255),
              ),
              onPressed: () async {
                setState(() {
                  isLoading = true;
                  transcriptionSegments.clear();
                });

                try {
                  for (final file in files) {
                    if (selectedModel != null) {
                      final result = await sendAudio(file, selectedModel);

                      transcriptionSegments.add({
                        'speaker': ' الملف: ${file.path.split('/').last}',
                        'text': '',
                      });

                      transcriptionSegments.addAll(result);
                    }
                  }
                } catch (e) {
                  ScaffoldMessenger.of(
                    context,
                  ).showSnackBar(SnackBar(content: Text('حدث خطأ: $e')));
                } finally {
                  setState(() {
                    isLoading = false;
                  });
                }
              },
              icon: const Icon(Icons.play_arrow, color: Colors.white, size: 35),
              label: const Text(
                'إرسال وتحويل الصوت إلى نص',
                style: TextStyle(color: Colors.white, fontSize: 20),
              ),
            ),
            const SizedBox(height: 20),
            if (isLoading)
              const Center(child: CircularProgressIndicator())
            else
              Expanded(
                child: ListView.builder(
                  itemCount: transcriptionSegments.length,
                  itemBuilder: (context, index) {
                    final segment = transcriptionSegments[index];
                    final speaker = segment['speaker'] ?? '';
                    final text = segment['text'] ?? '';

                    return Container(
                      margin: const EdgeInsets.symmetric(vertical: 5),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.blue.withOpacity(0.2),
                        borderRadius: BorderRadius.only(
                          topLeft: const Radius.circular(12),
                          topRight: const Radius.circular(12),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment:
                            speaker.contains('متكلم')
                                ? CrossAxisAlignment.start
                                : CrossAxisAlignment.end,
                        children: [
                          Text(
                            speaker,
                            style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Colors.blue,
                            ),
                          ),
                          const SizedBox(height: 5),
                          Text(text, style: const TextStyle(fontSize: 16)),
                        ],
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
