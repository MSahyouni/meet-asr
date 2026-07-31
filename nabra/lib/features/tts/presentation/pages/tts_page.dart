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
import 'package:flutter_app/features/tts/data/repositories/tts_repository_impl.dart';
import 'package:flutter_app/services/audio_download_service.dart';

class TtsPage extends ConsumerStatefulWidget {
  final String apiUrl;

  const TtsPage({super.key, required this.apiUrl});

  @override
  ConsumerState<TtsPage> createState() => _TtsPageState();
}

class _TtsPageState extends ConsumerState<TtsPage> {
  final _textController = TextEditingController();
  final _player = AudioPlayer();

  List<VoiceEntity> _voices = [];
  String? _selectedVoice;
  String? _localAudioPath;
  bool _loadingVoices = true;
  bool _converting = false;
  bool _playing = false;

  @override
  void initState() {
    super.initState();
    _loadVoices();
  }

  @override
  void dispose() {
    _textController.dispose();
    _player.dispose();
    super.dispose();
  }

  Future<void> _loadVoices() async {
    setState(() => _loadingVoices = true);
    try {
      final token = ref.read(authProvider).user?.accessToken;
      final voices = await AppInjector.ttsRepository.fetchVoices(
        apiBaseUrl: widget.apiUrl,
        authorization: token,
      );
      setState(() {
        _voices = voices;
        _selectedVoice = voices.isNotEmpty ? voices.first.id : null;
      });
    } catch (e) {
      if (!mounted) return;
      AppSnackbar.show(context, message: 'تعذر تحميل الأصوات: $e', isError: true);
    } finally {
      if (mounted) setState(() => _loadingVoices = false);
    }
  }

  Future<void> _convert() async {
    final text = _textController.text.trim();
    if (text.isEmpty) {
      AppSnackbar.show(context, message: 'الرجاء إدخال نص', isError: true);
      return;
    }
    if (_selectedVoice == null) {
      AppSnackbar.show(context, message: 'الرجاء اختيار صوت', isError: true);
      return;
    }

    setState(() => _converting = true);
    try {
      final auth = ref.read(authProvider);
      final url = await AppInjector.ttsRepository.convert(
        apiBaseUrl: widget.apiUrl,
        text: text,
        voiceId: _selectedVoice!,
        authorization: auth.user?.accessToken,
        userEmail: auth.user?.email,
      );

      final path = await AudioDownloadService.downloadAudio(audioUrl: url);
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
                'هنا يمكنك إدخال النص الذي ترغب في تحويله إلى صوت. اكتب النص ثم اضغط زر الاستماع.',
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
          const SizedBox(height: 14),
          EntranceItem(
            index: 2,
            child: _loadingVoices
                ? const Center(
                    child: CircularProgressIndicator(color: AppColors.primary),
                  )
                : Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: DropdownButtonHideUnderline(
                      child: DropdownButton<String>(
                        value: _selectedVoice,
                        isExpanded: true,
                        hint: Text('اختر الصوت', style: AppTheme.text()),
                        items: _voices
                            .map(
                              (v) => DropdownMenuItem(
                                value: v.id,
                                child: Text(
                                  v.name,
                                  textAlign: TextAlign.right,
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: (v) => setState(() => _selectedVoice = v),
                      ),
                    ),
                  ),
          ),
          const SizedBox(height: 18),
          EntranceItem(
            index: 3,
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
              index: 4,
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
