import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../bridge/bridge_models.dart';
import '../bridge/netra_bridge.dart';

/// NetraBridge singleton client provider.
final netraBridgeProvider = Provider<NetraBridge>((ref) {
  return const NetraBridge();
});

/// Startup ping check state provider.
/// Verifies schema_version == 1 and reads PingCapabilities.
/// Includes a resilient retry loop to allow Chaquopy background initialization on slower devices.
final pingStatusProvider = FutureProvider<PingPayload>((ref) async {
  final bridge = ref.watch(netraBridgeProvider);
  Object? lastError;
  for (var attempt = 1; attempt <= 4; attempt++) {
    try {
      return await bridge.ping();
    } catch (e) {
      lastError = e;
      if (attempt < 4) {
        await Future.delayed(Duration(milliseconds: 300 * attempt));
      }
    }
  }
  throw lastError ?? Exception('Failed to connect to Netra Core');
});

/// Polling QueueStatus provider (refreshes automatically or manually).
class QueueStatusNotifier extends AsyncNotifier<QueueStatus> {
  Timer? _timer;

  @override
  Future<QueueStatus> build() async {
    // Poll every 30 seconds while subscribed
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => refresh());
    ref.onDispose(() => _timer?.cancel());

    final bridge = ref.read(netraBridgeProvider);
    return bridge.queueStatus();
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    try {
      final bridge = ref.read(netraBridgeProvider);
      final status = await bridge.queueStatus();
      state = AsyncValue.data(status);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final queueStatusProvider =
    AsyncNotifierProvider<QueueStatusNotifier, QueueStatus>(() {
  return QueueStatusNotifier();
});
