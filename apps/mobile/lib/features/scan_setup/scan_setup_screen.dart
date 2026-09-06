import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../scanner/scanner_screen.dart';

/// Scan Setup Screen (Brief §5.2).
/// All inspector options:
/// - Package shape segmented control
/// - Dimensions per shape (height, width, diameter, total area)
/// - Commodity name
/// - Toggles: Blown/molded print, Institutional supply, Fast food, Dossier on PASS, Attach GPS
/// - Advanced: Fiducial marker size (mm)
class ScanSetupScreen extends ConsumerStatefulWidget {
  const ScanSetupScreen({super.key});

  @override
  ConsumerState<ScanSetupScreen> createState() => _ScanSetupScreenState();
}

class _ScanSetupScreenState extends ConsumerState<ScanSetupScreen> {
  late PackageShape _shape;
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _widthController = TextEditingController();
  final TextEditingController _diameterController = TextEditingController();
  final TextEditingController _areaController = TextEditingController();
  final TextEditingController _commodityController = TextEditingController();
  final TextEditingController _fiducialController = TextEditingController(text: '40');

  bool _blown = false;
  bool _institutional = false;
  bool _fastFood = false;
  bool _dossierOnPass = false;
  bool _attachGps = true;
  bool _calibrationExpanded = false;

  @override
  void initState() {
    super.initState();
    final cfg = ref.read(scanSessionProvider).config;
    _shape = cfg.shape;
    _blown = cfg.blown;
    _institutional = cfg.institutional;
    _fastFood = cfg.fastFood;
    _dossierOnPass = cfg.dossierOnPass;
    _attachGps = cfg.attachGps;
    _commodityController.text = cfg.commodity;
    if (cfg.heightCm != null) _heightController.text = cfg.heightCm.toString();
    if (cfg.widthCm != null) _widthController.text = cfg.widthCm.toString();
    if (cfg.diameterCm != null) _diameterController.text = cfg.diameterCm.toString();
    if (cfg.totalSurfaceAreaCm2 != null) _areaController.text = cfg.totalSurfaceAreaCm2.toString();
    _fiducialController.text = cfg.fiducialMm.toString();
  }

  @override
  void dispose() {
    _heightController.dispose();
    _widthController.dispose();
    _diameterController.dispose();
    _areaController.dispose();
    _commodityController.dispose();
    _fiducialController.dispose();
    super.dispose();
  }

  void _onStartCamera() {
    final double? h = double.tryParse(_heightController.text);
    final double? w = double.tryParse(_widthController.text);
    final double? d = double.tryParse(_diameterController.text);
    final double? a = double.tryParse(_areaController.text);
    final double fid = double.tryParse(_fiducialController.text) ?? 40.0;

    final updated = ScanConfig(
      shape: _shape,
      heightCm: h,
      widthCm: w,
      diameterCm: d,
      totalSurfaceAreaCm2: a,
      commodity: _commodityController.text.trim(),
      blown: _blown,
      institutional: _institutional,
      fastFood: _fastFood,
      dossierOnPass: _dossierOnPass,
      attachGps: _attachGps,
      fiducialMm: fid,
    );

    ref.read(scanSessionProvider.notifier).updateConfig(updated);
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const ScannerScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Inspection Setup'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 1. Package Shape Segmented Control
          const Text('PACKAGE SHAPE', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          SegmentedButton<PackageShape>(
            segments: PackageShape.values
                .map((s) => ButtonSegment(value: s, label: Text(s.label)))
                .toList(),
            selected: {_shape},
            onSelectionChanged: (set) {
              setState(() {
                _shape = set.first;
              });
            },
            style: SegmentedButton.styleFrom(
              selectedBackgroundColor: AppColors.navy,
              selectedForegroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
          ),
          const SizedBox(height: 20),

          // 2. Physical Dimensions Section
          const Text('PHYSICAL DIMENSIONS (CM)', style: AppTypography.sectionLabel),
          const SizedBox(height: 4),
          const Text(
            'Measure with a ruler — drives Rule 7 Principal Display Area (PDA) calculation & Table-I minimum font heights.',
            style: AppTypography.caption,
          ),
          const SizedBox(height: 12),
          _buildDimensionInputs(),
          const SizedBox(height: 20),

          // 3. Commodity Section
          const Text('COMMODITY (OPTIONAL)', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          TextField(
            controller: _commodityController,
            decoration: const InputDecoration(
              hintText: "e.g. 'cement', 'pan masala' — exemption rules use it",
              labelText: 'Commodity description',
            ),
          ),
          const SizedBox(height: 20),

          // 4. Statutory Toggles
          const Text('STATUTORY DECLARATION OPTIONS', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          Container(
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.border, width: 1),
            ),
            child: Column(
              children: [
                SwitchListTile(
                  title: const Text('Blown / molded / perforated print', style: AppTypography.body),
                  subtitle: const Text('Table-I column 2 minimum font sizes apply', style: AppTypography.caption),
                  value: _blown,
                  onChanged: (v) => setState(() => _blown = v),
                  activeThumbColor: AppColors.navy,
                ),
                const Divider(),
                SwitchListTile(
                  title: const Text('Institutional consumer package', style: AppTypography.body),
                  subtitle: const Text('Rule 26 exemption from retail declarations', style: AppTypography.caption),
                  value: _institutional,
                  onChanged: (v) => setState(() => _institutional = v),
                  activeThumbColor: AppColors.navy,
                ),
                const Divider(),
                SwitchListTile(
                  title: const Text('Fast food packaging', style: AppTypography.body),
                  subtitle: const Text('Rule 26 exemption for restaurant parcels', style: AppTypography.caption),
                  value: _fastFood,
                  onChanged: (v) => setState(() => _fastFood = v),
                  activeThumbColor: AppColors.navy,
                ),
                const Divider(),
                SwitchListTile(
                  title: const Text('Generate dossier on PASS', style: AppTypography.body),
                  subtitle: const Text('Creates signed audit trail for compliant packs', style: AppTypography.caption),
                  value: _dossierOnPass,
                  onChanged: (v) => setState(() => _dossierOnPass = v),
                  activeThumbColor: AppColors.navy,
                ),
                const Divider(),
                SwitchListTile(
                  title: const Text('Attach GPS metadata', style: AppTypography.body),
                  subtitle: const Text('Embed inspection coordinates into audit record', style: AppTypography.caption),
                  value: _attachGps,
                  onChanged: (v) => setState(() => _attachGps = v),
                  activeThumbColor: AppColors.navy,
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),

          // 5. Calibration Expander
          Container(
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.border, width: 1),
            ),
            child: ExpansionTile(
              title: const Text('OPTICAL CALIBRATION', style: AppTypography.sectionLabel),
              initiallyExpanded: _calibrationExpanded,
              onExpansionChanged: (v) => setState(() => _calibrationExpanded = v),
              childrenPadding: const EdgeInsets.all(16),
              children: [
                TextField(
                  controller: _fiducialController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    labelText: 'Fiducial marker size (mm)',
                    hintText: 'Default: 40 mm',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 28),

          // 6. Start Camera Button
          SizedBox(
            height: 52,
            child: ElevatedButton(
              onPressed: _onStartCamera,
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.camera, size: 20),
                  SizedBox(width: 8),
                  Text('START CAMERA'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Widget _buildDimensionInputs() {
    switch (_shape) {
      case PackageShape.rectangular:
      case PackageShape.pouch:
        return Row(
          children: [
            Expanded(
              child: TextField(
                controller: _heightController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Height (cm)'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: TextField(
                controller: _widthController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Width (cm)'),
              ),
            ),
          ],
        );
      case PackageShape.cylindrical:
      case PackageShape.bottle:
        return Row(
          children: [
            Expanded(
              child: TextField(
                controller: _heightController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Height (cm)'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: TextField(
                controller: _diameterController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Diameter (cm)'),
              ),
            ),
          ],
        );
      case PackageShape.other:
        return TextField(
          controller: _areaController,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Total surface area (cm²)'),
        );
    }
  }
}
