import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/bridge/bridge_models.dart';
import '../../core/bridge/request_builder.dart';
import '../../core/state/bridge_provider.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../core/util/bbox_painter.dart';
import '../report/report_screen.dart';
import 'widgets/auditing_overlay.dart';

/// Post-capture Review Screen (Brief §5.3).
/// - Processed image preview with debug OCR box overlay toggle (coordinate space verification)
/// - Vision prepass chips: marker detected, scale mm/px, tilt, blur, glare
/// - Quality gate evaluation: if quality.ok == false, shows RETRY view with prompts
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

      // 2. Geometry from prepass
      final prepass = session.prepassResult ?? {};
      final mmPerPx = (prepass['mm_per_px'] as num?)?.toDouble();

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

    final bool markerDetected = prepass['marker_detected'] as bool? ?? false;
    final double? mmPerPx = (prepass['mm_per_px'] as num?)?.toDouble();
    final double? tiltDeg = (prepass['tilt_degrees'] as num?)?.toDouble();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review Capture'),
        actions: [
          IconButton(
            icon: Icon(_showOcrBoxes ? Icons.visibility : Icons.visibility_off),
            tooltip: 'Toggle OCR BBoxes',
            onPressed: () => setState(() => _showOcrBoxes = !_showOcrBoxes),
          ),
        ],
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
              const SizedBox(height: 12),

              // 2. OCR Tokens & Verification Notice
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '${processed.tokens.length} OCR TOKENS EXTRACTED',
                    style: AppTypography.sectionLabel,
                  ),
                  Text(
                    '${processed.width}×${processed.height} px',
                    style: AppTypography.monoSmall,
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // 3. Vision Prepass Chips Strip
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _buildChip(
                    label: markerDetected
                        ? 'Fiducial: ${mmPerPx?.toStringAsFixed(4)} mm/px'
                        : 'No Fiducial (Font checks NA)',
                    color: markerDetected ? AppColors.verdictGreen : AppColors.naSlate,
                    bg: markerDetected ? AppColors.verdictGreenBg : AppColors.naSlateBg,
                  ),
                  if (tiltDeg != null && markerDetected)
                    _buildChip(
                      label: 'Tilt: ${tiltDeg.toStringAsFixed(1)}°',
                      color: AppColors.navy,
                      bg: AppColors.monoBg,
                    ),
                  _buildChip(
                    label: 'Shape: ${session.config.shape.label}',
                    color: AppColors.navy,
                    bg: AppColors.monoBg,
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // 4. Quality Gate Status
              if (!qualityOk) ...[
                Container(
                  padding: const EdgeInsets.all(14),
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
                          const Icon(Icons.warning_amber, color: AppColors.retryAmber, size: 20),
                          const SizedBox(width: 8),
                          Text(
                            'IMAGE QUALITY FAILED',
                            style: AppTypography.heading.copyWith(color: AppColors.retryAmber),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      ...prompts.map((p) => Padding(
                            padding: const EdgeInsets.only(left: 6, bottom: 2),
                            child: Text('• $p', style: AppTypography.body),
                          )),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // 5. Actions
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
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: qualityOk ? AppColors.navy : AppColors.retryAmber,
                      ),
                      onPressed: _onRunAudit,
                      child: Text(qualityOk ? 'RUN AUDIT' : 'PROCEED ANYWAY'),
                    ),
                  ),
                ],
              ),
            ],
          ),

          // 6. Honest Indeterminate Auditing Overlay
          if (_isAuditing) const AuditingOverlay(),
        ],
      ),
    );
  }

  Widget _buildChip({
    required String label,
    required Color color,
    required Color bg,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.3), width: 1),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: color,
        ),
      ),
    );
  }
}
