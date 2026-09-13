import 'package:flutter/material.dart';

/// Corner-bracket viewfinder framing for package alignment.
class CaptureFrame extends StatelessWidget {
  final double aspectRatio;
  final Color bracketColor;
  final double bracketLength;
  final double strokeWidth;

  const CaptureFrame({
    super.key,
    this.aspectRatio = 3 / 4,
    this.bracketColor = Colors.white70,
    this.bracketLength = 28.0,
    this.strokeWidth = 3.0,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Calculate framing rectangle dimensions centered in container
        final double maxWidth = constraints.maxWidth * 0.82;
        final double maxHeight = constraints.maxHeight * 0.68;

        double width = maxWidth;
        double height = width / aspectRatio;

        if (height > maxHeight) {
          height = maxHeight;
          width = height * aspectRatio;
        }

        return Center(
          child: SizedBox(
            width: width,
            height: height,
            child: Stack(
              children: [
                // Top-left
                Positioned(
                  top: 0,
                  left: 0,
                  child: CustomPaint(
                    size: Size(bracketLength, bracketLength),
                    painter: _BracketPainter(
                      color: bracketColor,
                      strokeWidth: strokeWidth,
                      isTop: true,
                      isLeft: true,
                    ),
                  ),
                ),
                // Top-right
                Positioned(
                  top: 0,
                  right: 0,
                  child: CustomPaint(
                    size: Size(bracketLength, bracketLength),
                    painter: _BracketPainter(
                      color: bracketColor,
                      strokeWidth: strokeWidth,
                      isTop: true,
                      isLeft: false,
                    ),
                  ),
                ),
                // Bottom-left
                Positioned(
                  bottom: 0,
                  left: 0,
                  child: CustomPaint(
                    size: Size(bracketLength, bracketLength),
                    painter: _BracketPainter(
                      color: bracketColor,
                      strokeWidth: strokeWidth,
                      isTop: false,
                      isLeft: true,
                    ),
                  ),
                ),
                // Bottom-right
                Positioned(
                  bottom: 0,
                  right: 0,
                  child: CustomPaint(
                    size: Size(bracketLength, bracketLength),
                    painter: _BracketPainter(
                      color: bracketColor,
                      strokeWidth: strokeWidth,
                      isTop: false,
                      isLeft: false,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _BracketPainter extends CustomPainter {
  final Color color;
  final double strokeWidth;
  final bool isTop;
  final bool isLeft;

  _BracketPainter({
    required this.color,
    required this.strokeWidth,
    required this.isTop,
    required this.isLeft,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final path = Path();
    final double startX = isLeft ? 0 : size.width;
    final double startY = isTop ? 0 : size.height;
    final double endX = isLeft ? size.width : 0;
    final double endY = isTop ? size.height : 0;

    // Horizontal arm
    path.moveTo(endX, startY);
    path.lineTo(startX, startY);
    // Vertical arm
    path.lineTo(startX, endY);

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _BracketPainter oldDelegate) =>
      color != oldDelegate.color ||
      strokeWidth != oldDelegate.strokeWidth ||
      isTop != oldDelegate.isTop ||
      isLeft != oldDelegate.isLeft;
}
