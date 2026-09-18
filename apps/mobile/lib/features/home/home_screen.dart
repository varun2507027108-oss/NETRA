import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/state/bridge_provider.dart';
import '../../core/state/scan_session.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../scan_setup/scan_setup_screen.dart';
import '../scanner/scanner_screen.dart';
import 'widgets/recent_inspections.dart';

/// Field tool Home Screen (Brief §5.1).
/// Task-first hierarchy:
/// 1. Prominent Hero Action: "+ NEW INSPECTION" (72dp, navy, immediately accessible)
/// 2. Active session / Recent inspection preview
/// 3. Core handshake status (compact)
/// 4. Offline Evidence Ledger metrics (compact cards)
class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pingAsync = ref.watch(pingStatusProvider);
    final queueAsync = ref.watch(queueStatusProvider);
    final session = ref.watch(scanSessionProvider);

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
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        children: [
          // 1. Task-First Hero: Big 72dp New Inspection Button
          SizedBox(
            height: 72,
            child: ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.navy,
                elevation: 2,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
              onPressed: () {
                ref.read(scanSessionProvider.notifier).resetSession();
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const ScanSetupScreen()),
                );
              },
              icon: const Icon(Icons.camera_alt, size: 28, color: Colors.white),
              label: const Text(
                'NEW INSPECTION',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.8,
                  color: Colors.white,
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Quick Inspection Presets (1-tap field shortcut)
          Row(
            children: [
              Expanded(
                child: _buildPresetCard(
                  context,
                  ref,
                  icon: Icons.inventory_2_outlined,
                  label: 'Pouch / Sachet',
                  shape: PackageShape.pouch,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildPresetCard(
                  context,
                  ref,
                  icon: Icons.local_drink_outlined,
                  label: 'Bottle / Can',
                  shape: PackageShape.cylindrical,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _buildPresetCard(
                  context,
                  ref,
                  icon: Icons.check_box_outline_blank,
                  label: 'Box / Carton',
                  shape: PackageShape.rectangular,
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // 2. Recent Inspection Strip
          const Text('RECENT INSPECTION', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          RecentInspectionsStrip(lastResult: session.scanResult),
          const SizedBox(height: 20),

          // 3. Core Handshake Banner (Compact)
          pingAsync.when(
            data: (ping) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.border, width: 1),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.verified, color: AppColors.verdictGreen, size: 18),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Core v${ping.coreVersion} connected (${ping.capabilities.stagesImplemented.length} stages)',
                        style: AppTypography.caption.copyWith(fontWeight: FontWeight.w500),
                      ),
                    ),
                    Text(
                      ping.channel.toUpperCase(),
                      style: AppTypography.monoSmall.copyWith(color: AppColors.inkSecondary),
                    ),
                  ],
                ),
              );
            },
            loading: () => const LinearProgressIndicator(minHeight: 2),
            error: (err, _) => Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppColors.verdictRedBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.verdictRed, width: 1),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline, color: AppColors.verdictRed, size: 18),
                  const SizedBox(width: 8),
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

          // 4. Offline Evidence Ledger (Compact metrics grid)
          const Text('OFFLINE EVIDENCE LEDGER', style: AppTypography.sectionLabel),
          const SizedBox(height: 8),
          queueAsync.when(
            data: (q) => Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.border, width: 1),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _buildCountItem('TOTAL SCANS', q.total),
                      _buildCountItem('PENDING SYNC', q.pendingSync),
                      _buildCountItem('SIGNED', q.signed),
                      _buildCountItem('DOSSIERS', q.dossiers),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Divider(height: 1),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      TextButton.icon(
                        onPressed: () => ref.read(queueStatusProvider.notifier).refresh(),
                        icon: const Icon(Icons.refresh, size: 14),
                        label: const Text('Refresh ledger', style: TextStyle(fontSize: 12)),
                      ),
                      pingAsync.maybeWhen(
                        data: (p) => p.capabilities.sync
                            ? TextButton(
                                onPressed: () async {
                                  try {
                                    final result = await ref.read(netraBridgeProvider).syncNow();
                                    await ref.read(queueStatusProvider.notifier).refresh();
                                    if (!context.mounted) return;
                                    final message = result.error != null
                                        ? 'Sync deferred: ${result.error}'
                                        : 'Sync complete: ${result.synced} sent, ${result.remaining} remaining.';
                                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
                                  } catch (_) {
                                    if (!context.mounted) return;
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      const SnackBar(content: Text('Sync could not start. Records remain safely queued on this device.')),
                                    );
                                  }
                                },
                                child: const Text('Sync queued records', style: TextStyle(fontSize: 12)),
                              )
                            : Text(
                                'Sync offline',
                                style: AppTypography.caption.copyWith(color: AppColors.inkSecondary),
                              ),
                        orElse: () => const SizedBox.shrink(),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            loading: () => const Center(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: CircularProgressIndicator(color: AppColors.navy),
              ),
            ),
            error: (err, _) => Text('Failed to load queue: $err', style: AppTypography.caption),
          ),
          const SizedBox(height: 20),

          // 5. Statutory Disclaimer Footer
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
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildCountItem(String label, int count) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(count.toString(), style: AppTypography.heading.copyWith(fontSize: 17)),
        const SizedBox(height: 2),
        Text(label, style: AppTypography.caption.copyWith(fontSize: 9)),
      ],
    );
  }

  Widget _buildPresetCard(
    BuildContext context,
    WidgetRef ref, {
    required IconData icon,
    required String label,
    required PackageShape shape,
  }) {
    return InkWell(
      onTap: () {
        ref.read(scanSessionProvider.notifier).resetSession();
        ref.read(scanSessionProvider.notifier).updateConfig(
              const ScanConfig().copyWith(
                shape: shape,
                fiducialMm: 40.0,
              ),
            );
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const ScannerScreen()),
        );
      },
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.border, width: 1),
        ),
        child: Column(
          children: [
            Icon(icon, size: 24, color: AppColors.navy),
            const SizedBox(height: 6),
            Text(
              label,
              textAlign: TextAlign.center,
              style: AppTypography.caption.copyWith(
                fontWeight: FontWeight.w600,
                fontSize: 11,
                color: AppColors.inkPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
