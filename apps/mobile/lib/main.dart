import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

void main() {
  runApp(const NetraSpikeApp());
}

class NetraSpikeApp extends StatelessWidget {
  const NetraSpikeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NETRA Core Spike',
      theme: ThemeData.dark(useMaterial3: true),
      home: const NetraSpikeScreen(),
    );
  }
}

class NetraSpikeScreen extends StatefulWidget {
  const NetraSpikeScreen({super.key});

  @override
  State<NetraSpikeScreen> createState() => _NetraSpikeScreenState();
}

class _NetraSpikeScreenState extends State<NetraSpikeScreen> {
  static const _channel = MethodChannel('netra.core');
  String _activeAction = '';
  String _output = 'Ready. Tap ping, queue, or smoke to probe on-device Python.';

  Future<void> _call(String method, [dynamic arg]) async {
    setState(() {
      _activeAction = method;
      _output = 'Invoking $method...';
    });

    try {
      final dynamic raw = await _channel.invokeMethod(method, arg);
      String formatted;
      try {
        final decoded = jsonDecode(raw.toString());
        const encoder = JsonEncoder.withIndent('  ');
        formatted = encoder.convert(decoded);
      } catch (_) {
        formatted = raw.toString();
      }
      setState(() {
        _output = formatted;
      });
    } on PlatformException catch (e) {
      setState(() {
        _output = 'PlatformException: ${e.code}\n${e.message}\n${e.details}';
      });
    } catch (e) {
      setState(() {
        _output = 'Error: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('NETRA Core On-Device Spike'),
        actions: [
          IconButton(
            icon: const Icon(Icons.copy),
            tooltip: 'Copy Output',
            onPressed: () {
              Clipboard.setData(ClipboardData(text: _output));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Copied output to clipboard')),
              );
            },
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: 8.0,
              runSpacing: 8.0,
              alignment: WrapAlignment.spaceEvenly,
              children: [
                ElevatedButton.icon(
                  icon: const Icon(Icons.network_ping),
                  label: const Text('ping'),
                  onPressed: () => _call('ping'),
                ),
                ElevatedButton.icon(
                  icon: const Icon(Icons.queue),
                  label: const Text('queue'),
                  onPressed: () => _call('queue_status'),
                ),
                ElevatedButton.icon(
                  icon: const Icon(Icons.science),
                  label: const Text('smoke'),
                  onPressed: () => _call('smoke'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              'Active action: ${_activeAction.isEmpty ? "none" : _activeAction}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.black87,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade800),
                ),
                child: SingleChildScrollView(
                  child: SelectableText(
                    _output,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 13,
                      color: Colors.greenAccent,
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
