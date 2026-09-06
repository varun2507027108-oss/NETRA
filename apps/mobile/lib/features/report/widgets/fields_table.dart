import 'package:flutter/material.dart';
import '../../../core/bridge/bridge_models.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Table displaying extracted field declarations (Brief §5.5).
class FieldsTable extends StatelessWidget {
  final Map<String, FieldValue> fields;

  const FieldsTable({super.key, required this.fields});

  @override
  Widget build(BuildContext context) {
    if (fields.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.border, width: 1),
        ),
        child: const Text('No fields extracted.', style: AppTypography.body),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: Table(
        border: const TableBorder(
          horizontalInside: BorderSide(color: AppColors.border, width: 0.5),
        ),
        columnWidths: const {
          0: FlexColumnWidth(1.2),
          1: FlexColumnWidth(1.2),
          2: FlexColumnWidth(1.6),
          3: FlexColumnWidth(0.8),
        },
        children: [
          // Header row
          TableRow(
            decoration: const BoxDecoration(
              color: AppColors.monoBg,
              borderRadius: BorderRadius.vertical(top: Radius.circular(10)),
            ),
            children: [
              _buildCell('FIELD', isHeader: true),
              _buildCell('VALUE', isHeader: true),
              _buildCell('RAW OCR', isHeader: true),
              _buildCell('CONF', isHeader: true, alignRight: true),
            ],
          ),
          ...fields.entries.map((entry) {
            final f = entry.value;
            final val = f.value ?? '—';
            final unitStr = f.unit != null ? ' ${f.unit}' : '';
            return TableRow(
              children: [
                _buildCell(entry.key, isBold: true),
                _buildCell('$val$unitStr', isMono: true),
                _buildCell(f.raw, isSecondary: true),
                _buildCell('${(f.conf * 100).round()}%', isMono: true, alignRight: true),
              ],
            );
          }),
        ],
      ),
    );
  }

  Widget _buildCell(
    String text, {
    bool isHeader = false,
    bool isBold = false,
    bool isMono = false,
    bool isSecondary = false,
    bool alignRight = false,
  }) {
    TextStyle style = AppTypography.body;
    if (isHeader) {
      style = AppTypography.sectionLabel.copyWith(fontSize: 10);
    } else if (isMono) {
      style = AppTypography.monoSmall;
    } else if (isSecondary) {
      style = AppTypography.caption;
    } else if (isBold) {
      style = AppTypography.body.copyWith(fontWeight: FontWeight.w600);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Text(
        text,
        textAlign: alignRight ? TextAlign.right : TextAlign.left,
        style: style,
        maxLines: 2,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}
