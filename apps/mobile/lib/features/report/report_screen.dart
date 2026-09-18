import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/bridge/bridge_models.dart';
import '../../core/state/bridge_provider.dart';
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
class ReportScreen extends ConsumerStatefulWidget {
  final ScanResult result;

  const ReportScreen({super.key, required this.result});

  @override
  ConsumerState<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends ConsumerState<ReportScreen> {
  SigStatus? _signatureStatus;
  bool _signing = false;
  bool _syncing = false;
  String? _actionMessage;

  ScanResult get result => widget.result;

  @override
  void initState() {
    super.initState();
    _signatureStatus = result.dossier?.sigStatus;
    if (result.dossier?.sigStatus == SigStatus.pending) _signEvidence();
  }

  Future<void> _signEvidence() async {
    if (_signing || result.dossier == null || _signatureStatus == SigStatus.signed) return;
    setState(() => _signing = true);
    try {
      final response = await ref.read(netraBridgeProvider).signAndAttach(result.toJson());
      if (!mounted) return;
      setState(() {
        _signatureStatus = response.sigStatus;
        _actionMessage = response.accepted
            ? 'Evidence signed on this device. It remains queued until sync completes.'
            : 'Evidence was not signed: ${response.error?.message ?? 'retry or contact technical operations.'}';
      });
      await ref.read(queueStatusProvider.notifier).refresh();
    } catch (_) {
      if (mounted) setState(() => _actionMessage = 'Evidence signing could not be completed. The dossier remains stored locally and unsigned.');
    } finally {
      if (mounted) setState(() => _signing = false);
    }
  }

  Future<void> _syncQueue() async {
    if (_syncing) return;
    setState(() => _syncing = true);
    try {
      final summary = await ref.read(netraBridgeProvider).syncNow();
      if (!mounted) return;
      setState(() => _actionMessage = summary.error != null
          ? 'Sync deferred: ${summary.error}. Evidence remains queued on this device.'
          : 'Sync complete: ${summary.synced} sent; ${summary.remaining} record(s) remain queued.');
      await ref.read(queueStatusProvider.notifier).refresh();
    } catch (_) {
      if (mounted) setState(() => _actionMessage = 'Sync could not start. Evidence remains safely queued on this device.');
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  Future<void> _verifyDossierCopy() async {
    final dossier = result.dossier;
    if (dossier == null) return;
    try {
      final file = await ref.read(netraBridgeProvider).getDossier(result.scanId);
      if (!mounted) return;
      if (file.error != null) {
        setState(() => _actionMessage = 'Dossier could not be retrieved: ${file.error!.message}');
        return;
      }
      final valid = sha256.convert(base64Decode(file.pdfB64)).toString() == dossier.sha256;
      setState(() => _actionMessage = valid
          ? 'The retrieved dossier matches its recorded SHA-256 fingerprint.'
          : 'Dossier integrity check failed. Do not use this record; contact technical operations.');
    } catch (_) {
      if (mounted) setState(() => _actionMessage = 'Dossier verification could not be completed. Try again while the record is available locally.');
    }
  }

  void _copyStatutorySummary() {
    final buffer = StringBuffer();
    buffer.writeln('========================================');
    buffer.writeln('NETRA LEGAL METROLOGY INSPECTION RECORD');
    buffer.writeln('========================================');
    buffer.writeln('Scan ID: ${result.scanId}');
    buffer.writeln('Timestamp: ${result.timestampUtc} (UTC)');
    if (result.commodity.isNotEmpty) {
      buffer.writeln('Commodity: ${result.commodity}');
    }
    buffer.writeln('Package Shape: ${result.shape}');
    buffer.writeln('Inspection Verdict: ${result.verdict.name.toUpperCase()}');
    buffer.writeln();

    buffer.writeln('STATUTORY RULES COMPLIANCE:');
    for (final check in result.checks) {
      final statusStr = check.status.name.toUpperCase();
      buffer.writeln('• ${check.rule}: $statusStr - ${check.description}');
      if (check.detail != null && check.detail!.isNotEmpty) {
        buffer.writeln('  Detail: ${check.detail}');
      }
    }
    buffer.writeln();

    if (result.dossier != null) {
      buffer.writeln('EVIDENCE DOSSIER:');
      buffer.writeln('SHA-256: ${result.dossier!.sha256}');
      buffer.writeln('Signature: ${result.dossier!.sigStatus.name.toUpperCase()}');
      buffer.writeln('Queue ID: ${result.dossier!.queueId}');
    }
    buffer.writeln('========================================');

    Clipboard.setData(ClipboardData(text: buffer.toString()));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Statutory notice summary copied to clipboard for Panchnama/Memo.'),
        duration: Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
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

          if (_actionMessage != null) ...[
            _buildLifecycleMessage(),
            const SizedBox(height: 16),
          ],

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
              'RETURN TO INSPECTION HOME',
              style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 0.5),
            ),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            icon: const Icon(Icons.copy_all, size: 18),
            style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 12),
              side: const BorderSide(color: AppColors.navy, width: 1.2),
            ),
            onPressed: _copyStatutorySummary,
            label: const Text(
              'COPY STATUTORY NOTICE SUMMARY (PANCHNAMA)',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: AppColors.navy),
            ),
          ),
          if (result.dossier != null) ...[
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _signatureStatus == SigStatus.signed || _signing ? null : _signEvidence,
              icon: _signing
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.draw_outlined),
              label: Text(_signatureStatus == SigStatus.signed ? 'EVIDENCE SIGNED' : 'SIGN EVIDENCE'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _syncing ? null : _syncQueue,
              icon: _syncing
                  ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.sync),
              label: const Text('SYNC QUEUED RECORDS'),
            ),
          ],
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _buildLifecycleMessage() {
    final isProblem = _actionMessage!.contains('not ') ||
        _actionMessage!.contains('could not') ||
        _actionMessage!.contains('failed') ||
        _actionMessage!.contains('deferred');
    final color = isProblem ? AppColors.retryAmber : AppColors.verdictGreen;
    final background = isProblem ? AppColors.retryAmberBg : AppColors.verdictGreenBg;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color),
      ),
      child: Row(
        children: [
          Icon(isProblem ? Icons.info_outline : Icons.verified_outlined, color: color),
          const SizedBox(width: 8),
          Expanded(child: Text(_actionMessage!, style: AppTypography.caption.copyWith(color: AppColors.ink))),
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

    final effectiveStatus = _signatureStatus ?? dossier.sigStatus;
    final Color badgeColor = effectiveStatus == SigStatus.signed
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
                  _signing ? 'SIGNING' : effectiveStatus.name.toUpperCase(),
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
          const SizedBox(height: 6),
          TextButton.icon(
            onPressed: _verifyDossierCopy,
            icon: const Icon(Icons.verified_user_outlined, size: 16),
            label: const Text('Verify local dossier copy'),
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
