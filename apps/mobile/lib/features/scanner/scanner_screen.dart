import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/state/bridge_provider.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/util/image_pipeline.dart';
import 'review_screen.dart';
import 'widgets/capture_frame.dart';
import 'widgets/capture_guidance.dart';
import 'widgets/focus_reticle.dart';

/// Live Camera Scanner Screen (Brief §5.3).
/// Enhanced for high-fidelity statutory declaration capture:
/// - Ultra-high resolution sensor preset (1080p+ for tiny font OCR)
/// - Hardware Torch / Flashlight toggle for godown and low-light inspection
/// - Tap-to-Focus & Tap-to-Expose with animated visual reticle
/// - 1x / 2x Optical & Digital Zoom controls to prevent casting phone shadows
/// - Anti-blur focus locking prior to shutter exposure
/// - Shutter flash confirmation & haptic feedback
/// Packaging lighting presets to prevent glare and reflections on different packet types.
enum PackagingLightingMode {
  normal(offset: 0.0, label: 'Normal', name: 'Normal Lighting'),
  antiGlare(offset: -1.0, label: 'Anti-Glare', name: 'Glossy Plastic'),
  foil(offset: -2.0, label: 'Foil Pack', name: 'Shiny Foil'),
  brighten(offset: 1.0, label: 'Brighten', name: 'Dark Room');

  final double offset;
  final String label;
  final String name;
  const PackagingLightingMode({required this.offset, required this.label, required this.name});
}


class ScannerScreen extends ConsumerStatefulWidget {
  const ScannerScreen({super.key});

  @override
  ConsumerState<ScannerScreen> createState() => _ScannerScreenState();
}

class _ScannerScreenState extends ConsumerState<ScannerScreen>
    with WidgetsBindingObserver {
  CameraController? _controller;
  List<CameraDescription>? _cameras;
  bool _isCapturing = false;
  bool _isTorchOn = false;
  PackagingLightingMode _activeLightingMode = PackagingLightingMode.normal;
  bool _isFocusLocked = false;
  double _minExposureOffset = 0.0;
  double _maxExposureOffset = 0.0;
  bool _showShutterFlash = false;
  String? _statusText;

  Offset? _focusPoint;
  double _currentZoom = 1.0;
  double _minZoom = 1.0;
  double _maxZoom = 1.0;
  double _baseZoom = 1.0;

  bool get _isInitialized => _controller != null && _controller!.value.isInitialized;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initCamera();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final CameraController? cameraController = _controller;

    // App state changed before camera initialized
    if (cameraController == null || !cameraController.value.isInitialized) {
      return;
    }

    if (state == AppLifecycleState.inactive) {
      // Free the camera resource when inactive to prevent locking Camera2
      cameraController.dispose();
      _controller = null;
      if (mounted) setState(() {});
    } else if (state == AppLifecycleState.resumed) {
      // Re-initialize camera when returning to foreground
      _initCamera();
    }
  }

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras != null && _cameras!.isNotEmpty) {
        final backCamera = _cameras!.firstWhere(
          (c) => c.lensDirection == CameraLensDirection.back,
          orElse: () => _cameras!.first,
        );

        // Multi-tier cascade: ultraHigh (4K/8MP) -> veryHigh (1080p) -> high (720p) -> max (fallback)
        CameraController? controller;
        for (final preset in [
          ResolutionPreset.ultraHigh,
          ResolutionPreset.veryHigh,
          ResolutionPreset.high,
          ResolutionPreset.max,
        ]) {
          try {
            final testController = CameraController(
              backCamera,
              preset,
              enableAudio: false,
              imageFormatGroup: ImageFormatGroup.jpeg,
            );
            await testController.initialize();
            controller = testController;
            break;
          } catch (_) {
            continue;
          }
        }

        if (controller == null) {
          throw Exception('No supported camera resolution found');
        }

        _controller = controller;

        // Fetch zoom boundaries
        try {
          _minZoom = await _controller!.getMinZoomLevel();
          _maxZoom = await _controller!.getMaxZoomLevel();
        } catch (_) {
          _minZoom = 1.0;
          _maxZoom = 1.0;
        }

        // Fetch exposure offset boundaries
        try {
          _minExposureOffset = await _controller!.getMinExposureOffset();
          _maxExposureOffset = await _controller!.getMaxExposureOffset();
        } catch (_) {
          _minExposureOffset = 0.0;
          _maxExposureOffset = 0.0;
        }

        // Lock capture orientation to portrait to maintain consistent evidence alignment
        try {
          await _controller!.lockCaptureOrientation(DeviceOrientation.portraitUp);
        } catch (_) {}

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
    WidgetsBinding.instance.removeObserver(this);
    // Ensure torch is turned off upon exit
    if (_isTorchOn) {
      _controller?.setFlashMode(FlashMode.off);
    }
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _toggleTorch() async {
    if (_controller == null || !_controller!.value.isInitialized) return;
    try {
      final newMode = _isTorchOn ? FlashMode.off : FlashMode.torch;
      await _controller!.setFlashMode(newMode);
      if (mounted) {
        setState(() => _isTorchOn = !_isTorchOn);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Flash/Torch not available on this camera: $e'),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    }
  }

  Future<void> _cycleLightingMode() async {
    if (_controller == null || !_controller!.value.isInitialized) return;
    final modes = PackagingLightingMode.values;
    final nextIndex = (modes.indexOf(_activeLightingMode) + 1) % modes.length;
    final nextMode = modes[nextIndex];

    try {
      final targetOffset = nextMode.offset.clamp(_minExposureOffset, _maxExposureOffset);
      await _controller!.setExposureOffset(targetOffset);
      if (mounted) {
        setState(() {
          _activeLightingMode = nextMode;
        });
        HapticFeedback.selectionClick();
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '${nextMode.name} enabled: '
              '${nextMode == PackagingLightingMode.foil ? "Reduces glare on shiny foil packs." : (nextMode == PackagingLightingMode.antiGlare ? "Reduces reflections on glossy plastic packets." : (nextMode == PackagingLightingMode.brighten ? "Brightens image in dimly lit godowns." : "Standard natural lighting."))}',
            ),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Lighting adjustment unavailable: $e')),
        );
      }
    }
  }

  Future<void> _toggleFocusLock() async {
    if (_controller == null || !_controller!.value.isInitialized || _isCapturing) return;

    final newLockState = !_isFocusLocked;
    try {
      if (newLockState) {
        await _controller!.setFocusMode(FocusMode.locked);
        await _controller!.setExposureMode(ExposureMode.locked);
        HapticFeedback.heavyImpact();
      } else {
        await _controller!.setFocusMode(FocusMode.auto);
        await _controller!.setExposureMode(ExposureMode.auto);
        HapticFeedback.mediumImpact();
      }
      if (mounted) {
        setState(() {
          _isFocusLocked = newLockState;
        });
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              newLockState
                  ? 'Focus locked. Movement won\'t cause blur.'
                  : 'Focus unlocked. Automatic focus restored.',
            ),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Focus lock failed: $e')),
        );
      }
    }
  }

  Future<void> _onViewfinderTap(TapDownDetails details, Size previewSize) async {
    if (_controller == null || !_controller!.value.isInitialized || _isCapturing) return;

    final localPos = details.localPosition;
    final double nx = (localPos.dx / previewSize.width).clamp(0.0, 1.0);
    final double ny = (localPos.dy / previewSize.height).clamp(0.0, 1.0);

    setState(() {
      _focusPoint = localPos;
    });

    try {
      if (_isFocusLocked) {
        // When locked, tapping still focuses and exposes at that specific point and keeps it locked
        await _controller!.setFocusPoint(Offset(nx, ny));
        await _controller!.setExposurePoint(Offset(nx, ny));
      } else {
        await _controller!.setFocusMode(FocusMode.auto);
        await _controller!.setFocusPoint(Offset(nx, ny));
        await _controller!.setExposureMode(ExposureMode.auto);
        await _controller!.setExposurePoint(Offset(nx, ny));
      }
    } catch (_) {}
  }

  Future<void> _setZoom(double zoom) async {
    if (_controller == null || !_controller!.value.isInitialized) return;
    final targetZoom = zoom.clamp(_minZoom, _maxZoom);
    try {
      await _controller!.setZoomLevel(targetZoom);
      if (mounted) {
        setState(() => _currentZoom = targetZoom);
      }
    } catch (_) {}
  }

  void _onScaleStart(ScaleStartDetails details) {
    _baseZoom = _currentZoom;
  }

  void _onScaleUpdate(ScaleUpdateDetails details) {
    if (_minZoom == _maxZoom) return;
    final newZoom = (_baseZoom * details.scale).clamp(_minZoom, _maxZoom);
    _setZoom(newZoom);
  }

  Future<void> _onCapture() async {
    if (_controller == null || !_controller!.value.isInitialized || _isCapturing) {
      return;
    }

    setState(() {
      _isCapturing = true;
      _showShutterFlash = true;
      _statusText = 'Verifying evidence & running OCR...';
    });

    // Tactile haptic feedback
    HapticFeedback.mediumImpact();

    // Fade out shutter flash effect
    Future.delayed(const Duration(milliseconds: 80), () {
      if (mounted) setState(() => _showShutterFlash = false);
    });

    try {
      // If focus not explicitly locked and no manual point was tapped, ensure center focus point
      if (!_isFocusLocked) {
        if (_focusPoint == null) {
          try {
            await _controller!.setFocusPoint(const Offset(0.5, 0.5));
            await _controller!.setExposurePoint(const Offset(0.5, 0.5));
          } catch (_) {}
        }
        // Lock focus immediately before firing shutter to prevent lens hunting blur
        try {
          await _controller!.setFocusMode(FocusMode.locked);
        } catch (_) {}
      }

      // Allow 140ms for VCM lens actuator & optical stabilization to settle micro-shake
      await Future.delayed(const Duration(milliseconds: 140));

      final xFile = await _controller!.takePicture();

      // Restore focus mode to auto if it wasn't locked by user
      if (!_isFocusLocked) {
        try {
          await _controller!.setFocusMode(FocusMode.auto);
        } catch (_) {}
      }

      // Process captured image (decode, bake EXIF, resize to 1600, encode, ML Kit OCR)
      final processed = await ImagePipeline.processCapturedImage(xFile.path);

      // Call Kotlin native vision prepass (fiducial detection, quality check, mm_per_px)
      final bridge = ref.read(netraBridgeProvider);
      final fiducialMm = ref.read(scanSessionProvider).config.fiducialMm;
      final prepassMap = await bridge.visionPrepass(
        imageB64: processed.base64,
        options: {
          'marker_side_mm': fiducialMm,
          'marker_size_mm': fiducialMm,
        },
      );

      ref.read(scanSessionProvider.notifier).setCapturedImage(
        image: processed,
        prepassResult: prepassMap,
      );

      if (!mounted) return;

      // Turn off torch when navigating to review screen
      if (_isTorchOn) {
        try {
          await _controller?.setFlashMode(FlashMode.off);
          _isTorchOn = false;
        } catch (_) {}
      }

      if (!mounted) return;

      // Navigate to ReviewScreen. If officer taps RETAKE, it pops back to camera cleanly
      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const ReviewScreen()),
      );

      // Upon returning from ReviewScreen (e.g. retake requested), reset state
      if (mounted) {
        setState(() {
          _isCapturing = false;
          _statusText = null;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isCapturing = false;
          _statusText = null;
          _showShutterFlash = false;
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
        title: Text(
          session.config.commodity.isNotEmpty
              ? session.config.commodity
              : 'Capture Package Evidence',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          // Packaging Lighting Preset (Normal / Anti-Glare / Foil Pack / Brighten)
          Center(
            child: InkWell(
              borderRadius: BorderRadius.circular(6),
              onTap: _isInitialized ? _cycleLightingMode : null,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                margin: const EdgeInsets.only(right: 4),
                decoration: BoxDecoration(
                  color: _activeLightingMode != PackagingLightingMode.normal
                      ? const Color(0xFFFFD54F).withValues(alpha: 0.2)
                      : Colors.white12,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: _activeLightingMode != PackagingLightingMode.normal
                        ? const Color(0xFFFFD54F)
                        : Colors.white24,
                    width: 0.8,
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _activeLightingMode == PackagingLightingMode.foil
                          ? Icons.shield_outlined
                          : (_activeLightingMode == PackagingLightingMode.antiGlare
                              ? Icons.brightness_medium
                              : (_activeLightingMode == PackagingLightingMode.brighten
                                  ? Icons.brightness_high
                                  : Icons.light_mode_outlined)),
                      size: 13,
                      color: _activeLightingMode != PackagingLightingMode.normal
                          ? const Color(0xFFFFD54F)
                          : Colors.white70,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _activeLightingMode.label,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: _activeLightingMode != PackagingLightingMode.normal
                            ? const Color(0xFFFFD54F)
                            : Colors.white70,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Focus Lock Toggle Button
          IconButton(
            tooltip: _isFocusLocked ? 'Unlock Focus' : 'Lock Focus',
            icon: Icon(
              _isFocusLocked ? Icons.lock : Icons.lock_open,
              color: _isFocusLocked ? const Color(0xFFFFD54F) : Colors.white70,
            ),
            onPressed: _isInitialized ? _toggleFocusLock : null,
          ),

          // Flashlight Toggle Button
          IconButton(
            tooltip: _isTorchOn ? 'Turn Off Flashlight' : 'Turn On Flashlight',
            icon: Icon(
              _isTorchOn ? Icons.flash_on : Icons.flash_off,
              color: _isTorchOn ? const Color(0xFFFFD54F) : Colors.white70,
            ),
            onPressed: _isInitialized ? _toggleTorch : null,
          ),
          const SizedBox(width: 4),
        ],
      ),
      body: Stack(
        children: [
          // 1. Camera Preview with Tap-to-Focus, Long-Press AE/AF Lock & Pinch-to-Zoom Gestures
          if (_isInitialized && _controller != null)
            Positioned.fill(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final double rawRatio = _controller!.value.aspectRatio;
                  final double previewRatio = rawRatio > 1.0 ? (1.0 / rawRatio) : rawRatio;
                  return GestureDetector(
                     behavior: HitTestBehavior.opaque,
                     onTapDown: (details) => _onViewfinderTap(
                       details,
                       Size(constraints.maxWidth, constraints.maxHeight),
                     ),
                     onLongPress: _toggleFocusLock,
                     onScaleStart: _onScaleStart,
                     onScaleUpdate: _onScaleUpdate,
                     child: Center(
                       child: AspectRatio(
                         aspectRatio: previewRatio,
                         child: CameraPreview(_controller!),
                       ),
                     ),
                   );
                },
              ),
            )
          else if (_statusText != null && !_isInitialized)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.videocam_off_outlined, color: Colors.amber, size: 48),
                    const SizedBox(height: 16),
                    Text(
                      _statusText!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white, fontSize: 14),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: () {
                        setState(() {
                          _statusText = null;
                        });
                        _initCamera();
                      },
                      icon: const Icon(Icons.refresh),
                      label: const Text('Retry Camera'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF1E88E5),
                        foregroundColor: Colors.white,
                      ),
                    ),
                  ],
                ),
              ),
            )
          else
            const Center(
              child: CircularProgressIndicator(color: Colors.white),
            ),

          // 2. Viewfinder Framing (Corner brackets with center level reticle & edge alignment ticks)
          if (_isInitialized)
            const Positioned.fill(
              child: IgnorePointer(
                child: CaptureFrame(
                  bracketLength: 32,
                  strokeWidth: 3.5,
                  bracketColor: Colors.white70,
                  showCenterGuide: true,
                ),
              ),
            ),

          // 3. Floating Focus Locked Badge
          if (_isFocusLocked)
            Positioned(
              top: 72,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFD54F),
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.45),
                        blurRadius: 6,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.lock, size: 12, color: Colors.black),
                      SizedBox(width: 4),
                      Text(
                        'FOCUS LOCKED',
                        style: TextStyle(
                          color: Colors.black,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.6,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // 4. Animated Tap-to-Focus Reticle
          if (_focusPoint != null)
            FocusReticle(
              position: _focusPoint!,
              onDismiss: () {
                if (mounted) setState(() => _focusPoint = null);
              },
            ),

          // 5. Contextual Guidance Banner at Top
          if (_isInitialized)
            Positioned(
              top: 14,
              left: 16,
              right: 16,
              child: CaptureGuidance(
                state: _isCapturing ? CaptureState.processing : CaptureState.aligning,
                customMessage: _statusText,
                subTip: _isFocusLocked
                    ? 'Focus locked. Long-press screen or tap lock icon to release.'
                    : (_activeLightingMode == PackagingLightingMode.foil
                        ? 'Foil Pack mode: Glare reduced for metallic packaging.'
                        : (_activeLightingMode == PackagingLightingMode.antiGlare
                            ? 'Anti-Glare mode: Reflections reduced on glossy packets.'
                            : (_activeLightingMode == PackagingLightingMode.brighten
                                ? 'Brighten mode: Boosted light for dark rooms or godowns.'
                                : (_currentZoom < 1.5
                                    ? 'Tip: Tap "2x Close-up" to inspect small text clearly'
                                    : 'Close-up active: Hold phone 15-20cm away from package.')))),
              ),
            ),

          // 6. Quick Zoom Controls (1x, 2x MACRO, 3x) above shutter
          if (_isInitialized && _maxZoom > 1.0)
            Positioned(
              bottom: 122,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.65),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Colors.white24, width: 1),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _buildZoomButton(label: '1x', targetZoom: 1.0),
                      const SizedBox(width: 4),
                      if (_maxZoom >= 2.0)
                        _buildZoomButton(label: '2x Close-up', targetZoom: 2.0),
                      if (_maxZoom >= 3.0) ...[
                        const SizedBox(width: 4),
                        _buildZoomButton(label: '3x', targetZoom: 3.0),
                      ],
                    ],
                  ),
                ),
              ),
            ),

          // 6. Visual Shutter Flash Confirmation Overlay
          if (_showShutterFlash)
            Positioned.fill(
              child: IgnorePointer(
                child: Container(
                  color: Colors.white.withValues(alpha: 0.85),
                ),
              ),
            ),

          // 7. Processing Overlay
          if (_isCapturing)
            Positioned.fill(
              child: Container(
                color: Colors.black.withValues(alpha: 0.72),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const CircularProgressIndicator(color: Colors.white),
                      const SizedBox(height: 16),
                      Text(
                        _statusText ?? 'Processing capture...',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // 8. Bottom Shutter Bar
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

  Widget _buildZoomButton({required String label, required double targetZoom}) {
    final bool isSelected = (_currentZoom - targetZoom).abs() < 0.25;

    return GestureDetector(
      onTap: () => _setZoom(targetZoom),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.black : Colors.white70,
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
          ),
        ),
      ),
    );
  }
}
