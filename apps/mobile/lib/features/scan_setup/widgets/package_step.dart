import 'package:flutter/material.dart';
import '../../../core/state/scan_session.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Step 1: Package Shape and Dimensions.
/// Shows dynamic dimension input fields relevant strictly to the chosen shape.
class PackageStep extends StatelessWidget {
  final PackageShape shape;
  final ValueChanged<PackageShape> onShapeChanged;
  final TextEditingController heightController;
  final TextEditingController widthController;
  final TextEditingController diameterController;
  final TextEditingController areaController;

  const PackageStep({
    super.key,
    required this.shape,
    required this.onShapeChanged,
    required this.heightController,
    required this.widthController,
    required this.diameterController,
    required this.areaController,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('PACKAGE SHAPE', style: AppTypography.sectionLabel),
        const SizedBox(height: 4),
        Text(
          'Select the container geometry to determine Rule 7 principal display area calculation.',
          style: AppTypography.caption,
        ),
        const SizedBox(height: 12),

        // Shape Selector Cards (spacious 2-column grid + other)
        _buildShapeSelector(),
        const SizedBox(height: 24),

        // Dynamic Dimension Fields
        Text('PACKAGE DIMENSIONS (CM)', style: AppTypography.sectionLabel),
        const SizedBox(height: 4),
        Text(
          'Optional field dimensions. If empty, the optical fiducial card will calibrate scale automatically.',
          style: AppTypography.caption,
        ),
        const SizedBox(height: 12),

        ..._buildDynamicDimensionFields(),
      ],
    );
  }

  List<Widget> _buildDynamicDimensionFields() {
    switch (shape) {
      case PackageShape.rectangular:
        return [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: heightController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Height (cm)',
                    hintText: 'e.g. 15.0',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: widthController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Width (cm)',
                    hintText: 'e.g. 10.0',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Rule 7(1)(a): PDA for rectangular package = Height × Width',
            style: AppTypography.caption,
          ),
        ];

      case PackageShape.cylindrical:
      case PackageShape.bottle:
        return [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: heightController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Height (cm)',
                    hintText: 'e.g. 20.0',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: diameterController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Diameter (cm)',
                    hintText: 'e.g. 7.5',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Rule 7(1)(b): PDA for cylindrical container = 40% of (Height × Circumference)',
            style: AppTypography.caption,
          ),
        ];

      case PackageShape.pouch:
      case PackageShape.other:
        return [
          TextField(
            controller: areaController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Total Surface Area (cm²)',
              hintText: 'e.g. 250.0',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Rule 7(1)(c): PDA for other shapes = Total Area',
            style: AppTypography.caption,
          ),
        ];
    }
  }

  Widget _buildShapeSelector() {
    return Column(
      children: [
        Row(
          children: [
            Expanded(child: _buildShapeCard(PackageShape.rectangular)),
            const SizedBox(width: 10),
            Expanded(child: _buildShapeCard(PackageShape.cylindrical)),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _buildShapeCard(PackageShape.pouch)),
            const SizedBox(width: 10),
            Expanded(child: _buildShapeCard(PackageShape.bottle)),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _buildShapeCard(PackageShape.other)),
          ],
        ),
      ],
    );
  }

  Widget _buildShapeCard(PackageShape s) {
    final isSelected = shape == s;
    return Material(
      color: isSelected ? AppColors.navy : AppColors.surface,
      borderRadius: BorderRadius.circular(10),
      elevation: isSelected ? 1 : 0,
      child: InkWell(
        onTap: () => onShapeChanged(s),
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isSelected ? AppColors.navy : AppColors.border,
              width: isSelected ? 1.5 : 1.0,
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                _iconForShape(s),
                size: 20,
                color: isSelected ? Colors.white : AppColors.navy,
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  s.label,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                    color: isSelected ? Colors.white : AppColors.ink,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (isSelected) ...[
                const SizedBox(width: 6),
                const Icon(Icons.check_circle_rounded, size: 16, color: Colors.white),
              ],
            ],
          ),
        ),
      ),
    );
  }

  IconData _iconForShape(PackageShape s) {
    switch (s) {
      case PackageShape.rectangular:
        return Icons.inventory_2_outlined;
      case PackageShape.cylindrical:
        return Icons.view_column_outlined;
      case PackageShape.pouch:
        return Icons.shopping_bag_outlined;
      case PackageShape.bottle:
        return Icons.local_drink_outlined;
      case PackageShape.other:
        return Icons.category_outlined;
    }
  }
}

