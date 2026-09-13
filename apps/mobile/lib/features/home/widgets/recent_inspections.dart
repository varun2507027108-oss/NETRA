import 'package:flutter/material.dart';
import 'package:netra/core/bridge/bridge_models.dart';
import 'package:netra/core/theme/app_colors.dart';
import 'package:netra/core/theme/app_typography.dart';
import 'package:netra/features/report/report_screen.dart';

/// Recent inspection card preview on HomeScreen.
class RecentInspectionsStrip extends StatelessWidget {
  final ScanResult? lastResult;

  const RecentInspectionsStrip({super.key, this.lastResult});

  @override
  Widget build(BuildContext context) {
    if (lastResult == null) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            const Icon(Icons.history, size: 20, color: AppColors.inkSecondary),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'No recent inspections in this session.',
                style: AppTypography.caption,
              ),
            ),
          ],
        ),
      );
    }

    final result = lastResult!;
    final Color verdictColor = switch (result.verdict) {
      Verdict.pass => AppColors.verdictGreen,
      Verdict.violation => AppColors.verdictRed,
      Verdict.retry => AppColors.retryAmber,
    };

    final Color verdictBg = switch (result.verdict) {
      Verdict.pass => AppColors.verdictGreenBg,
      Verdict.violation => AppColors.verdictRedBg,
      Verdict.retry => AppColors.retryAmberBg,
    };

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.border),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: () {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => ReportScreen(result: result)),
            );
          },
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: verdictBg,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: verdictColor.withValues(alpha: 0.5)),
                  ),
                  child: Text(
                    result.verdict.name.toUpperCase(),
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: verdictColor,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        result.scanId.isEmpty ? 'INSPECTION' : result.scanId,
                        style: AppTypography.monoSmall.copyWith(fontWeight: FontWeight.w600),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Pass: ${result.summary.pass} • Fail: ${result.summary.fail} • NA: ${result.summary.na}',
                        style: AppTypography.caption,
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.chevron_right, size: 20, color: AppColors.inkSecondary),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
