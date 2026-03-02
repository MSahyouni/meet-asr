import 'package:flutter/material.dart';
import 'package:flutter_app/router.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return Builder(
      builder: (context) {
        final screenWidth = MediaQuery.of(context).size.width;
        final screenHeight = MediaQuery.of(context).size.height;
        return MaterialApp.router(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
            textTheme: TextTheme(
              bodyMedium: TextStyle(fontSize: screenWidth * 0.04),
            ),
          ),
          debugShowCheckedModeBanner: false,
          routerConfig: router,
        );
      },
    );
  }
}
