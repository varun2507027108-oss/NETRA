import 'package:flutter/material.dart';

/// Design tokens strictly from Brief §4:
/// "Digital Legal Metrology field instrument"
/// Dense, flat, legible in daylight, zero decoration.
abstract final class AppColors {
  /// Screen background (warm off-white, not pure white)
  static const Color paper = Color(0xFFF6F4EF);

  /// Card surfaces
  static const Color surface = Color(0xFFFFFFFF);

  /// All card and chip borders (1dp)
  static const Color border = Color(0xFFE4E1D8);

  /// Primary text
  static const Color ink = Color(0xFF14161A);

  /// Captions, citations, secondary labels
  static const Color inkSecondary = Color(0xFF5C6068);

  /// Government Navy - buttons, active states, app bar accent
  static const Color navy = Color(0xFF1E3A5F);

  /// VIOLATION text & background
  static const Color verdictRed = Color(0xFFA61B1B);
  static const Color verdictRedBg = Color(0xFFFBEDEB);

  /// PASS text & background
  static const Color verdictGreen = Color(0xFF1B6B3A);
  static const Color verdictGreenBg = Color(0xFFE9F4EC);

  /// NA status text & background
  static const Color naSlate = Color(0xFF55606B);
  static const Color naSlateBg = Color(0xFFEFF1F3);

  /// RETRY / Pending text & background
  static const Color retryAmber = Color(0xFF9A5B00);
  static const Color retryAmberBg = Color(0xFFFDF3E3);

  /// Monospace fields background (scan_id, sha, timings)
  static const Color monoBg = Color(0xFFEFF1F3);
}
