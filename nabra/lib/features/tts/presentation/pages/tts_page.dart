import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/core/di/injector.dart';
import 'package:flutter_app/core/theme/app_colors.dart';
import 'package:flutter_app/core/theme/app_theme.dart';
import 'package:flutter_app/core/widgets/app_snackbar.dart';
import 'package:flutter_app/core/widgets/app_text_field.dart';
import 'package:flutter_app/core/widgets/nabra_scaffold.dart';
import 'package:flutter_app/core/widgets/primary_button.dart';
import 'package:flutter_app/core/widgets/staggered_entrance.dart';
import 'package:flutter_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:flutter_app/services/audio_download_service.dart';

class TtsPage extends ConsumerStatefulWidget {
  final String apiUrl;

  const TtsPage({super.key, required this.apiUrl});

  @override
  ConsumerState<TtsPage> createState() => _TtsPageState();
}

class _TtsPageState extends ConsumerState<TtsPage> {
  static const _defaultVoice = 'habibi_unified';
  static const _defaultEngine = 'habibi';

  final _textController = TextEditingController();
  final _player = AudioPlayer();

  String? _localAudioPath;
  bool _converting = false;
  bool _playing = false;

  @override
  void dispose() {
    _textController.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _convert() async {
    final text = _textController.text.trim();
    if (text.isEmpty) {
      AppSnackbar.show(context, message: 'الرجاء إدخال نص', isError: true);
      return;
    }

    setState(() => _converting = true);
    try {
      final auth = ref.read(authProvider);
      final token = auth.user?.accessToken;
      final url = await AppInjector.ttsRepository.convert(
        apiBaseUrl: widget.apiUrl,
        text: text,
        voiceId: _defaultVoice,
        engine: _defaultEngine,
        authorization: token,
        userEmail: auth.user?.email,
      );

      final path = await AudioDownloadService.downloadAudio(
        audioUrl: url,
        authorization: token,
      );
      setState(() => _localAudioPath = path);
      if (!mounted) return;
      AppSnackbar.show(context, message: 'تم إنشاء الصوت بنجاح');
    } catch (e) {
      if (!mounted) return;
      AppSnackbar.show(context, message: 'حدث خطأ أثناء التحويل: $e', isError: true);
    } finally {
      if (mounted) setState(() => _converting = false);
    }
  }

  Future<void> _togglePlay() async {
    if (_localAudioPath == null) return;
    if (_playing) {
      await _player.stop();
      setState(() => _playing = false);
      return;
    }
    await _player.play(DeviceFileSource(_localAudioPath!));
    setState(() => _playing = true);
    _player.onPlayerComplete.listen((_) {
      if (mounted) setState(() => _playing = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return NabraScaffold(
      title: 'تحويل النص إلى صوت',
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
        onPressed: () => context.pop(),
      ),
      body: ListView(
        children: [
          EntranceItem(
            index: 0,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.border),
              ),
              child: Text(
                'هنا يمكنك إدخال النص الذي ترغب في تحويله إلى صوت باستخدام Habibi. اكتب النص ثم اضغط زر الاستماع.',
                textAlign: TextAlign.right,
                style: AppTheme.text(
                  color: AppColors.textSecondary,
                  height: 1.5,
                  fontSize: 13,
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          EntranceItem(
            index: 1,
            child: AppTextField(
              controller: _textController,
              hint: '...أدخل النص هنا',
              maxLines: 6,
            ),
          ),
          const SizedBox(height: 18),
          EntranceItem(
            index: 2,
            child: PrimaryButton(
              label: 'الاستماع إلى النص',
              loading: _converting,
              icon: Icons.volume_up_rounded,
              onPressed: _convert,
            ),
          ),
          if (_localAudioPath != null) ...[
            const SizedBox(height: 16),
            EntranceItem(
              index: 3,
              child: PrimaryButton(
                label: _playing ? 'إيقاف' : 'تشغيل',
                icon: _playing ? Icons.stop_rounded : Icons.play_arrow_rounded,
                backgroundColor: AppTheme.primaryLight,
                onPressed: _togglePlay,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
