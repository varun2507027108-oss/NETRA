import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/state/bridge_provider.dart';
import 'core/theme/app_colors.dart';
import 'core/theme/app_theme.dart';
import 'core/theme/app_typography.dart';
import 'features/home/home_screen.dart';

/// Root Application widget for NETRA Metrology Field Tool.
class NetraApp extends ConsumerWidget {
  const NetraApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pingAsync = ref.watch(pingStatusProvider);

    return MaterialApp(
      title: 'NETRA Metrology',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: pingAsync.when(
        data: (ping) {
          if (ping.schemaVersion != 1) {
            return const _IncompatibleCoreScreen(
              message: 'Core schema version mismatch. Reinstall app.',
            );
          }
          return const HomeScreen();
        },
        loading: () => const _SplashScreen(),
        error: (error, _) => _IncompatibleCoreScreen(
          message: 'Core connection failed:\n$error\n\nReinstall app or verify Chaquopy environment.',
        ),
      ),
    );
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: AppColors.paper,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              'NETRA',
              style: TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.w700,
                letterSpacing: 2.0,
                color: AppColors.navy,
              ),
            ),
            SizedBox(height: 8),
            Text(
              'LEGAL METROLOGY FIELD AUDIT TOOL',
              style: AppTypography.sectionLabel,
            ),
            SizedBox(height: 24),
            CircularProgressIndicator(
              color: AppColors.navy,
              strokeWidth: 2,
            ),
          ],
        ),
      ),
    );
  }
}

class _IncompatibleCoreScreen extends StatelessWidget {
  final String message;

  const _IncompatibleCoreScreen({required this.message});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.paper,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(
                Icons.warning_amber_rounded,
                color: AppColors.verdictRed,
                size: 64,
              ),
              const SizedBox(height: 16),
              const Text(
                'CORE INCOMPATIBLE',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  color: AppColors.verdictRed,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.border),
                ),
                child: Text(
                  message,
                  textAlign: TextAlign.center,
                  style: AppTypography.monoSmall,
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'The Python metrology core must report schema_version == 1 '
                'and be properly embedded via Chaquopy. Contact technical operations.',
                textAlign: TextAlign.center,
                style: AppTypography.caption,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
