import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:netra/core/theme/app_theme.dart';
import 'package:netra/features/scan_setup/scan_setup_screen.dart';

void main() {
  testWidgets('ScanSetupScreen renders PackageStep and walks through all 3 steps', (tester) async {
    tester.view.physicalSize = const Size(1080, 2400);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          home: const ScanSetupScreen(),
        ),
      ),
    );

    await tester.pumpAndSettle();

    // Step 1: Package Step
    expect(find.text('Inspection Setup'), findsOneWidget);
    expect(find.text('PACKAGE SHAPE'), findsOneWidget);
    expect(find.text('Step 1 of 3'), findsOneWidget);
    expect(find.text('Continue'), findsOneWidget);

    // Tap Continue -> Step 2
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();

    // Step 2: Conditions Step
    expect(find.text('COMMODITY DECLARATION'), findsOneWidget);
    expect(find.text('Step 2 of 3'), findsOneWidget);
    expect(find.text('Back'), findsOneWidget);

    // Tap Continue -> Step 3
    await tester.tap(find.text('Continue'));
    await tester.pumpAndSettle();

    // Step 3: Confirmation Step
    expect(find.text('INSPECTION PARAMETERS SUMMARY'), findsOneWidget);
    expect(find.text('Step 3 of 3'), findsOneWidget);
    expect(find.text('Start Camera'), findsOneWidget);

    // Tap Back -> back to Step 2
    await tester.tap(find.text('Back'));
    await tester.pumpAndSettle();
    expect(find.text('Step 2 of 3'), findsOneWidget);
  });
}
