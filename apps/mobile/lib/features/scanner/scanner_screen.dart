import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/state/bridge_provider.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/util/image_pipeline.dart';
import 'review_screen.dart';
import 'widgets/capture_frame.dart';
import 'widgets/capture_guidance.dart';

/// Live Camera Scanner Screen (Brief §5.3).
/// Portrait camera preview, corner-bracket viewfinder framing, contextual guidance, and 72dp shutter.
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
      _statusText = 'Running native vision prepass & OCR...';
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
    final session = ref.watch(scanSessionProvider);

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: Text(session.config.commodity.isNotEmpty
            ? session.config.commodity
            : 'Capture Package Evidence'),
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

          // 2. Viewfinder Framing (Corner brackets)
          if (_isInitialized)
            const Positioned.fill(
              child: IgnorePointer(
                child: CaptureFrame(
                  bracketLength: 32,
                  strokeWidth: 3.5,
                  bracketColor: Colors.white70,
                ),
              ),
            ),

          // 3. Guidance Card at Top
          if (_isInitialized)
            Positioned(
              top: 16,
              left: 16,
              right: 16,
              child: CaptureGuidance(
                state: _isCapturing ? CaptureState.processing : CaptureState.aligning,
                customMessage: _statusText,
              ),
            ),

          // 4. Processing Overlay
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

          // 5. Bottom Shutter Bar
          Positioned(
            bottom: 28,
            left: 0,
            right: 0,
            child: Center(
              child: Semantics(
                button: true,
                enabled: !_isCapturing,
                label: _isCapturing ? 'Capture processing' : 'Capture package evidence',
                child: GestureDetector(
                  onTap: _isCapturing ? null : _onCapture,
                  child: Container(
                  width: 76,
                  height: 76,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _isCapturing ? Colors.grey.shade600 : Colors.white,
                    border: Border.all(
                      color: AppColors.navy,
                      width: 4,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.4),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Center(
                    child: Icon(
                      Icons.camera_alt,
                      color: _isCapturing ? Colors.white54 : AppColors.navy,
                      size: 34,
                    ),
                  ),
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
