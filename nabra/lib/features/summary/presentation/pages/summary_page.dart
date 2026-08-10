import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/core/di/injector.dart';
import 'package:flutter_app/core/theme/app_colors.dart';
import 'package:flutter_app/core/theme/app_theme.dart';
import 'package:flutter_app/core/widgets/app_snackbar.dart';
import 'package:flutter_app/core/widgets/nabra_scaffold.dart';
import 'package:flutter_app/core/widgets/staggered_entrance.dart';
import 'package:flutter_app/features/auth/presentation/providers/auth_provider.dart';

class SummaryPage extends ConsumerStatefulWidget {
  final String text;
  final String model;
  final String apiUrl;

  const SummaryPage({
    super.key,
    required this.text,
    required this.model,
    required this.apiUrl,
  });

  @override
  ConsumerState<SummaryPage> createState() => _SummaryPageState();
}

class _SummaryPageState extends ConsumerState<SummaryPage> {
  bool _loading = false;
  late String _summary;
  String _keywords = '';

  @override
  void initState() {
    super.initState();
    _summary = widget.text;
    WidgetsBinding.instance.addPostFrameCallback((_) => _summarize());
  }

  Future<void> _summarize() async {
    if (widget.text.trim().isEmpty) return;
    setState(() => _loading = true);
    try {
      final token = ref.read(authProvider).user?.accessToken;
      final result = await AppInjector.summaryRepository.summarize(
        text: widget.text,
        apiBaseUrl: widget.apiUrl,
        model: 'ultra',
        authorization: token,
      );
      setState(() {
        _summary = result.summary.isEmpty ? _summary : result.summary;
        _keywords = result.keywords;
      });
    } catch (e) {
      if (!mounted) return;
      AppSnackbar.show(context, message: 'حدث خطأ: $e', isError: true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return NabraScaffold(
      title: 'تلخيص النص',
      leading: IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded, color: Colors.white, size: 20),
        onPressed: () => context.pop(),
      ),
      actions: [
        IconButton(
          onPressed: _loading ? null : _summarize,
          icon: const Icon(Icons.refresh_rounded, color: Colors.white),
        ),
      ],
      body: Stack(
        children: [
          ListView(
            children: [
              EntranceItem(
                index: 0,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'ملخص التحليل',
                      textAlign: TextAlign.right,
                      style: AppTheme.text(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    _Panel(
                      text: _summary.isEmpty ? 'لا يوجد ملخص بعد' : _summary,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              EntranceItem(
                index: 1,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'الكلمات المفتاحية',
                      textAlign: TextAlign.right,
                      style: AppTheme.text(
                        fontWeight: FontWeight.w800,
                        fontSize: 16,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    _Panel(
                      text: _keywords.isEmpty
                          ? 'ستظهر الكلمات المفتاحية هنا'
                          : _keywords,
                      muted: _keywords.isEmpty,
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (_loading)
            const Center(
              child: CircularProgressIndicator(color: AppColors.primary),
            ),
        ],
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  final String text;
  final bool muted;

  const _Panel({required this.text, this.muted = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 140),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(
        text,
        textAlign: TextAlign.right,
        style: AppTheme.text(
          height: 1.6,
          color: muted ? AppColors.textHint : AppColors.textPrimary,
        ),
      ),
    );
  }
}
