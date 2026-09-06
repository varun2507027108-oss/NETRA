import 'package:flutter/material.dart';
import '../../../core/bridge/bridge_models.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Full-width 56dp verdict bar with summary counts (Brief §4).
class VerdictBanner extends StatelessWidget {
  final Verdict verdict;
  final int passCount;
  final int failCount;
  final int naCount;

  const VerdictBanner({
    super.key,
    required this.verdict,
    required this.passCount,
    required this.failCount,
    required this.naCount,
  });

  @override
  Widget build(BuildContext context) {
    final Color barColor = switch (verdict) {
      Verdict.pass => AppColors.verdictGreen,
      Verdict.violation => AppColors.verdictRed,
      Verdict.retry => AppColors.retryAmber,
    };

    final String verdictText = switch (verdict) {
      Verdict.pass => 'PASS',
      Verdict.violation => 'VIOLATION',
      Verdict.retry => 'RETRY',
    };

    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: barColor,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(verdictText, style: AppTypography.verdictBanner),
          Text(
            '$failCount FAIL  /  $passCount PASS  /  $naCount NA',
            style: const TextStyle(
              fontFamily: 'monospace',
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: Colors.white,
            ),
          ),
        ],
      ),
    );
  }
}
