// import 'package:flutter/material.dart';
// import 'package:http/http.dart' as http;
// import 'dart:convert';

// class SummaryScreen extends StatefulWidget {
//   final String text;

//   const SummaryScreen({super.key, required this.text});

//   @override
//   State<SummaryScreen> createState() => _SummaryScreenState();
// }

// class _SummaryScreenState extends State<SummaryScreen> {
//   bool isLoading = false;
//   String? summary;

//   Future<void> summarizeText() async {
//     setState(() {
//       isLoading = true;
//       summary = null;
//     });

//     try {
//       final response = await http.post(
//         Uri.parse("https://your-backend.com/summarize"), // رابط الباك-إند
//         headers: {"Content-Type": "application/json"},
//         body: json.encode({"text": widget.text}),
//       );

//       if (response.statusCode == 200) {
//         final decoded = json.decode(response.body);
//         setState(() {
//           summary =
//               decoded["summary"]; // الباك-إند لازم يرجع {"summary": "..."}
//         });
//       } else {
//         throw Exception("فشل التلخيص: ${response.statusCode}");
//       }
//     } catch (e) {
//       setState(() {
//         summary = "حدث خطأ أثناء التلخيص: $e";
//       });
//     } finally {
//       setState(() {
//         isLoading = false;
//       });
//     }
//   }

//   @override
//   void initState() {
//     super.initState();
//     summarizeText(); // يشتغل تلقائي عند الدخول للصفحة
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       appBar: AppBar(
//         title: const Text("ملخص النص"),
//         backgroundColor: Colors.blueAccent,
//       ),
//       body: Padding(
//         padding: const EdgeInsets.all(16.0),
//         child:
//             isLoading
//                 ? const Center(child: CircularProgressIndicator())
//                 : summary == null
//                 ? const Center(child: Text("لم يتم توليد ملخص بعد"))
//                 : Card(
//                   elevation: 4,
//                   shape: RoundedRectangleBorder(
//                     borderRadius: BorderRadius.circular(12),
//                   ),
//                   child: Padding(
//                     padding: const EdgeInsets.all(16.0),
//                     child: SingleChildScrollView(
//                       child: Text(
//                         summary!,
//                         style: const TextStyle(fontSize: 18, height: 1.5),
//                         textAlign: TextAlign.justify,
//                       ),
//                     ),
//                   ),
//                 ),
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

  const SummaryScreen({
    super.key,
    required this.summary,
    required this.keywords,
  });

  @override
  State<SummaryScreen> createState() => _SummaryScreenState();
}

class _SummaryScreenState extends State<SummaryScreen> {
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
                  Gap(110),
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
                    widget.summary,
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
                    widget.keywords,
                    textAlign: TextAlign.center,
                  ),
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
