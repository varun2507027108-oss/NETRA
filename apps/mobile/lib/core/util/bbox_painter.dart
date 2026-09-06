import 'package:flutter/material.dart';
import '../bridge/bridge_models.dart';
import '../theme/app_colors.dart';

/// Paints evidence or OCR bounding boxes over an image.
/// Scales from submitted image pixel space to display canvas space.
class BBoxPainter extends CustomPainter {
  final List<BBox> boxes;
  final BBox? highlightBox;
  final int imageWidth;
  final int imageHeight;
  final Color defaultColor;
  final Color highlightColor;
  final bool flipY;

  BBoxPainter({
    required this.boxes,
    this.highlightBox,
    required this.imageWidth,
    required this.imageHeight,
    Color? defaultColor,
    this.highlightColor = AppColors.verdictRed,
    this.flipY = false,
  }) : defaultColor = defaultColor ?? AppColors.navy.withValues(alpha: 0.5);

  @override
  void paint(Canvas canvas, Size size) {
    if (imageWidth == 0 || imageHeight == 0) return;

    final double scaleX = size.width / imageWidth;
    final double scaleY = size.height / imageHeight;

    final defaultPaint = Paint()
      ..color = defaultColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    final highlightPaint = Paint()
      ..color = highlightColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;

    for (final box in boxes) {
      final double x = box.x * scaleX;
      final double y = flipY
          ? (imageHeight - (box.y + box.h)) * scaleY
          : box.y * scaleY;
      final double w = box.w * scaleX;
      final double h = box.h * scaleY;

      canvas.drawRect(Rect.fromLTWH(x, y, w, h), defaultPaint);
    }

    if (highlightBox != null) {
      final double x = highlightBox!.x * scaleX;
      final double y = flipY
          ? (imageHeight - (highlightBox!.y + highlightBox!.h)) * scaleY
          : highlightBox!.y * scaleY;
      final double w = highlightBox!.w * scaleX;
      final double h = highlightBox!.h * scaleY;

      canvas.drawRect(Rect.fromLTWH(x, y, w, h), highlightPaint);
    }
  }

  @override
  bool shouldRepaint(covariant BBoxPainter oldDelegate) {
    return oldDelegate.boxes != boxes ||
        oldDelegate.highlightBox != highlightBox ||
        oldDelegate.imageWidth != imageWidth ||
        oldDelegate.imageHeight != imageHeight ||
        oldDelegate.flipY != flipY;
  }
}
