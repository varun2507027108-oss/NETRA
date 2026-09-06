import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:netra/core/bridge/bridge_models.dart';
import 'package:netra/core/bridge/netra_bridge.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel('netra.core');
  late NetraBridge bridge;
  late List<MethodCall> log;

  setUp(() {
    log = <MethodCall>[];
    bridge = const NetraBridge(channel);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test('ping returns PingPayload on success', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall call) async {
      log.add(call);
      // Verify arg is JSON encoded string
      expect(call.arguments, isA<String>());
      expect(call.method, equals('ping'));
      return jsonEncode({
        'schema_version': 1,
        'core_version': '0.1.0',
        'channel': 'netra.core',
        'capabilities': {
          'stages_implemented': ['s1_frame_quality'],
          'stages_planned': [],
          'dossier': true,
          'signing': 'platform',
          'sync': true,
          'ocr_engines': ['mlkit'],
        },
      });
    });

    final resp = await bridge.ping();
    expect(resp.schemaVersion, equals(1));
    expect(resp.coreVersion, equals('0.1.0'));
    expect(log.length, equals(1));
  });

  test('ping throws BridgeParseError if schema_version != 1', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall call) async {
      return jsonEncode({
        'schema_version': 2,
        'core_version': '0.2.0',
        'channel': 'netra.core',
        'capabilities': {
          'stages_implemented': [],
          'stages_planned': [],
          'dossier': false,
          'signing': 'platform',
          'sync': false,
          'ocr_engines': [],
        },
      });
    });

    expect(() => bridge.ping(), throwsA(isA<BridgeParseError>()));
  });

  test('scanTokens passes JSON string and receives ScanResult with in-band error', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall call) async {
      log.add(call);
      expect(call.arguments, isA<String>());
      final decodedArg = jsonDecode(call.arguments as String) as Map<String, dynamic>;
      expect(decodedArg['tokens'], isNotNull);

      // Return in-band error response
      return jsonEncode({
        'schema_version': 1,
        'scan_id': '',
        'verdict': 'RETRY',
        'captured_utc': '2026-09-06T12:00:00.000Z',
        'completed_utc': '2026-09-06T12:00:00.100Z',
        'total_ms': 0.0,
        'timings_ms': {},
        'quality': {
          'ok': null,
          'laplacian_var': null,
          'glare_pct': null,
          'prompts': [],
          'glare_bbox': null,
        },
        'geometry': null,
        'ocr': {'engines_used': [], 'tokens': []},
        'fields': {},
        'checks': [],
        'exemption': null,
        'summary': {'total': 0, 'pass': 0, 'fail': 0, 'na': 0},
        'dossier': null,
        'meta': null,
        'error': {
          'code': 'DECODE_ERROR',
          'message': 'Image unreadable — retake',
        },
      });
    });

    final result = await bridge.scanTokens({'tokens': [{'text': 'hi', 'bbox': [0,0,10,10]}]});
    expect(result.verdict, equals(Verdict.retry));
    expect(result.error, isNotNull);
    expect(result.error!.code, equals('DECODE_ERROR'));
    expect(result.error!.message, equals('Image unreadable — retake'));
  });

  test('configure passes arguments as JSON string', () async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (MethodCall call) async {
      log.add(call);
      expect(call.arguments, isA<String>());
      final arg = jsonDecode(call.arguments as String) as Map<String, dynamic>;
      expect(arg['sync_url'], equals('https://gateway.netra.gov.in'));
      return jsonEncode({'sync_url': 'https://gateway.netra.gov.in'});
    });

    final res = await bridge.configure(syncUrl: 'https://gateway.netra.gov.in');
    expect(res['sync_url'], equals('https://gateway.netra.gov.in'));
    expect(log.length, equals(1));
  });
}
