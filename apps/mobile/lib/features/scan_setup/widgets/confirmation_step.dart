import 'package:flutter/material.dart';
import '../../../core/state/scan_session.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Step 3: Confirmation and Calibration Settings.
/// Summarizes selected parameters before entering live camera.
class ConfirmationStep extends StatefulWidget {
  final PackageShape shape;
  final String commodity;
  final String dimensionsSummary;
  final List<String> activeConditions;
  final TextEditingController fiducialController;
  final bool dossierOnPass;
  final ValueChanged<bool> onDossierOnPassChanged;

  const ConfirmationStep({
    super.key,
    required this.shape,
    required this.commodity,
    required this.dimensionsSummary,
    required this.activeConditions,
    required this.fiducialController,
    required this.dossierOnPass,
    required this.onDossierOnPassChanged,
  });

  @override
  State<ConfirmationStep> createState() => _ConfirmationStepState();
}

class _ConfirmationStepState extends State<ConfirmationStep> {
  bool _calibrationExpanded = false;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('INSPECTION PARAMETERS SUMMARY', style: AppTypography.sectionLabel),
        const SizedBox(height: 12),

        // Summary Card
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.border, width: 1),
          ),
          child: Column(
            children: [
              _buildSummaryRow('Commodity Name', widget.commodity.isNotEmpty ? widget.commodity : 'Unspecified'),
              const Divider(height: 16),
              _buildSummaryRow('Package Geometry', widget.shape.label),
              const Divider(height: 16),
              _buildSummaryRow('Dimensions Input', widget.dimensionsSummary),
              const Divider(height: 16),
              _buildSummaryRow(
                'Statutory Conditions',
                widget.activeConditions.isNotEmpty ? widget.activeConditions.join(', ') : 'Standard package',
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),

        // Dossier On Pass Checkbox
        Material(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(8),
          clipBehavior: Clip.antiAlias,
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: SwitchListTile(
              title: const Text('Generate Dossier on Pass', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: const Text(
                'By default dossiers are only generated on violations. Turn on to archive compliant scans too.',
                style: AppTypography.caption,
              ),
              value: widget.dossierOnPass,
              onChanged: widget.onDossierOnPassChanged,
              activeThumbColor: AppColors.navy,
              contentPadding: EdgeInsets.zero,
            ),
          ),
        ),
        const SizedBox(height: 20),

        // Expandable Fiducial Calibration
        Material(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(8),
          clipBehavior: Clip.antiAlias,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: ExpansionTile(
            initiallyExpanded: _calibrationExpanded,
            onExpansionChanged: (val) => setState(() => _calibrationExpanded = val),
            title: const Text(
              'OPTICAL CALIBRATION SETTINGS',
              style: AppTypography.sectionLabel,
            ),
            subtitle: const Text(
              'Default fiducial marker square size: 40.0 mm',
              style: AppTypography.caption,
            ),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            children: [
              const SizedBox(height: 8),
              TextField(
                controller: widget.fiducialController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'Fiducial Marker Size (mm)',
                  helperText: 'Standard NETRA calibration card is 40 mm',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
        ),
      ),
      const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildSummaryRow(String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: AppTypography.caption.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(width: 16),
        Expanded(
          child: Text(
            value,
            textAlign: TextAlign.right,
            style: AppTypography.body.copyWith(fontSize: 13),
          ),
        ),
      ],
    );
  }
}
