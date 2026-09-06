import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/state/bridge_provider.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/util/image_pipeline.dart';
import 'review_screen.dart';

/// Live Camera Scanner Screen (Brief §5.3).
/// Portrait camera preview, guidance banner for blur/glare, 72dp shutter button.
class ScannerScreen extends ConsumerStatefulWidget {
  const ScannerScreen({super.key});

  @override
  ConsumerState<ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends ConsumerState<ScannerScreen> {
  CameraController? _controller;
  List<CameraDescription>? _cameras;
  bool _isCapturing = false;
  String? _statusText;

  bool get _isInitialized => _controller != null && _controller!.value.isInitialized;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras != null && _cameras!.isNotEmpty) {
        final backCamera = _cameras!.firstWhere(
          (c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => _cameras!.first,
        );

        _controller = CameraController(
          backCamera,
          ResolutionPreset.high,
          enableAudio: false,
        );

        await _controller!.initialize();
        if (mounted) setState(() {});
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _statusText = 'Camera initialization failed: $e';
        });
      }
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _onCapture() async {
    if (_controller == null || !_controller!.value.isInitialized || _isCapturing) {
      return;
    }

    setState(() {
      _isCapturing = true;
      _statusText = 'Processing image & running native vision prepass...';
    });

    try {
      final xFile = await _controller!.takePicture();

      // Run ImagePipeline (decode -> single resize to 1600 long-edge -> JPEG 90 -> ML Kit OCR)
      final processed = await ImagePipeline.processCapturedImage(xFile.path);

      // Call Kotlin native vision prepass
      final bridge = ref.read(netraBridgeProvider);
      final prepassMap = await bridge.visionPrepass(
        imageB64: processed.base64,
        options: {'marker_size_mm': ref.read(scanSessionProvider).config.fiducialMm},
      );

      ref.read(scanSessionProvider.notifier).setCapturedImage(
        image: processed,
        prepassResult: prepassMap,
      );

      if (!mounted) return;

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const ReviewScreen()),
      );
    } catch (e) {
      if (mounted) {
        setState(() {
          _isCapturing = false;
          _statusText = null;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Capture processing error: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Capture Package Evidence'),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
      ),
      body: Stack(
        children: [
          // 1. Camera Preview
          if (_isInitialized && _controller != null)
            Positioned.fill(
              child: AspectRatio(
                aspectRatio: _controller!.value.aspectRatio,
                child: CameraPreview(_controller!),
              ),
            )
          else
            const Center(
              child: CircularProgressIndicator(color: Colors.white),
            ),

          // 2. Guidance Card at Top
          if (_isInitialized)
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.7),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white24, width: 1),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.white, size: 18),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Align package & fiducial card flat in bright light. Avoid glare.',
                        style: TextStyle(color: Colors.white, fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // 3. Processing Overlay
          if (_isCapturing)
            Positioned.fill(
              child: Container(
                color: Colors.black.withValues(alpha: 0.7),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircularProgressIndicator(color: Colors.white),
                      const SizedBox(height: 16),
                      Text(
                        _statusText ?? 'Processing capture...',
                        style: const TextStyle(color: Colors.white, fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // 4. Bottom Shutter Bar
          Positioned(
            bottom: 24,
            left: 0,
            right: 0,
            child: Center(
              child: GestureDetector(
                onTap: _isCapturing ? null : _onCapture,
                child: Container(
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _isCapturing ? Colors.grey : Colors.white,
                    border: Border.all(color: AppColors.navy, width: 4),
                  ),
                  child: const Center(
                    child: Icon(Icons.camera_alt, color: AppColors.navy, size: 32),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
