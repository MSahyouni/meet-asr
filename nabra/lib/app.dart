import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/core/theme/app_theme.dart';
import 'package:flutter_app/features/asr/presentation/pages/analysis_page.dart';
import 'package:flutter_app/features/auth/presentation/pages/login_page.dart';
import 'package:flutter_app/features/auth/presentation/pages/register_page.dart';
import 'package:flutter_app/features/home/presentation/pages/home_page.dart';
import 'package:flutter_app/features/splash/presentation/pages/splash_page.dart';
import 'package:flutter_app/features/summary/presentation/pages/summary_page.dart';
import 'package:flutter_app/features/tts/presentation/pages/tts_page.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/splash',
  routes: [
    GoRoute(path: '/splash', builder: (context, state) => const SplashPage()),
    GoRoute(path: '/', redirect: (context, state) => '/home'),
    GoRoute(path: '/home', builder: (context, state) => const HomePage()),
    GoRoute(path: '/login', builder: (context, state) => const LoginPage()),
    GoRoute(path: '/register', builder: (context, state) => const RegisterPage()),
    GoRoute(path: '/analysis', builder: (context, state) => const AnalysisPage()),
    GoRoute(
      path: '/summary',
      builder: (context, state) {
        final extra = state.extra as Map<String, dynamic>?;
        return SummaryPage(
          text: extra?['text']?.toString() ?? '',
          model: extra?['model']?.toString() ?? 'ultra',
          apiUrl: extra?['apiUrl']?.toString() ?? '',
        );
      },
    ),
    GoRoute(
      path: '/tts',
      builder: (context, state) {
        final extra = state.extra as Map<String, dynamic>?;
        return TtsPage(apiUrl: extra?['apiUrl']?.toString() ?? '');
      },
    ),
    GoRoute(path: '/analysis_audio', redirect: (context, state) => '/analysis'),
    GoRoute(path: '/text_to_speech', redirect: (context, state) => '/tts'),
    GoRoute(path: '/create_account', redirect: (context, state) => '/register'),
  ],
);

class NabraApp extends StatelessWidget {
  const NabraApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ProviderScope(
      child: MaterialApp.router(
        title: 'نبرة',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        routerConfig: appRouter,
        builder: (context, child) {
          return Directionality(
            textDirection: TextDirection.rtl,
            child: child ?? const SizedBox.shrink(),
          );
        },
      ),
    );
  }
}
