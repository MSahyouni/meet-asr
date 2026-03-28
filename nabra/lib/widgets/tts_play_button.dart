import 'package:flutter/material.dart';

class TtsPlayButton extends StatelessWidget {
  final VoidCallback onPressed;
  final bool isPlaying;

  const TtsPlayButton({
    super.key,
    required this.onPressed,
    required this.isPlaying,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      style: ElevatedButton.styleFrom(backgroundColor: Colors.white24),
      onPressed: isPlaying ? null : onPressed,
      icon: const Icon(Icons.play_arrow),
      label: const Text("تشغيل"),
    );
  }
}
