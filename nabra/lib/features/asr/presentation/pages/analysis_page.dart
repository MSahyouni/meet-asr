import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nabra/core/di/injector.dart';
import 'package:nabra/core/theme/app_colors.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/widgets/app_snackbar.dart';
import 'package:nabra/core/widgets/nabra_scaffold.dart';
import 'package:nabra/core/widgets/outlined_action_tile.dart';
import 'package:nabra/core/widgets/primary_button.dart';
import 'package:nabra/core/widgets/staggered_entrance.dart';
import 'package:nabra/features/asr/infrastructure/repositories/asr_repository_impl.dart';
import 'package:nabra/features/auth/presentation/providers/auth_provider.dart';
import 'package:nabra/services/text_saver.dart';

class AnalysisPage extends ConsumerStatefulWidget {
  const AnalysisPage({super.key});

  @override
  ConsumerState<AnalysisPage> createState() => _AnalysisPageState();
}

class _AnalysisPageState extends ConsumerState<AnalysisPage> {
  bool _loading = false;
  String _transcript = '';
  String _summaryModel = 'light';
  bool _autoStarted = false;

  final _models = const {
    'light': 'Light Model (سريع وأخف)',
    'ultra': 'Ultra Model (أدق وأقوى)',
  };

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_autoStarted) return;

    final extra = GoRouterState.of(context).extra as Map<String, dynamic>?;
    final files =
        (extra?['files'] as List<dynamic>?)?.map((e) => e as File).toList() ??
            <File>[];
    final apiUrl = extra?['apiUrl'] as String? ?? '';

    if (files.isEmpty) return;

    _autoStarted = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _transcribe(files: files, apiUrl: apiUrl);
    });
  }

  @override
  Widget build(BuildContext context) {
    final extra = GoRouterState.of(context).extra as Map<String, dynamic>?;
    final files =
        (extra?['files'] as List<dynamic>?)?.map((e) => e as File).toList() ??
            <File>[];
    final apiUrl = extra?['apiUrl'] as String? ?? '';

    if (files.isEmpty) {
      return NabraScaffold(
        title: 'تحليل الصوت',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
          onPressed: () => context.pop(),
        ),
        body: const Center(child: Text('لا يوجد ملف صوتي')),
      );
    }

    return NabraScaffold(
      title: 'تحليل الصوت',
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
        onPressed: () => context.pop(),
      ),
      actions: [
        PopupMenuButton<String>(
          icon: const Icon(Icons.more_vert, color: Colors.white),
          color: AppColors.primary,
          onSelected: (value) async {
            if (value == 'save' && _transcript.trim().isNotEmpty) {
              await FileSaver.saveAnalyzedText(
                context: context,
                analyzedText: _transcript,
              );
            }
          },
          itemBuilder: (_) => [
            PopupMenuItem(
              value: 'save',
              child: Text(
                'حفظ النص كملف TXT',
                style: AppTheme.text(color: Colors.white),
              ),
            ),
          ],
        ),
      ],
      body: ListView(
        children: [
          EntranceItem(
            index: 0,
            child: OutlinedActionTile(
            label: _loading
                ? 'جاري التحويل... قد يستغرق وقتاً على CPU'
                : (_transcript.isEmpty
                    ? 'إرسال وتحويل الصوت إلى نص'
                    : 'إعادة التحويل'),
              icon: Icons.play_arrow_rounded,
              onTap: _loading
                  ? null
                  : () => _transcribe(files: files, apiUrl: apiUrl),
            ),
          ),
          const SizedBox(height: 12),
          EntranceItem(
            index: 1,
            child: _ResultBox(
              hint: 'تلخيص النص',
              text: _transcript.isEmpty
                  ? null
                  : 'اضغط الزر أدناه لفتح صفحة التلخيص',
              onTap: _transcript.trim().isEmpty
                  ? null
                  : () {
                      context.push('/summary', extra: {
                        'text': _transcript,
                        'model': _summaryModel,
                        'apiUrl': apiUrl,
                      });
                    },
            ),
          ),
          const SizedBox(height: 20),
          EntranceItem(
            index: 2,
            child: Column(
              children: [
                Text(
                  'اختر نموذج التلخيص',
                  textAlign: TextAlign.center,
                  style: AppTheme.text(
                    fontWeight: FontWeight.w800,
                    fontSize: 16,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 10),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.primary,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String>(
                      value: _summaryModel,
                      isExpanded: true,
                      dropdownColor: AppTheme.primaryLight,
                      iconEnabledColor: Colors.white,
                      style: AppTheme.text(
                        color: AppColors.goldSoft,
                        fontSize: 14,
                      ),
                      items: _models.entries
                          .map(
                            (e) => DropdownMenuItem(
                              value: e.key,
                              child:
                                  Text(e.value, textAlign: TextAlign.right),
                            ),
                          )
                          .toList(),
                      onChanged: (v) {
                        if (v != null) setState(() => _summaryModel = v);
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (_transcript.isNotEmpty) ...[
            const SizedBox(height: 20),
            EntranceItem(
              index: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'النص المستخرج',
                    textAlign: TextAlign.right,
                    style: AppTheme.text(
                      fontWeight: FontWeight.w700,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Text(
                      _transcript,
                      textAlign: TextAlign.right,
                      style: AppTheme.text(height: 1.55),
                    ),
                  ),
                  const SizedBox(height: 16),
                  PrimaryButton(
                    label: 'الانتقال إلى التلخيص',
                    onPressed: () {
                      context.push('/summary', extra: {
                        'text': _transcript,
                        'model': _summaryModel,
                        'apiUrl': apiUrl,
                      });
                    },
                  ),
                ],
              ),
            ),
          ],
          if (_loading)
            const Padding(
              padding: EdgeInsets.only(top: 24),
              child: Center(
                child: CircularProgressIndicator(color: AppColors.primary),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _transcribe({
    required List<File> files,
    required String apiUrl,
  }) async {
    setState(() {
      _loading = true;
      _transcript = '';
    });

    try {
      final token = ref.read(authProvider).user?.accessToken;
      final buffer = StringBuffer();

      for (final file in files) {
        final TranscriptionResult result = await AppInjector.asrRepository.transcribe(
          file: file,
          apiBaseUrl: apiUrl,
          authorization: token,
          model: 'light',
          diarize: false,
        );
        if (files.length > 1) {
          buffer.writeln('— ${file.path.split(Platform.pathSeparator).last} —');
        }
        buffer.writeln(result.text);
        buffer.writeln();
      }

      setState(() => _transcript = buffer.toString().trim());
      if (!mounted) return;
      AppSnackbar.show(context, message: 'تم تحويل الصوت إلى نص');
    } catch (e) {
      if (!mounted) return;
      AppSnackbar.show(context, message: 'حدث خطأ: $e', isError: true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }
}

class _ResultBox extends StatelessWidget {
  final String hint;
  final String? text;
  final VoidCallback? onTap;

  const _ResultBox({required this.hint, this.text, this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 72),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.borderStrong.withValues(alpha: 0.55)),
            ),
            alignment: Alignment.centerRight,
            child: Text(
              text ?? hint,
              textAlign: TextAlign.right,
              style: AppTheme.text(
                color: text == null ? AppColors.textHint : AppColors.textPrimary,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
