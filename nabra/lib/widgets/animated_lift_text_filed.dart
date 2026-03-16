import 'package:flutter/material.dart';

class AnimatedLiftTextField extends StatefulWidget {
  const AnimatedLiftTextField({
    super.key,
    required this.controller,
    required this.hint,
    required this.prefix,
    this.keyboardType = TextInputType.text,
    this.obscureText = false,
    this.suffix,
    this.onSuffixTap,
    this.mirrorPrefixWhenRTL = false,
  });

  final TextEditingController controller;
  final String hint;
  final IconData prefix;
  final TextInputType keyboardType;
  final bool obscureText;

  final IconData? suffix;
  final VoidCallback? onSuffixTap;

  final bool mirrorPrefixWhenRTL;

  @override
  State<AnimatedLiftTextField> createState() => _AnimatedLiftTextFieldState();
}

class _AnimatedLiftTextFieldState extends State<AnimatedLiftTextField> {
  final FocusNode _focusNode = FocusNode();
  bool _focused = false;

  @override
  void initState() {
    super.initState();
    _focusNode.addListener(() {
      if (!mounted) return;
      setState(() => _focused = _focusNode.hasFocus);
    });
  }

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const hintColor = Color(0xFF9AA6AE);
    const iconColor = Color(0xFFB7C2C8);
    const accent = Color(0xFF2BB39D);

    final isRTL = Directionality.of(context) == TextDirection.rtl;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOutCubic,
      transform: Matrix4.translationValues(0, _focused ? -4 : 0, 0),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Color(0xFF0C3A34), Color(0xFF125B4A), Color(0xFF1A7B6A)],

          begin: Alignment.centerRight,
          end: Alignment.centerLeft,
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _focused
              ? accent.withOpacity(0.60)
              : Colors.white.withOpacity(0.10),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: _focused
                ? const Color(0xFF2AA876).withOpacity(0.22)
                : const Color(0xFF2AA876).withOpacity(0.10),
            blurRadius: _focused ? 22 : 14,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: TextField(
        textAlign: TextAlign.right,
        focusNode: _focusNode,
        controller: widget.controller,
        keyboardType: widget.keyboardType,
        obscureText: widget.obscureText,
        style: const TextStyle(
          color: Color(0xFFE9EEF1),
          fontSize: 12.5,
          fontWeight: FontWeight.w700,
        ),
        cursorColor: accent,
        decoration: InputDecoration(
          border: InputBorder.none,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 12,
            vertical: 12,
          ),
          hintText: widget.hint,
          hintStyle: const TextStyle(
            color: hintColor,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
          suffixIcon: Transform(
            alignment: Alignment.center,
            transform: (isRTL && widget.mirrorPrefixWhenRTL)
                ? Matrix4.diagonal3Values(-1.0, 1.0, 1.0)
                : Matrix4.identity(),
            child: Icon(widget.prefix, size: 18, color: iconColor),
          ),

          prefixIcon: widget.suffix == null
              ? null
              : InkWell(
                  onTap: widget.onSuffixTap,
                  borderRadius: BorderRadius.circular(999),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Icon(widget.suffix, size: 18, color: iconColor),
                  ),
                ),
        ),
      ),
    );
  }
}
