import 'package:flutter/material.dart';

class TtsInputSection extends StatelessWidget {
  final TextEditingController controller;

  const TtsInputSection({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Text(
            "هنا يمكنك إدخال النص الذي ترغب في تحويله إلى صوت. قم بكتابة النص في الحقل أدناه واضغط على زر التحويل للاستماع إلى النتيجة.",
            style: TextStyle(color: Colors.white, fontSize: 18, height: 1.5),
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: 20),
        TextField(
          controller: controller,
          style: const TextStyle(
            color: Color.fromARGB(255, 221, 217, 217),
            fontSize: 16,
          ),
          maxLines: 5,
          decoration: InputDecoration(
            hintText: "أدخل النص هنا...",
            hintStyle: const TextStyle(
              color: Color.fromARGB(255, 158, 156, 156),
            ),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(15)),
          ),
        ),
      ],
    );
  }
}
