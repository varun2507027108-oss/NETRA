package com.netra.netra

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import netra.core.NetraCorePlugin

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        NetraCorePlugin.register(this, flutterEngine.dartExecutor.binaryMessenger)
    }
}
