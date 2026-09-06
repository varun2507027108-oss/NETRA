import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../bridge/bridge_models.dart';
import '../util/image_pipeline.dart';

/// Inspection package shapes for scan setup.
enum PackageShape {
  rectangular('rectangular', 'Rectangular'),
  cylindrical('cylindrical', 'Cylindrical'),
  pouch('pouch', 'Pouch'),
  bottle('bottle', 'Bottle'),
  other('other', 'Other');

  final String code;
  final String label;
  const PackageShape(this.code, this.label);
}

/// Active scan setup configuration set by the inspector in ScanSetupScreen.
class ScanConfig {
  final PackageShape shape;
  final double? heightCm;
  final double? widthCm;
  final double? diameterCm;
  final double? totalSurfaceAreaCm2;
  final String commodity;
  final bool blown;
  final bool institutional;
  final bool fastFood;
  final bool dossierOnPass;
  final bool attachGps;
  final double fiducialMm;

  const ScanConfig({
    this.shape = PackageShape.rectangular,
    this.heightCm,
    this.widthCm,
    this.diameterCm,
    this.totalSurfaceAreaCm2,
    this.commodity = '',
    this.blown = false,
    this.institutional = false,
    this.fastFood = false,
    this.dossierOnPass = false,
    this.attachGps = true,
    this.fiducialMm = 40.0,
  });

  ScanConfig copyWith({
    PackageShape? shape,
    double? heightCm,
    double? widthCm,
    double? diameterCm,
    double? totalSurfaceAreaCm2,
    String? commodity,
    bool? blown,
    bool? institutional,
    bool? fastFood,
    bool? dossierOnPass,
    bool? attachGps,
    double? fiducialMm,
  }) {
    return ScanConfig(
      shape: shape ?? this.shape,
      heightCm: heightCm ?? this.heightCm,
      widthCm: widthCm ?? this.widthCm,
      diameterCm: diameterCm ?? this.diameterCm,
      totalSurfaceAreaCm2: totalSurfaceAreaCm2 ?? this.totalSurfaceAreaCm2,
      commodity: commodity ?? this.commodity,
      blown: blown ?? this.blown,
      institutional: institutional ?? this.institutional,
      fastFood: fastFood ?? this.fastFood,
      dossierOnPass: dossierOnPass ?? this.dossierOnPass,
      attachGps: attachGps ?? this.attachGps,
      fiducialMm: fiducialMm ?? this.fiducialMm,
    );
  }
}

/// Inspection session state machine:
/// idle -> setup -> captured -> prepassOk/prepassRetry -> auditing -> completed
class ScanSessionState {
  final ScanConfig config;
  final ProcessedImage? processedImage;
  final Map<String, dynamic>? prepassResult;
  final ScanResult? scanResult;
  final bool isAuditing;
  final String? errorMessage;

  const ScanSessionState({
    this.config = const ScanConfig(),
    this.processedImage,
    this.prepassResult,
    this.scanResult,
    this.isAuditing = false,
    this.errorMessage,
  });

  ScanSessionState copyWith({
    ScanConfig? config,
    ProcessedImage? processedImage,
    Map<String, dynamic>? prepassResult,
    ScanResult? scanResult,
    bool? isAuditing,
    String? errorMessage,
    bool clearProcessed = false,
    bool clearResult = false,
  }) {
    return ScanSessionState(
      config: config ?? this.config,
      processedImage: clearProcessed ? null : (processedImage ?? this.processedImage),
      prepassResult: clearProcessed ? null : (prepassResult ?? this.prepassResult),
      scanResult: clearResult ? null : (scanResult ?? this.scanResult),
      isAuditing: isAuditing ?? this.isAuditing,
      errorMessage: errorMessage,
    );
  }
}

class ScanSessionNotifier extends StateNotifier<ScanSessionState> {
  ScanSessionNotifier() : super(const ScanSessionState());

  void updateConfig(ScanConfig config) {
    state = state.copyWith(config: config);
  }

  void setCapturedImage({
    required ProcessedImage image,
    required Map<String, dynamic> prepassResult,
  }) {
    state = state.copyWith(
      processedImage: image,
      prepassResult: prepassResult,
      clearResult: true,
      errorMessage: null,
    );
  }

  void setAuditing(bool auditing) {
    state = state.copyWith(isAuditing: auditing);
  }

  void setCompletedResult(ScanResult result) {
    state = state.copyWith(
      scanResult: result,
      isAuditing: false,
      errorMessage: null,
    );
  }

  void resetSession() {
    state = ScanSessionState(config: state.config);
  }
}

final scanSessionProvider =
    StateNotifierProvider<ScanSessionNotifier, ScanSessionState>((ref) {
  return ScanSessionNotifier();
});
