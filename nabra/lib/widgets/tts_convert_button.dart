import 'package:flutter/material.dart';

class TtsConvertButton extends StatelessWidget {
  final VoidCallback onPressed;

  const TtsConvertButton({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 250,
      height: 45,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
      ),
      child: ElevatedButton(
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent,
          elevation: 0,
          fixedSize: const Size(200, 50),
        ),
        onPressed: onPressed,
        child: const Text(
          'الاستماع إلى النص',
          style: TextStyle(color: Colors.white, fontSize: 16),
        ),
      ),
    );
  }
}
