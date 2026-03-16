import 'package:flutter/material.dart';
import 'package:gap/gap.dart';

class LoginButton extends StatelessWidget {
  const LoginButton({
    required this.text,
    required this.isRTL,
    required this.onPressed,
  });

  final String text;
  final bool isRTL;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent, // مهم
          foregroundColor: Colors.white,
          shadowColor: Colors.transparent, // نلغي شادو الافتراضي
          elevation: 0,
          padding: EdgeInsets.zero, // مهم
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
        child: Ink(
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
              colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],
            ),
            borderRadius: BorderRadius.circular(10),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF1FB45F).withOpacity(0.25),
                blurRadius: 18,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: Container(
            alignment: Alignment.center,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  isRTL ? Icons.arrow_back : Icons.arrow_forward,
                  size: 18,
                  color: Colors.white,
                ),
                const Gap(10),
                Text(
                  text,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
