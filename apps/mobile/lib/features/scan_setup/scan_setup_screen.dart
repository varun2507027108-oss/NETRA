import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../scanner/scanner_screen.dart';
import 'widgets/package_step.dart';
import 'widgets/conditions_step.dart';
import 'widgets/confirmation_step.dart';

/// 3-Step Setup Wizard Screen (Brief §5.2).
/// Step 1: Package Shape & Dynamic Dimensions
/// Step 2: Commodity & Statutory Conditions
/// Step 3: Confirmation & Calibration Settings
class ScanSetupScreen extends ConsumerStatefulWidget {
  const ScanSetupScreen({super.key});

  @override
  ConsumerState<ScanSetupScreen> createState() => _ScanSetupScreenState();
}

class _ScanSetupScreenState extends ConsumerState<ScanSetupScreen> {
  final PageController _pageController = PageController();
  int _currentStep = 0;

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
  bool _attachGps = false;

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
    _pageController.dispose();
    _heightController.dispose();
    _widthController.dispose();
    _diameterController.dispose();
    _areaController.dispose();
    _commodityController.dispose();
    _fiducialController.dispose();
    super.dispose();
  }

  String get _dimensionsSummary {
    switch (_shape) {
      case PackageShape.rectangular:
        final h = _heightController.text.trim();
        final w = _widthController.text.trim();
        if (h.isNotEmpty && w.isNotEmpty) return '$h cm × $w cm';
        if (h.isNotEmpty) return 'H: $h cm';
        return 'Optical calibration (fiducial)';
      case PackageShape.cylindrical:
      case PackageShape.bottle:
        final h = _heightController.text.trim();
        final d = _diameterController.text.trim();
        if (h.isNotEmpty && d.isNotEmpty) return 'H: $h cm, Dia: $d cm';
        if (h.isNotEmpty) return 'H: $h cm';
        return 'Optical calibration (fiducial)';
      case PackageShape.pouch:
      case PackageShape.other:
        final a = _areaController.text.trim();
        if (a.isNotEmpty) return 'Area: $a cm²';
        return 'Optical calibration (fiducial)';
    }
  }

  List<String> get _activeConditions {
    final list = <String>[];
    if (_blown) list.add('Blown/Molded (Rule 9(1))');
    if (_institutional) list.add('Institutional Supply (Rule 3)');
    if (_fastFood) list.add('Fast Food / Restaurant (Rule 26)');
    if (_attachGps) list.add('Location requested');
    return list;
  }

  void _onNextStep() {
    if (_currentStep < 2) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeInOut,
      );
      setState(() => _currentStep += 1);
    } else {
      _onStartCamera();
    }
  }

  void _onPrevStep() {
    if (_currentStep > 0) {
      _pageController.previousPage(
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeInOut,
      );
      setState(() => _currentStep -= 1);
    } else {
      Navigator.of(context).pop();
    }
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
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: Text(
                'Step ${_currentStep + 1} of 3',
                style: AppTypography.monoSmall.copyWith(
                  fontWeight: FontWeight.w600,
                  color: AppColors.inkSecondary,
                ),
              ),
            ),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: LinearProgressIndicator(
            value: (_currentStep + 1) / 3.0,
            backgroundColor: AppColors.border,
            valueColor: const AlwaysStoppedAnimation<Color>(AppColors.navy),
            minHeight: 4,
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // PageView Stepper
            Expanded(
              child: PageView(
                controller: _pageController,
                physics: const NeverScrollableScrollPhysics(),
                children: [
                  PackageStep(
                    shape: _shape,
                    onShapeChanged: (s) => setState(() => _shape = s),
                    heightController: _heightController,
                    widthController: _widthController,
                    diameterController: _diameterController,
                    areaController: _areaController,
                  ),
                  ConditionsStep(
                    commodityController: _commodityController,
                    blown: _blown,
                    onBlownChanged: (v) => setState(() => _blown = v),
                    institutional: _institutional,
                    onInstitutionalChanged: (v) => setState(() => _institutional = v),
                    fastFood: _fastFood,
                    onFastFoodChanged: (v) => setState(() => _fastFood = v),
                    attachGps: _attachGps,
                    onAttachGpsChanged: (v) => setState(() => _attachGps = v),
                  ),
                  ConfirmationStep(
                    shape: _shape,
                    commodity: _commodityController.text.trim(),
                    dimensionsSummary: _dimensionsSummary,
                    activeConditions: _activeConditions,
                    fiducialController: _fiducialController,
                    dossierOnPass: _dossierOnPass,
                    onDossierOnPassChanged: (v) => setState(() => _dossierOnPass = v),
                  ),
                ],
              ),
            ),

            // Bottom Navigation Controls
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: const BoxDecoration(
                color: AppColors.surface,
                border: Border(top: BorderSide(color: AppColors.border, width: 1)),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _onPrevStep,
                      icon: const Icon(Icons.arrow_back, size: 16),
                      label: Text(_currentStep == 0 ? 'Cancel' : 'Back'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: _currentStep == 2 ? 2 : 1,
                    child: ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.navy,
                      ),
                      onPressed: _onNextStep,
                      icon: Icon(
                        _currentStep == 2 ? Icons.camera_alt : Icons.arrow_forward,
                        size: 16,
                        color: Colors.white,
                      ),
                      label: Text(_currentStep == 2 ? 'Start Camera' : 'Continue'),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
