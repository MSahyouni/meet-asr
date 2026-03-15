import 'package:flutter/material.dart';
import 'package:flutter_app/widgets/get_drawer.dart';
import 'package:gap/gap.dart';

class Standerd extends StatelessWidget {
  const Standerd({super.key, required this.widget});

  final Widget widget;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        flexibleSpace: Image.asset(
          'assets/images/image_5.png',
          fit: BoxFit.cover,
        ),
        toolbarHeight: 120,
        title: Row(
          children: [
            Gap(130),
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: Image.asset(
                "assets/images/image_1.png",
                height: 80,
                width: 90,
                fit: BoxFit.contain,
              ),
            ),
          ],
        ),
      ),
      // drawer: get_Drawer(context),
      body: Stack(
        children: [
          Image.asset(
            fit: BoxFit.cover,
            height: 900,
            width: 500,
            "assets/images/image_5.png",
          ),
          widget,
        ],
      ),
    );
  }
}
