import 'package:flutter/material.dart';

enum CaptureState {
  aligning,
  ready,
  processing,
}

/// Contextual guidance banner for viewfinder.
class CaptureGuidance extends StatelessWidget {
  final CaptureState state;
  final String? customMessage;

  const CaptureGuidance({
    super.key,
    required this.state,
    this.customMessage,
  });

  @override
  Widget build(BuildContext context) {
    IconData icon;
    Color iconColor;
    String message;

    switch (state) {
      case CaptureState.aligning:
        icon = Icons.center_focus_strong;
        iconColor = Colors.white70;
        message = customMessage ?? 'Align package & fiducial card flat in bright light. Avoid glare.';
        break;
      case CaptureState.ready:
        icon = Icons.check_circle_outline;
        iconColor = const Color(0xFF2E7D32); // Emerald
        message = customMessage ?? 'Position stabilized. Tap shutter to capture.';
        break;
      case CaptureState.processing:
        icon = Icons.hourglass_top;
        iconColor = const Color(0xFFE65100); // Amber
        message = customMessage ?? 'Analyzing package image & native vision prepass...';
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.75),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: state == CaptureState.ready
              ? const Color(0xFF2E7D32).withValues(alpha: 0.6)
              : Colors.white24,
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Icon(icon, color: iconColor, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w500,
                letterSpacing: 0.2,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
