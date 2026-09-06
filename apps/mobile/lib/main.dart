import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() => runApp(const NetraDiag());

class NetraDiag extends StatefulWidget {
  const NetraDiag({super.key});
  @override
  State<NetraDiag> createState() => _NetraDiagState();
}

class _NetraDiagState extends State<NetraDiag> {
  static const _ch = MethodChannel('netra.core');
  String _out = 'NETRA device diagnostic — tap a button';

  Future<void> _call(String method, [String? arg]) async {
    setState(() => _out = 'calling $method ...');
    try {
      final raw = await _ch.invokeMethod<String>(method, arg);
      setState(() => _out = const JsonEncoder.withIndent('  ')
          .convert(jsonDecode(raw!)));
    } catch (e) {
      setState(() => _out = 'ERROR: $e');
    }
  }

  /// The SIH26034 demo label as ML Kit line tokens — the exact payload
  /// shape the real app will send after OCR.
  static const _tokens = [
    {"text": "Instant Masala Noodles", "bbox": [200, 60, 420, 60], "conf": 0.98},
    {"text": "Net Quantity:", "bbox": [120, 340, 150, 30], "conf": 0.96},
    {"text": "70 gms", "bbox": [280, 340, 90, 30], "conf": 0.97},
    {"text": "MRP", "bbox": [120, 388, 60, 40], "conf": 0.97},
    {"text": "₹ 14.00", "bbox": [185, 388, 110, 40], "conf": 0.98},
    {"text": "Unit Sale Price", "bbox": [120, 432, 160, 30], "conf": 0.95},
    {"text": "₹ 0.35 / g", "bbox": [285, 432, 130, 30], "conf": 0.96},
    {"text": "MFG", "bbox": [40, 560, 70, 26], "conf": 0.97},
    {"text": "08/2026", "bbox": [115, 560, 90, 26], "conf": 0.98},
    {"text": "Imported by: Global Foods,", "bbox": [40, 600, 300, 26], "conf": 0.95},
    {"text": "Mumbai 400001", "bbox": [40, 630, 180, 26], "conf": 0.96},
    {"text": "Made in PRC", "bbox": [40, 700, 160, 26], "conf": 0.96},
    {"text": "Consumer Care: Global Foods,", "bbox": [40, 740, 300, 26], "conf": 0.94},
    {"text": "Tel: 1800-123-4567", "bbox": [40, 770, 220, 26], "conf": 0.95},
  ];

  void _scanTokens() => _call('scan_tokens', jsonEncode({
        "tokens": _tokens,
        "geometry": {
          "shape": "pouch",
          "mm_per_px": 0.04,
          "pda_cm2": 80.0,
          "pda_method": "demo",
        },
        "quality": {"ok": true},
        "captured_utc": DateTime.now().toUtc().toIso8601String(),
        "device": {"model": "diagnostic shell", "os": "android"},
      }));

  // 1x1 gray JPEG in base64
  static const _tinyJpeg =
      '/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=';

  void _visionPrepass() => _call('vision_prepass', jsonEncode({
        "image_b64": _tinyJpeg,
        "options": {"shape_hint": "rectangular"},
      }));


  @override
  Widget build(BuildContext context) => MaterialApp(
        home: Scaffold(
          appBar: AppBar(title: const Text('NETRA device diagnostic')),
          body: Column(children: [
            Wrap(spacing: 8, runSpacing: 8, children: [
              ElevatedButton(
                  onPressed: () => _call('ping'), child: const Text('ping')),
              ElevatedButton(
                  onPressed: () => _call('queue_status'),
                  child: const Text('queue')),
              ElevatedButton(
                  onPressed: () => _call('smoke'), child: const Text('smoke')),
              ElevatedButton(
                  onPressed: _scanTokens,
                  style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.deepPurple,
                      foregroundColor: Colors.white),
                  child: const Text('scan_tokens ▶ VIOLATION')),
              ElevatedButton(
                  onPressed: _visionPrepass,
                  style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.teal,
                      foregroundColor: Colors.white),
                  child: const Text('vision_prepass')),
            ]),
            Expanded(
                child: SingleChildScrollView(
                    padding: const EdgeInsets.all(12),
                    child: SelectableText(_out,
                        style: const TextStyle(
                            fontFamily: 'monospace', fontSize: 11)))),
          ]),
        ),
      );

}
