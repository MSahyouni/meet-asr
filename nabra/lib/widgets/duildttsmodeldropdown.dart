import 'package:flutter/material.dart';
import 'package:flutter_app/services/tts_services.dart';
import '../models/voice_model.dart';

class TtsModelDropdown extends StatefulWidget {
  final String? selectedModel;
  final ValueChanged<String> onChanged;
  final String apiUrl;

  const TtsModelDropdown({
    super.key,
    required this.selectedModel,
    required this.onChanged,
    required this.apiUrl,
  });

  @override
  State<TtsModelDropdown> createState() => _TtsModelDropdownState();
}

class _TtsModelDropdownState extends State<TtsModelDropdown> {
  List<VoiceModel> voices = [];
  String? selectedVoice;
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    loadVoices();
  }

  Future<void> loadVoices() async {
    try {
      final result = await TtsService.fetchVoices(apiUrl: widget.apiUrl);

      setState(() {
        voices = result;
        selectedVoice =
            widget.selectedModel ??
            (voices.isNotEmpty ? voices.first.id : null);
        isLoading = false;
      });
    } catch (e) {
      setState(() {
        isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (voices.isEmpty) {
      return const Text("لا يوجد أصوات متاحة");
    }

    return Column(
      children: [
        const Text(
          "اختر نوع الصوت المراد استخدامه",
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 10),
        DropdownButton<String>(
          value: selectedVoice,
          isExpanded: true,
          dropdownColor: const Color(0xFF125B4A),
          style: const TextStyle(color: Colors.white),
          items: voices.map((voice) {
            return DropdownMenuItem<String>(
              value: voice.id,
              child: Text(voice.name),
            );
          }).toList(),
          onChanged: (value) {
            if (value != null) {
              setState(() {
                selectedVoice = value;
              });
              widget.onChanged(value);
            }
          },
        ),
      ],
    );
  }
}
