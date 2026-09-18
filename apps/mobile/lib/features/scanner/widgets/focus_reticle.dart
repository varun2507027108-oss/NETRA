import 'package:flutter/material.dart';

/// Visual focus and exposure reticle indicating tap-to-focus point.
class FocusReticle extends StatefulWidget {
  final Offset position;
  final VoidCallback? onDismiss;

  const FocusReticle({
    super.key,
    required this.position,
    this.onDismiss,
  });

  @override
  State<FocusReticle> createState() => _FocusReticleState();
}

class _FocusReticleState extends State<FocusReticle>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _scaleAnimation;
  late Animation<double> _opacityAnimation;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );

    _scaleAnimation = TweenSequence<double>([
      TweenSequenceItem(
        tween: Tween<double>(begin: 1.35, end: 1.0)
            .chain(CurveTween(curve: Curves.easeOutBack)),
        weight: 30,
      ),
      TweenSequenceItem(
        tween: ConstantTween<double>(1.0),
        weight: 70,
      ),
    ]).animate(_animController);

    _opacityAnimation = TweenSequence<double>([
      TweenSequenceItem(
        tween: Tween<double>(begin: 0.0, end: 1.0)
            .chain(CurveTween(curve: Curves.easeIn)),
        weight: 15,
      ),
      TweenSequenceItem(
        tween: ConstantTween<double>(1.0),
        weight: 55,
      ),
      TweenSequenceItem(
        tween: Tween<double>(begin: 1.0, end: 0.0)
            .chain(CurveTween(curve: Curves.easeOut)),
        weight: 30,
      ),
    ]).animate(_animController);

    _animController.forward().then((_) {
      if (mounted) {
        widget.onDismiss?.call();
      }
    });
  }

  @override
  void didUpdateWidget(covariant FocusReticle oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.position != widget.position) {
      _animController.reset();
      _animController.forward().then((_) {
        if (mounted) {
          widget.onDismiss?.call();
        }
      });
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    const double reticleSize = 64.0;

    return Positioned(
      left: widget.position.dx - (reticleSize / 2),
      top: widget.position.dy - (reticleSize / 2),
      child: AnimatedBuilder(
        animation: _animController,
        builder: (context, child) {
          return Opacity(
            opacity: _opacityAnimation.value,
            child: Transform.scale(
              scale: _scaleAnimation.value,
              child: child,
            ),
          );
        },
        child: SizedBox(
          width: reticleSize,
          height: reticleSize,
          child: CustomPaint(
            painter: _ReticlePainter(),
          ),
        ),
      ),
    );
  }
}

class _ReticlePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFFFFD54F) // Focus amber-yellow
      ..strokeWidth = 2.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.square;

    final dotPaint = Paint()
      ..color = const Color(0xFFFFD54F)
      ..style = PaintingStyle.fill;

    const double bracketLen = 10.0;
    const double inset = 2.0;

    final double l = inset;
    final double t = inset;
    final double r = size.width - inset;
    final double b = size.height - inset;

    // Top-left
    canvas.drawLine(Offset(l, t), Offset(l + bracketLen, t), paint);
    canvas.drawLine(Offset(l, t), Offset(l, t + bracketLen), paint);

    // Top-right
    canvas.drawLine(Offset(r, t), Offset(r - bracketLen, t), paint);
    canvas.drawLine(Offset(r, t), Offset(r, t + bracketLen), paint);

    // Bottom-left
    canvas.drawLine(Offset(l, b), Offset(l + bracketLen, b), paint);
    canvas.drawLine(Offset(l, b), Offset(l, b - bracketLen), paint);

    // Bottom-right
    canvas.drawLine(Offset(r, b), Offset(r - bracketLen, b), paint);
    canvas.drawLine(Offset(r, b), Offset(r, b - bracketLen), paint);

    // Center focal dot
    final double cx = size.width / 2;
    final double cy = size.height / 2;
    canvas.drawCircle(Offset(cx, cy), 2.5, dotPaint);
  }

  @override
  bool shouldRepaint(covariant _ReticlePainter oldDelegate) => false;
}
