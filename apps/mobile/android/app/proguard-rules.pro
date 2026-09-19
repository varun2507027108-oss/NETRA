# ProGuard / R8 rules for Netra mobile

# Preserve attributes needed for reflection and type inspection
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod

# Google ML Kit - Keep all classes, interfaces, methods, and fields
-keep class com.google.mlkit.** { *; }
-keep interface com.google.mlkit.** { *; }
-dontwarn com.google.mlkit.**

# Google Play Services & GMS internal classes (used by ML Kit)
-keep class com.google.android.gms.** { *; }
-keep interface com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**

# Google DataTransport (used by ML Kit for telemetry & logging)
-keep class com.google.android.datatransport.** { *; }
-keep interface com.google.android.datatransport.** { *; }
-dontwarn com.google.android.datatransport.**

# Flutter Google ML Kit plugin wrappers
-keep class com.google_mlkit_text_recognition.** { *; }
-keep class com.google_mlkit_commons.** { *; }
-dontwarn com.google_mlkit_text_recognition.**
-dontwarn com.google_mlkit_commons.**

# Suppress warnings for optional ML Kit text recognition language packs
-dontwarn com.google.mlkit.vision.text.chinese.**
-dontwarn com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions$Builder
-dontwarn com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
-dontwarn com.google.mlkit.vision.text.devanagari.**
-dontwarn com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions$Builder
-dontwarn com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions
-dontwarn com.google.mlkit.vision.text.japanese.**
-dontwarn com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions$Builder
-dontwarn com.google.mlkit.vision.text.japanese.JapaneseTextRecognizerOptions
-dontwarn com.google.mlkit.vision.text.korean.**
-dontwarn com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions$Builder
-dontwarn com.google.mlkit.vision.text.korean.KoreanTextRecognizerOptions

# Keep LiteRT and OpenCV classes from being stripped
-keep class com.google.ai.edge.litert.** { *; }
-keep class org.opencv.** { *; }
-dontwarn org.opencv.**

# Keep Netra native core plugin, vision, YOLO, and keystore classes
-keep class netra.core.** { *; }
-keep interface netra.core.** { *; }

# Keep TensorFlow Lite classes
-keep class org.tensorflow.lite.** { *; }
-dontwarn org.tensorflow.lite.**

# Keep Chaquopy classes
-keep class com.chaquo.python.** { *; }
-dontwarn com.chaquo.python.**

