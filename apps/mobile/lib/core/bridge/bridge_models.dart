// ignore_for_file: unused_import

import 'dart:convert';

/// Thrown when a contract response or payload fails to parse according
/// to the frozen NETRA bridge contract (v1.3.0).
class BridgeParseError implements Exception {
  final String message;
  final Object? details;

  const BridgeParseError(this.message, [this.details]);

  @override
  String toString() => details != null
      ? 'BridgeParseError: $message ($details)'
      : 'BridgeParseError: $message';
}

/// Status of a statutory rule check.
enum CheckStatus {
  pass('PASS'),
  fail('FAIL'),
  na('NA');

  final String value;
  const CheckStatus(this.value);

  static CheckStatus fromString(String raw) {
    switch (raw.toUpperCase()) {
      case 'PASS':
        return CheckStatus.pass;
      case 'FAIL':
        return CheckStatus.fail;
      case 'NA':
        return CheckStatus.na;
      default:
        throw BridgeParseError('Unknown CheckStatus: "$raw"');
    }
  }
}

/// Overall inspection verdict.
enum Verdict {
  pass('PASS'),
  violation('VIOLATION'),
  retry('RETRY');

  final String value;
  const Verdict(this.value);

  static Verdict fromString(String raw) {
    switch (raw.toUpperCase()) {
      case 'PASS':
        return Verdict.pass;
      case 'VIOLATION':
        return Verdict.violation;
      case 'RETRY':
        return Verdict.retry;
      default:
        throw BridgeParseError('Unknown Verdict: "$raw"');
    }
  }
}

enum SigStatus {
  pending('pending'),
  signed('signed'),
  unsupported('unsupported');

  final String value;
  const SigStatus(this.value);

  static SigStatus fromString(String raw) {
    switch (raw.toLowerCase()) {
      case 'pending':
        return SigStatus.pending;
      case 'signed':
        return SigStatus.signed;
      case 'unsupported':
        return SigStatus.unsupported;
      default:
        throw BridgeParseError('Unknown SigStatus: "$raw"');
    }
  }

  String toJson() => name;
}

/// Pixel bounding box [x, y, w, h] in submitted-image space.
class BBox {
  final int x;
  final int y;
  final int w;
  final int h;

  const BBox(this.x, this.y, this.w, this.h);

  static BBox? fromList(dynamic raw) {
    if (raw == null) return null;
    if (raw is! List || raw.length != 4) {
      throw BridgeParseError('BBox must have exactly 4 elements: $raw');
    }
    for (int i = 0; i < 4; i++) {
      if (raw[i] is! num) {
        throw BridgeParseError('BBox element at index $i must be a number: ${raw[i]}');
      }
    }
    return BBox(
      (raw[0] as num).toInt(),
      (raw[1] as num).toInt(),
      (raw[2] as num).toInt(),
      (raw[3] as num).toInt(),
    );
  }

  List<int> toList() => [x, y, w, h];

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BBox &&
          runtimeType == other.runtimeType &&
          x == other.x &&
          y == other.y &&
          w == other.w &&
          h == other.h;

  @override
  int get hashCode => Object.hash(x, y, w, h);

  @override
  String toString() => '[$x, $y, $w, $h]';
}

/// Single OCR token / line token.
class Token {
  final String text;
  final BBox bbox;
  final double conf;
  final String engine;
  final String lang;

  const Token({
    required this.text,
    required this.bbox,
    this.conf = 1.0,
    this.engine = 'mlkit',
    this.lang = 'en',
  });

  factory Token.fromJson(Map<String, dynamic> json) {
    final text = json['text'];
    if (text is! String || text.isEmpty) {
      throw const BridgeParseError('Token.text must be a non-empty string');
    }
    final rawBbox = json['bbox'];
    if (rawBbox is! List) {
      throw const BridgeParseError('Token.bbox must be a list [x,y,w,h]');
    }
    final bbox = BBox.fromList(rawBbox);
    if (bbox == null) {
      throw const BridgeParseError('Token.bbox cannot be null');
    }
    final conf = (json['conf'] as num?)?.toDouble() ?? 1.0;
    final engine = (json['engine'] as String?) ?? 'mlkit';
    final lang = (json['lang'] as String?) ?? 'en';

    return Token(
      text: text,
      bbox: bbox,
      conf: conf,
      engine: engine,
      lang: lang,
    );
  }

  Map<String, dynamic> toJson() => {
        'text': text,
        'bbox': bbox.toList(),
        'conf': conf,
        'engine': engine,
        'lang': lang,
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Token &&
          runtimeType == other.runtimeType &&
          text == other.text &&
          bbox == other.bbox &&
          conf == other.conf &&
          engine == other.engine &&
          lang == other.lang;

  @override
  int get hashCode => Object.hash(text, bbox, conf, engine, lang);
}

/// Extracted field declaration value.
/// CONTRACT §4.3 & §10.3: money and quantity values are String?, NEVER double.
class FieldValue {
  final String raw;
  final String? value;
  final String? unit;
  final BBox? bbox;
  final double conf;

  const FieldValue({
    required this.raw,
    this.value,
    this.unit,
    this.bbox,
    this.conf = 0.0,
  });

  factory FieldValue.fromJson(Map<String, dynamic> json) {
    final raw = json['raw'];
    if (raw is! String) {
      throw BridgeParseError('FieldValue.raw must be a string, got $raw');
    }
    final val = json['value'];
    final String? strVal = val?.toString();

    return FieldValue(
      raw: raw,
      value: strVal,
      unit: json['unit'] as String?,
      bbox: BBox.fromList(json['bbox'] as List<dynamic>?),
      conf: (json['conf'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() => {
        'raw': raw,
        'value': value,
        'unit': unit,
        'bbox': bbox?.toList(),
        'conf': conf,
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FieldValue &&
          runtimeType == other.runtimeType &&
          raw == other.raw &&
          value == other.value &&
          unit == other.unit &&
          bbox == other.bbox &&
          conf == other.conf;

  @override
  int get hashCode => Object.hash(raw, value, unit, bbox, conf);
}

/// Statutory rule check entry (Contract §4.4).
class CheckItem {
  final String rule;
  final CheckStatus status;
  final String message;
  final String citation;
  final BBox? evidenceBbox;

  const CheckItem({
    required this.rule,
    required this.status,
    required this.message,
    required this.citation,
    this.evidenceBbox,
  });

  factory CheckItem.fromJson(Map<String, dynamic> json) {
    final rule = json['rule'];
    if (rule is! String) {
      throw BridgeParseError('CheckItem.rule must be a string, got $rule');
    }
    final statusStr = json['status'];
    if (statusStr is! String) {
      throw BridgeParseError('CheckItem.status must be a string, got $statusStr');
    }
    final status = CheckStatus.fromString(statusStr);
    final message = json['message'];
    if (message is! String) {
      throw BridgeParseError('CheckItem.message must be a string, got $message');
    }
    final citation = json['citation'];
    if (citation is! String) {
      throw BridgeParseError('CheckItem.citation must be a string, got $citation');
    }

    return CheckItem(
      rule: rule,
      status: status,
      message: message,
      citation: citation,
      evidenceBbox: BBox.fromList(json['evidence_bbox'] as List<dynamic>?),
    );
  }

  Map<String, dynamic> toJson() => {
        'rule': rule,
        'status': status.value,
        'message': message,
        'citation': citation,
        'evidence_bbox': evidenceBbox?.toList(),
      };
}

/// Stage 1 frame quality assessment.
class Quality {
  final bool? ok;
  final double? laplacianVar;
  final double? glarePct;
  final List<String> prompts;
  final BBox? glareBbox;

  const Quality({
    this.ok,
    this.laplacianVar,
    this.glarePct,
    this.prompts = const [],
    this.glareBbox,
  });

  factory Quality.fromJson(Map<String, dynamic> json) {
    return Quality(
      ok: json['ok'] as bool?,
      laplacianVar: (json['laplacian_var'] as num?)?.toDouble(),
      glarePct: (json['glare_pct'] as num?)?.toDouble(),
      prompts: (json['prompts'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      glareBbox: BBox.fromList(json['glare_bbox'] as List<dynamic>?),
    );
  }

  Map<String, dynamic> toJson() => {
        'ok': ok,
        'laplacian_var': laplacianVar,
        'glare_pct': glarePct,
        'prompts': prompts,
        'glare_bbox': glareBbox?.toList(),
      };
}

/// Region of interest detected in s2.
class RoiItem {
  final String roi;
  final BBox bbox;
  final double conf;

  const RoiItem({
    required this.roi,
    required this.bbox,
    this.conf = 0.0,
  });

  factory RoiItem.fromJson(Map<String, dynamic> json) {
    final roi = json['roi'] as String;
    final bbox = BBox.fromList(json['bbox'] as List<dynamic>)!;
    final conf = (json['conf'] as num?)?.toDouble() ?? 0.0;
    return RoiItem(roi: roi, bbox: bbox, conf: conf);
  }

  Map<String, dynamic> toJson() => {
        'roi': roi,
        'bbox': bbox.toList(),
        'conf': conf,
      };
}

/// Stage 2/3 geometry & calibration.
class Geometry {
  final String? shape;
  final String? shapeDetected;
  final double? mmPerPx;
  final double? pdaCm2;
  final String? pdaMethod;
  final List<RoiItem> rois;

  const Geometry({
    this.shape,
    this.shapeDetected,
    this.mmPerPx,
    this.pdaCm2,
    this.pdaMethod,
    this.rois = const [],
  });

  factory Geometry.fromJson(Map<String, dynamic> json) {
    final roisRaw = json['rois'] as List<dynamic>?;
    final rois = roisRaw != null
        ? roisRaw.map((e) => RoiItem.fromJson(e as Map<String, dynamic>)).toList()
        : <RoiItem>[];

    return Geometry(
      shape: json['shape'] as String?,
      shapeDetected: json['shape_detected'] as String?,
      mmPerPx: (json['mm_per_px'] as num?)?.toDouble(),
      pdaCm2: (json['pda_cm2'] as num?)?.toDouble(),
      pdaMethod: json['pda_method'] as String?,
      rois: rois,
    );
  }

  Map<String, dynamic> toJson() => {
        'shape': shape,
        'shape_detected': shapeDetected,
        'mm_per_px': mmPerPx,
        'pda_cm2': pdaCm2,
        'pda_method': pdaMethod,
        'rois': rois.map((r) => r.toJson()).toList(),
      };

  /// Serializes only populated geometry fields for scan_tokens request (§14).
  Map<String, dynamic> toRequestJson() => {
        if (shape != null) 'shape': shape,
        if (shapeDetected != null) 'shape_detected': shapeDetected,
        if (mmPerPx != null) 'mm_per_px': mmPerPx,
        if (pdaCm2 != null) 'pda_cm2': pdaCm2,
        if (pdaMethod != null) 'pda_method': pdaMethod,
        if (rois.isNotEmpty) 'rois': rois.map((r) => r.toJson()).toList(),
      };
}

/// Stage 4 OCR payload.
class OcrResult {
  final List<String> enginesUsed;
  final List<Token> tokens;

  const OcrResult({
    this.enginesUsed = const [],
    this.tokens = const [],
  });

  factory OcrResult.fromJson(Map<String, dynamic> json) {
    final engines = (json['engines_used'] as List<dynamic>?)
            ?.map((e) => e.toString())
            .toList() ??
        const [];
    final tokensRaw = json['tokens'] as List<dynamic>?;
    final tokens = tokensRaw != null
        ? tokensRaw
            .map((e) => Token.fromJson(e as Map<String, dynamic>))
            .toList()
        : <Token>[];
    return OcrResult(enginesUsed: engines, tokens: tokens);
  }

  Map<String, dynamic> toJson() => {
        'engines_used': enginesUsed,
        'tokens': tokens.map((t) => t.toJson()).toList(),
      };
}

class Exemption {
  final bool exempt;
  final String? clause;
  final String? note;

  const Exemption({required this.exempt, this.clause, this.note});

  factory Exemption.fromJson(Map<String, dynamic> json) => Exemption(
        exempt: json['exempt'] as bool? ?? false,
        clause: json['clause'] as String?,
        note: json['note'] as String?,
      );

  Map<String, dynamic> toJson() =>
      {'exempt': exempt, 'clause': clause, 'note': note};
}

/// Summary counts of statutory checks.
class CheckSummary {
  final int total;
  final int pass;
  final int fail;
  final int na;

  const CheckSummary({
    required this.total,
    required this.pass,
    required this.fail,
    required this.na,
  });

  factory CheckSummary.fromJson(Map<String, dynamic> json) {
    return CheckSummary(
      total: (json['total'] as num).toInt(),
      pass: (json['pass'] as num).toInt(),
      fail: (json['fail'] as num).toInt(),
      na: (json['na'] as num).toInt(),
    );
  }

  Map<String, dynamic> toJson() => {
        'total': total,
        'pass': pass,
        'fail': fail,
        'na': na,
      };
}

/// Cryptographic evidence dossier details.
class Dossier {
  final String sha256;
  final String? pdfPath;
  final bool signed;
  final String? signature;
  final String? certPem;
  final SigStatus sigStatus;

  const Dossier({
    required this.sha256,
    this.pdfPath,
    required this.signed,
    this.signature,
    this.certPem,
    required this.sigStatus,
  });

  factory Dossier.fromJson(Map<String, dynamic> json) {
    final sha = json['sha256'];
    if (sha is! String) {
      throw BridgeParseError('Dossier.sha256 must be a string, got $sha');
    }
    final signed = json['signed'] as bool? ?? false;
    final sigStatusStr = (json['sig_status'] as String?) ?? 'pending';

    return Dossier(
      sha256: sha,
      pdfPath: json['pdf_path'] as String?,
      signed: signed,
      signature: json['signature'] as String?,
      certPem: json['cert_pem'] as String?,
      sigStatus: SigStatus.fromString(sigStatusStr),
    );
  }

  Map<String, dynamic> toJson() => {
        'sha256': sha256,
        'pdf_path': pdfPath,
        'signed': signed,
        'signature': signature,
        'cert_pem': certPem,
        'sig_status': sigStatus.value,
      };
}

class ScanError {
  final String code;
  final String message;
  final String? stage;
  final bool includeStageInJson;

  const ScanError({
    required this.code,
    required this.message,
    this.stage,
    this.includeStageInJson = true,
  });

  factory ScanError.fromJson(Map<String, dynamic> json) => ScanError(
        code: json['code'] as String? ?? 'INTERNAL',
        message: json['message'] as String? ?? 'Unknown error',
        stage: json['stage'] as String?,
        includeStageInJson: json.containsKey('stage'),
      );

  Map<String, dynamic> toJson() => {
        'code': code,
        'message': message,
        if (includeStageInJson) 'stage': stage,
      };
}

/// Complete 17-key ScanResult payload (Contract §4).
class ScanResult {
  final int schemaVersion;
  final String scanId;
  final Verdict verdict;
  final String capturedUtc;
  final String completedUtc;
  final double totalMs;
  final Map<String, double> timingsMs;
  final Quality quality;
  final Geometry? geometry;
  final OcrResult ocr;
  final Map<String, FieldValue> fields;
  final List<CheckItem> checks;
  final Exemption? exemption;
  final CheckSummary summary;
  final Dossier? dossier;
  final Map<String, dynamic>? meta;
  final ScanError? error;

  const ScanResult({
    required this.schemaVersion,
    required this.scanId,
    required this.verdict,
    required this.capturedUtc,
    required this.completedUtc,
    required this.totalMs,
    required this.timingsMs,
    required this.quality,
    this.geometry,
    required this.ocr,
    required this.fields,
    required this.checks,
    this.exemption,
    required this.summary,
    this.dossier,
    this.meta,
    this.error,
  });

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    // Validate required top-level presence (contract §4: exactly 17 keys, always present)
    const requiredKeys = [
      'schema_version',
      'scan_id',
      'verdict',
      'captured_utc',
      'completed_utc',
      'total_ms',
      'timings_ms',
      'quality',
      'geometry',
      'ocr',
      'fields',
      'checks',
      'exemption',
      'summary',
      'dossier',
      'meta',
      'error',
    ];

    for (final key in requiredKeys) {
      if (!json.containsKey(key)) {
        throw BridgeParseError('Missing required ScanResult key: "$key"');
      }
    }

    final schemaVersion = (json['schema_version'] as num).toInt();
    final scanId = json['scan_id'] as String;
    final verdict = Verdict.fromString(json['verdict'] as String);
    final capturedUtc = json['captured_utc'] as String;
    final completedUtc = json['completed_utc'] as String;
    final totalMs = (json['total_ms'] as num).toDouble();

    final rawTimings = json['timings_ms'] as Map<String, dynamic>? ?? {};
    final timingsMs = <String, double>{};
    for (final entry in rawTimings.entries) {
      timingsMs[entry.key] = (entry.value as num).toDouble();
    }

    final quality = Quality.fromJson(json['quality'] as Map<String, dynamic>);
    final geometry = json['geometry'] != null
        ? Geometry.fromJson(json['geometry'] as Map<String, dynamic>)
        : null;

    final ocr = OcrResult.fromJson(json['ocr'] as Map<String, dynamic>);

    final rawFields = json['fields'] as Map<String, dynamic>? ?? {};
    final fields = <String, FieldValue>{};
    for (final entry in rawFields.entries) {
      fields[entry.key] =
          FieldValue.fromJson(entry.value as Map<String, dynamic>);
    }

    final rawChecks = json['checks'] as List<dynamic>? ?? [];
    final checks = rawChecks
        .map((e) => CheckItem.fromJson(e as Map<String, dynamic>))
        .toList();

    final exemption = json['exemption'] != null
        ? Exemption.fromJson(json['exemption'] as Map<String, dynamic>)
        : null;

    final summary =
        CheckSummary.fromJson(json['summary'] as Map<String, dynamic>);

    final dossier = json['dossier'] != null
        ? Dossier.fromJson(json['dossier'] as Map<String, dynamic>)
        : null;

    final meta = json['meta'] as Map<String, dynamic>?;

    final error = json['error'] != null
        ? ScanError.fromJson(json['error'] as Map<String, dynamic>)
        : null;

    return ScanResult(
      schemaVersion: schemaVersion,
      scanId: scanId,
      verdict: verdict,
      capturedUtc: capturedUtc,
      completedUtc: completedUtc,
      totalMs: totalMs,
      timingsMs: timingsMs,
      quality: quality,
      geometry: geometry,
      ocr: ocr,
      fields: fields,
      checks: checks,
      exemption: exemption,
      summary: summary,
      dossier: dossier,
      meta: meta,
      error: error,
    );
  }

  Map<String, dynamic> toJson() => {
        'schema_version': schemaVersion,
        'scan_id': scanId,
        'verdict': verdict.value,
        'captured_utc': capturedUtc,
        'completed_utc': completedUtc,
        'total_ms': totalMs,
        'timings_ms': timingsMs,
        'quality': quality.toJson(),
        'geometry': geometry?.toJson(),
        'ocr': ocr.toJson(),
        'fields': fields.map((k, v) => MapEntry(k, v.toJson())),
        'checks': checks.map((c) => c.toJson()).toList(),
        'exemption': exemption?.toJson(),
        'summary': summary.toJson(),
        'dossier': dossier?.toJson(),
        'meta': meta,
        'error': error?.toJson(),
      };
}

class PingCapabilities {
  final List<String> stagesImplemented;
  final List<String> stagesPlanned;
  final bool dossier;
  final String signing;
  final bool sync;
  final List<String> ocrEngines;

  const PingCapabilities({
    this.stagesImplemented = const [],
    this.stagesPlanned = const [],
    this.dossier = false,
    this.signing = 'platform',
    this.sync = false,
    this.ocrEngines = const [],
  });

  factory PingCapabilities.fromJson(Map<String, dynamic> json) =>
      PingCapabilities(
        stagesImplemented:
            (json['stages_implemented'] as List<dynamic>? ?? const [])
                .map((e) => e.toString()).toList(),
        stagesPlanned:
            (json['stages_planned'] as List<dynamic>? ?? const [])
                .map((e) => e.toString()).toList(),
        dossier: json['dossier'] as bool? ?? false,
        signing: json['signing'] as String? ?? 'platform',
        sync: json['sync'] as bool? ?? false,
        ocrEngines: (json['ocr_engines'] as List<dynamic>? ?? const [])
            .map((e) => e.toString()).toList(),
      );

  Map<String, dynamic> toJson() => {
        'stages_implemented': stagesImplemented,
        'stages_planned': stagesPlanned,
        'dossier': dossier,
        'signing': signing,
        'sync': sync,
        'ocr_engines': ocrEngines,
      };
}

class PingPayload {
  final int schemaVersion;
  final String coreVersion;
  final String channel;
  final PingCapabilities capabilities;

  const PingPayload({
    required this.schemaVersion,
    required this.coreVersion,
    required this.channel,
    required this.capabilities,
  });

  factory PingPayload.fromJson(Map<String, dynamic> json) {
    final sv = json['schema_version'];
    if (sv is! int) {
      throw const BridgeParseError('PingPayload.schema_version must be an int');
    }
    final caps = json['capabilities'];
    if (caps is! Map<String, dynamic>) {
      throw const BridgeParseError('PingPayload.capabilities is required');
    }
    return PingPayload(
      schemaVersion: sv,
      coreVersion: json['core_version'] as String? ?? '',
      channel: json['channel'] as String? ?? '',
      capabilities: PingCapabilities.fromJson(caps),
    );
  }

  Map<String, dynamic> toJson() => {
        'schema_version': schemaVersion,
        'core_version': coreVersion,
        'channel': channel,
        'capabilities': capabilities.toJson(),
      };
}

class QueueStatus {
  final int schemaVersion;
  final int total;
  final int pendingSync;
  final int failed;
  final int signed;
  final int dossiers;

  const QueueStatus({
    this.schemaVersion = 1,
    this.total = 0,
    this.pendingSync = 0,
    this.failed = 0,
    this.signed = 0,
    this.dossiers = 0,
  });

  factory QueueStatus.fromJson(Map<String, dynamic> json) => QueueStatus(
        schemaVersion: json['schema_version'] as int? ?? 1,
        total: json['total'] as int? ?? 0,
        pendingSync: json['pending_sync'] as int? ?? 0,
        failed: json['failed'] as int? ?? 0,
        signed: json['signed'] as int? ?? 0,
        dossiers: json['dossiers'] as int? ?? 0,
      );

  Map<String, dynamic> toJson() => {
        'schema_version': schemaVersion,
        'total': total,
        'pending_sync': pendingSync,
        'failed': failed,
        'signed': signed,
        'dossiers': dossiers,
      };
}

/// Response payload from `sync_now` (Contract §2).
class SyncSummary {
  final int schemaVersion;
  final int attempted;
  final int synced;
  final int failed;
  final int deferred;
  final int remaining;
  final bool offline;
  final String? error;

  const SyncSummary({
    required this.schemaVersion,
    required this.attempted,
    required this.synced,
    required this.failed,
    required this.deferred,
    required this.remaining,
    required this.offline,
    this.error,
  });

  factory SyncSummary.fromJson(Map<String, dynamic> json) {
    if (!json.containsKey('schema_version') ||
        !json.containsKey('attempted') ||
        !json.containsKey('synced') ||
        !json.containsKey('failed') ||
        !json.containsKey('deferred') ||
        !json.containsKey('remaining') ||
        !json.containsKey('offline')) {
      throw const BridgeParseError('Missing required field in SyncSummary');
    }

    return SyncSummary(
      schemaVersion: (json['schema_version'] as num).toInt(),
      attempted: (json['attempted'] as num).toInt(),
      synced: (json['synced'] as num).toInt(),
      failed: (json['failed'] as num).toInt(),
      deferred: (json['deferred'] as num).toInt(),
      remaining: (json['remaining'] as num).toInt(),
      offline: json['offline'] as bool,
      error: json['error'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'schema_version': schemaVersion,
        'attempted': attempted,
        'synced': synced,
        'failed': failed,
        'deferred': deferred,
        'remaining': remaining,
        'offline': offline,
        'error': error,
      };
}

/// Response payload from `attach_signature` (Contract §2, §8).
class SigResponse {
  final int schemaVersion;
  final String scanId;
  final bool accepted;
  final SigStatus sigStatus;
  final bool verified;
  final ScanError? error;

  const SigResponse({
    required this.schemaVersion,
    required this.scanId,
    required this.accepted,
    required this.sigStatus,
    required this.verified,
    this.error,
  });

  factory SigResponse.fromJson(Map<String, dynamic> json) {
    if (!json.containsKey('schema_version') ||
        !json.containsKey('scan_id') ||
        !json.containsKey('accepted') ||
        !json.containsKey('sig_status') ||
        !json.containsKey('verified')) {
      throw const BridgeParseError('Missing required field in SigResponse');
    }

    return SigResponse(
      schemaVersion: (json['schema_version'] as num).toInt(),
      scanId: json['scan_id'] as String,
      accepted: json['accepted'] as bool,
      sigStatus: SigStatus.fromString(json['sig_status'] as String),
      verified: json['verified'] as bool,
      error: json['error'] != null
          ? ScanError.fromJson(json['error'] as Map<String, dynamic>)
          : null,
    );
  }

  Map<String, dynamic> toJson() => {
        'schema_version': schemaVersion,
        'scan_id': scanId,
        'accepted': accepted,
        'sig_status': sigStatus.value,
        'verified': verified,
        'error': error?.toJson(),
      };
}

/// Response payload from `get_dossier` (Brief §2(a)).
class DossierFile {
  final String scanId;
  final String pdfB64;
  final String? sha256;
  final bool signed;
  final String sigStatus;
  final ScanError? error;

  const DossierFile({
    required this.scanId,
    required this.pdfB64,
    this.sha256,
    required this.signed,
    required this.sigStatus,
    this.error,
  });

  factory DossierFile.fromJson(Map<String, dynamic> json) {
    if (json.containsKey('error') && json['error'] != null) {
      return DossierFile(
        scanId: json['scan_id'] as String? ?? '',
        pdfB64: json['pdf_b64'] as String? ?? '',
        sha256: json['sha256'] as String?,
        signed: json['signed'] as bool? ?? false,
        sigStatus: json['sig_status'] as String? ?? 'pending',
        error: ScanError.fromJson(json['error'] as Map<String, dynamic>),
      );
    }

    if (!json.containsKey('scan_id') || !json.containsKey('pdf_b64')) {
      throw const BridgeParseError('Missing required field in DossierFile');
    }

    return DossierFile(
      scanId: json['scan_id'] as String,
      pdfB64: json['pdf_b64'] as String,
      sha256: json['sha256'] as String?,
      signed: json['signed'] as bool? ?? false,
      sigStatus: json['sig_status'] as String? ?? 'pending',
      error: null,
    );
  }

  Map<String, dynamic> toJson() => {
        'scan_id': scanId,
        'pdf_b64': pdfB64,
        'sha256': sha256,
        'signed': signed,
        'sig_status': sigStatus,
        if (error != null) 'error': error?.toJson(),
      };
}
