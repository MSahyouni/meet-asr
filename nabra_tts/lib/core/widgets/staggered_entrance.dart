import 'package:flutter/material.dart';

/// عنصر يظهر بتدرّج خفيف (شفافية + انزلاق بسيط للأعلى).
class EntranceItem extends StatefulWidget {
  final Widget child;
  final int index;
  final Duration duration;
  final Duration stagger;
  final Duration initialDelay;
  final double offsetY;

  const EntranceItem({
    super.key,
    required this.child,
    required this.index,
    this.duration = const Duration(milliseconds: 420),
    this.stagger = const Duration(milliseconds: 75),
    this.initialDelay = const Duration(milliseconds: 40),
    this.offsetY = 14,
  });

  @override
  State<EntranceItem> createState() => _EntranceItemState();
}

class _EntranceItemState extends State<EntranceItem>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: widget.duration);
    _animation = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutCubic,
    );

    final delay = widget.initialDelay +
        Duration(milliseconds: widget.stagger.inMilliseconds * widget.index);
    Future.delayed(delay, () {
      if (mounted) _controller.forward();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animation,
      child: widget.child,
      builder: (context, child) {
        final t = _animation.value;
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, (1 - t) * widget.offsetY),
            child: child,
          ),
        );
      },
    );
  }
}

/// يغلّف قائمة عناصر بظهور متدرج داخل [Column].
class StaggeredEntrance extends StatelessWidget {
  final List<Widget> children;
  final CrossAxisAlignment crossAxisAlignment;
  final MainAxisSize mainAxisSize;
  final MainAxisAlignment mainAxisAlignment;

  const StaggeredEntrance({
    super.key,
    required this.children,
    this.crossAxisAlignment = CrossAxisAlignment.stretch,
    this.mainAxisSize = MainAxisSize.min,
    this.mainAxisAlignment = MainAxisAlignment.start,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: crossAxisAlignment,
      mainAxisSize: mainAxisSize,
      mainAxisAlignment: mainAxisAlignment,
      children: [
        for (var i = 0; i < children.length; i++)
          EntranceItem(index: i, child: children[i]),
      ],
    );
  }
}
