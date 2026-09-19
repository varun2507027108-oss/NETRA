import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:netra/core/bridge/bridge_models.dart';
import 'package:netra/core/theme/app_theme.dart';
import 'package:netra/features/report/widgets/check_tile.dart';
import 'package:netra/features/report/widgets/verdict_banner.dart';

void main() {
  group('VerdictBanner simplified wording tests', () {
    testWidgets('renders simplified count pill and sublabels for violation', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const Scaffold(
            body: VerdictBanner(
              verdict: Verdict.violation,
              passCount: 2,
              failCount: 5,
              naCount: 3,
            ),
          ),
        ),
      );

      expect(find.text('VIOLATION'), findsOneWidget);
      expect(find.text('5 VIOLATIONS'), findsOneWidget);
      expect(find.text('2 Compliant · 3 Exempt'), findsOneWidget);
    });

    testWidgets('renders ALL COMPLIANT when failCount is 0', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const Scaffold(
            body: VerdictBanner(
              verdict: Verdict.pass,
              passCount: 8,
              failCount: 0,
              naCount: 2,
            ),
          ),
        ),
      );

      expect(find.text('PASS'), findsOneWidget);
      expect(find.text('ALL COMPLIANT'), findsOneWidget);
      expect(find.text('8 Compliant · 2 Exempt'), findsOneWidget);
    });
  });

  group('CheckTile simplified presentation tests', () {
    testWidgets('displays human-readable rule title alongside rule number and VIOLATION badge', (tester) async {
      const check = CheckItem(
        rule: '6(1)(c)',
        status: CheckStatus.fail,
        message: 'The net quantity is printed in a non-standard unit.',
        plain: 'The net quantity is printed in a non-standard unit.',
        citation: 'Rule 6(1)(c) specifies standard units.',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const Scaffold(
            body: CheckTile(check: check),
          ),
        ),
      );

      // Human title
      expect(find.text('Net Quantity'), findsOneWidget);
      // Rule chip
      expect(find.text('Rule 6(1)(c)'), findsOneWidget);
      // Status badge: VIOLATION instead of FAIL
      expect(find.text('VIOLATION'), findsOneWidget);
      expect(find.text('FAIL'), findsNothing);
      expect(find.text('The net quantity is printed in a non-standard unit.'), findsOneWidget);
    });

    testWidgets('sanitizes {missing} placeholders from messages', (tester) async {
      const check = CheckItem(
        rule: '6(1)(e)',
        status: CheckStatus.fail,
        message: "The MRP is printed but '{missing}' — this wording is legally required.",
        plain: "The MRP is printed but '{missing}' — this wording is legally required.",
        citation: 'Rule 6(1)(e)',
      );

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: const Scaffold(
            body: CheckTile(check: check),
          ),
        ),
      );

      expect(find.text('Retail Price (MRP)'), findsOneWidget);
      expect(find.textContaining('{missing}'), findsNothing);
      expect(find.text("The MRP is printed but 'inclusive of all taxes' is missing — this wording is legally required."), findsOneWidget);
    });
  });
}
