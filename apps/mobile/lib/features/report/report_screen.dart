import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/bridge/bridge_models.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import 'widgets/verdict_banner.dart';
import 'widgets/check_tile.dart';
import 'widgets/fields_table.dart';
import 'widgets/geometry_card.dart';
import 'widgets/exemption_card.dart';
import 'widgets/evidence_viewer.dart';

/// Complete Report Screen (Brief §5.5).
/// Renders statutory inspection results with verdict-first hierarchy and evidence linkage.
class ReportScreen extends ConsumerWidget {
  final ScanResult result;

  const ReportScreen({super.key, required this.result});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final processedImage = ref.watch(scanSessionProvider).processedImage;

    // Split checks into failed/actionable vs passed/na for instant inspector triage
    final failedChecks = result.checks.where((c) => c.status == CheckStatus.fail).toList();
    final otherChecks = result.checks.where((c) => c.status != CheckStatus.fail).toList();

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
          // 1. Verdict Banner & Statutory Summary (Immediate primary answer)
          VerdictBanner(
            verdict: result.verdict,
            passCount: result.summary.pass,
            failCount: result.summary.fail,
            naCount: result.summary.na,
          ),
          const SizedBox(height: 16),

          // 2. RETRY / In-Band Error Guidance (if applicable)
          if (result.verdict == Verdict.retry || result.error != null) ...[
            _buildRetryGuidanceCard(context),
            const SizedBox(height: 16),
          ],

          // 3. Failed Checks / Violations Section (Highlight what needs attention)
          if (failedChecks.isNotEmpty) ...[
            Row(
              children: [
                const Icon(Icons.error_outline, size: 16, color: AppColors.verdictRed),
                const SizedBox(width: 6),
                Text(
                  'STATUTORY VIOLATIONS DETECTED (${failedChecks.length})',
                  style: AppTypography.sectionLabel.copyWith(color: AppColors.verdictRed),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ...failedChecks.map((check) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: CheckTile(
                    check: check,
                    onEvidenceTap: processedImage != null && check.evidenceBbox != null
                        ? () => EvidenceViewerDialog.show(
                              context,
                              check: check,
                              processedImage: processedImage,
                            )
                        : null,
                  ),
                )),
            const SizedBox(height: 16),
          ],

          // 4. All Other Statutory Checks
          if (otherChecks.isNotEmpty) ...[
            Text(
              failedChecks.isNotEmpty
                  ? 'COMPLIANT & EXEMPT CHECKS (${otherChecks.length})'
                  : 'STATUTORY DECLARATION AUDIT',
              style: AppTypography.sectionLabel,
            ),
            const SizedBox(height: 8),
            ...otherChecks.map((check) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: CheckTile(
                    check: check,
                    onEvidenceTap: processedImage != null && check.evidenceBbox != null
                        ? () => EvidenceViewerDialog.show(
                              context,
                              check: check,
                              processedImage: processedImage,
                            )
                        : null,
                  ),
                )),
            const SizedBox(height: 16),
          ],

          // 5. Extracted Fields Table
          const Text('EXTRACTED FIELD DECLARATIONS', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          FieldsTable(fields: result.fields),
          const SizedBox(height: 16),

          // 6. Dossier Card (if present)
          if (result.dossier != null) ...[
            _buildDossierCard(context, result.dossier!),
            const SizedBox(height: 16),
          ],

          // 7. Geometry Card (if present)
          if (result.geometry != null) ...[
            GeometryCard(geometry: result.geometry!),
            const SizedBox(height: 16),
          ],

          // 8. Exemption Card (if present)
          if (result.exemption != null) ...[
            ExemptionCard(exemption: result.exemption!),
            const SizedBox(height: 16),
          ],

          // 9. Processing & Audit Details (Scan ID, Captures UTC, Pipeline Timings)
          _buildInspectionMetadataAccordion(),
          const SizedBox(height: 24),

          // 10. Complete Inspection Action
          ElevatedButton.icon(
            icon: const Icon(Icons.check_circle_outline, size: 20),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.navy,
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
            label: const Text(
              'COMPLETE INSPECTION',
              style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 0.5),
            ),
          ),
          const SizedBox(height: 20),
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
            Text(
              'Error code: ${err.code}${err.stage != null ? " (${err.stage})" : ""}',
              style: AppTypography.monoSmall,
            ),
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

  Widget _buildInspectionMetadataAccordion() {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border, width: 1),
      ),
      child: ExpansionTile(
        title: const Text('PROCESSING DETAILS & TIMINGS', style: AppTypography.sectionLabel),
        subtitle: Text(
          'Scan ID: ${result.scanId.isEmpty ? "UNASSIGNED" : result.scanId} • ${result.totalMs.toStringAsFixed(1)} ms',
          style: AppTypography.monoSmall.copyWith(color: AppColors.inkSecondary),
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
        children: [
          Row(
            children: [
              const Text('Captured UTC: ', style: AppTypography.caption),
              Text(result.capturedUtc, style: AppTypography.monoSmall),
            ],
          ),
          const SizedBox(height: 10),
          const Divider(height: 1),
          const SizedBox(height: 8),
          const Text('Pipeline Stage Timings', style: AppTypography.caption),
          const SizedBox(height: 6),
          Table(
            columnWidths: const {
              0: FlexColumnWidth(2),
              1: FlexColumnWidth(1),
            },
            children: result.timingsMs.entries.map((entry) {
              return TableRow(
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Text(entry.key, style: AppTypography.body.copyWith(fontSize: 13)),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
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
