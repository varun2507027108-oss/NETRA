import 'dart:convert';
import 'package:flutter/services.dart';
import 'bridge_models.dart';

/// Client for the netra_core Chaquopy bridge (Contract v1.3.0).
/// Every method invocation takes and returns JSON-encoded STRINGS.
class NetraBridge {
  static const MethodChannel _defaultChannel = MethodChannel('netra.core');
  final MethodChannel _channel;

  const NetraBridge([MethodChannel? channel])
      : _channel = channel ?? _defaultChannel;

  /// Internal caller: serializes body to JSON string, invokes method,
  /// parses returned string to Map<String, dynamic>.
  Future<Map<String, dynamic>> _call(String method,
      [Map<String, dynamic>? body]) async {
    final argString = jsonEncode(body ?? const {});
    final rawResp = await _channel.invokeMethod<String>(method, argString);
    if (rawResp == null || rawResp.isEmpty) {
      throw BridgeParseError('Method $method returned empty or null response');
    }
    final decoded = jsonDecode(rawResp);
    if (decoded is! Map<String, dynamic>) {
      throw BridgeParseError(
          'Method $method response must be JSON object, got ${decoded.runtimeType}');
    }
    return decoded;
  }

  /// Ping handshake at startup (§2 & §6).
  /// Verifies core schema version compatibility.
  Future<PingPayload> ping() async {
    final map = await _call('ping');
    final payload = PingPayload.fromJson(map);
    if (payload.schemaVersion != 1) {
      throw BridgeParseError(
          'Core schema version ${payload.schemaVersion} is incompatible with app (expected 1)');
    }
    return payload;
  }

  /// Configure core directories and sync gateway (§2).
  Future<Map<String, dynamic>> configure({
    String? dataDir,
    String? syncUrl,
    String? syncToken,
  }) async {
    final body = <String, dynamic>{};
    if (dataDir != null) body['data_dir'] = dataDir;
    if (syncUrl != null) body['sync_url'] = syncUrl;
    if (syncToken != null) body['sync_token'] = syncToken;
    return await _call('configure', body);
  }

  /// Run statutory audit via OCR tokens on B1 architecture (§14).
  /// Note: errors are in-band inside ScanResult (error != null).
  Future<ScanResult> scanTokens(Map<String, dynamic> requestBody) async {
    final map = await _call('scan_tokens', requestBody);
    return ScanResult.fromJson(map);
  }

  /// Fast Kotlin vision prepass (s1 quality + s3 fiducial marker).
  Future<Map<String, dynamic>> visionPrepass({
    required String imageB64,
    Map<String, dynamic>? options,
  }) async {
    final body = {
      'image_b64': imageB64,
      'options': options ?? const {},
    };
    return await _call('vision_prepass', body);
  }

  /// Sign evidence dossier and attach signature to ledger row (§2 & §8).
  /// Passes the full ScanResult JSON map to Kotlin for signing.
  Future<SigResponse> signAndAttach(Map<String, dynamic> scanResultJson) async {
    final map = await _call('sign_and_attach', scanResultJson);
    return SigResponse.fromJson(map);
  }

  /// Retrieve compiled dossier PDF bytes for in-app viewing/sharing (Brief §2(a)).
  Future<DossierFile> getDossier(String scanId) async {
    final map = await _call('get_dossier', {'scan_id': scanId});
    return DossierFile.fromJson(map);
  }

  /// Fetch on-device ledger and queue status (§2).
  Future<QueueStatus> queueStatus() async {
    final map = await _call('queue_status');
    return QueueStatus.fromJson(map);
  }

  /// Trigger immediate sync against the institutional gateway (§2).
  Future<SyncSummary> syncNow() async {
    final map = await _call('sync_now');
    return SyncSummary.fromJson(map);
  }
}
