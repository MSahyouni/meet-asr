import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:gap/gap.dart';

class TtsAudioPlayer extends StatefulWidget {
  final String audioUrl;

  const TtsAudioPlayer({super.key, required this.audioUrl});

  @override
  State<TtsAudioPlayer> createState() => _TtsAudioPlayerState();
}

class _TtsAudioPlayerState extends State<TtsAudioPlayer> {
  final AudioPlayer _audioPlayer = AudioPlayer();
  bool isPlaying = false;

  @override
  void initState() {
    super.initState();

    _audioPlayer.onPlayerComplete.listen((event) {
      if (mounted) {
        setState(() {
          isPlaying = false;
        });
      }
    });
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> playAudio() async {
    try {
      await _audioPlayer.play(UrlSource(widget.audioUrl));
      setState(() {
        isPlaying = true;
      });
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text("فشل تشغيل الصوت: $e")));
    }
  }

  Future<void> stopAudio() async {
    try {
      await _audioPlayer.stop();
      setState(() {
        isPlaying = false;
      });
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text("فشل إيقاف الصوت: $e")));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          const Text(
            "تم إنشاء الملف الصوتي",
            style: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const Gap(12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white24,
                ),
                onPressed: isPlaying ? null : playAudio,
                icon: const Icon(Icons.play_arrow),
                label: const Text("تشغيل"),
              ),
              const Gap(12),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white24,
                ),
                onPressed: isPlaying ? stopAudio : null,
                icon: const Icon(Icons.stop),
                label: const Text("إيقاف"),
              ),
            ],
          ),
          const Gap(10),
          Text(
            widget.audioUrl,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white70, fontSize: 12),
          ),
        ],
      ),
    );
  }
}
