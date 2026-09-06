import 'package:flutter/material.dart';
import '../../../core/bridge/bridge_models.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Single statutory check card (Brief §4).
/// [status dot 8dp] [rule chip e.g. "6(1)"] [status word]
/// Message / Expandable "Statutory basis ▾" citation.
class CheckTile extends StatefulWidget {
  final CheckItem check;

  const CheckTile({super.key, required this.check});

  @override
  State<CheckTile> createState() => _CheckTileState();
}

class _CheckTileState extends State<CheckTile> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (widget.check.status) {
      CheckStatus.pass => AppColors.verdictGreen,
      CheckStatus.fail => AppColors.verdictRed,
      CheckStatus.na => AppColors.naSlate,
    };

    final statusBg = switch (widget.check.status) {
      CheckStatus.pass => AppColors.verdictGreenBg,
      CheckStatus.fail => AppColors.verdictRedBg,
      CheckStatus.na => AppColors.naSlateBg,
    };

    final statusLabel = switch (widget.check.status) {
      CheckStatus.pass => 'PASS',
      CheckStatus.fail => 'FAIL',
      CheckStatus.na => 'NA',
    };

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row: status dot + rule chip + status word
          Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: statusColor,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.monoBg,
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: AppColors.border, width: 1),
                ),
                child: Text(
                  widget.check.rule,
                  style: AppTypography.monoSmall,
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: statusBg,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  statusLabel,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: statusColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Message
          Text(
            widget.check.message,
            style: AppTypography.body,
          ),
          const SizedBox(height: 4),

          // Statutory citation expander
          if (widget.check.citation.isNotEmpty) ...[
            InkWell(
              onTap: () => setState(() => _expanded = !_expanded),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _expanded ? 'Statutory basis ▴' : 'Statutory basis ▾',
                    style: AppTypography.caption.copyWith(
                      color: AppColors.navy,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            if (_expanded) ...[
              const SizedBox(height: 4),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.monoBg,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  widget.check.citation,
                  style: AppTypography.caption,
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
