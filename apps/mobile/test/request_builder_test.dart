import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:netra/core/bridge/bridge_models.dart';
import 'package:netra/core/bridge/request_builder.dart';

void main() {
  test('request_builder output equals scan_tokens_request.json shape', () {
    final file = File('../../core/fixtures/contract/scan_tokens_request.json');
    expect(file.existsSync(), isTrue);
    final reference = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;

    final rawTokens = reference['tokens'] as List<dynamic>;
    final tokens = rawTokens
        .map((t) => Token.fromJson(t as Map<String, dynamic>))
        .toList();

    final builder = ScanTokensRequestBuilder()
        .setTokens(tokens)
        .setGeometry(
          shape: 'pouch',
          mmPerPx: 0.04,
          pdaCm2: 80.0,
          pdaMethod: 'demo',
        );

    final built = builder.build();

    expect(built.containsKey('tokens'), isTrue);
    expect(built.containsKey('geometry'), isTrue);
    expect(built.containsKey('options'), isTrue);

    // Tokens match exactly
    expect(built['tokens'], equals(reference['tokens']));

    // Geometry matches exactly
    expect(built['geometry'], equals(reference['geometry']));

    // Options matches
    expect(built['options'], equals(reference['options']));
  });

  test('request_builder all options test', () {
    final builder = ScanTokensRequestBuilder()
        .setTokens([
          const Token(text: 'Sample', bbox: BBox(0, 0, 10, 10))
        ])
        .setShapeHint('cylindrical')
        .setOptions(
          institutional: true,
          fastFood: false,
          commodity: 'pan masala',
          blown: true,
          packageHeightCm: 15.0,
          packageDiameterCm: 7.5,
          markerSideMm: 40.0,
        )
        .setCapturedUtc(DateTime.utc(2026, 9, 6, 12, 0, 0))
        .setGps(lat: 19.076, lon: 72.8777, accuracyM: 5.0)
        .setDevice(model: 'Pixel 7', os: 'Android 14', appBuild: '1.0.0');

    final built = builder.build();
    expect(built['shape_hint'], equals('cylindrical'));
    expect(built['captured_utc'], equals('2026-09-06T12:00:00.000Z'));
    expect(built['gps']['lat'], equals(19.076));
    expect(built['device']['model'], equals('Pixel 7'));
    expect(built['options']['institutional'], isTrue);
    expect(built['options']['commodity'], equals('pan masala'));
    expect(built['options']['package_height_cm'], equals(15.0));
  });
}
