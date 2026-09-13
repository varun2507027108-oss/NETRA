import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Expandable technical diagnostics accordion for OCR tokens and prepass metrics.
class TechnicalDetailsTile extends StatelessWidget {
  final int tokenCount;
  final int imageWidth;
  final int imageHeight;
  final String packageShape;
  final double? mmPerPx;
  final double? tiltDeg;
  final int? roiCount;
  final bool showOcrBoxes;
  final ValueChanged<bool> onToggleOcrBoxes;

  const TechnicalDetailsTile({
    super.key,
    required this.tokenCount,
    required this.imageWidth,
    required this.imageHeight,
    required this.packageShape,
    this.mmPerPx,
    this.tiltDeg,
    this.roiCount,
    required this.showOcrBoxes,
    required this.onToggleOcrBoxes,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          iconColor: AppColors.navy,
          collapsedIconColor: AppColors.inkSecondary,
          title: Text(
            'Technical & Vision Diagnostics',
            style: AppTypography.caption.copyWith(fontWeight: FontWeight.w600, color: AppColors.ink),
          ),
          subtitle: Text(
            '$tokenCount tokens • $imageWidth×$imageHeight px • $packageShape',
            style: AppTypography.monoSmall.copyWith(color: AppColors.inkSecondary),
          ),
          childrenPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          children: [
            const Divider(height: 1),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Visual OCR Bounding Boxes', style: TextStyle(fontSize: 12)),
                Switch(
                  value: showOcrBoxes,
                  onChanged: onToggleOcrBoxes,
                  activeThumbColor: AppColors.navy,
                ),
              ],
            ),
            const SizedBox(height: 6),
            _buildRow('Resolution', '$imageWidth×$imageHeight px'),
            _buildRow('OCR Tokens Detected', '$tokenCount tokens'),
            _buildRow('Package Shape Mode', packageShape),
            if (mmPerPx != null)
              _buildRow('Pixel Scale (mm/px)', mmPerPx!.toStringAsFixed(4)),
            if (tiltDeg != null)
              _buildRow('Surface Tilt Angle', '${tiltDeg!.toStringAsFixed(1)}°'),
            if (roiCount != null)
              _buildRow('YOLO ROI Detections', '$roiCount boxes'),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _buildRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: AppTypography.caption.copyWith(color: AppColors.inkSecondary),
          ),
          Text(
            value,
            style: AppTypography.monoSmall.copyWith(fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
