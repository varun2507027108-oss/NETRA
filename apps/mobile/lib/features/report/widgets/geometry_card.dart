import 'package:flutter/material.dart';
import '../../../core/bridge/bridge_models.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Card showing package geometry & scale recovery (Brief §4).
/// Monospace values, detected shape, PDA, mm/px, and method.
class GeometryCard extends StatelessWidget {
  final Geometry geometry;

  const GeometryCard({super.key, required this.geometry});

  @override
  Widget build(BuildContext context) {
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
          const Text('PACKAGE GEOMETRY & SCALE', style: AppTypography.sectionLabel),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _buildMetric(
                  'SHAPE',
                  geometry.shape ?? geometry.shapeDetected ?? '—',
                ),
              ),
              Expanded(
                child: _buildMetric(
                  'SCALE (MM/PX)',
                  geometry.mmPerPx?.toStringAsFixed(4) ?? '—',
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _buildMetric(
                  'PDA (CM²)',
                  geometry.pdaCm2?.toStringAsFixed(1) ?? '—',
                ),
              ),
              Expanded(
                child: _buildMetric(
                  'METHOD',
                  geometry.pdaMethod ?? '—',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMetric(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppTypography.caption.copyWith(fontSize: 10)),
        const SizedBox(height: 2),
        Text(value, style: AppTypography.mono),
      ],
    );
  }
}
