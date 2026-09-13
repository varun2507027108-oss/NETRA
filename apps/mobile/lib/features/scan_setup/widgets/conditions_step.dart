import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Step 2: Statutory Conditions & Commodity.
/// Handles commodity title and Legal Metrology Rule toggles.
class ConditionsStep extends StatelessWidget {
  final TextEditingController commodityController;
  final bool blown;
  final ValueChanged<bool> onBlownChanged;
  final bool institutional;
  final ValueChanged<bool> onInstitutionalChanged;
  final bool fastFood;
  final ValueChanged<bool> onFastFoodChanged;
  final bool attachGps;
  final ValueChanged<bool> onAttachGpsChanged;

  const ConditionsStep({
    super.key,
    required this.commodityController,
    required this.blown,
    required this.onBlownChanged,
    required this.institutional,
    required this.onInstitutionalChanged,
    required this.fastFood,
    required this.onFastFoodChanged,
    required this.attachGps,
    required this.onAttachGpsChanged,
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('COMMODITY DECLARATION', style: AppTypography.sectionLabel),
        const SizedBox(height: 4),
        const Text(
          'Specific trade or general product identity to match against OCR findings.',
          style: AppTypography.caption,
        ),
        const SizedBox(height: 12),

        TextField(
          controller: commodityController,
          decoration: const InputDecoration(
            labelText: 'Commodity Name (optional)',
            hintText: 'e.g. Edible Oil, Coconut Oil, Wheat Flour',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 24),

        const Text('STATUTORY EXEMPTIONS & CONDITIONS', style: AppTypography.sectionLabel),
        const SizedBox(height: 4),
        const Text(
          'Enables legal exemptions under Legal Metrology Rules 2011.',
          style: AppTypography.caption,
        ),
        const SizedBox(height: 12),

        Material(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(10),
          clipBehavior: Clip.antiAlias,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.border, width: 1),
            ),
            child: Column(
            children: [
              SwitchListTile(
                title: const Text('Blown / Molded Container', style: AppTypography.body),
                subtitle: const Text(
                  'Second Proviso to Rule 9(1): Applies relaxed min font height schedule.',
                  style: AppTypography.caption,
                ),
                value: blown,
                onChanged: onBlownChanged,
              ),
              const Divider(height: 1),
              SwitchListTile(
                title: const Text('Institutional Consumer', style: AppTypography.body),
                subtitle: const Text(
                  'Rule 3: Non-retail supply exempt from retail MRP/consumer care requirements.',
                  style: AppTypography.caption,
                ),
                value: institutional,
                onChanged: onInstitutionalChanged,
              ),
              const Divider(height: 1),
              SwitchListTile(
                title: const Text('Fast Food / Restaurant Package', style: AppTypography.body),
                subtitle: const Text(
                  'Rule 26: Exemption for immediate service foods.',
                  style: AppTypography.caption,
                ),
                value: fastFood,
                onChanged: onFastFoodChanged,
              ),
              const Divider(height: 1),
              SwitchListTile(
                title: const Text('Attach GPS Coordinates', style: AppTypography.body),
                subtitle: const Text(
                  'Embeds geographical coordinates into the cryptographic evidence dossier.',
                  style: AppTypography.caption,
                ),
                value: attachGps,
                onChanged: onAttachGpsChanged,
              ),
            ],
          ),
        ),
      ),
    ],
  );
  }
}
