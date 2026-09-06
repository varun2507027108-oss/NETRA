import 'package:flutter/material.dart';
import '../../../core/bridge/bridge_models.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Card showing Rule 26 statutory exemption status (Brief §5.5).
/// Preserves and renders the exemption note text.
class ExemptionCard extends StatelessWidget {
  final Exemption exemption;

  const ExemptionCard({super.key, required this.exemption});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('RULE 26 EXEMPTION STATUS', style: AppTypography.sectionLabel),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: exemption.exempt ? AppColors.retryAmberBg : AppColors.monoBg,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: exemption.exempt ? AppColors.retryAmber : AppColors.border,
                    width: 1,
                  ),
                ),
                child: Text(
                  exemption.exempt ? 'EXEMPT' : 'NOT EXEMPT',
                  style: AppTypography.monoSmall.copyWith(
                    color: exemption.exempt ? AppColors.retryAmber : AppColors.ink,
                  ),
                ),
              ),
            ],
          ),
          if (exemption.clause != null) ...[
            const SizedBox(height: 6),
            Text('Clause: ${exemption.clause}', style: AppTypography.caption),
          ],
          if (exemption.note != null && exemption.note!.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              exemption.note!,
              style: AppTypography.body.copyWith(fontSize: 13),
            ),
          ],
        ],
      ),
    );
  }
}
