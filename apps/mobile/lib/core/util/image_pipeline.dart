import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image/image.dart' as img;
import 'package:path_provider/path_provider.dart';
import '../bridge/bridge_models.dart';

/// Image processing result following Brief §6.
class ProcessedImage {
  final File file;
  final String base64;
  final String sha256;
  final int width;
  final int height;
  final List<Token> tokens;

  const ProcessedImage({
    required this.file,
    required this.base64,
    required this.sha256,
    required this.width,
    required this.height,
    required this.tokens,
  });
}

/// Image Pipeline adhering strictly to Brief §6:
/// 1. read raw bytes from camera
/// 2. decodeJpg -> if longest side > 1600, copyResize ONCE (interpolation: average)
/// 3. encodeJpg(quality: 90) -> singleBytes
/// 4. write singleBytes to temp file
/// 5. image_b64 = base64Encode(singleBytes); sha256 of singleBytes
/// 6. ML Kit: InputImage.fromFilePath(tempPath) -> line-level tokens
abstract final class ImagePipeline {
  static final TextRecognizer _recognizer = TextRecognizer(
    script: TextRecognitionScript.latin,
  );

  static Future<ProcessedImage> processCapturedImage(String rawImagePath) async {
    final rawBytes = await File(rawImagePath).readAsBytes();
    img.Image? decoded = img.decodeImage(rawBytes);
    if (decoded == null) {
      throw Exception('Failed to decode captured image');
    }

    // 2. Resize once if longest side > 1600
    final int longestSide = decoded.width > decoded.height ? decoded.width : decoded.height;
    if (longestSide > 1600) {
      if (decoded.width >= decoded.height) {
        decoded = img.copyResize(
          decoded,
          width: 1600,
          interpolation: img.Interpolation.average,
        );
      } else {
        decoded = img.copyResize(
          decoded,
          height: 1600,
          interpolation: img.Interpolation.average,
        );
      }
    }

    // 3. encodeJpg(quality: 90)
    final singleBytes = img.encodeJpg(decoded, quality: 90);

    // 4. write to temp file
    final tempDir = await getTemporaryDirectory();
    final tempFile = File('${tempDir.path}/netra_processed_${DateTime.now().millisecondsSinceEpoch}.jpg');
    await tempFile.writeAsBytes(singleBytes, flush: true);

    // 5. base64 & sha256
    final imageB64 = base64Encode(singleBytes);
    final imageSha = sha256.convert(singleBytes).toString();

    // 6. ML Kit OCR on the SAME temp file
    final inputImage = InputImage.fromFilePath(tempFile.path);
    final recognizedText = await _recognizer.processImage(inputImage);

    final List<Token> tokens = [];
    for (final block in recognizedText.blocks) {
      for (final line in block.lines) {
        final box = line.boundingBox;
        // BBox is [left, top, width, height]
        final bbox = BBox(
          box.left.round(),
          box.top.round(),
          box.width.round(),
          box.height.round(),
        );
        tokens.add(Token(
          text: line.text,
          bbox: bbox,
          conf: 1.0,
          engine: 'mlkit',
          lang: 'en',
        ));
      }
    }

    return ProcessedImage(
      file: tempFile,
      base64: imageB64,
      sha256: imageSha,
      width: decoded.width,
      height: decoded.height,
      tokens: tokens,
    );
  }
}
