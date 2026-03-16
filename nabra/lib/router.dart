import 'package:flutter_app/screens/TTS.dart';
import 'package:flutter_app/screens/analysis_audio.dart';
import 'package:flutter_app/screens/create_account.dart';
import 'package:flutter_app/screens/home_screen.dart';
import 'package:flutter_app/screens/log_in_screen.dart';
import 'package:flutter_app/screens/splash_screen.dart';
import 'package:flutter_app/screens/summary_page.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter/material.dart';

final GoRouter router = GoRouter(
  initialLocation: "/splash",

  routes: [
    GoRoute(path: "/splash", builder: (context, state) => SplashScreen()),
    GoRoute(path: "/", builder: (context, state) => HomeScreen()),
    GoRoute(
      path: "/analysis_audio",
      builder: (context, state) => AnalysisAudioScreen(),
    ),
    GoRoute(
      path: '/summary',
      builder: (context, state) {
        // هنا نستقبل الـ extra كخريطة
        final extra = state.extra as Map<String, dynamic>?;

        return SummaryScreen(
          text: extra?['text'] ?? '',
          model: extra?['model'] ?? 'Light',
          apiUrl: extra?['apiUrl'] ?? '',
        );
      },
    ),
    GoRoute(
      path: "/text_to_speech",
      builder: (context, state) {
        final extra = state.extra as Map<String, dynamic>?;

        return Tts(apiUrl: extra?['apiUrl'] ?? '');
      },
    ),
    GoRoute(
      path: "/login",
      builder: (context, state) {
        return LoginScreen();
      },
    ),
    GoRoute(
      path: "/create_account",
      builder: (context, state) {
        return CreateAccountScreen();
      },
    ),
  ],
);
