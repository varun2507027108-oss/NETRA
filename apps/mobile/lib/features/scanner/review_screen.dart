import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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

      // 5. Execute statutory scan_tokens call via bridge
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
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Audit execution error: $e')),
        );
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
                      onPressed: _onRunAudit,
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
