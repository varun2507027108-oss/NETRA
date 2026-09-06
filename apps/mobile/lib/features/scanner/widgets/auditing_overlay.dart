import 'dart:async';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_typography.dart';

/// Modal overlay for statutory audit call (Brief §5.4).
/// Honest indeterminate spinner + live elapsed-ms counter + static pipeline legend.
/// Zero fake progress percentages.
class AuditingOverlay extends StatefulWidget {
  const AuditingOverlay({super.key});

  @override
  State<AuditingOverlay> createState() => _AuditingOverlayState();
}

class _AuditingOverlayState extends State<AuditingOverlay> {
  final Stopwatch _stopwatch = Stopwatch();
  Timer? _timer;
  int _elapsedMs = 0;

  @override
  void initState() {
    super.initState();
    _stopwatch.start();
    _timer = Timer.periodic(const Duration(milliseconds: 16), (_) {
      setState(() {
        _elapsedMs = _stopwatch.elapsedMilliseconds;
      });
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _stopwatch.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.black.withValues(alpha: 0.6),
      child: Center(
        child: Container(
          margin: const EdgeInsets.symmetric(horizontal: 32),
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.border, width: 1),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(
                width: 40,
                height: 40,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  color: AppColors.navy,
                ),
              ),
              const SizedBox(height: 20),
              const Text(
                'EXECUTING STATUTORY AUDIT',
                style: AppTypography.sectionLabel,
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                decoration: BoxDecoration(
                  color: AppColors.monoBg,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  '${_elapsedMs}ms',
                  style: AppTypography.mono.copyWith(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ),
              const SizedBox(height: 24),
              const Divider(),
              const SizedBox(height: 16),
              const Text(
                'PIPELINE SEQUENCE',
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.w600,
                  color: AppColors.inkSecondary,
                  letterSpacing: 1.0,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Decode → OCR → Extract → Statutory engine → Dossier',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontSize: 11,
                  color: AppColors.inkSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
