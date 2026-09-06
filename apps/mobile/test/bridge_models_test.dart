import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:netra/core/bridge/bridge_models.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // Path to contract fixtures
  final fixturesDir = Directory('../../core/fixtures/contract');

  String fixture(String name) {
    final file = File('${fixturesDir.path}/$name');
    if (!file.existsSync()) {
      throw Exception('Fixture not found at ${file.path}');
    }
    return file.readAsStringSync();
  }

  group('Bridge Models Strict Fixture Round-trip Tests', () {
    test('1. ping.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('ping.json')) as Map<String, dynamic>;
      final model = PingPayload.fromJson(original);
      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('2. queue_status.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('queue_status.json')) as Map<String, dynamic>;
      final model = QueueStatus.fromJson(original);
      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('3. sync_summary_success.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('sync_summary_success.json')) as Map<String, dynamic>;
      final model = SyncSummary.fromJson(original);
      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('4. sync_summary_not_configured.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('sync_summary_not_configured.json')) as Map<String, dynamic>;
      final model = SyncSummary.fromJson(original);
      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('5. attach_signature_responses.json round-trip (strict deep equality)', () {
      final originalMap = jsonDecode(fixture('attach_signature_responses.json')) as Map<String, dynamic>;
      for (final entry in originalMap.entries) {
        final original = entry.value as Map<String, dynamic>;
        final model = SigResponse.fromJson(original);
        // Contract asserts sig_status is 'pending' or 'signed'
        expect(model.sigStatus == SigStatus.pending || model.sigStatus == SigStatus.signed, isTrue);
        final reencoded = jsonDecode(jsonEncode(model.toJson()));
        expect(reencoded, original, reason: 'Failed on case: ${entry.key}');
      }
    });

    test('6. scan_error_decode.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('scan_error_decode.json')) as Map<String, dynamic>;
      final model = ScanResult.fromJson(original);
      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('7. scan_retry_blur.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('scan_retry_blur.json')) as Map<String, dynamic>;
      final model = ScanResult.fromJson(original);
      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('8. scan_tokens_request.json round-trip (strict deep equality for tokens & geometry)', () {
      final original = jsonDecode(fixture('scan_tokens_request.json')) as Map<String, dynamic>;
      final rawTokens = original['tokens'] as List<dynamic>;
      final tokens = rawTokens.map((t) => Token.fromJson(t as Map<String, dynamic>)).toList();
      final reencodedTokens = jsonDecode(jsonEncode(tokens.map((t) => t.toJson()).toList()));
      expect(reencodedTokens, rawTokens);

      final rawGeom = original['geometry'] as Map<String, dynamic>;
      final geom = Geometry.fromJson(rawGeom);
      final reencodedGeom = jsonDecode(jsonEncode(geom.toRequestJson()));
      expect(reencodedGeom, rawGeom);
    });

    test('9. scan_tokens_result.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('scan_tokens_result.json')) as Map<String, dynamic>;
      final model = ScanResult.fromJson(original);

      // Contract §4.3 & §10.3: money and quantity values are String?, NEVER double
      expect(model.fields['mrp']?.value, isA<String>());
      expect(model.fields['mrp']?.value, equals('14.00'));
      expect(model.fields['net_qty']?.value, isA<String>());
      expect(model.fields['net_qty']?.value, equals('70'));

      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('10. scan_violation.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('scan_violation.json')) as Map<String, dynamic>;
      final model = ScanResult.fromJson(original);

      // Exemption note must be preserved ("No Rule 26 exemption applies...")
      expect(model.exemption?.note, equals('No Rule 26 exemption applies; all Rule 6 declarations required.'));

      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('11. scan_violation_dossier.json round-trip (strict deep equality)', () {
      final original = jsonDecode(fixture('scan_violation_dossier.json')) as Map<String, dynamic>;
      final model = ScanResult.fromJson(original);
      final reencoded = jsonDecode(jsonEncode(model.toJson()));
      expect(reencoded, original);
    });

    test('Missing required ScanResult key throws BridgeParseError', () {
      final original = jsonDecode(fixture('scan_tokens_result.json')) as Map<String, dynamic>;
      final copy = Map<String, dynamic>.from(original)..remove('verdict');
      expect(() => ScanResult.fromJson(copy), throwsA(isA<BridgeParseError>()));
    });

    test('SigStatus unknown value throws BridgeParseError', () {
      expect(() => SigStatus.fromString('invalid_status'), throwsA(isA<BridgeParseError>()));
    });

    test('BBox malformed input throws BridgeParseError', () {
      expect(() => BBox.fromList([10, 20, 'thirty', 40]), throwsA(isA<BridgeParseError>()));
      expect(() => BBox.fromList([10, 20, 30]), throwsA(isA<BridgeParseError>()));
    });
  });
}
