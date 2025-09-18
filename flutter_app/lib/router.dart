import 'package:flutter_app/screens/analysis_audio.dart';
import 'package:flutter_app/screens/home_screen.dart';
import 'package:flutter_app/screens/splash_screen.dart';
import 'package:go_router/go_router.dart';

final GoRouter router = GoRouter(
  initialLocation: "/splash",

  routes: [
    GoRoute(path: "/splash", builder: (context, state) => SplashScreen()),
    GoRoute(path: "/", builder: (context, state) => HomeScreen()),
    GoRoute(
      path: "/analysis_audio",
      builder: (context, state) => AnalysisAudioScreen(),
    ),
  ],
);
