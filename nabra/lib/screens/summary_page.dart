// import 'package:flutter/material.dart';
// import 'package:flutter_app/widgets/standerd.dart';
// import 'package:gap/gap.dart';
// import 'package:http/http.dart' as http;
// import 'dart:convert';

// class SummaryScreen extends StatefulWidget {
//   final String summary;
//   final String keywords;

//   const SummaryScreen({
//     super.key,
//     required this.summary,
//     required this.keywords,
//   });

//   @override
//   State<SummaryScreen> createState() => _SummaryScreenState();
// }

// class _SummaryScreenState extends State<SummaryScreen> {
//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       extendBodyBehindAppBar: true,
//       appBar: AppBar(
//         backgroundColor: Colors.transparent,
//         elevation: 0,
//         centerTitle: true,
//         title: const Text(
//           "تلخيص النص",
//           style: TextStyle(
//             color: Colors.white,
//             fontSize: 26,
//             fontWeight: FontWeight.w500,
//           ),
//         ),
//         actions: const [
//           Padding(
//             padding: EdgeInsets.only(right: 12),
//             child: Icon(Icons.more_vert, color: Colors.white),
//           ),
//         ],
//       ),
//       body: Stack(
//         children: [
//           Positioned.fill(
//             child: Image.asset("assets/images/image_5.png", fit: BoxFit.cover),
//           ),
//           Container(color: Colors.black.withOpacity(0.25)),

//           Padding(
//             padding: const EdgeInsets.all(16.0),
//             child: SingleChildScrollView(
//               child: Column(
//                 crossAxisAlignment: CrossAxisAlignment.center,
//                 children: [
//                   Gap(110),
//                   const Text(
//                     'ملخص التحليل',
//                     style: TextStyle(
//                       fontSize: 22,
//                       fontWeight: FontWeight.bold,
//                       color: Color.fromARGB(255, 56, 168, 153),
//                     ),
//                   ),
//                   const Gap(20),
//                   _buildGradientBox(
//                     widget.summary,
//                     textAlign: TextAlign.justify,
//                   ),
//                   const Gap(30),
//                   const Text(
//                     'الكلمات المفتاحية',
//                     style: TextStyle(
//                       fontSize: 20,
//                       fontWeight: FontWeight.bold,
//                       color: Color.fromARGB(255, 56, 168, 153),
//                     ),
//                   ),
//                   const Gap(15),
//                   _buildGradientBox(
//                     widget.keywords,
//                     textAlign: TextAlign.center,
//                   ),
//                 ],
//               ),
//             ),
//           ),
//         ],
//       ),
//     );
//   }

//   Widget _buildGradientBox(
//     String content, {
//     TextAlign textAlign = TextAlign.start,
//   }) {
//     return Container(
//       width: double.infinity,
//       padding: const EdgeInsets.all(16),
//       decoration: BoxDecoration(
//         gradient: const LinearGradient(
//           colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
//           begin: Alignment.topLeft,
//           end: Alignment.bottomRight,
//         ),
//         borderRadius: BorderRadius.circular(20),
//       ),
//       child: Center(
//         child: Text(
//           content,
//           style: const TextStyle(
//             fontSize: 16,
//             color: Colors.white,
//             height: 1.6,
//           ),
//           textAlign: textAlign,
//         ),
//       ),
//     );
//   }
// }

import 'package:flutter/material.dart';
import 'package:flutter_app/widgets/standerd.dart';
import 'package:gap/gap.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class SummaryScreen extends StatefulWidget {
  final String summary;
  final String keywords;
  final String model; // النموذج المختار: Light أو Large

  const SummaryScreen({
    super.key,
    required this.summary,
    required this.keywords,
    required this.model,
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
    currentSummary = widget.summary;
    currentKeywords = widget.keywords;
  }

  // دالة لإعادة تلخيص النص حسب النموذج المختار
  Future<void> summarizeAgain(String text) async {
    setState(() {
      isLoading = true;
    });

    try {
      final response = await http.post(
        Uri.parse("YOUR_API_URL"), // ضع هنا رابط API الخاص بالتلخيص
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "text": text,
          "model": widget.model, // إرسال النموذج المختار
        }),
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
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 12),
            child: Icon(Icons.more_vert, color: Colors.white),
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
      child: Center(
        child: Text(
          content,
          style: const TextStyle(
            fontSize: 16,
            color: Colors.white,
            height: 1.6,
          ),
          textAlign: textAlign,
        ),
      ),
    );
  }
}
