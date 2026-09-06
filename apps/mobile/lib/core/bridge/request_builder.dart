import 'bridge_models.dart';

/// Builder for scan_tokens request payload (Contract §14).
/// All coordinate bboxes must be in the submitted-image pixel space.
class ScanTokensRequestBuilder {
  int schemaVersion = 1;
  List<Token> tokens = [];
  Quality? quality;
  Geometry? geometry;
  List<Map<String, dynamic>> glyphs = [];
  String? imageB64;
  String? imageSha256;
  String? shapeHint;
  String? capturedUtc;
  Map<String, dynamic>? gps;
  Map<String, dynamic>? device;
  Map<String, dynamic> options = {};

  ScanTokensRequestBuilder();

  ScanTokensRequestBuilder setTokens(List<Token> t) {
    tokens = List.of(t);
    return this;
  }

  ScanTokensRequestBuilder setQuality({
    bool? ok,
    double? laplacianVar,
    double? glarePct,
    List<String>? prompts,
    BBox? glareBbox,
  }) {
    quality = Quality(
      ok: ok,
      laplacianVar: laplacianVar,
      glarePct: glarePct,
      prompts: prompts ?? const [],
      glareBbox: glareBbox,
    );
    return this;
  }

  ScanTokensRequestBuilder setGeometry({
    String? shape,
    String? shapeDetected,
    double? mmPerPx,
    double? pdaCm2,
    String? pdaMethod,
    List<RoiItem>? rois,
  }) {
    geometry = Geometry(
      shape: shape,
      shapeDetected: shapeDetected,
      mmPerPx: mmPerPx,
      pdaCm2: pdaCm2,
      pdaMethod: pdaMethod,
      rois: rois ?? const [],
    );
    return this;
  }

  ScanTokensRequestBuilder setImage({
    required String b64,
    String? sha256,
  }) {
    imageB64 = b64;
    imageSha256 = sha256;
    return this;
  }

  ScanTokensRequestBuilder setCapturedUtc(DateTime dt) {
    capturedUtc = dt.toUtc().toIso8601String();
    return this;
  }

  ScanTokensRequestBuilder setGps({
    required double lat,
    required double lon,
    double? accuracyM,
  }) {
    gps = {
      'lat': lat,
      'lon': lon,
      if (accuracyM != null) 'accuracy_m': accuracyM,
    };
    return this;
  }

  ScanTokensRequestBuilder setDevice({
    String? model,
    String? os,
    String? appBuild,
  }) {
    device = {
      if (model != null) 'model': model,
      if (os != null) 'os': os,
      if (appBuild != null) 'app_build': appBuild,
    };
    return this;
  }

  ScanTokensRequestBuilder setShapeHint(String hint) {
    shapeHint = hint;
    return this;
  }

  ScanTokensRequestBuilder setOptions({
    bool? institutional,
    bool? fastFood,
    String? commodity,
    bool? blown,
    double? packageHeightCm,
    double? packageWidthCm,
    double? packageDiameterCm,
    double? totalSurfaceCm2,
    double? markerSideMm,
    double? cameraFocalPx,
    int? cylinderLeftPx,
    int? cylinderRightPx,
    bool? dossierOnPass,
  }) {
    if (institutional != null) options['institutional'] = institutional;
    if (fastFood != null) options['fast_food'] = fastFood;
    if (commodity != null && commodity.isNotEmpty) {
      options['commodity'] = commodity;
    }
    if (blown != null) options['blown'] = blown;
    if (packageHeightCm != null) options['package_height_cm'] = packageHeightCm;
    if (packageWidthCm != null) options['package_width_cm'] = packageWidthCm;
    if (packageDiameterCm != null) {
      options['package_diameter_cm'] = packageDiameterCm;
    }
    if (totalSurfaceCm2 != null) options['total_surface_cm2'] = totalSurfaceCm2;
    if (markerSideMm != null) options['marker_side_mm'] = markerSideMm;
    if (cameraFocalPx != null) options['camera_focal_px'] = cameraFocalPx;
    if (cylinderLeftPx != null) options['cylinder_left_px'] = cylinderLeftPx;
    if (cylinderRightPx != null) options['cylinder_right_px'] = cylinderRightPx;
    if (dossierOnPass != null) options['dossier_on_pass'] = dossierOnPass;
    return this;
  }

  Map<String, dynamic> build() {
    if (tokens.isEmpty) {
      throw const BridgeParseError(
          'ScanTokensRequest requires non-empty tokens list');
    }

    final out = <String, dynamic>{
      'tokens': tokens.map((t) => t.toJson()).toList(),
    };

    if (schemaVersion != 1) {
      out['schema_version'] = schemaVersion;
    }
    if (quality != null) {
      out['quality'] = quality!.toJson();
    }
    if (geometry != null) {
      out['geometry'] = geometry!.toRequestJson();
    }
    if (glyphs.isNotEmpty) {
      out['glyphs'] = glyphs;
    }
    if (imageB64 != null) {
      out['image_b64'] = imageB64;
    }
    if (imageSha256 != null) {
      out['image_sha256'] = imageSha256;
    }
    if (shapeHint != null && shapeHint!.isNotEmpty) {
      out['shape_hint'] = shapeHint;
    }
    if (capturedUtc != null) {
      out['captured_utc'] = capturedUtc;
    }
    if (gps != null) {
      out['gps'] = gps;
    }
    if (device != null) {
      out['device'] = device;
    }
    out['options'] = options;

    return out;
  }
}
