import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:nabra/core/error/failures.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/utils/pcm_wav.dart';
import 'package:nabra/core/widgets/app_snackbar.dart';
import 'package:nabra/features/asr/domain/services/live_asr_service.dart';
import 'package:nabra/features/asr/presentation/providers/live_transcript_provider.dart';
import 'package:nabra/features/auth/presentation/providers/auth_provider.dart';

/// شريط تسجيل سفلي مع تفريغ مباشر بدون فقدان صوت:
/// الميكروفون يبقى مفتوحاً (PCM stream)، والمقاطع تُقطَّع من الذاكرة فقط.
class VoiceRecorderBar extends ConsumerStatefulWidget {
  final ValueChanged<File>? onRecordedFile;

  const VoiceRecorderBar({super.key, this.onRecordedFile});

  @override
  ConsumerState<VoiceRecorderBar> createState() => _VoiceRecorderBarState();
}

class _VoiceRecorderBarState extends ConsumerState<VoiceRecorderBar>
    with SingleTickerProviderStateMixin {
  static const _chunkSeconds = 4;
  static const _sampleRate = 16000;
  static const _numChannels = 1;

  final AudioRecorder _recorder = AudioRecorder();
  final LiveAsrService _liveAsr = const LiveAsrService();

  bool _isRecording = false;
  int _seconds = 0;
  Timer? _tickTimer;
  Timer? _chunkTimer;
  StreamSubscription<Uint8List>? _streamSub;

  /// بايتات المقطع الحالي (للتفريغ المباشر).
  final BytesBuilder _pendingPcm = BytesBuilder();

  /// بايتات الجلسة كاملة (ملف التسجيل النهائي).
  final BytesBuilder _sessionPcm = BytesBuilder();

  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
  }

  @override
  void dispose() {
    _tickTimer?.cancel();
    _chunkTimer?.cancel();
    unawaited(_streamSub?.cancel());
    _pulse.dispose();
    _recorder.dispose();
    super.dispose();
  }

  String get _timeLabel {
    final m = (_seconds ~/ 60).toString().padLeft(2, '0');
    final s = (_seconds % 60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  RecordConfig get _streamConfig => const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: _sampleRate,
        numChannels: _numChannels,
      );

  Future<void> _start() async {
    try {
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

      _pendingPcm.clear();
      _sessionPcm.clear();

      ref.read(liveTranscriptProvider.notifier).startSession();

      final stream = await _recorder.startStream(_streamConfig);
      await _streamSub?.cancel();
      _streamSub = stream.listen(
        (data) {
          if (data.isEmpty) return;
          _pendingPcm.add(data);
          _sessionPcm.add(data);
        },
        onError: (_) {
          // نستمر؛ الأخطاء اللحظية لا توقف الجلسة
        },
      );

      setState(() {
        _isRecording = true;
        _seconds = 0;
      });
      _pulse.repeat(reverse: true);

      _tickTimer?.cancel();
      _tickTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (!mounted) return;
        setState(() => _seconds += 1);
      });

      _chunkTimer?.cancel();
      _chunkTimer = Timer.periodic(
        const Duration(seconds: _chunkSeconds),
        (_) => _flushPendingChunk(),
      );
    } catch (e) {
      if (!mounted) return;
      AppSnackbar.show(context, message: 'خطأ في التسجيل: $e', isError: true);
    }
  }

  /// يأخذ بايتات المقطع الحالية بدون إيقاف الميكروفون.
  void _flushPendingChunk() {
    if (!_isRecording) return;
    final pcm = _pendingPcm.takeBytes();
    if (pcm.isEmpty) return;
    unawaited(_transcribePcm(pcm));
  }

  Future<File> _writeWavTemp(Uint8List pcm, {String prefix = 'live'}) async {
    final tempDir = await getTemporaryDirectory();
    final path =
        '${tempDir.path}/${prefix}_${DateTime.now().millisecondsSinceEpoch}.wav';
    final wav = pcm16ToWav(
      pcm,
      sampleRate: _sampleRate,
      numChannels: _numChannels,
    );
    final file = File(path);
    await file.writeAsBytes(wav, flush: true);
    return file;
  }

  Future<void> _transcribePcm(Uint8List pcm) async {
    File? file;
    final live = ref.read(liveTranscriptProvider.notifier);
    final auth = ref.read(authProvider);
    live.markTranscribing();

    try {
      file = await _writeWavTemp(pcm);
      if (auth.user?.accessToken == null ||
          auth.user!.accessToken!.trim().isEmpty) {
        throw const Failure('يجب تسجيل الدخول أولاً لاستخدام التفريغ المباشر');
      }
      final text = await _liveAsr.transcribeChunk(
        file: file,
        apiBaseUrl: auth.apiBaseUrl,
        authorization: auth.user?.accessToken,
      );
      if (text.isNotEmpty) {
        live.appendText(text);
      } else if (ref.read(liveTranscriptProvider).isRecording) {
        live.appendText('');
      }
    } catch (e) {
      final msg = e is Failure
          ? e.message
          : 'التفريغ المباشر غير جاهز من الخادم';
      final firstTime = live.markOffline(msg);
      if (firstTime && mounted) {
        AppSnackbar.show(
          context,
          message: msg,
          isError: true,
          duration: const Duration(seconds: 6),
        );
      }
    } finally {
      try {
        if (file != null && await file.exists()) await file.delete();
      } catch (_) {}
    }
  }

  Future<void> _stop() async {
    try {
      _chunkTimer?.cancel();
      _tickTimer?.cancel();

      await _recorder.stop();
      await _streamSub?.cancel();
      _streamSub = null;

      _pulse
        ..stop()
        ..reset();
      setState(() => _isRecording = false);

      // آخر بايتات لم تُرسل بعد — بدون فقدان
      final remaining = _pendingPcm.takeBytes();
      if (remaining.isNotEmpty) {
        await _transcribePcm(remaining);
      }

      // ملف الجلسة الكاملة للمستخدم (إن وُجدت بايتات)
      final session = _sessionPcm.takeBytes();
      if (session.isNotEmpty) {
        final fullFile = await _writeWavTemp(session, prefix: 'session');
        widget.onRecordedFile?.call(fullFile);
      }

      final offline = ref.read(liveTranscriptProvider).status ==
          LiveTranscriptStatus.offline;
      ref.read(liveTranscriptProvider.notifier).stopSession();
      if (!mounted) return;
      // لا نستبدل رسالة الفشل برسالة نجاح
      if (!offline) {
        AppSnackbar.show(context, message: 'تم إنهاء التسجيل');
      }
    } catch (e) {
      ref.read(liveTranscriptProvider.notifier).stopSession();
      if (!mounted) return;
      AppSnackbar.show(context, message: 'خطأ في الإيقاف: $e', isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.paddingOf(context).bottom;
    final live = ref.watch(liveTranscriptProvider);

    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(16, 10, 16, 10 + bottomInset),
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.28),
        border: Border(
          top: BorderSide(
            color: AppTheme.cardBorder.withValues(alpha: 0.65),
          ),
        ),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primary.withValues(alpha: 0.025),
            blurRadius: 10,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: _isRecording
          ? _buildRecordingRow(live.status == LiveTranscriptStatus.transcribing)
          : _buildIdleRow(),
    );
  }

  Widget _buildIdleRow() {
    return Row(
      textDirection: TextDirection.ltr,
      children: [
        _MicButton(onTap: _start, recording: false),
        const SizedBox(width: 12),
        Expanded(
          child: Container(
            height: 48,
            alignment: Alignment.centerRight,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: AppTheme.surface.withValues(alpha: 0.22),
              borderRadius: BorderRadius.circular(28),
              border: Border.all(
                color: AppTheme.cardBorder.withValues(alpha: 0.8),
              ),
            ),
            child: Text(
              'اضغط للتسجيل مع التفريغ المباشر',
              textAlign: TextAlign.right,
              style: AppTheme.text(
                color: AppTheme.textMuted,
                fontSize: 13.5,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildRecordingRow(bool isTranscribing) {
    return Row(
      textDirection: TextDirection.ltr,
      children: [
        _MicButton(onTap: _stop, recording: true, pulse: _pulse),
        const SizedBox(width: 12),
        Expanded(
          child: Container(
            height: 48,
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: AppTheme.burgundySoft.withValues(alpha: 0.28),
              borderRadius: BorderRadius.circular(28),
              border: Border.all(
                color: AppTheme.error.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              textDirection: TextDirection.rtl,
              children: [
                ScaleTransition(
                  scale: Tween<double>(begin: 0.85, end: 1.15).animate(
                    CurvedAnimation(parent: _pulse, curve: Curves.easeInOut),
                  ),
                  child: Container(
                    width: 10,
                    height: 10,
                    decoration: const BoxDecoration(
                      color: AppTheme.error,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    isTranscribing ? 'جاري التفريغ...' : 'تسجيل + تفريغ مباشر',
                    overflow: TextOverflow.ellipsis,
                    style: AppTheme.text(
                      color: AppTheme.error,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                ),
                Text(
                  _timeLabel,
                  style: AppTheme.text(
                    color: AppTheme.error,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(width: 4),
                TextButton(
                  onPressed: _stop,
                  style: TextButton.styleFrom(
                    foregroundColor: AppTheme.error,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                  ),
                  child: Text(
                    'إيقاف',
                    style: AppTheme.text(
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                      color: AppTheme.error,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _MicButton extends StatelessWidget {
  final VoidCallback onTap;
  final bool recording;
  final Animation<double>? pulse;

  const _MicButton({
    required this.onTap,
    required this.recording,
    this.pulse,
  });

  @override
  Widget build(BuildContext context) {
    final button = Material(
      color: recording ? AppTheme.error : AppTheme.primary,
      shape: const CircleBorder(),
      elevation: 2,
      shadowColor: (recording ? AppTheme.error : AppTheme.primary)
          .withValues(alpha: 0.35),
      child: InkWell(
        customBorder: const CircleBorder(),
        onTap: onTap,
        child: SizedBox(
          width: 56,
          height: 56,
          child: Icon(
            recording ? Icons.stop_rounded : Icons.mic_rounded,
            color: Colors.white,
            size: 26,
          ),
        ),
      ),
    );

    if (pulse == null) return button;

    return ScaleTransition(
      scale: Tween<double>(begin: 1.0, end: 1.08).animate(
        CurvedAnimation(parent: pulse!, curve: Curves.easeInOut),
      ),
      child: button,
    );
  }
}
