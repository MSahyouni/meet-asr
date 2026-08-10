import 'package:flutter/material.dart';
import 'package:nabra/services/tts_services.dart';
import 'package:nabra/widgets/staggered_fade_slide.dart';
import 'package:nabra/widgets/tts_audio_download.dart';

import 'package:nabra/widgets/tts_convert_button.dart';
import 'package:nabra/widgets/tts_input_section.dart';
import 'package:nabra/widgets/tts_voices_dropdown.dart';
import 'package:gap/gap.dart';

class Tts extends StatefulWidget {
  final String apiUrl;

  const Tts({super.key, required this.apiUrl});

  @override
  State<Tts> createState() => _TtsState();
}

class _TtsState extends State<Tts> {
  final TextEditingController _textController = TextEditingController();
  String? selectedVoice;
  String? audioUrl;

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  Future<void> _handleConvert() async {
    if (_textController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("الرجاء إدخال نص"),

          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
      return;
    }

    if (selectedVoice == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("الرجاء اختيار صوت"),

          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
      return;
    }

    try {
      final generateAudioUrl = await TtsService.convertTextToSpeech(
        text: _textController.text.trim(),
        voiceId: selectedVoice!,
        apiUrl: widget.apiUrl,
      );
      setState(() {
        audioUrl = generateAudioUrl;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("تم إنشاء الصوت بنجاح"),
          backgroundColor: const Color.fromARGB(255, 75, 151, 78),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("حدث خطأ أثناء التحويل:$e"),

          backgroundColor: const Color.fromARGB(255, 158, 75, 69),
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
          margin: EdgeInsets.all(16),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      backgroundColor: Colors.transparent,

      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: const Text(
          "تحويل النص إلى صوت",
          style: TextStyle(
            color: Colors.white,
            fontSize: 26,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),

      body: Stack(
        children: [
          Positioned.fill(
            child: Image.asset('assets/images/image_5.png', fit: BoxFit.cover),
          ),
          Container(color: Colors.black.withOpacity(0.25)),
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 140, 20, 20),
            child: SingleChildScrollView(
              child: StaggeredFadeSlide(
                children: [
                  const Gap(20),
                  // Container(
                  //   width: double.infinity,
                  //   padding: const EdgeInsets.all(16),
                  //   decoration: BoxDecoration(
                  //     gradient: LinearGradient(
                  //       colors: [
                  //         Color(0xFF0C3A34),
                  //         Color(0xFF125B4A),
                  //         Color(0xFF1A7B6A),
                  //       ],
                  //       begin: Alignment.topLeft,
                  //       end: Alignment.bottomRight,
                  //     ),
                  //     borderRadius: BorderRadius.circular(12),
                  //   ),
                  //   child: const Text(
                  //     "هنا يمكنك إدخال النص الذي ترغب في تحويله إلى صوت. قم بكتابة النص في الحقل أدناه واضغط على زر التحويل للاستماع إلى النتيجة.",
                  //     style: TextStyle(
                  //       color: Colors.white,
                  //       fontSize: 18,
                  //       height: 1.5,
                  //     ),
                  //     textAlign: TextAlign.center,
                  //   ),
                  // ),
                  TtsInputSection(controller: _textController),

                  const Gap(20),

                  // TextField(
                  //   controller: _textController,
                  //   style: TextStyle(
                  //     color: const Color.fromARGB(255, 221, 217, 217),
                  //     fontSize: 16,
                  //   ),
                  //   maxLines: 5,
                  //   decoration: InputDecoration(
                  //     hintText: "أدخل النص هنا...",
                  //     hintStyle: TextStyle(
                  //       color: const Color.fromARGB(255, 158, 156, 156),
                  //     ),
                  //     border: OutlineInputBorder(
                  //       borderRadius: BorderRadius.circular(15),
                  //     ),
                  //   ),
                  // ),
                  TtsVoiceDropdown(
                    selectedVoice: selectedVoice,
                    apiUrl: widget.apiUrl,
                    onChanged: (value) {
                      setState(() {
                        selectedVoice = value;
                      });
                    },
                  ),

                  Gap(20),

                  // Container(
                  //   width: 250,
                  //   height: 45,
                  //   decoration: BoxDecoration(
                  //     gradient: LinearGradient(
                  //       colors: [
                  //         Color(0xFF0C3A34),
                  //         Color(0xFF125B4A),
                  //         Color(0xFF1A7B6A),
                  //       ],
                  //       begin: Alignment.topLeft,
                  //       end: Alignment.bottomRight,
                  //     ),
                  //     borderRadius: BorderRadius.circular(20),
                  //   ),
                  //   child: ElevatedButton(
                  //     style: ElevatedButton.styleFrom(
                  //       backgroundColor: Colors.transparent,
                  //       elevation: 0,
                  //     )
                  //     child: Text(
                  //       'الاستماع إلى النص',
                  //       style: TextStyle(color: Colors.white, fontSize: 16),
                  //     ),
                  //   ),
                  // ),
                  TtsConvertButton(onPressed: _handleConvert),

                  Gap(20),
                  if (audioUrl != null && audioUrl!.isNotEmpty)
                    TtsDownloadButton(audioUrl: audioUrl!),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
