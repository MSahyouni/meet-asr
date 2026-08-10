import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/widgets/app_snackbar.dart';
import 'package:nabra/features/asr/presentation/providers/live_transcript_provider.dart';

/// بطاقة النص المباشر — نفس أسلوب بطاقات الرئيسية.
class LiveTranscriptCard extends ConsumerWidget {
  const LiveTranscriptCard({super.key});

  String _statusLabel(LiveTranscriptState state) {
    switch (state.status) {
      case LiveTranscriptStatus.recording:
        return 'تفريغ مباشر...';
      case LiveTranscriptStatus.transcribing:
        return 'جاري تحويل المقطع...';
      case LiveTranscriptStatus.ready:
        return 'النص المستخرج';
      case LiveTranscriptStatus.offline:
        return 'التفريغ المباشر غير جاهز من الخادم';
      case LiveTranscriptStatus.idle:
        return 'سيظهر النص هنا أثناء التسجيل';
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(liveTranscriptProvider);

    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 140),
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(AppTheme.radiusLg),
        gradient: LinearGradient(
          begin: Alignment.topRight,
          end: Alignment.bottomLeft,
          colors: [
            AppTheme.surface,
            AppTheme.goldSoft.withValues(alpha: 0.55),
          ],
        ),
        border: Border.all(
          color: AppTheme.cardBorder.withValues(alpha: 0.85),
        ),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primary.withValues(alpha: 0.045),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            textDirection: TextDirection.rtl,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppTheme.primarySoft,
                  borderRadius: BorderRadius.circular(AppTheme.radiusSm),
                  border: Border.all(
                    color: AppTheme.primary.withValues(alpha: 0.12),
                  ),
                ),
                child: const Icon(
                  Icons.subtitles_rounded,
                  color: AppTheme.primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'النص المباشر',
                      textAlign: TextAlign.right,
                      style: AppTheme.text(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _statusLabel(state),
                      textAlign: TextAlign.right,
                      style: AppTheme.text(
                        fontSize: 12,
                        color: state.status == LiveTranscriptStatus.offline
                            ? AppTheme.error
                            : AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              if (state.hasText)
                IconButton(
                  tooltip: 'نسخ',
                  onPressed: () async {
                    await Clipboard.setData(ClipboardData(text: state.text));
                    if (!context.mounted) return;
                    AppSnackbar.show(context, message: 'تم نسخ النص');
                  },
                  icon: const Icon(
                    Icons.copy_rounded,
                    size: 20,
                    color: AppTheme.iconAccent,
                  ),
                ),
              if (state.hasText)
                IconButton(
                  tooltip: 'مسح',
                  onPressed: () =>
                      ref.read(liveTranscriptProvider.notifier).clear(),
                  icon: const Icon(
                    Icons.close_rounded,
                    size: 20,
                    color: AppTheme.textMuted,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            constraints: const BoxConstraints(minHeight: 72),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface.withValues(alpha: 0.75),
              borderRadius: BorderRadius.circular(AppTheme.radiusField),
              border: Border.all(
                color: AppTheme.cardBorder.withValues(alpha: 0.7),
              ),
            ),
            child: state.hasText
                ? Text(
                    state.text,
                    textAlign: TextAlign.right,
                    textDirection: TextDirection.rtl,
                    style: AppTheme.text(
                      fontSize: 14.5,
                      height: 1.65,
                      color: AppTheme.textPrimary,
                      fontWeight: FontWeight.w500,
                    ),
                  )
                : Text(
                    state.status == LiveTranscriptStatus.offline
                        ? (state.lastError ??
                            'التفريغ المباشر غير جاهز من الخادم')
                        : state.isRecording
                            ? 'ابدأ بالحديث... سيظهر النص تلقائياً'
                            : 'اضغط الميكروفون في الأسفل لبدء التفريغ المباشر',
                    textAlign: TextAlign.right,
                    style: AppTheme.text(
                      fontSize: 13.5,
                      color: state.status == LiveTranscriptStatus.offline
                          ? AppTheme.error
                          : AppTheme.textMuted,
                      height: 1.5,
                      fontWeight: state.status == LiveTranscriptStatus.offline
                          ? FontWeight.w600
                          : FontWeight.w500,
                    ),
                  ),
          ),
          if (state.status == LiveTranscriptStatus.transcribing) ...[
            const SizedBox(height: 10),
            const LinearProgressIndicator(
              minHeight: 3,
              color: AppTheme.primary,
              backgroundColor: AppTheme.primarySoft,
            ),
          ],
        ],
      ),
    );
  }
}
