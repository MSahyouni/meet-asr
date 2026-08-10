import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/widgets/app_snackbar.dart';
import 'package:nabra/core/widgets/outlined_action_tile.dart';

class VoiceRecorderTile extends StatefulWidget {
  final ValueChanged<File>? onRecordedFile;

  const VoiceRecorderTile({super.key, this.onRecordedFile});

  @override
  State<VoiceRecorderTile> createState() => _VoiceRecorderTileState();
}

class _VoiceRecorderTileState extends State<VoiceRecorderTile> {
  final AudioRecorder _recorder = AudioRecorder();
  bool _isRecording = false;

  @override
  void dispose() {
    _recorder.dispose();
    super.dispose();
  }

  Future<void> _toggle() async {
    try {
      if (!_isRecording) {
        final hasPerm = await _recorder.hasPermission();
        if (!hasPerm) {
          if (!mounted) return;
          AppSnackbar.show(
            context,
            message: 'يلزم إذن الميكروفون للتسجيل',
            isError: true,
          );
          return;
        }

        final tempDir = await getTemporaryDirectory();
        final path =
            '${tempDir.path}/rec_${DateTime.now().millisecondsSinceEpoch}.m4a';
        await _recorder.start(const RecordConfig(), path: path);
        setState(() => _isRecording = true);
        if (!mounted) return;
        AppSnackbar.show(context, message: 'بدأ التسجيل...');
      } else {
        final path = await _recorder.stop();
        setState(() => _isRecording = false);
        if (path == null) return;
        final file = File(path);
        widget.onRecordedFile?.call(file);
        if (!mounted) return;
        AppSnackbar.show(context, message: 'تم حفظ التسجيل');
      }
    } catch (e) {
      if (!mounted) return;
      AppSnackbar.show(context, message: 'خطأ في التسجيل: $e', isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isRecording) {
      return Column(
        children: [
          OutlinedActionTile(
            label: 'جاري التسجيل...',
            subtitle: 'اضغط إيقاف عند الانتهاء',
            icon: Icons.mic_rounded,
            accent: AppTheme.error,
            iconBackground: AppTheme.burgundySoft,
            showChevron: false,
            highlighted: true,
            onTap: null,
          ),
          const SizedBox(height: 10),
          Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: _toggle,
              borderRadius: BorderRadius.circular(AppTheme.radiusLg),
              child: Ink(
                width: double.infinity,
                height: 52,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(AppTheme.radiusLg),
                  gradient: AppTheme.errorGradient,
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.error.withValues(alpha: 0.22),
                      blurRadius: 14,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.stop_rounded, color: Colors.white, size: 22),
                    const SizedBox(width: 8),
                    Text(
                      'إيقاف التسجيل',
                      style: AppTheme.text(
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      );
    }

    return OutlinedActionTile(
      label: 'تسجيل صوتي',
      subtitle: 'سجّل مباشرة من الميكروفون',
      icon: Icons.mic_none_rounded,
      accent: AppTheme.primary,
      iconBackground: AppTheme.primarySoft,
      onTap: _toggle,
    );
  }
}
