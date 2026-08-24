import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:nabra/core/theme/app_colors.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/widgets/app_snackbar.dart';
import 'package:nabra/core/widgets/app_text_field.dart';
import 'package:nabra/core/widgets/nabra_scaffold.dart';
import 'package:nabra/core/widgets/primary_button.dart';
import 'package:nabra/core/widgets/staggered_entrance.dart';
import 'package:nabra/features/home/presentation/widgets/app_drawer.dart';
import 'package:nabra/features/tts/presentation/providers/tts_provider.dart';


class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

class _HomePageState extends ConsumerState<HomePage> {
  final _scaffoldKey = GlobalKey<ScaffoldState>();
  final _textController = TextEditingController();

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  Future<void> _convert() async {
    final text = _textController.text.trim();

    if (text.isEmpty) {
      AppSnackbar.show(
        context,
        message: 'الرجاء إدخال نص أولاً',
        isError: true,
      );
      return;
    }

    try {
      await ref.read(ttsProvider.notifier).convert(text);

      if (!mounted) return;

      AppSnackbar.show(
        context,
        message: 'تم إنشاء الصوت بنجاح',
      );
    } catch (_) {
      if (!mounted) return;

      AppSnackbar.show(
        context,
        message: 'حدث خطأ أثناء تحويل النص إلى صوت',
        isError: true,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final ttsState = ref.watch(ttsProvider);

    return NabraScaffold(
      scaffoldKey: _scaffoldKey,
      drawer: const AppDrawer(),
      title: 'نبرة',
      contentPadding: const EdgeInsets.fromLTRB(
        20,
        20,
        20,
        20,
      ),
      leading: IconButton(
        icon: const Icon(
          Icons.menu_rounded,
          color: Colors.white,
        ),
        onPressed: () {
          _scaffoldKey.currentState?.openDrawer();
        },
      ),
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          // البطاقة الرئيسية
          EntranceItem(
            index: 0,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  begin: Alignment.topRight,
                  end: Alignment.bottomLeft,
                  colors: [
                    AppTheme.primary,
                    AppTheme.primaryLight,
                  ],
                ),
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primary.withValues(alpha: 0.16),
                    blurRadius: 22,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    width: 60,
                    height: 60,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: const Icon(
                      Icons.record_voice_over_rounded,
                      color: Colors.white,
                      size: 32,
                    ),
                  ),
                  const SizedBox(width: 15),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'تحويل النص إلى صوت',
                          style: AppTheme.text(
                            color: Colors.white,
                            fontSize: 19,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'اكتب النص الذي تريده واستمع إليه بصوت عربي طبيعي وواضح.',
                          style: AppTheme.text(
                            color: Colors.white.withValues(alpha: 0.88),
                            fontSize: 12.5,
                            fontWeight: FontWeight.w400,
                            height: 1.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 24),

          // عنوان قسم النص
          EntranceItem(
            index: 1,
            child: Row(
              children: [
                Container(
                  width: 4,
                  height: 20,
                  decoration: BoxDecoration(
                    color: AppTheme.goldDark,
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  'النص المراد تحويله',
                  style: AppTheme.text(
                    color: AppTheme.textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 12),

          // حقل إدخال النص
          EntranceItem(
            index: 2,
            child: Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: AppColors.border,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.025),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: AppTextField(
                controller: _textController,
                hint: 'اكتب النص هنا...',
                maxLines: 8,
              ),
            ),
          ),

          const SizedBox(height: 18),

          // زر التحويل
          EntranceItem(
            index: 3,
            child: PrimaryButton(
              label: 'تحويل النص إلى صوت',
              icon: Icons.auto_awesome_rounded,
              loading: ttsState.converting,
              onPressed: _convert,
            ),
          ),

          // يظهر فقط بعد نجاح إنشاء الصوت
          if (ttsState.localAudioPath != null) ...[
            const SizedBox(height: 26),

            EntranceItem(
              index: 4,
              child: Row(
                children: [
                  Container(
                    width: 4,
                    height: 20,
                    decoration: BoxDecoration(
                      color: AppTheme.iconAccent,
                      borderRadius: BorderRadius.circular(10),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'الصوت الناتج',
                    style: AppTheme.text(
                      color: AppTheme.textPrimary,
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 12),

            // بطاقة حالة الصوت
            EntranceItem(
              index: 5,
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: AppColors.border,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.035),
                      blurRadius: 14,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: AppTheme.iconAccentSoft,
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Icon(
                        ttsState.playing
                            ? Icons.graphic_eq_rounded
                            : Icons.audiotrack_rounded,
                        color: AppTheme.iconAccent,
                        size: 25,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'الصوت جاهز',
                            style: AppTheme.text(
                              color: AppTheme.textPrimary,
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Text(
                            ttsState.playing
                                ? 'يتم تشغيل الصوت الآن'
                                : 'يمكنك الآن الاستماع إلى النص',
                            style: AppTheme.text(
                              color: AppTheme.textSecondary,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 12),

            // تشغيل / إيقاف الصوت
            EntranceItem(
              index: 6,
              child: PrimaryButton(
                label: ttsState.playing
                    ? 'إيقاف الصوت'
                    : 'تشغيل الصوت',
                icon: ttsState.playing
                    ? Icons.stop_rounded
                    : Icons.play_arrow_rounded,
                backgroundColor: ttsState.playing
                    ? AppTheme.error
                    : AppTheme.primaryLight,
                onPressed: () {
                  ref.read(ttsProvider.notifier).togglePlay();
                },
              ),
            ),
          ],

          const SizedBox(height: 20),

          // الملاحظة
          EntranceItem(
            index: 7,
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppTheme.goldSoft.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.info_outline_rounded,
                    color: AppTheme.goldDark,
                    size: 21,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'بعد إنشاء الصوت يتم حفظ الملف الناتج على جهازك لتتمكن من الاستماع إليه.',
                      style: AppTheme.text(
                        color: AppTheme.textSecondary,
                        fontSize: 12,
                        height: 1.6,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}