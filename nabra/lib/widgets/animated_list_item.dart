import 'package:flutter/material.dart';

class AnimatedListItem extends StatefulWidget {
  final Widget child;
  final int index;
  final double slideOffset;

  const AnimatedListItem({
    super.key,
    required this.child,
    required this.index,
    this.slideOffset = 18,
  });

  @override
  State<AnimatedListItem> createState() => _AnimatedListItemState();
}

class _AnimatedListItemState extends State<AnimatedListItem>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;
  late final Animation<double> _a;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 420),
    );
    _a = CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);

    final delay = Duration(milliseconds: 100 + (widget.index * 35));
    Future.delayed(delay, () {
      if (mounted) _c.forward();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _a,
      child: widget.child,
      builder: (context, child) {
        final t = _a.value;
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, (1 - t) * widget.slideOffset),
            child: child,
          ),
        );
      },
    );
  }
}
