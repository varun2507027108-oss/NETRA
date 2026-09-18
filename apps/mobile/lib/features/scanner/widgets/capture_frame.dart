import 'package:flutter/material.dart';

/// Corner-bracket viewfinder framing for package alignment.
class CaptureFrame extends StatelessWidget {
  final double aspectRatio;
  final Color bracketColor;
  final double bracketLength;
  final double strokeWidth;
  final bool showCenterGuide;
  final bool showFiducialGuide;

  const CaptureFrame({
    super.key,
    this.aspectRatio = 3 / 4,
    this.bracketColor = Colors.white70,
    this.bracketLength = 28.0,
    this.strokeWidth = 3.0,
    this.showCenterGuide = true,
    this.showFiducialGuide = true,
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
                // Center alignment reticle
                if (showCenterGuide) ...[
                  Center(
                    child: CustomPaint(
                      size: const Size(28, 28),
                      painter: _CenterCrosshairPainter(
                        color: bracketColor.withValues(alpha: 0.35),
                        strokeWidth: 1.5,
                      ),
                    ),
                  ),
                  // Edge center alignment notches (top, bottom, left, right)
                  Positioned(
                    top: 0,
                    left: width / 2 - 8,
                    child: CustomPaint(
                      size: const Size(16, 8),
                      painter: _EdgeTickPainter(color: bracketColor.withValues(alpha: 0.4), isVertical: true),
                    ),
                  ),
                  Positioned(
                    bottom: 0,
                    left: width / 2 - 8,
                    child: CustomPaint(
                      size: const Size(16, 8),
                      painter: _EdgeTickPainter(color: bracketColor.withValues(alpha: 0.4), isVertical: true),
                    ),
                  ),
                  Positioned(
                    left: 0,
                    top: height / 2 - 8,
                    child: CustomPaint(
                      size: const Size(8, 16),
                      painter: _EdgeTickPainter(color: bracketColor.withValues(alpha: 0.4), isVertical: false),
                    ),
                  ),
                  Positioned(
                    right: 0,
                    top: height / 2 - 8,
                    child: CustomPaint(
                      size: const Size(8, 16),
                      painter: _EdgeTickPainter(color: bracketColor.withValues(alpha: 0.4), isVertical: false),
                    ),
                  ),
                ],
                // Bottom-right Calibration Card guide
                if (showFiducialGuide)
                  Positioned(
                    bottom: 12,
                    right: 12,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.35),
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(
                          color: const Color(0xFFFFD54F).withValues(alpha: 0.7),
                          width: 1.2,
                        ),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.crop_square,
                            size: 14,
                            color: Color(0xFFFFD54F),
                          ),
                          SizedBox(width: 4),
                          Text(
                            'CARD (40mm)',
                            style: TextStyle(
                              color: Color(0xFFFFD54F),
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
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

class _EdgeTickPainter extends CustomPainter {
  final Color color;
  final bool isVertical;

  const _EdgeTickPainter({
    required this.color,
    required this.isVertical,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    if (isVertical) {
      canvas.drawLine(Offset(size.width / 2, 0), Offset(size.width / 2, size.height), paint);
    } else {
      canvas.drawLine(Offset(0, size.height / 2), Offset(size.width, size.height / 2), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _EdgeTickPainter oldDelegate) =>
      color != oldDelegate.color || isVertical != oldDelegate.isVertical;
}

class _CenterCrosshairPainter extends CustomPainter {
  final Color color;
  final double strokeWidth;

  const _CenterCrosshairPainter({
    required this.color,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = strokeWidth
      ..style = PaintingStyle.stroke;

    final cx = size.width / 2;
    final cy = size.height / 2;
    const arm = 9.0;

    canvas.drawLine(Offset(cx - arm, cy), Offset(cx + arm, cy), paint);
    canvas.drawLine(Offset(cx, cy - arm), Offset(cx, cy + arm), paint);
    canvas.drawCircle(Offset(cx, cy), 3, paint);
  }

  @override
  bool shouldRepaint(covariant _CenterCrosshairPainter oldDelegate) =>
      color != oldDelegate.color || strokeWidth != oldDelegate.strokeWidth;
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
