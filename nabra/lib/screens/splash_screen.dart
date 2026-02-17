import 'package:animated_splash_screen/animated_splash_screen.dart';
import 'package:flutter/material.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return AnimatedSplashScreen.withScreenRouteFunction(
      splashIconSize: 400,
      splash: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: FittedBox(
              child: Image.asset(
                "assets/images/image_1.png",
                height: 180,
                width: 180,
                fit: BoxFit.contain,
              ),
            ),
          ),
          Gap(15),
          Text(
            "الجمهورية العربية السورية\n   وزارة الدفاع السورية ",
            style: TextStyle(fontSize: 35, fontWeight: FontWeight.bold),
          ),
        ],
      ),
      splashTransition: SplashTransition.sizeTransition,
      animationDuration: Duration(seconds: 4),
      screenRouteFunction: () async {
        await Future.delayed(Duration(seconds: 2)).then((value) {
          // ignore: use_build_context_synchronously
          context.pushReplacement('/');
        });
        return "/";
      },
    );
  }
}
