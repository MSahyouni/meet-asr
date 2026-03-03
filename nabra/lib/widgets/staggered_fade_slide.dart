import 'package:flutter/material.dart';

class StaggeredFadeSlide extends StatefulWidget {
  final List<Widget> children;

  const StaggeredFadeSlide({super.key, required this.children});

  @override
  State<StaggeredFadeSlide> createState() => _StaggeredFadeSlideState();
}

class _StaggeredFadeSlideState extends State<StaggeredFadeSlide>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  final Duration itemDuration = const Duration(milliseconds: 450);
  final Duration staggerDelay = const Duration(milliseconds: 70);

  @override
  void initState() {
    super.initState();

    final totalDuration = Duration(
      milliseconds:
          itemDuration.inMilliseconds +
          staggerDelay.inMilliseconds * (widget.children.length - 1),
    );

    _controller = AnimationController(vsync: this, duration: totalDuration);

    Future.delayed(const Duration(milliseconds: 100), () {
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
    final total = _controller.duration!.inMilliseconds.toDouble();
    final item = itemDuration.inMilliseconds.toDouble();
    final stagger = staggerDelay.inMilliseconds.toDouble();

    return Column(
      children: List.generate(widget.children.length, (i) {
        final startMs = i * stagger;
        final endMs = startMs + item;

        final start = startMs / total;
        final end = endMs / total;

        final animation = CurvedAnimation(
          parent: _controller,
          curve: Interval(start, end, curve: Curves.easeOut),
        );

        return AnimatedBuilder(
          animation: animation,
          child: widget.children[i],
          builder: (context, child) {
            final value = animation.value;

            return Opacity(
              opacity: value,
              child: Transform.translate(
                offset: Offset(0, (1 - value) * 25), // نزول خفيف مثل الصورة
                child: child,
              ),
            );
          },
        );
      }),
    );
  }
}
