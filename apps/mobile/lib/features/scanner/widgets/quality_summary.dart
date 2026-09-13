import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Summary card displaying key capture quality checks: sharpness, lighting, fiducial marker.
class QualitySummaryCard extends StatelessWidget {
  final bool qualityOk;
  final bool markerDetected;
  final double? mmPerPx;
  final List<String> prompts;

  const QualitySummaryCard({
    super.key,
    required this.qualityOk,
    required this.markerDetected,
    this.mmPerPx,
    this.prompts = const [],
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: qualityOk ? Colors.white : AppColors.retryAmberBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: qualityOk ? AppColors.border : AppColors.retryAmber,
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'CAPTURE QUALITY CHECK',
                style: AppTypography.sectionLabel.copyWith(
                  color: qualityOk ? AppColors.navy : AppColors.retryAmber,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: qualityOk ? AppColors.verdictGreenBg : AppColors.retryAmberBg,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: qualityOk ? AppColors.verdictGreen : AppColors.retryAmber,
                    width: 1,
                  ),
                ),
                child: Text(
                  qualityOk ? 'PASSED' : 'ACTION REQUIRED',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: qualityOk ? AppColors.verdictGreen : AppColors.retryAmber,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildCheckRow(
            label: 'Image Clarity & Sharpness',
            ok: qualityOk,
            detail: qualityOk ? 'Adequate contrast & sharpness' : 'Blur/contrast issues detected',
          ),
          const SizedBox(height: 8),
          _buildCheckRow(
            label: 'Lighting & Glare',
            ok: qualityOk,
            detail: qualityOk ? 'No specular saturation' : 'Specular reflections present',
          ),
          const SizedBox(height: 8),
          _buildCheckRow(
            label: 'Fiducial Scale Reference',
            ok: markerDetected,
            detail: markerDetected
                ? 'Detected (${mmPerPx?.toStringAsFixed(3)} mm/px)'
                : 'Not found (Font height checks marked N/A)',
          ),
          if (prompts.isNotEmpty) ...[
            const Divider(height: 20),
            Text(
              'Recommendations:',
              style: AppTypography.caption.copyWith(fontWeight: FontWeight.w600, color: AppColors.ink),
            ),
            const SizedBox(height: 4),
            ...prompts.map(
              (p) => Padding(
                padding: const EdgeInsets.only(left: 4, top: 2),
                child: Text(
                  '• $p',
                  style: AppTypography.caption.copyWith(color: AppColors.inkSecondary),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCheckRow({
    required String label,
    required bool ok,
    required String detail,
  }) {
    return Row(
      children: [
        Icon(
          ok ? Icons.check_circle : Icons.warning_amber_rounded,
          size: 16,
          color: ok ? AppColors.verdictGreen : AppColors.retryAmber,
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
              ),
              Text(
                detail,
                style: AppTypography.monoSmall.copyWith(
                  fontSize: 10,
                  color: AppColors.inkSecondary,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
