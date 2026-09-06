import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Typography strictly from Brief §4:
/// Platform Roboto default, NO network/google fonts.
abstract final class AppTypography {
  /// Verdict banner: 20sp, w600, white on colored bar
  static const TextStyle verdictBanner = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    color: Colors.white,
    letterSpacing: 0.5,
  );

  /// Screen titles: 16sp w500
  static const TextStyle screenTitle = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w500,
    color: AppColors.ink,
  );

  /// Card/section headers: 15sp w600
  static const TextStyle heading = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.w600,
    color: AppColors.ink,
  );

  /// Body: 15sp regular
  static const TextStyle body = TextStyle(
    fontSize: 15,
    fontWeight: FontWeight.normal,
    color: AppColors.ink,
    height: 1.3,
  );

  /// Secondary body / captions / citations: 12sp inkSecondary
  static const TextStyle caption = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.normal,
    color: AppColors.inkSecondary,
    height: 1.3,
  );

  /// Section labels: 11sp, UPPERCASE, letterSpacing 1.2, w600 (the gov-tool tell)
  static const TextStyle sectionLabel = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    color: AppColors.inkSecondary,
    letterSpacing: 1.2,
  );

  /// Monospace values: 12sp monospace for IDs, hashes, timestamps, values
  static const TextStyle mono = TextStyle(
    fontFamily: 'monospace',
    fontSize: 12,
    fontWeight: FontWeight.w500,
    color: AppColors.ink,
    letterSpacing: 0.3,
  );

  /// Monospace small: 11sp monospace for rule chips
  static const TextStyle monoSmall = TextStyle(
    fontFamily: 'monospace',
    fontSize: 11,
    fontWeight: FontWeight.w600,
    color: AppColors.ink,
  );
}
