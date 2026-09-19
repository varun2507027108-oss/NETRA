import 'package:flutter/material.dart';
import '../../../core/bridge/bridge_models.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Single statutory check card (Brief §4).
/// [status dot 8dp] [rule chip e.g. "6(1)"] [status word]
/// Message / Expandable "Statutory basis ▾" citation / "View evidence →" link.
class CheckTile extends StatefulWidget {
  final CheckItem check;
  final VoidCallback? onEvidenceTap;

  const CheckTile({
    super.key,
    required this.check,
    this.onEvidenceTap,
  });

  @override
  State<CheckTile> createState() => _CheckTileState();
}

class _CheckTileState extends State<CheckTile> {
  bool _expanded = false;

  String _getRuleTitle(String rule) {
    final clean = rule.trim();
    return switch (clean) {
      '6(1)(a)' => 'Manufacturer Address',
      '6(1)(aa)' => 'Country of Origin',
      '6(1)(b)' => 'Commodity Name',
      '6(1)(c)' => 'Net Quantity',
      '6(1)(d)' => 'Date of Mfg / Packing',
      '6(1)(e)' => 'Retail Price (MRP)',
      '6(1)(n)' => 'Consumer Care',
      '6(11)' => 'Unit Sale Price (USP)',
      '7' => 'Minimum Font Height',
      '7(3)' => 'Letter Width Ratio',
      '13' => 'Metric Unit Symbol',
      '26' => 'Statutory Exemption',
      _ => 'Rule $clean',
    };
  }

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
      CheckStatus.pass => 'COMPLIANT',
      CheckStatus.fail => 'VIOLATION',
      CheckStatus.na => 'EXEMPT',
    };

    final bool hasEvidence = widget.check.evidenceBbox != null && widget.onEvidenceTap != null;
    final rawText = widget.check.plain.isNotEmpty ? widget.check.plain : widget.check.message;
    final cleanText = rawText
        .replaceAll("'{missing}'", "'inclusive of all taxes' is missing")
        .replaceAll("{missing}", "required wording is missing");

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: widget.check.status == CheckStatus.fail
              ? AppColors.verdictRed.withValues(alpha: 0.5)
              : AppColors.border,
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row: status dot + human title + rule code + status badge + optional evidence
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
              Expanded(
                child: Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 6,
                  children: [
                    Text(
                      _getRuleTitle(widget.check.rule),
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: AppColors.ink,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1.5),
                      decoration: BoxDecoration(
                        color: AppColors.monoBg,
                        borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: AppColors.border, width: 0.8),
                      ),
                      child: Text(
                        'Rule ${widget.check.rule}',
                        style: AppTypography.monoSmall.copyWith(fontSize: 10),
                      ),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2.5),
                decoration: BoxDecoration(
                  color: statusBg,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  statusLabel,
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.4,
                    color: statusColor,
                  ),
                ),
              ),
              if (hasEvidence) ...[
                const SizedBox(width: 6),
                InkWell(
                  onTap: widget.onEvidenceTap,
                  borderRadius: BorderRadius.circular(4),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.crop_free, size: 13, color: AppColors.navy),
                        const SizedBox(width: 3),
                        Text(
                          'Evidence →',
                          style: AppTypography.caption.copyWith(
                            color: AppColors.navy,
                            fontWeight: FontWeight.w600,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 8),

          // Primary text: Plain language inspector voice
          Text(
            cleanText,
            style: AppTypography.body,
          ),
          const SizedBox(height: 6),

          // Details expander: Statutory message + citation
          if (widget.check.citation.isNotEmpty || widget.check.message.isNotEmpty) ...[
            InkWell(
              onTap: () => setState(() => _expanded = !_expanded),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _expanded ? 'Details ▴' : 'Details ▾',
                    style: AppTypography.caption.copyWith(
                      color: AppColors.navy,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
            if (_expanded) ...[
              const SizedBox(height: 6),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.monoBg,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (widget.check.message != widget.check.plain) ...[
                      Text(
                        'Inspection Finding:',
                        style: AppTypography.caption.copyWith(
                          fontWeight: FontWeight.w600,
                          color: AppColors.inkSecondary,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        widget.check.message,
                        style: AppTypography.caption,
                      ),
                      const SizedBox(height: 6),
                    ],
                    if (widget.check.citation.isNotEmpty) ...[
                      Text(
                        'Legal Basis:',
                        style: AppTypography.caption.copyWith(
                          fontWeight: FontWeight.w600,
                          color: AppColors.inkSecondary,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        widget.check.citation,
                        style: AppTypography.caption,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ],
        ],
      ),
    );
  }
}
