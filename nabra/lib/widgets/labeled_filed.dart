import 'package:flutter/material.dart';
import 'package:gap/gap.dart';

class AuthLabeledField extends StatelessWidget {
  final String text;
  final bool requiredStar;
  final Widget child;

  const AuthLabeledField({
    super.key,
    required this.text,
    required this.child,
    this.requiredStar = false,
  });

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.end,
          children: [
            Text(
              text,
              style: t.bodySmall?.copyWith(
                color: Colors.white70,
                fontWeight: FontWeight.w800,
              ),
            ),
            if (requiredStar) ...[
              const SizedBox(width: 2),
              Text(
                '*',
                style: TextStyle(
                  color: Colors.redAccent,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ],
        ),
        const Gap(6),
        child,
      ],
    );
  }
}
