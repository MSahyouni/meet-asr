// import 'package:audioplayers/audioplayers.dart';
// import 'package:flutter/material.dart';
// import 'package:nabra/services/audio_download_service.dart';
// import 'package:gap/gap.dart';

// class TtsAudioPlayer extends StatefulWidget {
//   final String audioUrl;

//   const TtsAudioPlayer({super.key, required this.audioUrl});

//   @override
//   State<TtsAudioPlayer> createState() => _TtsAudioPlayerState();
// }

// class _TtsAudioPlayerState extends State<TtsAudioPlayer> {
//   final AudioPlayer _audioPlayer = AudioPlayer();
//   bool isPlaying = false;
//   bool isDownloading = false;

//   @override
//   void initState() {
//     super.initState();

//     _audioPlayer.onPlayerComplete.listen((event) {
//       if (mounted) {
//         setState(() {
//           isPlaying = false;
//         });
//       }
//     });
//   }

//   @override
//   void dispose() {
//     _audioPlayer.dispose();
//     super.dispose();
//   }

//   // Future<void> playAudio() async {
//   //   try {
//   //     await _audioPlayer.play(UrlSource(widget.audioUrl));
//   //     setState(() {
//   //       isPlaying = true;
//   //     });
//   //   } catch (e) {
//   //     ScaffoldMessenger.of(
//   //       context,
//   //     ).showSnackBar(SnackBar(content: Text("فشل تشغيل الصوت: $e")));
//   //   }
//   }

//   // Future<void> stopAudio() async {
//   //   try {
//   //     await _audioPlayer.stop();
//   //     setState(() {
//   //       isPlaying = false;
//   //     });
//   //   } catch (e) {
//   //     ScaffoldMessenger.of(
//   //       context,
//   //     ).showSnackBar(SnackBar(content: Text("فشل إيقاف الصوت: $e")));
//   //   }
//   // }

//   Future<void> downloadAudio() async {
//     try {
//       setState(() {
//         isDownloading = true;
//       });

//       final savedPath = await AudioDownloadService.downloadAudio(
//         audioUrl: widget.audioUrl,
//       );

//       ScaffoldMessenger.of(
//         context,
//       ).showSnackBar(SnackBar(content: Text("تم حفظ الملف في:\n$savedPath")));
//     } catch (e) {
//       ScaffoldMessenger.of(
//         context,
//       ).showSnackBar(SnackBar(content: Text("فشل حفظ الملف: $e")));
//     } finally {
//       if (mounted) {
//         setState(() {
//           isDownloading = false;
//         });
//       }
//     }
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Container(
//       width: double.infinity,
//       padding: const EdgeInsets.all(16),
//       decoration: BoxDecoration(
//         gradient: const LinearGradient(
//           colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
//           begin: Alignment.topLeft,
//           end: Alignment.bottomRight,
//         ),
//         borderRadius: BorderRadius.circular(16),
//       ),
//       child: Column(
//         children: [
//           const Text(
//             "تم إنشاء الملف الصوتي",
//             style: TextStyle(
//               color: Colors.white,
//               fontSize: 18,
//               fontWeight: FontWeight.bold,
//             ),
//           ),
//           const Gap(12),
//           Row(
//             mainAxisAlignment: MainAxisAlignment.center,
//             children: [
//               ElevatedButton.icon(
//                 style: ElevatedButton.styleFrom(
//                   backgroundColor: Colors.white24,
//                 ),
//                 onPressed: isPlaying ? null : playAudio,
//                 icon: const Icon(Icons.play_arrow),
//                 label: const Text("تشغيل"),
//               ),
//               const Gap(12),
//               ElevatedButton.icon(
//                 style: ElevatedButton.styleFrom(
//                   backgroundColor: Colors.white24,
//                 ),
//                 onPressed: isPlaying ? stopAudio : null,
//                 icon: const Icon(Icons.stop),
//                 label: const Text("إيقاف"),
//               ),
//             ],
//           ),
//           const Gap(12),
//           ElevatedButton.icon(
//             style: ElevatedButton.styleFrom(backgroundColor: Colors.white24),
//             onPressed: isDownloading ? null : downloadAudio,
//             icon: isDownloading
//                 ? const SizedBox(
//                     height: 18,
//                     width: 18,
//                     child: CircularProgressIndicator(strokeWidth: 2),
//                   )
//                 : const Icon(Icons.download),
//             label: Text(
//               isDownloading ? "جارٍ الحفظ..." : "حفظ في مجلد الصوتيات",
//             ),
//           ),
//           const Gap(10),
//           Text(
//             widget.audioUrl,
//             textAlign: TextAlign.center,
//             style: const TextStyle(color: Colors.white70, fontSize: 12),
//           ),
//         ],
//       ),
//     );
//   }
// }

//////////////////////////////////////////////////////////////////////////////////////////////////////////

// import 'package:flutter/material.dart';
// import 'package:nabra/services/audio_download_service.dart';
// import 'package:gap/gap.dart';

// class TtsDownloadButton extends StatefulWidget {
//   final String audioUrl;

//   const TtsDownloadButton({super.key, required this.audioUrl});

//   @override
//   State<TtsDownloadButton> createState() => _TtsDownloadButtonState();
// }

// class _TtsDownloadButtonState extends State<TtsDownloadButton> {
//   bool isDownloading = false;

//   Future<void> downloadAudio() async {
//     try {
//       setState(() {
//         isDownloading = true;
//       });

//       final savedPath = await AudioDownloadService.downloadAudio(
//         audioUrl: widget.audioUrl,
//       );

//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(
//           content: Text("تم حفظ الملف في:\n$savedPath"),
//           backgroundColor: const Color.fromARGB(255, 75, 151, 78),
//           behavior: SnackBarBehavior.floating,
//           shape: RoundedRectangleBorder(
//             borderRadius: BorderRadius.circular(10),
//           ),
//           margin: EdgeInsets.all(16),
//         ),
//       );
//     } catch (e) {
//       ScaffoldMessenger.of(context).showSnackBar(
//         SnackBar(
//           content: Text("فشل حفظ الملف: $e"),
//           backgroundColor: const Color.fromARGB(255, 75, 151, 78),
//           behavior: SnackBarBehavior.floating,
//           shape: RoundedRectangleBorder(
//             borderRadius: BorderRadius.circular(10),
//           ),
//           margin: EdgeInsets.all(16),
//         ),
//       );
//     } finally {
//       if (mounted) {
//         setState(() {
//           isDownloading = false;
//         });
//       }
//     }
//   }

//   @override
//   Widget build(BuildContext context) {
//     return Container(
//       width: double.infinity,
//       padding: const EdgeInsets.all(16),
//       decoration: BoxDecoration(
//         gradient: const LinearGradient(
//           colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
//           begin: Alignment.topLeft,
//           end: Alignment.bottomRight,
//         ),
//         borderRadius: BorderRadius.circular(16),
//       ),
//       child: Column(
//         children: [
//           const Text(
//             "تم إنشاء الملف الصوتي",
//             style: TextStyle(
//               color: Colors.white,
//               fontSize: 18,
//               fontWeight: FontWeight.bold,
//             ),
//           ),

//           const Gap(20),

//           ElevatedButton.icon(
//             style: ElevatedButton.styleFrom(backgroundColor: Colors.white24),
//             onPressed: isDownloading ? null : downloadAudio,
//             icon: isDownloading
//                 ? const SizedBox(
//                     height: 18,
//                     width: 18,
//                     child: CircularProgressIndicator(strokeWidth: 2),
//                   )
//                 : const Icon(Icons.download),
//             label: Text(isDownloading ? "جارٍ الحفظ..." : "تحميل الملف الصوتي"),
//           ),
//         ],
//       ),
//     );
//   }
// }

//////////////////////////////////////////////////////////////////////////

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:nabra/services/audio_download_service.dart';
import 'package:nabra/widgets/tts_audio_slide.dart';
import 'package:nabra/widgets/tts_play_button.dart';
import 'package:nabra/widgets/tts_stop_button.dart';
import 'package:gap/gap.dart';

class TtsDownloadButton extends StatefulWidget {
  final String audioUrl;

  const TtsDownloadButton({super.key, required this.audioUrl});

  @override
  State<TtsDownloadButton> createState() => _TtsDownloadButtonState();
}

class _TtsDownloadButtonState extends State<TtsDownloadButton> {
  bool isDownloading = false;
  bool isPlaying = false;
  Duration totalDuration = Duration.zero;
  Duration currentPosition = Duration.zero;

  final AudioPlayer _audioPlayer = AudioPlayer();

  String? savedPath;

  @override
  @override
  void initState() {
    super.initState();

    _audioPlayer.onPlayerComplete.listen((event) {
      if (mounted) {
        setState(() {
          isPlaying = false;
          currentPosition = Duration.zero;
        });
      }
    });

    _audioPlayer.onDurationChanged.listen((duration) {
      setState(() {
        totalDuration = duration;
      });
    });

    _audioPlayer.onPositionChanged.listen((position) {
      setState(() {
        currentPosition = position;
      });
    });
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  // 🔽 تحميل الصوت
  Future<void> downloadAudio() async {
    try {
      setState(() {
        isDownloading = true;
      });

      final path = await AudioDownloadService.downloadAudio(
        audioUrl: widget.audioUrl,
      );

      setState(() {
        savedPath = path;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("تم حفظ الملف في:\n$path"),
          backgroundColor: const Color.fromARGB(255, 75, 151, 78),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text("فشل حفظ الملف: $e")));
    } finally {
      if (mounted) {
        setState(() {
          isDownloading = false;
        });
      }
    }
  }

  // ▶️ تشغيل
  Future<void> playAudio() async {
    if (savedPath == null) return;

    await _audioPlayer.play(DeviceFileSource(savedPath!));

    setState(() {
      isPlaying = true;
    });
  }

  // ⏹️ إيقاف
  Future<void> stopAudio() async {
    await _audioPlayer.stop();

    setState(() {
      isPlaying = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
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

          const Gap(20),

          // زر التحميل
          ElevatedButton.icon(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.white24),
            onPressed: isDownloading ? null : downloadAudio,
            icon: isDownloading
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.download),
            label: Text(isDownloading ? "جارٍ الحفظ..." : "تحميل الملف الصوتي"),
          ),

          const Gap(20),

          // أزرار التشغيل والإيقاف تظهر بعد التحميل
          if (savedPath != null) ...[
            //  Slider
            TtsAudioSlider(
              currentPosition: currentPosition,
              totalDuration: totalDuration,
              onSeek: (duration) async {
                await _audioPlayer.seek(duration);
              },
            ),

            const Gap(10),

            // ▶️ ⏹️ الأزرار
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TtsPlayButton(onPressed: playAudio, isPlaying: isPlaying),
                const Gap(12),
                TtsStopButton(onPressed: stopAudio, isPlaying: isPlaying),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
