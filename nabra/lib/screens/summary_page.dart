import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class SummaryScreen extends StatefulWidget {
  final String text;

  const SummaryScreen({super.key, required this.text});

  @override
  State<SummaryScreen> createState() => _SummaryScreenState();
}

class _SummaryScreenState extends State<SummaryScreen> {
  bool isLoading = false;
  String? summary;

  Future<void> summarizeText() async {
    setState(() {
      isLoading = true;
      summary = null;
    });

    try {
      final response = await http.post(
        Uri.parse("https://your-backend.com/summarize"), // رابط الباك-إند
        headers: {"Content-Type": "application/json"},
        body: json.encode({"text": widget.text}),
      );

      if (response.statusCode == 200) {
        final decoded = json.decode(response.body);
        setState(() {
          summary =
              decoded["summary"]; // الباك-إند لازم يرجع {"summary": "..."}
        });
      } else {
        throw Exception("فشل التلخيص: ${response.statusCode}");
      }
    } catch (e) {
      setState(() {
        summary = "حدث خطأ أثناء التلخيص: $e";
      });
    } finally {
      setState(() {
        isLoading = false;
      });
    }
  }

  @override
  void initState() {
    super.initState();
    summarizeText(); // يشتغل تلقائي عند الدخول للصفحة
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("ملخص النص"),
        backgroundColor: Colors.blueAccent,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child:
            isLoading
                ? const Center(child: CircularProgressIndicator())
                : summary == null
                ? const Center(child: Text("لم يتم توليد ملخص بعد"))
                : Card(
                  elevation: 4,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: SingleChildScrollView(
                      child: Text(
                        summary!,
                        style: const TextStyle(fontSize: 18, height: 1.5),
                        textAlign: TextAlign.justify,
                      ),
                    ),
                  ),
                ),
      ),
    );
  }
}
