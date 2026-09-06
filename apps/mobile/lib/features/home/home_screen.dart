import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/state/bridge_provider.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../scan_setup/scan_setup_screen.dart';

/// Field tool Home Screen (Brief §5.1).
/// Big bordered tile "New inspection" (navy, 72dp) -> scan_setup.
/// Below: queue summary card (total/pending/signed/dossiers), last sync line,
/// Sync now text button, and capability status.
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pingAsync = ref.watch(pingStatusProvider);
    final queueAsync = ref.watch(queueStatusProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('NETRA Metrology Field Tool'),
        actions: [
          queueAsync.when(
            data: (q) => Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.monoBg,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: AppColors.border, width: 1),
                  ),
                  child: Text(
                    '⌁ ${q.pendingSync} queued',
                    style: AppTypography.monoSmall,
                  ),
                ),
              ),
            ),
            loading: () => const SizedBox.shrink(),
            error: (_, _) => const SizedBox.shrink(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // 1. Core Handshake Banner
          pingAsync.when(
            data: (ping) {
              return Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.border, width: 1),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.verified, color: AppColors.verdictGreen, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'CORE CONNECTED (v${ping.coreVersion})',
                            style: AppTypography.sectionLabel.copyWith(color: AppColors.verdictGreen),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Channel: ${ping.channel} · Stages: ${ping.capabilities.stagesImplemented.length} implemented',
                            style: AppTypography.caption,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
            loading: () => const LinearProgressIndicator(minHeight: 2),
            error: (err, _) => Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.verdictRedBg,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.verdictRed, width: 1),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: AppColors.verdictRed, size: 20),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Core ping failed: $err',
                      style: AppTypography.caption.copyWith(color: AppColors.verdictRed),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          // 2. Big 72dp New Inspection Button
          SizedBox(
            height: 72,
            child: ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.navy,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                  side: const BorderSide(color: AppColors.navy, width: 1),
                ),
              ),
              onPressed: () {
                ref.read(scanSessionProvider.notifier).resetSession();
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const ScanSetupScreen()),
                );
              },
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.camera_alt, size: 28, color: Colors.white),
                  SizedBox(width: 12),
                  Text(
                    'NEW INSPECTION',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.5,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          // 3. Queue & Ledger Status Card
          const Text('OFFLINE EVIDENCE LEDGER', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          queueAsync.when(
            data: (q) => Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.border, width: 1),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _buildCountItem('TOTAL SCANS', q.total),
                      _buildCountItem('PENDING SYNC', q.pendingSync),
                      _buildCountItem('SIGNED', q.signed),
                      _buildCountItem('DOSSIERS', q.dossiers),
                    ],
                  ),
                  const SizedBox(height: 16),
                  const Divider(),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      TextButton.icon(
                        onPressed: () => ref.read(queueStatusProvider.notifier).refresh(),
                        icon: const Icon(Icons.refresh, size: 16),
                        label: const Text('Refresh ledger'),
                      ),
                      pingAsync.maybeWhen(
                        data: (p) => p.capabilities.sync
                            ? TextButton(
                                onPressed: () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(content: Text('Sync gateway configured')),
                                  );
                                },
                                child: const Text('Sync now'),
                              )
                            : Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppColors.monoBg,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Text(
                                  'Sync unavailable in this build',
                                  style: AppTypography.caption,
                                ),
                              ),
                        orElse: () => const SizedBox.shrink(),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            loading: () => const Center(child: Padding(
              padding: EdgeInsets.all(24),
              child: CircularProgressIndicator(color: AppColors.navy),
            )),
            error: (err, _) => Text('Failed to load queue status: $err', style: AppTypography.caption),
          ),
          const SizedBox(height: 24),

          // 4. Statutory Disclaimer Footer
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.monoBg,
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Text(
              'Statutory compliance is verified according to the Legal Metrology '
              '(Packaged Commodities) Rules, 2011. Offline evidence dossiers are '
              'cryptographically anchored with ECDSA keys in Android KeyStore.',
              style: AppTypography.caption,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCountItem(String label, int count) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(count.toString(), style: AppTypography.heading.copyWith(fontSize: 18)),
        const SizedBox(height: 2),
        Text(label, style: AppTypography.caption.copyWith(fontSize: 10)),
      ],
    );
  }
}
