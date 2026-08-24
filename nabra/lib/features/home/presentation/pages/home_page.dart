// import 'dart:io';
// import 'package:file_picker/file_picker.dart';
// import 'package:flutter/material.dart';
// import 'package:flutter_riverpod/flutter_riverpod.dart';
// import 'package:go_router/go_router.dart';
// import 'package:nabra/core/theme/app_theme.dart';
// import 'package:nabra/core/widgets/nabra_scaffold.dart';
// import 'package:nabra/core/widgets/outlined_action_tile.dart';
// import 'package:nabra/core/widgets/staggered_entrance.dart';
// import 'package:nabra/features/auth/presentation/providers/auth_provider.dart';
// import 'package:nabra/features/home/presentation/widgets/app_drawer.dart';
// import 'package:nabra/features/home/presentation/widgets/live_transcript_card.dart';
// import 'package:nabra/features/home/presentation/widgets/voice_recorder_bar.dart';

// class HomePage extends ConsumerStatefulWidget {
//   const HomePage({super.key});

//   @override
//   ConsumerState<HomePage> createState() => _HomePageState();
// }

// class _HomePageState extends ConsumerState<HomePage> {
//   File? _recordedFile;
//   final _scaffoldKey = GlobalKey<ScaffoldState>();

//   String get _apiUrl => ref.read(authProvider).apiBaseUrl;

//   Future<void> _pickFiles() async {
//     final result = await FilePicker.platform.pickFiles(
//       type: FileType.custom,
//       allowedExtensions: const ['mp3', 'wav', 'm4a', 'aac', 'opus'],
//       allowMultiple: true,
//     );
//     if (result == null || !mounted) return;

//     final files = result.files
//         .where((f) => f.path != null)
//         .map((f) => File(f.path!))
//         .toList();
//     if (files.isEmpty) return;

//     context.push('/analysis', extra: {'files': files, 'apiUrl': _apiUrl});
//   }

//   void _goTts() {
//     context.push('/tts', extra: {'apiUrl': _apiUrl});
//   }

//   @override
//   Widget build(BuildContext context) {
//     return NabraScaffold(
//       scaffoldKey: _scaffoldKey,
//       drawer: const AppDrawer(),
//       title: 'نبرة',
//       contentPadding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
//       leading: IconButton(
//         icon: const Icon(Icons.menu_rounded, color: Colors.white),
//         onPressed: () => _scaffoldKey.currentState?.openDrawer(),
//       ),
//       bottomBar: EntranceItem(
//         index: 4,
//         child: VoiceRecorderBar(
//           onRecordedFile: (file) => setState(() => _recordedFile = file),
//         ),
//       ),
//       body: ListView(
//         padding: EdgeInsets.zero,
//         children: [
//           EntranceItem(
//             index: 0,
//             child: Text(
//               'ماذا تريد أن تفعل؟',
//               textAlign: TextAlign.right,
//               style: AppTheme.text(
//                 fontSize: 13,
//                 fontWeight: FontWeight.w600,
//                 color: AppTheme.textSecondary,
//               ),
//             ),
//           ),
//           const SizedBox(height: 14),
//           const EntranceItem(
//             index: 1,
//             child: LiveTranscriptCard(),
//           ),
//           const SizedBox(height: 12),
//           EntranceItem(
//             index: 2,
//             child: OutlinedActionTile(
//               label: 'تحميل ملف صوتي',
//               subtitle: 'اختر ملفاً للتحليل — يُفتح التحليل تلقائياً',
//               icon: Icons.audio_file_rounded,
//               accent: AppTheme.goldDark,
//               iconBackground: AppTheme.goldSoft,
//               onTap: _pickFiles,
//             ),
//           ),
//           const SizedBox(height: 12),
//           EntranceItem(
//             index: 3,
//             child: OutlinedActionTile(
//               label: 'تحويل النص إلى صوت',
//               subtitle: 'استمع لنصك بصوت طبيعي وواضح',
//               icon: Icons.record_voice_over_rounded,
//               accent: AppTheme.iconAccent,
//               iconBackground: AppTheme.iconAccentSoft,
//               onTap: _goTts,
//             ),
//           ),
//           // يُحتفظ بآخر ملف داخلياً دون عرضه في الواجهة
//           if (_recordedFile != null) const SizedBox.shrink(),
//         ],
//       ),
//     );
//   }
// }


import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/core/widgets/nabra_scaffold.dart';
import 'package:nabra/core/widgets/outlined_action_tile.dart';
import 'package:nabra/core/widgets/staggered_entrance.dart';

import 'package:nabra/features/auth/presentation/providers/auth_provider.dart';
import 'package:nabra/features/home/presentation/widgets/app_drawer.dart';
import 'package:nabra/features/home/presentation/widgets/live_transcript_card.dart';
import 'package:nabra/features/home/presentation/widgets/voice_recorder_bar.dart';

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
      allowedExtensions: const [
        'mp3',
        'wav',
        'm4a',
        'aac',
        'opus',
      ],
      allowMultiple: true,
    );

    if (result == null || !mounted) return;

    final files = result.files
        .where((file) => file.path != null)
        .map((file) => File(file.path!))
        .toList();

    if (files.isEmpty) return;

    context.push(
      '/analysis',
      extra: {
        'files': files,
        'apiUrl': _apiUrl,
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final primaryColor = Theme.of(context).colorScheme.primary;

    return NabraScaffold(
      scaffoldKey: _scaffoldKey,
      drawer: const AppDrawer(),
      title: 'نبرة',
      contentPadding: const EdgeInsets.fromLTRB(
        20,
        20,
        20,
        12,
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

      // شريط التسجيل المباشر
      bottomBar: EntranceItem(
        index: 4,
        child: VoiceRecorderBar(
          onRecordedFile: (file) {
            setState(() {
              _recordedFile = file;
            });
          },
        ),
      ),

      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          // بطاقة تعريفية للتطبيق
          EntranceItem(
            index: 0,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(
                horizontal: 18,
                vertical: 18,
              ),
              decoration: BoxDecoration(
                color: primaryColor,
                borderRadius: BorderRadius.circular(22),
                boxShadow: [
                  BoxShadow(
                    color: primaryColor.withValues(alpha: 0.14),
                    blurRadius: 18,
                    offset: const Offset(0, 7),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    width: 54,
                    height: 54,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Icon(
                      Icons.graphic_eq_rounded,
                      size: 30,
                      color: Colors.white,
                    ),
                  ),

                  const SizedBox(width: 14),

                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'حوّل صوتك إلى نص',
                          style: AppTheme.text(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),

                        const SizedBox(height: 5),

                        Text(
                          'سجّل صوتك مباشرة أو حمّل ملفاً صوتياً لتحويله إلى نص.',
                          style: AppTheme.text(
                            fontSize: 12,
                            fontWeight: FontWeight.w400,
                            color: Colors.white.withValues(alpha: 0.85),
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

          // عنوان قسم التسجيل المباشر
          EntranceItem(
            index: 1,
            child: Row(
              children: [
                Container(
                  width: 4,
                  height: 19,
                  decoration: BoxDecoration(
                    color: AppTheme.goldDark,
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),

                const SizedBox(width: 8),

                Text(
                  'التفريغ المباشر',
                  style: AppTheme.text(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 12),

          // النص الناتج من التسجيل المباشر
          const EntranceItem(
            index: 2,
            child: LiveTranscriptCard(),
          ),

          const SizedBox(height: 24),

          // قسم رفع ملف صوتي
          EntranceItem(
            index: 3,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 4,
                      height: 19,
                      decoration: BoxDecoration(
                        color: AppTheme.iconAccent,
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),

                    const SizedBox(width: 8),

                    Text(
                      'تحليل ملف صوتي',
                      style: AppTheme.text(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 12),

                OutlinedActionTile(
                  label: 'تحميل ملف صوتي',
                  subtitle: 'اختر ملفاً صوتياً لتحويله إلى نص وتحليله',
                  icon: Icons.audio_file_rounded,
                  accent: AppTheme.goldDark,
                  iconBackground: AppTheme.goldSoft,
                  onTap: _pickFiles,
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // نحتفظ بآخر تسجيل داخلياً
          // لأن VoiceRecorderBar يعيده بعد انتهاء التسجيل.
          if (_recordedFile != null)
            const SizedBox.shrink(),
        ],
      ),
    );
  }
}