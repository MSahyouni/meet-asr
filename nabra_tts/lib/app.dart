import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:nabra/core/theme/app_theme.dart';
import 'package:nabra/features/auth/presentation/pages/login_page.dart';
import 'package:nabra/features/auth/presentation/pages/register_page.dart';
import 'package:nabra/features/home/presentation/pages/home_page_tts.dart';
import 'package:nabra/features/splash/presentation/pages/splash_page.dart';


final GoRouter appRouter = GoRouter(

  initialLocation: '/splash',
  routes: [
    GoRoute(path: '/splash', builder: (context, state) => const SplashPage()),
    GoRoute(path: '/', redirect: (context, state) => '/home'),
    GoRoute(path: '/home', builder: (context, state) => const HomePage()),
    GoRoute(path: '/login', builder: (context, state) => const LoginPage()),
    GoRoute(path: '/register', builder: (context, state) => const RegisterPage()),
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
