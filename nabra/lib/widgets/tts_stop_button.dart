import 'package:flutter/material.dart';

class TtsStopButton extends StatelessWidget {
  final VoidCallback onPressed;
  final bool isPlaying;

  const TtsStopButton({
    super.key,
    required this.onPressed,
    required this.isPlaying,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      style: ElevatedButton.styleFrom(backgroundColor: Colors.white24),
      onPressed: isPlaying ? onPressed : null,
      icon: const Icon(Icons.stop),
      label: const Text("إيقاف"),
    );
  }
}
