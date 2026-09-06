import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../core/bridge/bridge_models.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import 'widgets/verdict_banner.dart';
import 'widgets/check_tile.dart';
import 'widgets/fields_table.dart';
import 'widgets/geometry_card.dart';
import 'widgets/exemption_card.dart';

/// Complete Report Screen (Brief §5.5).
/// Renders statutory inspection results with full evidentiary detail.
class ReportScreen extends StatelessWidget {
  final ScanResult result;

  const ReportScreen({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Inspection Report'),
        actions: [
          IconButton(
            icon: const Icon(Icons.copy, size: 20),
            tooltip: 'Copy Scan ID',
            onPressed: () {
              Clipboard.setData(ClipboardData(text: result.scanId));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Scan ID copied to clipboard'),
                  duration: Duration(seconds: 2),
                ),
              );
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        children: [
          // 1. Report Header: Scan ID + Timestamps
          Container(
            padding: const EdgeInsets.all(12),
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
                    const Text('SCAN IDENTIFIER', style: AppTypography.sectionLabel),
                    Text(
                      '${result.totalMs.toStringAsFixed(1)} ms',
                      style: AppTypography.monoSmall.copyWith(color: AppColors.navy),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                SelectableText(
                  result.scanId.isEmpty ? 'UNASSIGNED' : result.scanId,
                  style: AppTypography.mono.copyWith(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Text('Captured UTC: ', style: AppTypography.caption),
                    Text(result.capturedUtc, style: AppTypography.monoSmall),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // 2. Verdict Banner & Summary Strip
          VerdictBanner(
            verdict: result.verdict,
            passCount: result.summary.pass,
            failCount: result.summary.fail,
            naCount: result.summary.na,
          ),
          const SizedBox(height: 16),

          // 3. RETRY / In-Band Error Guidance (if applicable)
          if (result.verdict == Verdict.retry || result.error != null) ...[
            _buildRetryGuidanceCard(context),
            const SizedBox(height: 16),
          ],

          // 4. Dossier Card (if present)
          if (result.dossier != null) ...[
            _buildDossierCard(context, result.dossier!),
            const SizedBox(height: 16),
          ],

          // 5. Geometry Card (if present)
          if (result.geometry != null) ...[
            GeometryCard(geometry: result.geometry!),
            const SizedBox(height: 16),
          ],

          // 6. Exemption Card (if present)
          if (result.exemption != null) ...[
            ExemptionCard(exemption: result.exemption!),
            const SizedBox(height: 16),
          ],

          // 7. Statutory Checks List
          const Text('STATUTORY DECLARATION AUDIT', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          if (result.checks.isEmpty)
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.border, width: 1),
              ),
              child: const Text('No checks evaluated.', style: AppTypography.body),
            )
          else
            ...result.checks.map((check) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: CheckTile(check: check),
                )),
          const SizedBox(height: 16),

          // 8. Extracted Fields Table
          const Text('EXTRACTED FIELD DECLARATIONS', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          FieldsTable(fields: result.fields),
          const SizedBox(height: 16),

          // 9. Engine Timings Expander
          _buildTimingsExpander(),
          const SizedBox(height: 24),

          // 10. Actions
          ElevatedButton(
            onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
            child: const Text('Complete Inspection'),
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildRetryGuidanceCard(BuildContext context) {
    final List<String> prompts = result.quality.prompts;
    final err = result.error;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.retryAmberBg,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.retryAmber, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.info_outline, color: AppColors.retryAmber, size: 20),
              const SizedBox(width: 8),
              Text(
                err != null ? 'CAPTURE AUDIT ERROR' : 'INSPECTION RETRY REQUIRED',
                style: AppTypography.heading.copyWith(color: AppColors.retryAmber),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (err != null) ...[
            Text(
              err.message,
              style: AppTypography.body.copyWith(fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 4),
            Text('Error code: ${err.code}${err.stage != null ? " (${err.stage})" : ""}',
                style: AppTypography.monoSmall),
          ],
          if (prompts.isNotEmpty) ...[
            const SizedBox(height: 8),
            const Text('Quality prompts:', style: AppTypography.caption),
            const SizedBox(height: 4),
            ...prompts.map((p) => Padding(
                  padding: const EdgeInsets.only(left: 8, bottom: 2),
                  child: Text('• $p', style: AppTypography.body),
                )),
          ],
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Retake Photo'),
          ),
        ],
      ),
    );
  }

  Widget _buildDossierCard(BuildContext context, Dossier dossier) {
    final String shortSha = dossier.sha256.length > 16
        ? '${dossier.sha256.substring(0, 16)}...'
        : dossier.sha256;

    final Color badgeColor = dossier.sigStatus == SigStatus.signed
        ? AppColors.verdictGreen
        : AppColors.retryAmber;

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
              const Text('EVIDENCE DOSSIER (PDF/A)', style: AppTypography.sectionLabel),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: badgeColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: badgeColor, width: 1),
                ),
                child: Text(
                  dossier.sigStatus.name.toUpperCase(),
                  style: AppTypography.monoSmall.copyWith(color: badgeColor),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Text('SHA-256: ', style: AppTypography.caption),
              Expanded(
                child: Text(shortSha, style: AppTypography.monoSmall),
              ),
              IconButton(
                icon: const Icon(Icons.copy, size: 16),
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: dossier.sha256));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Dossier SHA-256 copied')),
                  );
                },
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildTimingsExpander() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: ExpansionTile(
        title: const Text('PIPELINE STAGE TIMINGS', style: AppTypography.sectionLabel),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          Table(
            columnWidths: const {
              0: FlexColumnWidth(2),
              1: FlexColumnWidth(1),
            },
            children: result.timingsMs.entries.map((entry) {
              return TableRow(
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Text(entry.key, style: AppTypography.body),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Text(
                      '${entry.value.toStringAsFixed(1)} ms',
                      textAlign: TextAlign.right,
                      style: AppTypography.monoSmall,
                    ),
                  ),
                ],
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
