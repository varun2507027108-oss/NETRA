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
      constraints: const BoxConstraints(minHeight: 64),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: barColor,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Semantics(
        label: '$verdictText. $failCount failed checks, $passCount passed checks, $naCount not applicable checks.',
        child: Row(
        children: [
          Icon(
            verdict == Verdict.pass ? Icons.verified_outlined : verdict == Verdict.violation ? Icons.report_problem_outlined : Icons.refresh,
            color: Colors.white,
            size: 24,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(verdictText, style: AppTypography.verdictBanner),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.22),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  failCount > 0
                      ? '$failCount ${failCount == 1 ? "VIOLATION" : "VIOLATIONS"}'
                      : (verdict == Verdict.retry ? 'UNCLEAR' : 'ALL COMPLIANT'),
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.6,
                    color: Colors.white,
                  ),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '$passCount Compliant${naCount > 0 ? " · $naCount Exempt" : ""}',
                textAlign: TextAlign.right,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: Colors.white.withValues(alpha: 0.92),
                ),
              ),
            ],
          ),
        ],
      ),
      ),
    );
  }
}
