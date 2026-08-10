import 'package:flutter/material.dart';
import 'package:nabra/widgets/duildttsmodeldropdown.dart';

class TtsVoiceDropdown extends StatelessWidget {
  final String? selectedVoice;
  final String apiUrl;
  final ValueChanged<String?> onChanged;

  const TtsVoiceDropdown({
    super.key,
    required this.selectedVoice,
    required this.apiUrl,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return TtsModelDropdown(
      selectedModel: selectedVoice,
      apiUrl: apiUrl,
      onChanged: onChanged,
    );
  }
}
