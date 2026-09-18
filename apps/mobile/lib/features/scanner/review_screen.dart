import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import '../../core/bridge/bridge_models.dart';
import '../../core/bridge/request_builder.dart';
import '../../core/state/bridge_provider.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/util/bbox_painter.dart';
import '../report/report_screen.dart';
import 'widgets/auditing_overlay.dart';
import 'widgets/quality_summary.dart';
import 'widgets/technical_details.dart';

/// Post-capture Review Screen (Brief §5.3).
/// - Quality gate evaluation: Actionable Retake vs Proceed
/// - Quality Summary Card with clear check status
/// - Expandable Technical Details Tile (keeps raw token count & diagnostics out of way)
/// - "Run audit" primary button triggers honest indeterminate audit overlay & scan_tokens call
class ReviewScreen extends ConsumerStatefulWidget {
  const ReviewScreen({super.key});

  @override
  ConsumerState<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends ConsumerState<ReviewScreen> {
  bool _showOcrBoxes = true;
  bool _isAuditing = false;

  Future<Map<String, dynamic>?> _captureLocationIfRequested() async {
    final config = ref.read(scanSessionProvider).config;
    if (!config.attachGps) return null;

    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      throw const _OfficerActionException(
        'Location was requested, but device location is turned off. Turn it on or return to setup and continue without location.',
      );
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      throw const _OfficerActionException(
        'Location permission was not granted. Return to setup to continue without location, or grant permission and retry.',
      );
    }

    final position = await Geolocator.getCurrentPosition(
      desiredAccuracy: LocationAccuracy.high,
      timeLimit: const Duration(seconds: 15),
    );
    return {
      'lat': position.latitude,
      'lon': position.longitude,
      'accuracy_m': position.accuracy,
    };
  }

  Future<bool> _confirmIncompleteCapture() async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Continue with incomplete capture?'),
            content: const Text(
              'The quality gate did not approve this image. The audit may be incomplete and must be reviewed before any enforcement action. Retake is recommended.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Retake'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Continue'),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<void> _onRunAudit() async {
    final session = ref.read(scanSessionProvider);
    final processed = session.processedImage;
    if (processed == null) return;

    setState(() => _isAuditing = true);

    try {
      final builder = ScanTokensRequestBuilder();

      // 1. Tokens from ML Kit
      builder.setTokens(processed.tokens);

      // 2. Geometry from prepass — nested envelope (NetraVision.prepass);
      final prepass = session.prepassResult ?? {};
      final geometryMap = prepass['geometry'] as Map<String, dynamic>?;
      final mmPerPx = (geometryMap?['mm_per_px'] as num?)?.toDouble();

      builder.setGeometry(
        shape: session.config.shape.code,
        mmPerPx: mmPerPx,
        pdaMethod: 'field_input',
      );

      // 3. Quality from prepass
      final qualityMap = prepass['quality'] as Map<String, dynamic>?;
      if (qualityMap != null) {
        builder.setQualityObject(Quality.fromJson(qualityMap));
      }

      // 4. ML ROI boxes from prepass (v1.4.0)
      final roiBoxes = (prepass['roi_boxes'] as List<dynamic>?)
          ?.whereType<Map<String, dynamic>>()
          .toList();
      final roiFrame = prepass['roi_frame'] as Map<String, dynamic>?;
      if (roiBoxes != null && roiFrame != null) {
        builder.setRoiBoxes(
          boxes: roiBoxes,
          frameW: (roiFrame['w'] as num).toInt(),
          frameH: (roiFrame['h'] as num).toInt(),
        );
      }

      // 4. Shape Hint & Options (drives Rule 7 PDA calculation & Table-I font heights)
      builder.setShapeHint(session.config.shape.code);
      builder.setOptions(
        blown: session.config.blown,
        institutional: session.config.institutional,
        fastFood: session.config.fastFood,
        commodity: session.config.commodity,
        dossierOnPass: session.config.dossierOnPass,
        packageHeightCm: session.config.heightCm,
        packageWidthCm: session.config.widthCm,
        packageDiameterCm: session.config.diameterCm,
        totalSurfaceCm2: session.config.totalSurfaceAreaCm2,
        markerSideMm: session.config.fiducialMm,
      );

      // 5. Location is captured only after clear user intent and permission.
      // It is evidence metadata, never described as a signature.
      final gps = await _captureLocationIfRequested();
      if (gps != null) {
        builder.setGps(
          lat: gps['lat'] as double,
          lon: gps['lon'] as double,
          accuracyM: gps['accuracy_m'] as double,
        );
      }

      // 6. Execute statutory scan_tokens call via bridge
      final bridge = ref.read(netraBridgeProvider);
      final result = await bridge.scanTokens(builder.build());

      ref.read(scanSessionProvider.notifier).setCompletedResult(result);

      if (!mounted) return;
      setState(() => _isAuditing = false);

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => ReportScreen(result: result)),
      );
    } catch (e) {
      if (mounted) {
        setState(() => _isAuditing = false);
        final message = e is _OfficerActionException
            ? e.message
            : 'The audit could not be completed. Your capture is still available; retry or retake the photo.';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(scanSessionProvider);
    final processed = session.processedImage;
    final prepass = session.prepassResult ?? {};

    if (processed == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Review')),
        body: const Center(child: Text('No image captured.')),
      );
    }

    final quality = prepass['quality'] as Map<String, dynamic>?;
    final bool qualityOk = quality?['ok'] as bool? ?? true;
    final List<dynamic> promptsRaw = quality?['prompts'] as List<dynamic>? ?? [];
    final List<String> prompts = promptsRaw.map((e) => e.toString()).toList();

    final geometry = prepass['geometry'] as Map<String, dynamic>?;
    final bool markerDetected = geometry?['marker_detected'] as bool? ?? false;
    final double? mmPerPx = (geometry?['mm_per_px'] as num?)?.toDouble();
    final double? tiltDeg = (geometry?['tilt_degrees'] as num?)?.toDouble();

    final roiBoxes = prepass['roi_boxes'] as List<dynamic>?;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review Capture Quality'),
      ),
      body: Stack(
        children: [
          ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // 1. Image Preview with CustomPainter BBoxes
              Container(
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.border, width: 1),
                ),
                clipBehavior: Clip.antiAlias,
                child: AspectRatio(
                  aspectRatio: processed.width / processed.height,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Image.file(
                        processed.file,
                        fit: BoxFit.contain,
                      ),
                      if (_showOcrBoxes)
                        CustomPaint(
                          painter: BBoxPainter(
                            boxes: processed.tokens.map((t) => t.bbox).toList(),
                            imageWidth: processed.width,
                            imageHeight: processed.height,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),

              // 2. Actionable Quality Gate Summary
              QualitySummaryCard(
                qualityOk: qualityOk,
                markerDetected: markerDetected,
                mmPerPx: mmPerPx,
                prompts: prompts,
              ),
              const SizedBox(height: 12),

              // 3. Expandable Technical Diagnostics
              TechnicalDetailsTile(
                tokenCount: processed.tokens.length,
                imageWidth: processed.width,
                imageHeight: processed.height,
                packageShape: session.config.shape.label,
                mmPerPx: mmPerPx,
                tiltDeg: tiltDeg,
                roiCount: roiBoxes?.length,
                showOcrBoxes: _showOcrBoxes,
                onToggleOcrBoxes: (val) => setState(() => _showOcrBoxes = val),
              ),
              const SizedBox(height: 18),

              // 4. Actions: Hierarchy prioritized by quality status
              if (qualityOk)
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('RETAKE'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.verified, size: 18),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.navy,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                        ),
                        onPressed: _onRunAudit,
                        label: const Text(
                          'RUN AUDIT',
                          style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 0.5),
                        ),
                      ),
                    ),
                  ],
                )
              else
                Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    ElevatedButton.icon(
                      icon: const Icon(Icons.refresh, size: 18),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.navy,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                      onPressed: () => Navigator.of(context).pop(),
                      label: const Text(
                        'RETAKE CAPTURE (RECOMMENDED)',
                        style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 0.5),
                      ),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.retryAmber,
                        side: const BorderSide(color: AppColors.retryAmber),
                      ),
                      onPressed: () async {
                        if (await _confirmIncompleteCapture()) {
                          await _onRunAudit();
                        }
                      },
                      child: const Text('PROCEED WITH INCOMPLETE DATA'),
                    ),
                  ],
                ),
            ],
          ),

          // 5. Honest Indeterminate Auditing Overlay
          if (_isAuditing) const AuditingOverlay(),
        ],
      ),
    );
  }
}

class _OfficerActionException implements Exception {
  final String message;
  const _OfficerActionException(this.message);
}
