import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/core/theme/app_theme.dart';
import 'package:flutter_app/core/widgets/nabra_scaffold.dart';
import 'package:flutter_app/core/widgets/outlined_action_tile.dart';
import 'package:flutter_app/core/widgets/staggered_entrance.dart';
import 'package:flutter_app/features/auth/presentation/providers/auth_provider.dart';
import 'package:flutter_app/features/home/presentation/widgets/app_drawer.dart';
import 'package:flutter_app/features/home/presentation/widgets/live_transcript_card.dart';
import 'package:flutter_app/features/home/presentation/widgets/voice_recorder_bar.dart';

class HomePage extends ConsumerStatefulWidget {
  const HomePage({super.key});

  @override
  ConsumerState<HomePage> createState() => _HomePageState();
}

class _HomePageState extends ConsumerState<HomePage> {
  File? _recordedFile;
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  String get _apiUrl => ref.read(authProvider).apiBaseUrl;

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['mp3', 'wav', 'm4a', 'aac', 'opus'],
      allowMultiple: true,
    );
    if (result == null || !mounted) return;

    final files = result.files
        .where((f) => f.path != null)
        .map((f) => File(f.path!))
        .toList();
    if (files.isEmpty) return;

    context.push('/analysis', extra: {'files': files, 'apiUrl': _apiUrl});
  }

  void _goTts() {
    context.push('/tts', extra: {'apiUrl': _apiUrl});
  }

  @override
  Widget build(BuildContext context) {
    return NabraScaffold(
      scaffoldKey: _scaffoldKey,
      drawer: const AppDrawer(),
      title: 'نبرة',
      contentPadding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
      leading: IconButton(
        icon: const Icon(Icons.menu_rounded, color: Colors.white),
        onPressed: () => _scaffoldKey.currentState?.openDrawer(),
      ),
      bottomBar: EntranceItem(
        index: 4,
        child: VoiceRecorderBar(
          onRecordedFile: (file) => setState(() => _recordedFile = file),
        ),
      ),
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          EntranceItem(
            index: 0,
            child: Text(
              'ماذا تريد أن تفعل؟',
              textAlign: TextAlign.right,
              style: AppTheme.text(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: AppTheme.textSecondary,
              ),
            ),
          ),
          const SizedBox(height: 14),
          const EntranceItem(
            index: 1,
            child: LiveTranscriptCard(),
          ),
          const SizedBox(height: 12),
          EntranceItem(
            index: 2,
            child: OutlinedActionTile(
              label: 'تحميل ملف صوتي',
              subtitle: 'اختر ملفاً للتحليل — يُفتح التحليل تلقائياً',
              icon: Icons.audio_file_rounded,
              accent: AppTheme.goldDark,
              iconBackground: AppTheme.goldSoft,
              onTap: _pickFiles,
            ),
          ),
          const SizedBox(height: 12),
          EntranceItem(
            index: 3,
            child: OutlinedActionTile(
              label: 'تحويل النص إلى صوت',
              subtitle: 'استمع لنصك بصوت طبيعي وواضح',
              icon: Icons.record_voice_over_rounded,
              accent: AppTheme.iconAccent,
              iconBackground: AppTheme.iconAccentSoft,
              onTap: _goTts,
            ),
          ),
          // يُحتفظ بآخر ملف داخلياً دون عرضه في الواجهة
          if (_recordedFile != null) const SizedBox.shrink(),
        ],
      ),
    );
  }
}
