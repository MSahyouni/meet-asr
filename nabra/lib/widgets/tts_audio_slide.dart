import 'package:flutter/material.dart';

class TtsAudioSlider extends StatelessWidget {
  final Duration currentPosition;
  final Duration totalDuration;
  final Function(Duration) onSeek;

  const TtsAudioSlider({
    super.key,
    required this.currentPosition,
    required this.totalDuration,
    required this.onSeek,
  });

  String formatDuration(Duration d) {
    final minutes = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return "$minutes:$seconds";
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // 🎵 Slider
        Slider(
          value: currentPosition.inSeconds.toDouble(),
          min: 0,
          max: totalDuration.inSeconds > 0
              ? totalDuration.inSeconds.toDouble()
              : 1,
          onChanged: (value) {
            onSeek(Duration(seconds: value.toInt()));
          },
        ),

        // ⏱ الوقت
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              formatDuration(currentPosition),
              style: const TextStyle(color: Colors.white),
            ),
            Text(
              formatDuration(totalDuration),
              style: const TextStyle(color: Colors.white),
            ),
          ],
        ),
      ],
    );
  }
}
