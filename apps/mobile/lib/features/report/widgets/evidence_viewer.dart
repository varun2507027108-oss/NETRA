import 'package:flutter/material.dart';
import '../../../core/bridge/bridge_models.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/util/bbox_painter.dart';
import '../../../core/util/image_pipeline.dart';

/// Evidence modal viewer highlighting a specific check's evidence_bbox over the captured image.
class EvidenceViewerDialog extends StatelessWidget {
  final CheckItem check;
  final ProcessedImage processedImage;

  const EvidenceViewerDialog({
    super.key,
    required this.check,
    required this.processedImage,
  });

  static void show(BuildContext context, {
    required CheckItem check,
    required ProcessedImage processedImage,
  }) {
    showDialog(
      context: context,
      builder: (context) => EvidenceViewerDialog(
        check: check,
        processedImage: processedImage,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (check.status) {
      CheckStatus.pass => AppColors.verdictGreen,
      CheckStatus.fail => AppColors.verdictRed,
      CheckStatus.na => AppColors.naSlate,
    };

    return Dialog(
      backgroundColor: Colors.white,
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppColors.monoBg,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Text(check.rule, style: AppTypography.monoSmall),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Evidence Context',
                    style: AppTypography.heading,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close, size: 20),
                  onPressed: () => Navigator.of(context).pop(),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Image Preview with Evidence BBox
            Container(
              decoration: BoxDecoration(
                color: Colors.black,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.border),
              ),
              clipBehavior: Clip.antiAlias,
              child: AspectRatio(
                aspectRatio: processedImage.width / processedImage.height,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Image.file(
                      processedImage.file,
                      fit: BoxFit.contain,
                    ),
                    if (check.evidenceBbox != null)
                      CustomPaint(
                        painter: BBoxPainter(
                          boxes: const [],
                          highlightBox: check.evidenceBbox,
                          highlightColor: statusColor,
                          imageWidth: processedImage.width,
                          imageHeight: processedImage.height,
                        ),
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),

            // Inspection Finding
            Text(
              check.plain.isNotEmpty ? check.plain : check.message,
              style: AppTypography.body.copyWith(fontWeight: FontWeight.w500),
            ),
            if (check.evidenceBbox != null) ...[
              const SizedBox(height: 4),
              Text(
                'Bounding Box: [${check.evidenceBbox!.x}, ${check.evidenceBbox!.y}, ${check.evidenceBbox!.w}, ${check.evidenceBbox!.h}]',
                style: AppTypography.monoSmall.copyWith(color: AppColors.inkSecondary),
              ),
            ],
            const SizedBox(height: 12),

            // Action
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Close'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
