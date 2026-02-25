import 'package:flutter/material.dart';
import 'package:gap/gap.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class SummaryScreen extends StatefulWidget {
  final String text; // النص الكامل المحلل من صفحة AnalysisAudioScreen
  final String model; // النموذج المختار: Light أو Large
  final String apiUrl; // رابط API الأصلي من صفحة التحليل (transcribe)

  const SummaryScreen({
    super.key,
    required this.text,
    required this.model,
    required this.apiUrl,
  });

  @override
  State<SummaryScreen> createState() => _SummaryScreenState();
}

class _SummaryScreenState extends State<SummaryScreen> {
  bool isLoading = false;
  String currentSummary = "";
  String currentKeywords = "";

  @override
  void initState() {
    super.initState();
    currentSummary = widget.text; // عرض النص الكامل المحلل أولاً
    currentKeywords = ""; // يمكن ترك الكلمات المفتاحية فارغة مبدئياً
  }

  Future<void> summarizeAgain() async {
    setState(() {
      isLoading = true;
    });

    try {
      final summaryApiUrl = widget.apiUrl.replaceAll("transcribe", "summarize");

      final response = await http.post(
        Uri.parse(summaryApiUrl),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"text": widget.text, "model": widget.model}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          currentSummary = data['summary'] ?? currentSummary;
          currentKeywords = data['keywords'] ?? currentKeywords;
        });
      } else {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text("فشل التلخيص")));
      }
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text("حدث خطأ: $e")));
    } finally {
      setState(() {
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: const Text(
          "تلخيص النص",
          style: TextStyle(
            color: Colors.white,
            fontSize: 26,
            fontWeight: FontWeight.w500,
          ),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: summarizeAgain, // إعادة التلخيص بالنص الكامل
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
            padding: const EdgeInsets.all(16.0),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Gap(110),
                  const Text(
                    'ملخص التحليل',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: Color.fromARGB(255, 56, 168, 153),
                    ),
                  ),
                  const Gap(20),
                  _buildGradientBox(
                    currentSummary,
                    textAlign: TextAlign.justify,
                  ),
                  const Gap(30),
                  const Text(
                    'الكلمات المفتاحية',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      color: Color.fromARGB(255, 56, 168, 153),
                    ),
                  ),
                  const Gap(15),
                  _buildGradientBox(
                    currentKeywords,
                    textAlign: TextAlign.center,
                  ),
                  const Gap(30),
                  if (isLoading)
                    const Center(child: CircularProgressIndicator()),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGradientBox(
    String content, {
    TextAlign textAlign = TextAlign.start,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        content,
        style: const TextStyle(fontSize: 16, color: Colors.white, height: 1.6),
        textAlign: textAlign,
      ),
    );
  }
}
