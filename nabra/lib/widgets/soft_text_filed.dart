import 'package:flutter/material.dart';

class AuthSoftTextField extends StatefulWidget {
  final TextEditingController controller;
  final String hint;
  final IconData prefix;
  final TextInputType keyboardType;
  final bool obscureText;
  final IconData? suffix;
  final VoidCallback? onSuffixTap;

  const AuthSoftTextField({
    super.key,
    required this.controller,
    required this.hint,
    required this.prefix,
    this.keyboardType = TextInputType.text,
    this.obscureText = false,
    this.suffix,
    this.onSuffixTap,
  });

  @override
  State<AuthSoftTextField> createState() => _AuthSoftTextFieldState();
}

class _AuthSoftTextFieldState extends State<AuthSoftTextField> {
  final FocusNode _focusNode = FocusNode();
  bool _focused = false;

  @override
  void initState() {
    super.initState();
    _focusNode.addListener(() {
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
    final t = Theme.of(context).textTheme;

    final gradient = const LinearGradient(
      colors: [
        Color.fromARGB(30, 7, 14, 13), // أخضر مزرق خفيف
        Color.fromARGB(255, 30, 85, 77), // أخضر أغمق
      ],
      begin: Alignment.centerRight,
      end: Alignment.centerLeft,
    );

    return AnimatedContainer(
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOutCubic,

      //  الحركة للأمام (يرتفع لفوق شوي)
      transform: Matrix4.translationValues(0, _focused ? -6 : 0, 0),

      decoration: BoxDecoration(
        gradient: gradient,
        borderRadius: BorderRadius.circular(10),

        //  border يتغير وقت الفوكس
        border: Border.all(
          color: _focused ? const Color(0xFF2AA876) : const Color(0xFFBFE7D6),
          width: 1,
        ),

        //  shadow يزيد وقت الفوكس
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
        style: t.bodyMedium?.copyWith(
          color: Colors.white,
          fontWeight: FontWeight.w700,
        ),
        decoration: InputDecoration(
          border: InputBorder.none,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: 12,
            vertical: 12,
          ),
          hintText: widget.hint,
          hintStyle: t.bodySmall?.copyWith(
            color: const Color(0xFF8AA79C),
            fontWeight: FontWeight.w700,
          ),

          suffixIcon: Icon(
            widget.prefix,
            size: 18,
            color: const Color(0xFF7AAE99),
          ),
          prefixIcon: widget.suffix == null
              ? null
              : InkWell(
                  onTap: widget.onSuffixTap,
                  child: Icon(
                    widget.suffix,
                    size: 18,
                    color: const Color(0xFF7AAE99),
                  ),
                ),
        ),
      ),
    );
  }
}
